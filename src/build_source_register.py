"""
Build source_register.csv for Milestone 1.

Compiles an inventory of all raw data sources evaluated and acquired:
1. Hourly Ridership monthly files from data.ny.gov (dataset gxb3-akrn).
2. GTFS timetable snapshots from Mobility Database (feed mdb-513), including used
   versions, excluded duplicates/incomplete versions, and the uncollected 17 Oct feed.

Outputs:
  reports/source_register.csv

Usage:
    python src/build_source_register.py
"""

from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
GTFS_RAW = ROOT / "data" / "raw" / "gtfs" / "manhattan"
RID_RAW = ROOT / "data" / "raw" / "ridership"

FEED_MDB = "mdb-513"
BASE_MDB = f"https://files.mobilitydatabase.org/{FEED_MDB}"
RID_URL = "https://data.ny.gov/resource/gxb3-akrn.json"


def build_register():
    records = []

    # 1. Ridership monthly files
    for m in ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09"]:
        p = RID_RAW / f"{m}.csv"
        size_kb = round(p.stat().st_size / 1024, 1) if p.exists() else None
        records.append({
            "source_id": f"ridership_{m}",
            "source_type": "ridership",
            "provider": "MTA / New York State Open Data (data.ny.gov)",
            "dataset_name": "MTA Bus Hourly Ridership: Beginning 2025 (gxb3-akrn)",
            "source_url": RID_URL,
            "local_path": f"data/raw/ridership/{m}.csv",
            "file_size": f"{size_kb} KB" if size_kb else "N/A",
            "service_start": f"{m}-01",
            "service_end": pd.Period(m, freq="M").end_time.strftime("%Y-%m-%d"),
            "status": "used",
            "notes": f"Server-side aggregated Manhattan hourly bus ridership for {m}.",
        })

    # 2. GTFS versions from gtfs_versions.csv
    v_path = GTFS_RAW / "gtfs_versions.csv"
    if v_path.exists():
        df_v = pd.read_csv(v_path)
        for _, r in df_v.iterrows():
            status = "used" if r["use"] else "not used"
            notes = r["reason"] if pd.notna(r["reason"]) and r["reason"] else "Used in active schedule assignment."
            records.append({
                "source_id": f"gtfs_{r['snapshot_date']}",
                "source_type": "gtfs_timetable",
                "provider": "MTA New York City Transit / Mobility Database",
                "dataset_name": f"NYCT Manhattan Bus GTFS ({r['mdb_dataset_id']})",
                "source_url": r["source_url"],
                "local_path": r["path"],
                "file_size": f"{r['size_mb']} MB",
                "service_start": r["service_start"],
                "service_end": r["service_end"],
                "status": status,
                "notes": notes,
            })

    # 3. 17 October snapshot (catalogued on Mobility Database, evaluated but skipped)
    records.append({
        "source_id": "gtfs_2026-10-17",
        "source_type": "gtfs_timetable",
        "provider": "MTA New York City Transit / Mobility Database",
        "dataset_name": "NYCT Manhattan Bus GTFS (mdb-513-202610170031)",
        "source_url": f"{BASE_MDB}/mdb-513-202610170031/mdb-513-202610170031.zip",
        "local_path": "N/A",
        "file_size": "N/A",
        "service_start": "2026-10-18",
        "service_end": "2027-01-02",
        "status": "not used",
        "notes": "not used: after the end of the ridership data",
    })

    df = pd.DataFrame(records)
    REPORTS.mkdir(parents=True, exist_ok=True)
    out = REPORTS / "source_register.csv"
    df.to_csv(out, index=False)
    print(f"Wrote {len(df)} sources -> {out.relative_to(ROOT)}")
    print(df[["source_id", "source_type", "status", "notes"]].to_string(index=False))


if __name__ == "__main__":
    build_register()
