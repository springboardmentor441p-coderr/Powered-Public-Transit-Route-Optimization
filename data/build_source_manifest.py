import json
import hashlib
import os
import pandas as pd
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")
MANIFEST_PATH = os.path.join(BASE_DIR, "data", "source_manifest.json")

def sha256_file(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def build_manifest():
    datasets = [
        {
            "dataset_id": "cta_bus_ridership_daily",
            "snapshot_id": "chicago_data_portal_bus_daily_20261022",
            "file_name": "cta_ridership_bus_routes_daily.csv",
            "relative_path": "data/raw/cta_ridership_bus_routes_daily.csv",
            "source_url": "https://data.cityofchicago.org/Transportation/CTA-Ridership-Bus-Routes-Daily-Totals-by-Route/t2rn-p8d7",
            "coverage_start": "2023-02-03",
            "coverage_end": "2026-08-31",
            "agency_timezone": "America/Chicago",
            "grain": "route x date",
            "rows": 150000,
            "status": "verified_immutable_raw"
        },
        {
            "dataset_id": "cta_gtfs_schedule_archive",
            "snapshot_id": "cta_gtfs_snapshot_20260911_v38",
            "file_name": "google_transit.zip",
            "relative_path": "data/raw/google_transit.zip",
            "source_url": "https://www.transitchicago.com/downloads/sch_data/",
            "coverage_start": "2026-09-11",
            "coverage_end": "2026-11-30",
            "agency_timezone": "America/Chicago",
            "grain": "trips x stops x calendar",
            "status": "verified_immutable_raw"
        },
        {
            "dataset_id": "cta_daily_system_totals",
            "snapshot_id": "chicago_data_portal_system_totals_20260831",
            "file_name": "cta_ridership_daily_system_totals.csv",
            "relative_path": "data/raw/cta_ridership_daily_system_totals.csv",
            "source_url": "https://data.cityofchicago.org/Transportation/CTA-Ridership-Daily-Boarding-Totals/6iiy-9s97",
            "coverage_start": "2001-01-01",
            "coverage_end": "2026-08-31",
            "agency_timezone": "America/Chicago",
            "grain": "date (system total)",
            "rows": 9374,
            "status": "verified_immutable_raw"
        },
        {
            "dataset_id": "cta_rail_station_entries",
            "snapshot_id": "chicago_data_portal_l_station_daily_20261022",
            "file_name": "cta_ridership_l_station_daily_entries.csv",
            "relative_path": "data/raw/cta_ridership_l_station_daily_entries.csv",
            "source_url": "https://data.cityofchicago.org/Transportation/CTA-Ridership-L-Station-Entries-Daily-Totals/5neh-572f",
            "coverage_start": "2023-02-03",
            "coverage_end": "2026-08-31",
            "agency_timezone": "America/Chicago",
            "grain": "station_id x date",
            "status": "verified_immutable_raw"
        }
    ]

    for ds in datasets:
        abs_p = os.path.join(BASE_DIR, ds["relative_path"])
        if os.path.exists(abs_p):
            ds["file_size_bytes"] = os.path.getsize(abs_p)
            ds["sha256"] = sha256_file(abs_p)
            ds["validated_at"] = datetime.now(timezone.utc).isoformat()

    manifest_data = {
        "manifest_version": "3.8.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "geographic_scope": "Chicago Transit Authority (CTA), Cook County, Illinois, USA ONLY",
        "datasets": datasets,
        "reference_exceptions": {
            "route_1001": "Recorded rides present in historical archive but no matching schedule in GTFS. Maintained as demand-only history without synthetic geometry.",
            "route_169": "Designated special/contract service with scheduled GTFS presence but sparse ridership reporting.",
            "routes_10_and_130": "Downtown seasonal museum/lakefront corridor routes operating under specific calendar patterns."
        }
    }

    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)
    print(f"Source manifest successfully generated at {MANIFEST_PATH}")
    return manifest_data

if __name__ == "__main__":
    build_manifest()

