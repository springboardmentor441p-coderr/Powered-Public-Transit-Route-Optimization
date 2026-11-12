"""
RouteRanker: CTA Official Data Acquisition Script
Downloads official Chicago Transit Authority datasets from:
1. Chicago Transit Authority Developer Center (google_transit.zip GTFS)
2. Chicago Data Portal (Socrata Open Data API / Views)
"""

import os
import sys
import time
import zipfile
import urllib.request
import urllib.error

RAW_DIR = os.path.join(os.path.dirname(__file__), "raw")
GTFS_DIR = os.path.join(RAW_DIR, "gtfs")

os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(GTFS_DIR, exist_ok=True)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) RouteRanker-TransitResearch/1.0"

DATASETS = [
    {
        "name": "CTA - Ridership - Daily Boarding Totals",
        "file_name": "cta_ridership_daily_system_totals.csv",
        "url": "https://data.cityofchicago.org/api/views/6iiy-9s97/rows.csv?accessType=DOWNLOAD",
        "fallback_url": "https://data.cityofchicago.org/resource/6iiy-9s97.csv?$limit=50000",
        "description": "System-wide daily passenger totals for CTA bus and rail from 2001 to present."
    },
    {
        "name": "CTA - System Information - List of 'L' (Rapid Transit) Stations",
        "file_name": "cta_l_stations_list.csv",
        "url": "https://data.cityofchicago.org/api/views/8pix-ypme/rows.csv?accessType=DOWNLOAD",
        "fallback_url": "https://data.cityofchicago.org/resource/8pix-ypme.csv?$limit=5000",
        "description": "Station identifiers, station names, lines served, ADA status, and coordinates."
    },
    {
        "name": "CTA - Ridership - 'L' Station Entries - Daily Totals",
        "file_name": "cta_ridership_l_station_daily_entries.csv",
        # Use SODA API with recent years or full view. Note that full view is >1M rows (~50MB).
        # We can download recent comprehensive window or full export. Let's query recent 5 years (2019-present) or full export.
        "url": "https://data.cityofchicago.org/resource/5neh-572f.csv?$limit=150000&$order=date%20DESC",
        "description": "Daily station entry counts by station ID, name, date, and day type."
    },
    {
        "name": "CTA - Ridership - Bus Routes - Daily Totals",
        "file_name": "cta_ridership_bus_routes_daily.csv",
        "url": "https://data.cityofchicago.org/resource/jyb9-n7fm.csv?$limit=150000&$order=date%20DESC",
        "description": "Daily route boarding totals by bus route, date, and day type."
    }
]

GTFS_URL = "https://www.transitchicago.com/downloads/sch_data/google_transit.zip"

def download_file(url, target_path, description=""):
    print(f"Downloading: {description or target_path}")
    print(f"  URL: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    
    start_time = time.time()
    try:
        with urllib.request.urlopen(req, timeout=60) as resp, open(target_path, "wb") as out_file:
            total_size = resp.headers.get("Content-Length")
            total_size = int(total_size) if total_size else None
            downloaded = 0
            chunk_size = 1024 * 256
            
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                out_file.write(chunk)
                downloaded += len(chunk)
                if total_size:
                    pct = (downloaded / total_size) * 100
                    print(f"\r  Progress: {downloaded / (1024*1024):.2f} MB / {total_size / (1024*1024):.2f} MB ({pct:.1f}%)", end="", flush=True)
                else:
                    print(f"\r  Downloaded: {downloaded / (1024*1024):.2f} MB", end="", flush=True)
            print()
        
        elapsed = time.time() - start_time
        final_size = os.path.getsize(target_path)
        print(f"  Saved to: {target_path} ({final_size / (1024*1024):.2f} MB in {elapsed:.1f}s)")
        return True
    except Exception as e:
        print(f"\n  Error downloading from {url}: {e}")
        return False

def extract_gtfs(zip_path, extract_dir):
    print(f"\nExtracting GTFS files from {zip_path} to {extract_dir}...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        file_list = zip_ref.namelist()
        print(f"  Files in GTFS archive: {file_list}")
        zip_ref.extractall(extract_dir)
    print("  GTFS extraction complete.")

def main():
    print("=" * 70)
    print("RouteRanker: Chicago Transit Authority (CTA) Data Acquisition")
    print("=" * 70)
    
    # 1. Download GTFS Static Zip
    gtfs_zip_path = os.path.join(RAW_DIR, "google_transit.zip")
    if not os.path.exists(gtfs_zip_path) or os.path.getsize(gtfs_zip_path) < 1000:
        success = download_file(GTFS_URL, gtfs_zip_path, "CTA Official GTFS Schedule Archive")
        if success:
            extract_gtfs(gtfs_zip_path, GTFS_DIR)
        else:
            print("Failed to download CTA GTFS zip!")
    else:
        print(f"CTA GTFS zip already exists: {gtfs_zip_path} ({os.path.getsize(gtfs_zip_path)/(1024*1024):.2f} MB)")
        extract_gtfs(gtfs_zip_path, GTFS_DIR)

    # 2. Download Chicago Data Portal Datasets
    for ds in DATASETS:
        target_path = os.path.join(RAW_DIR, ds["file_name"])
        if os.path.exists(target_path) and os.path.getsize(target_path) > 1000:
            print(f"File already exists: {ds['file_name']} ({os.path.getsize(target_path)/(1024*1024):.2f} MB), skipping download.")
            continue
        
        success = download_file(ds["url"], target_path, ds["name"])
        if not success and "fallback_url" in ds:
            print(f"  Attempting fallback URL: {ds['fallback_url']}")
            download_file(ds["fallback_url"], target_path, ds["name"])

    print("\nData collection stage complete. Listing downloaded files in data/raw:")
    for f in os.listdir(RAW_DIR):
        p = os.path.join(RAW_DIR, f)
        if os.path.isfile(p):
            print(f"  - {f}: {os.path.getsize(p)/(1024*1024):.2f} MB")
        elif os.path.isdir(p):
            sub_files = os.listdir(p)
            print(f"  - [{f}/]: {len(sub_files)} files")

if __name__ == "__main__":
    main()

