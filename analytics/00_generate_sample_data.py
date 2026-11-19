"""
Generates realistic CTA-schema sample raw files (ridership CSV + dated GTFS ZIP snapshots)
so the entire pipeline, ML models, API, and frontend run immediately out-of-the-box.
Replace files in data/raw/ with official CTA / Mobility Database downloads for full production runs.
"""
import os
import zipfile
import hashlib
import json
from datetime import date, timedelta
import numpy as np
import pandas as pd

RAW_DIR = "data/raw"
RIDERSHIP_DIR = os.path.join(RAW_DIR, "ridership")
GTFS_DIR = os.path.join(RAW_DIR, "gtfs")

ROUTES = [
    ("22", "Clark", "3"),
    ("8", "Halsted", "3"),
    ("79", "79th", "3"),
    ("66", "Chicago", "3"),
    ("49", "Western", "3"),
    ("9", "Ashland", "3"),
    ("151", "Sheridan", "3"),
    ("36", "Broadway", "3"),
    ("146", "Inner Lake Shore/Michigan Exp", "3"),
    ("20", "Madison", "3"),
    ("169", "69th-UPS Express", "3"),  # Schedule without ridership edge case
]

# Route 1001 exists in ridership without GTFS schedule (Spec Section 9.6.4.2)
UNMATCHED_RIDERSHIP_ROUTES = ["1001"]

