"""
RouteRanker: Phase 2 Data Inspection, Inventory & GTFS Compatibility Audit
Audits all raw CTA datasets and extracted GTFS tables.
Generates:
1. data/dataset_inventory.csv
2. Detailed metrics for documentation reports
"""

import os
import glob
import json
import pandas as pd
import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
GTFS_DIR = os.path.join(RAW_DIR, "gtfs")
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs", "reports")
os.makedirs(OUTPUTS_DIR, exist_ok=True)

DOWNLOAD_DATE = datetime.datetime.now().strftime("%Y-%m-%d")

inventory_records = []

# --- 1. Audit Chicago Data Portal Historical Datasets ---
print("=" * 60)
print("AUDITING CHICAGO DATA PORTAL HISTORICAL DATASETS")
print("=" * 60)

csv_files = {
    "cta_ridership_daily_system_totals.csv": {
        "name": "CTA - Ridership - Daily Boarding Totals",
        "source": "https://data.cityofchicago.org/api/views/6iiy-9s97/rows.csv?accessType=DOWNLOAD",
        "date_col": "service_date"
    },
    "cta_ridership_bus_routes_daily.csv": {
        "name": "CTA - Ridership - Bus Routes - Daily Totals",
        "source": "https://data.cityofchicago.org/resource/jyb9-n7fm.csv",
        "date_col": "date"
    },
    "cta_ridership_l_station_daily_entries.csv": {
        "name": "CTA - Ridership - 'L' Station Entries - Daily Totals",
        "source": "https://data.cityofchicago.org/resource/5neh-572f.csv",
        "date_col": "date"
    },
    "cta_l_stations_list.csv": {
        "name": "CTA - System Information - List of 'L' (Rapid Transit) Stations",
        "source": "https://data.cityofchicago.org/api/views/8pix-ypme/rows.csv?accessType=DOWNLOAD",
        "date_col": None
    }
}

dfs = {}

for filename, meta in csv_files.items():
    filepath = os.path.join(RAW_DIR, filename)
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        continue
    
    df = pd.read_csv(filepath, low_memory=False)
    dfs[filename] = df
    row_count = len(df)
    cols = list(df.columns)
    missing_count = int(df.isnull().sum().sum())
    
    date_coverage = "N/A"
    if meta["date_col"] and meta["date_col"] in df.columns:
        date_series = pd.to_datetime(df[meta["date_col"]], errors="coerce").dropna()
        if not date_series.empty:
            date_coverage = f"{date_series.min().strftime('%Y-%m-%d')} to {date_series.max().strftime('%Y-%m-%d')}"
    
    inventory_records.append({
        "dataset_name": meta["name"],
        "source_url": meta["source"],
        "file_name": filename,
        "download_date": DOWNLOAD_DATE,
        "format": "CSV",
        "rows": row_count,
        "columns_count": len(cols),
        "columns_list": "; ".join(cols),
        "date_coverage": date_coverage,
        "total_missing_values": missing_count,
        "file_size_bytes": os.path.getsize(filepath)
    })
    
    print(f"\n[{meta['name']}]")
    print(f"  Rows: {row_count:,} | Cols: {len(cols)}")
    print(f"  Columns: {cols}")
    print(f"  Date coverage: {date_coverage}")
    print(f"  Missing values: {missing_count:,}")
    print(f"  Sample head:\n{df.head(2)}")

# --- 2. Audit GTFS Tables ---
print("\n" + "=" * 60)
print("AUDITING CTA GTFS STATIC ARCHIVE")
print("=" * 60)

gtfs_tables = [
    "agency.txt", "calendar.txt", "calendar_dates.txt", "frequencies.txt",
    "routes.txt", "shapes.txt", "stops.txt", "stop_times.txt", "transfers.txt", "trips.txt"
]

