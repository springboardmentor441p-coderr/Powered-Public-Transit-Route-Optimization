"""
Milestone 1 — Step 10: Build Route Crosswalk (route_crosswalk.csv)

Compares route codes in ridership data against route IDs in the GTFS timetable:
  - Both datasets use uppercase route identifiers.
  - Verifies Select Bus Service routes (ending in '+', e.g. M15+, M14A+, M86+).
  - Documents exact matches (41 routes) and unmatched routes (5 in ridership, 0 in GTFS).
  - Saves table to reports/route_crosswalk.csv.
"""

import glob
import zipfile
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RIDERSHIP_DIR = ROOT / "data" / "raw" / "ridership"
GTFS_DIR = ROOT / "data" / "raw" / "gtfs" / "manhattan"
OUT_CSV = ROOT / "reports" / "route_crosswalk.csv"

# Route decisions established in Step 4
ROUTE_DECISIONS = {
    "M14A": ("drop", "Replaced by Select Bus Service M14A+. Zero ridership across all of 2026; no GTFS trips."),
    "M14D": ("drop", "Replaced by Select Bus Service M14D+. Zero ridership across all of 2026; no GTFS trips."),
    "M90": ("drop", "Subway shuttle bus; only 31 riders in 2026; no GTFS trips."),
    "M99": ("drop", "Subway shuttle bus; 0 riders in 2026; no GTFS trips."),
    "M100": ("drop", "Manhattan route whose timetable is published in the Bronx GTFS feed. Out of scope for Manhattan GTFS."),
}


def build_route_crosswalk():
    print("--- Milestone 1 Step 10: Building Route Crosswalk ---")

    # 1. Collect all route codes and total ridership from raw ridership files
    raw_files = sorted(glob.glob(str(RIDERSHIP_DIR / "*.csv")))
    print(f"Reading raw ridership files: {len(raw_files)} monthly files")

    ridership_totals = {}
    for f in raw_files:
        df = pd.read_csv(f, usecols=["bus_route", "ridership"])
        df["bus_route"] = df["bus_route"].str.upper().str.strip()
        df["ridership"] = pd.to_numeric(df["ridership"], errors="coerce").fillna(0).astype(int)
        for route, r_sum in df.groupby("bus_route")["ridership"].sum().items():
            ridership_totals[route] = ridership_totals.get(route, 0) + r_sum

    ridership_codes = sorted(ridership_totals.keys())
    print(f"Total ridership route codes found: {len(ridership_codes)}")

    # 2. Collect all active route IDs from usable GTFS snapshots
    usable_snaps = ["2025-12-30", "2026-03-27", "2026-04-09", "2026-06-24", "2026-09-03"]
    gtfs_routes_with_trips = set()
    gtfs_route_names = {}

    for snap in usable_snaps:
        zip_path = GTFS_DIR / snap / "original.zip"
        if not zip_path.exists():
            continue
        zf = zipfile.ZipFile(zip_path)
        r_df = pd.read_csv(zf.open("routes.txt"), dtype=str)
        t_df = pd.read_csv(zf.open("trips.txt"), dtype=str)

        active = set(t_df["route_id"].str.upper().unique())
        m_active = {r for r in active if r.startswith("M")}
        gtfs_routes_with_trips.update(m_active)

        for _, row in r_df.iterrows():
            r_id = row["route_id"].upper().strip()
            if r_id.startswith("M") and r_id not in gtfs_route_names:
                long_n = row.get("route_long_name", "")
                short_n = row.get("route_short_name", "")
                gtfs_route_names[r_id] = (short_n, long_n)

    gtfs_codes = sorted(gtfs_routes_with_trips)
    print(f"Total GTFS Manhattan routes with trips: {len(gtfs_codes)}")

    # 3. Match comparison
    all_codes = sorted(set(ridership_codes) | set(gtfs_codes))
    records = []

    matched_cnt = 0
    ridership_only_cnt = 0
    gtfs_only_cnt = 0

    for code in all_codes:
        in_ridership = code in ridership_totals
        in_gtfs = code in gtfs_routes_with_trips

        r_total = ridership_totals.get(code, 0)
        short_name, long_name = gtfs_route_names.get(code, (code, ""))

        if in_ridership and in_gtfs:
            status = "matched"
            decision = "keep"
            reason = "Active regular route present with scheduled trips and ridership."
            matched_cnt += 1
        elif in_ridership and not in_gtfs:
            status = "ridership_only_unmatched"
            dec, reas = ROUTE_DECISIONS.get(code, ("drop", "No GTFS trips in Manhattan feeds."))
            decision = dec
            reason = reas
            ridership_only_cnt += 1
        else:
            status = "gtfs_only_unmatched"
            decision = "unmatched"
            reason = "Timetable defined in GTFS but no boardings recorded in ridership."
            gtfs_only_cnt += 1

        service_type = (
            "Select Bus Service (+)" if "+" in code
            else "Shuttle" if code in ["M90", "M99"]
            else "Bronx Feed" if code == "M100"
            else "Legacy Code" if code in ["M14A", "M14D"]
            else "Local"
        )

        records.append({
            "route_code": code,
            "in_ridership": in_ridership,
            "in_gtfs": in_gtfs,
            "match_status": status,
            "service_type": service_type,
            "ridership_2026_total": r_total,
            "route_long_name": long_name,
            "decision": decision,
            "decision_reason": reason,
        })

    df_crosswalk = pd.DataFrame(records)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df_crosswalk.to_csv(OUT_CSV, index=False)

    print(f"\nCrosswalk Summary:")
    print(f"  Matched routes:                 {matched_cnt:>2}")
    print(f"  Ridership only (unmatched):      {ridership_only_cnt:>2}")
    print(f"  GTFS only (unmatched):           {gtfs_only_cnt:>2}")
    print(f"  Total route codes evaluated:    {len(all_codes):>2}")
    print(f"Saved crosswalk -> {OUT_CSV.relative_to(ROOT)}")

    # SBS route check verification
    sbs_routes = [c for c in all_codes if "+" in c]
    print(f"\nSelect Bus Service (+) Crosswalk Verification ({len(sbs_routes)} routes):")
    for r in sbs_routes:
        row = df_crosswalk[df_crosswalk["route_code"] == r].iloc[0]
        print(f"  {r:<6} in_ridership={row['in_ridership']}, in_gtfs={row['in_gtfs']}, riders={row['ridership_2026_total']:,}")

    return df_crosswalk


if __name__ == "__main__":
    build_route_crosswalk()