def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def generate():
    os.makedirs(RIDERSHIP_DIR, exist_ok=True)
    os.makedirs(GTFS_DIR, exist_ok=True)
    rng = np.random.default_rng(42)

    start_date = date(2025, 10, 1)
    end_date = date(2026, 7, 31)
    all_dates = [start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)]

    # 1. Generate CTA Ridership CSV
    rows = []
    base_demand = {
        "22": 14500, "8": 16200, "79": 19800, "66": 17400, "49": 15900,
        "9": 16800, "151": 13200, "36": 11900, "146": 12400, "20": 11100,
        "1001": 420
    }
    for d in all_dates:
        wd = d.weekday()
        daytype = "U" if wd == 6 else ("A" if wd == 5 else "W")
        mult = 1.0 if daytype == "W" else (0.68 if daytype == "A" else 0.52)
        seasonal = 1.0 + 0.08 * np.sin(2 * np.pi * d.timetuple().tm_yday / 365.0)
        for r_code, base in base_demand.items():
            # Genuine zero-ride edge case
            if r_code == "1001" and d == date(2026, 1, 1):
                rides = 0
            else:
                noise = rng.normal(1.0, 0.07)
                rides = max(0, int(round(base * mult * seasonal * noise)))
            rows.append({
                "route": r_code,
                "date": d.strftime("%m/%d/%Y"),
                "daytype": daytype,
                "rides": f"{rides:,}"
            })

    ridership_path = os.path.join(RIDERSHIP_DIR, "CTA_Ridership_Bus_Routes_Daily_Sample.csv")
    pd.DataFrame(rows).to_csv(ridership_path, index=False)

    # 2. Generate Two Dated GTFS Snapshots covering Nov 2025 - Jul 2026
    snapshots = [
        ("mdb-389-202511230128", "2025-11-23", "20251119", "20260331", 1.0),
        ("mdb-389-202603260020", "2026-03-26", "20260320", "20260731", 1.05),
    ]

    manifest = []
    manifest.append({
        "dataset_id": "cta_daily_ridership",
        "snapshot_id": "2026-07-31-sample",
        "source_url": "https://data.cityofchicago.org/Transportation/CTA-Ridership-Bus-Routes-Daily-Totals-by-Route/jyb9-n7fm",
        "catalog_retrieved_date": "2026-07-31",
        "file_path": ridership_path,
        "sha256": sha256_file(ridership_path),
        "byte_size": os.path.getsize(ridership_path),
    })

    for snap_id, retrieved_date, cal_start, cal_end, trip_scale in snapshots:
        snap_dir = os.path.join(GTFS_DIR, snap_id)
        ext_dir = os.path.join(snap_dir, "extracted")
        os.makedirs(ext_dir, exist_ok=True)

        pd.DataFrame([{
            "agency_id": "CTA",
            "agency_name": "Chicago Transit Authority",
            "agency_url": "https://www.transitchicago.com",
            "agency_timezone": "America/Chicago"
        }]).to_csv(os.path.join(ext_dir, "agency.txt"), index=False)

        routes_df = pd.DataFrame([
            {"route_id": f"R_{r[0]}", "route_short_name": r[0], "route_long_name": r[1], "route_type": r[2]}
            for r in ROUTES
        ])
        routes_df.to_csv(os.path.join(ext_dir, "routes.txt"), index=False)

        cal_df = pd.DataFrame([
            {"service_id": "SVC_W", "monday": 1, "tuesday": 1, "wednesday": 1, "thursday": 1, "friday": 1, "saturday": 0, "sunday": 0, "start_date": cal_start, "end_date": cal_end},
            {"service_id": "SVC_A", "monday": 0, "tuesday": 0, "wednesday": 0, "thursday": 0, "friday": 0, "saturday": 1, "sunday": 0, "start_date": cal_start, "end_date": cal_end},
            {"service_id": "SVC_U", "monday": 0, "tuesday": 0, "wednesday": 0, "thursday": 0, "friday": 0, "saturday": 0, "sunday": 1, "start_date": cal_start, "end_date": cal_end},
        ])
        cal_df.to_csv(os.path.join(ext_dir, "calendar.txt"), index=False)

        # Holiday exception: Dec 25, 2025 removes Weekday (type 2) and adds Sunday/Holiday (type 1)
        cal_dates = [
            {"service_id": "SVC_W", "date": "20251225", "exception_type": 2},
            {"service_id": "SVC_U", "date": "20251225", "exception_type": 1},
        ]
        pd.DataFrame(cal_dates).to_csv(os.path.join(ext_dir, "calendar_dates.txt"), index=False)

        stops_rows = []
        for s_idx in range(1, 61):
            stops_rows.append({
                "stop_id": f"STOP_{s_idx:03d}",
                "stop_name": f"Stop {s_idx}",
                "stop_lat": round(41.80 + (s_idx * 0.003), 6),
                "stop_lon": round(-87.68 + ((s_idx % 10) * 0.004), 6),
            })
        pd.DataFrame(stops_rows).to_csv(os.path.join(ext_dir, "stops.txt"), index=False)

        trips_rows = []
        stop_times_rows = []
        shapes_rows = []
        trip_counter = 1

        for idx, (r_short, r_name, _) in enumerate(ROUTES):
            r_id = f"R_{r_short}"
            shape_id = f"SHP_{r_short}"
            route_stops = [f"STOP_{((idx * 4 + k) % 60) + 1:03d}" for k in range(10)]
            for seq, st_id in enumerate(route_stops, start=1):
                st_info = stops_rows[int(st_id.split("_")[1]) - 1]
                shapes_rows.append({
                    "shape_id": shape_id,
                    "shape_pt_lat": st_info["stop_lat"],
                    "shape_pt_lon": st_info["stop_lon"],
                    "shape_pt_sequence": seq
                })

            for svc, daily_trips in [("SVC_W", int(90 * trip_scale)), ("SVC_A", int(64 * trip_scale)), ("SVC_U", int(52 * trip_scale))]:
                for t_i in range(daily_trips):
                    t_id = f"{snap_id}_T{trip_counter:06d}"
                    trip_counter += 1
                    dir_id = t_i % 2
                    trips_rows.append({
                        "trip_id": t_id,
                        "route_id": r_id,
                        "service_id": svc,
                        "direction_id": dir_id,
                        "shape_id": shape_id
                    })
                    # Include an after-midnight trip (>24:00:00) to verify spec rule
                    start_min = 300 + int((1180 / max(1, daily_trips)) * t_i)
                    duration_min = 38 + (idx % 12)
                    end_min = start_min + duration_min

                    def fmt_gtfs_time(total_m: int) -> str:
                        hh = total_m // 60
                        mm = total_m % 60
                        return f"{hh:02d}:{mm:02d}:00"

                    stop_times_rows.append({
                        "trip_id": t_id,
                        "stop_id": route_stops[0],
                        "stop_sequence": 1,
                        "arrival_time": fmt_gtfs_time(start_min),
                        "departure_time": fmt_gtfs_time(start_min),
                    })
                    stop_times_rows.append({
                        "trip_id": t_id,
                        "stop_id": route_stops[-1],
                        "stop_sequence": 2,
                        "arrival_time": fmt_gtfs_time(end_min),
                        "departure_time": fmt_gtfs_time(end_min),
                    })

        pd.DataFrame(trips_rows).to_csv(os.path.join(ext_dir, "trips.txt"), index=False)
        pd.DataFrame(stop_times_rows).to_csv(os.path.join(ext_dir, "stop_times.txt"), index=False)
        pd.DataFrame(shapes_rows).to_csv(os.path.join(ext_dir, "shapes.txt"), index=False)
        pd.DataFrame(columns=["trip_id", "start_time", "end_time", "headway_secs"]).to_csv(
            os.path.join(ext_dir, "frequencies.txt"), index=False
        )

        zip_path = os.path.join(snap_dir, "original.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for fname in os.listdir(ext_dir):
                zf.write(os.path.join(ext_dir, fname), arcname=fname)

        manifest.append({
            "dataset_id": "cta_gtfs_schedule",
            "snapshot_id": snap_id,
            "source_url": f"https://files.mobilitydatabase.org/mdb-389/{snap_id}/{snap_id}.zip",
            "catalog_retrieved_date": retrieved_date,
            "file_path": zip_path,
            "sha256": sha256_file(zip_path),
            "byte_size": os.path.getsize(zip_path),
        })

    with open(os.path.join(RAW_DIR, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"Sample data generated successfully in {RAW_DIR}/")

if __name__ == "__main__":
    generate()