gtfs_dfs = {}
for g_file in gtfs_tables:
    g_path = os.path.join(GTFS_DIR, g_file)
    if not os.path.exists(g_path):
        continue
    
    # For very large files like stop_times.txt and shapes.txt, read efficiently
    try:
        if g_file in ["stop_times.txt", "shapes.txt"]:
            # read row count quickly
            with open(g_path, 'r', encoding='utf-8', errors='ignore') as f:
                row_count = sum(1 for _ in f) - 1
            # read sample for columns and missing values
            sample_df = pd.read_csv(g_path, nrows=5000)
            cols = list(sample_df.columns)
            missing_count = int(sample_df.isnull().sum().sum())
            gtfs_dfs[g_file] = sample_df
        else:
            gdf = pd.read_csv(g_path, low_memory=False)
            row_count = len(gdf)
            cols = list(gdf.columns)
            missing_count = int(gdf.isnull().sum().sum())
            gtfs_dfs[g_file] = gdf
        
        # Check calendar date coverage
        date_cov = "N/A"
        if g_file == "calendar.txt" and "start_date" in cols and "end_date" in cols:
            start_min = str(gdf["start_date"].min())
            end_max = str(gdf["end_date"].max())
            date_cov = f"{start_min} to {end_max}"
        elif g_file == "calendar_dates.txt" and "date" in cols:
            cd_dates = gdf["date"].astype(str)
            date_cov = f"{cd_dates.min()} to {cd_dates.max()}"
        
        inventory_records.append({
            "dataset_name": f"CTA GTFS: {g_file}",
            "source_url": "https://www.transitchicago.com/downloads/sch_data/google_transit.zip",
            "file_name": f"gtfs/{g_file}",
            "download_date": DOWNLOAD_DATE,
            "format": "TXT (GTFS CSV)",
            "rows": row_count,
            "columns_count": len(cols),
            "columns_list": "; ".join(cols),
            "date_coverage": date_cov,
            "total_missing_values": missing_count,
            "file_size_bytes": os.path.getsize(g_path)
        })
        print(f"  GTFS [{g_file}]: {row_count:,} rows, {len(cols)} cols ({', '.join(cols[:5])}...)")
    except Exception as e:
        print(f"  Error reading {g_file}: {e}")

# Save inventory CSV
inventory_df = pd.DataFrame(inventory_records)
inv_csv_path = os.path.join(BASE_DIR, "data", "dataset_inventory.csv")
inventory_df.to_csv(inv_csv_path, index=False)
print(f"\nSaved dataset inventory to: {inv_csv_path}")

# --- 3. Historical Ridership & GTFS Compatibility Audit ---
print("\n" + "=" * 60)
print("HISTORICAL RIDERSHIP & GTFS DATA MATCHING AUDIT")
print("=" * 60)

compat_report = {}

# A. Bus Routes Matching
routes_gtfs = pd.read_csv(os.path.join(GTFS_DIR, "routes.txt"))
bus_hist = dfs["cta_ridership_bus_routes_daily.csv"]

gtfs_route_ids = set(routes_gtfs["route_id"].astype(str).str.strip())
gtfs_route_short_names = set(routes_gtfs["route_short_name"].dropna().astype(str).str.strip())
gtfs_all_bus_keys = gtfs_route_ids.union(gtfs_route_short_names)

hist_bus_routes = set(bus_hist["route"].dropna().astype(str).str.strip())

matched_bus_routes = hist_bus_routes.intersection(gtfs_all_bus_keys)
unmatched_bus_routes = hist_bus_routes - gtfs_all_bus_keys

print(f"Bus Routes Compatibility:")
print(f"  Historical unique bus routes: {len(hist_bus_routes)}")
print(f"  GTFS total routes: {len(gtfs_route_ids)}")
print(f"  Matched bus routes: {len(matched_bus_routes)} ({len(matched_bus_routes)/len(hist_bus_routes)*100:.1f}%)")
print(f"  Unmatched bus routes: {len(unmatched_bus_routes)}")
if unmatched_bus_routes:
    print(f"    Examples of unmatched: {list(unmatched_bus_routes)[:10]}")

compat_report["bus_routes_matching"] = {
    "historical_unique_routes": len(hist_bus_routes),
    "gtfs_routes": len(gtfs_route_ids),
    "matched_routes_count": len(matched_bus_routes),
    "match_percentage": round(len(matched_bus_routes) / len(hist_bus_routes) * 100, 2),
    "unmatched_routes_count": len(unmatched_bus_routes),
    "unmatched_examples": list(unmatched_bus_routes)[:10]
}

