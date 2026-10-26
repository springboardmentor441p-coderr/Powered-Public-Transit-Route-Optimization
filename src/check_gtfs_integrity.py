"""
Step 6: Check GTFS timetable versions for referential integrity and valid timestamps.

Checks:
  1. Every trip in trips.txt points to a valid route in routes.txt.
  2. Every stop_time in stop_times.txt points to a valid trip in trips.txt.
  3. Every stop_time in stop_times.txt points to a valid stop in stops.txt.
  4. Arrival and departure times are valid, with arrival_time <= departure_time.
  5. Times are chronologically ordered within each trip by stop_sequence.
  6. Times like 25:10:00 (>= 24:00:00) are recognized as valid service day spillover.

Outputs:
  reports/gtfs_integrity_report.json

Usage:
    python src/check_gtfs_integrity.py
"""

import json
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
GTFS_DIR = ROOT / "data" / "raw" / "gtfs" / "manhattan"
REPORTS_DIR = ROOT / "reports"

USABLE_SNAPSHOTS = [
    "2025-12-30",
    "2026-03-27",
    "2026-04-09",
    "2026-06-24",
    "2026-09-03",
]


def parse_gtfs_time_to_seconds(time_series: pd.Series) -> pd.Series:
    """Parse HH:MM:SS (including HH >= 24) to total seconds from service day start."""
    parts = time_series.str.split(":", expand=True).astype(int)
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def check_snapshot_integrity(snapshot_date: str) -> dict:
    zip_path = GTFS_DIR / snapshot_date / "original.zip"
    if not zip_path.exists():
        raise FileNotFoundError(f"Missing GTFS archive: {zip_path}")

    print(f"\nChecking GTFS snapshot: {snapshot_date} ({zip_path.stat().st_size / 1e6:.1f} MB)...")

    with zipfile.ZipFile(zip_path) as z:
        routes = pd.read_csv(z.open("routes.txt"), dtype=str)
        trips = pd.read_csv(z.open("trips.txt"), dtype=str)
        st = pd.read_csv(z.open("stop_times.txt"), dtype=str)
        stops = pd.read_csv(z.open("stops.txt"), dtype=str)
        calendar = pd.read_csv(z.open("calendar.txt"), dtype=str) if "calendar.txt" in z.namelist() else None
        calendar_dates = pd.read_csv(z.open("calendar_dates.txt"), dtype=str) if "calendar_dates.txt" in z.namelist() else None
        shapes = pd.read_csv(z.open("shapes.txt"), dtype=str, usecols=["shape_id"]) if "shapes.txt" in z.namelist() else None

    # Every trip's service_id must be defined in calendar or calendar_dates
    known_services = set()
    if calendar is not None:
        known_services |= set(calendar["service_id"])
    if calendar_dates is not None:
        known_services |= set(calendar_dates["service_id"])
    trips_unknown_service = int((~trips["service_id"].isin(known_services)).sum())

    # Every trip's shape_id (if given) must exist in shapes.txt
    has_shape = trips["shape_id"].notna() if "shape_id" in trips else pd.Series(False, index=trips.index)
    shape_ids = set(shapes["shape_id"]) if shapes is not None else set()
    trips_missing_shapes = int((has_shape & ~trips["shape_id"].isin(shape_ids)).sum())

    # Check 1: trips -> routes
    trips_missing_routes = int((~trips["route_id"].isin(routes["route_id"])).sum())

    # Check 2: stop_times -> trips
    st_missing_trips = int((~st["trip_id"].isin(trips["trip_id"])).sum())

    # Check 3: stop_times -> stops
    st_missing_stops = int((~st["stop_id"].isin(stops["stop_id"])).sum())

    # Check 4: time validity & arr <= dep
    st["arr_sec"] = parse_gtfs_time_to_seconds(st["arrival_time"])
    st["dep_sec"] = parse_gtfs_time_to_seconds(st["departure_time"])
    arr_gt_dep = int((st["arr_sec"] > st["dep_sec"]).sum())

    # Check 5: chronological order within trip
    st["seq"] = st["stop_sequence"].astype(int)
    st_sorted = st.sort_values(["trip_id", "seq"])
    prev_dep = st_sorted.groupby("trip_id")["dep_sec"].shift(1)
    time_order_violations = int((st_sorted["arr_sec"] < prev_dep.fillna(-1)).sum())

    # Check 6: spillover times >= 24:00:00
    times_ge_24h = int((st["arr_sec"] >= 86400).sum())
    max_hour = int(st["arr_sec"].max() // 3600)

    # Routes with trips
    routes_with_trips = sorted(trips["route_id"].unique().tolist())

    res = {
        "snapshot_date": snapshot_date,
        "n_routes_total": len(routes),
        "n_routes_with_trips": len(routes_with_trips),
        "n_trips": len(trips),
        "n_stop_times": len(st),
        "n_stops": len(stops),
        "n_calendar_services": len(calendar) if calendar is not None else 0,
        "n_calendar_exceptions": len(calendar_dates) if calendar_dates is not None else 0,
        "trips_missing_routes": trips_missing_routes,
        "trips_unknown_service": trips_unknown_service,
        "trips_missing_shapes": trips_missing_shapes,
        "st_missing_trips": st_missing_trips,
        "st_missing_stops": st_missing_stops,
        "arr_gt_dep": arr_gt_dep,
        "time_order_violations": time_order_violations,
        "times_ge_24h": times_ge_24h,
        "max_hour_encoded": max_hour,
        "referential_integrity_passed": (
            trips_missing_routes == 0
            and trips_unknown_service == 0
            and trips_missing_shapes == 0
            and st_missing_trips == 0
            and st_missing_stops == 0
            and arr_gt_dep == 0
            and time_order_violations == 0
        ),
    }

    status = "PASSED" if res["referential_integrity_passed"] else "FAILED"
    print(f"  Referential integrity: {status}")
    print(f"  Trips: {res['n_trips']:,} across {res['n_routes_with_trips']} routes")
    print(f"  Stop times: {res['n_stop_times']:,} ({times_ge_24h:,} times >= 24:00, max hour={max_hour})")
    print(f"  Violations (routes/trips/stops/times): {trips_missing_routes}/{st_missing_trips}/{st_missing_stops}/{time_order_violations}")

    return res


def main():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    all_results = []
    all_passed = True

    for snap in USABLE_SNAPSHOTS:
        res = check_snapshot_integrity(snap)
        all_results.append(res)
        if not res["referential_integrity_passed"]:
            all_passed = False

    out_file = REPORTS_DIR / "gtfs_integrity_report.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)

    print(f"\nAll usable GTFS snapshots integrity check: {'PASSED' if all_passed else 'FAILED'}")
    print(f"Report saved to: {out_file.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