# B. Rail Stations Matching
rail_hist = dfs["cta_ridership_l_station_daily_entries.csv"]
stops_gtfs = pd.read_csv(os.path.join(GTFS_DIR, "stops.txt"))
stations_list = dfs["cta_l_stations_list.csv"]

hist_station_ids = set(rail_hist["station_id"].dropna().astype(int).astype(str))
hist_station_names = set(rail_hist["stationname"].dropna().str.lower().str.strip())

gtfs_stop_ids = set(stops_gtfs["stop_id"].astype(str))
# In CTA GTFS, stops.txt has parent_station or stop_id. Station IDs often start with 4xxxx.
station_stops = stops_gtfs[stops_gtfs["location_type"] == 1] if "location_type" in stops_gtfs.columns else stops_gtfs
gtfs_parent_station_ids = set(stops_gtfs["parent_station"].dropna().astype(str))
gtfs_station_candidates = gtfs_stop_ids.union(gtfs_parent_station_ids)

matched_station_ids = hist_station_ids.intersection(gtfs_station_candidates)
unmatched_station_ids = hist_station_ids - gtfs_station_candidates

print(f"\nRail Station IDs Compatibility:")
print(f"  Historical unique station IDs: {len(hist_station_ids)}")
print(f"  Matched station IDs in GTFS: {len(matched_station_ids)} ({len(matched_station_ids)/len(hist_station_ids)*100:.1f}%)")
print(f"  Unmatched station IDs: {len(unmatched_station_ids)}")

# Check matching with station list table (CTA L Stations)
station_map_ids = set(stations_list["MAP_ID"].dropna().astype(int).astype(str))
matched_map_ids = hist_station_ids.intersection(station_map_ids)
print(f"  Matching with CTA 'L' Station Master Reference (MAP_ID): {len(matched_map_ids)} / {len(hist_station_ids)} ({len(matched_map_ids)/len(hist_station_ids)*100:.1f}%)")

compat_report["rail_stations_matching"] = {
    "historical_unique_station_ids": len(hist_station_ids),
    "matched_with_gtfs_station_ids": len(matched_station_ids),
    "match_percentage_gtfs": round(len(matched_station_ids) / len(hist_station_ids) * 100, 2),
    "matched_with_station_master_map_id": len(matched_map_ids),
    "match_percentage_master": round(len(matched_map_ids) / len(hist_station_ids) * 100, 2),
    "unmatched_station_ids": list(unmatched_station_ids)[:10]
}

# C. Service Date Alignment
sys_dates = pd.to_datetime(dfs["cta_ridership_daily_system_totals.csv"]["service_date"]).dt.date
cal_dates = pd.to_datetime(gtfs_dfs["calendar.txt"]["start_date"].astype(str), format="%Y%m%d").dt.date
cal_end = pd.to_datetime(gtfs_dfs["calendar.txt"]["end_date"].astype(str), format="%Y%m%d").dt.date

compat_report["date_alignment"] = {
    "historical_system_range": f"{sys_dates.min()} to {sys_dates.max()}",
    "historical_bus_range": f"{pd.to_datetime(bus_hist['date']).min().date()} to {pd.to_datetime(bus_hist['date']).max().date()}",
    "historical_rail_range": f"{pd.to_datetime(rail_hist['date']).min().date()} to {pd.to_datetime(rail_hist['date']).max().date()}",
    "gtfs_schedule_range": f"{cal_dates.min()} to {cal_end.max()}",
    "notes": "GTFS schedules represent active service timetables for current transit operations, whereas historical ridership spans 2001 through recent months. System modeling links static route geometries and stops with longitudinal demand trends."
}

# Save JSON report
compat_json_path = os.path.join(OUTPUTS_DIR, "ridership_gtfs_compatibility.json")
with open(compat_json_path, "w") as f:
    json.dump(compat_report, f, indent=2)

print(f"\nSaved compatibility report to: {compat_json_path}")
print("=" * 60)
print("PHASE 2 INSPECTION AUDIT COMPLETE")
print("=" * 60)

