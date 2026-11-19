import hashlib
import json
import os
import zipfile
from datetime import datetime, timezone
import requests

RAW_RIDERSHIP_DIR = "data/raw/ridership"
RAW_GTFS_DIR = "data/raw/gtfs"
MANIFEST_PATH = "data/raw/source_manifest.json"

RIDERSHIP_URL = "https://data.cityofchicago.org/api/views/jyb9-n7fm/rows.csv?accessType=DOWNLOAD"

GTFS_ARCHIVES = [
    {"snapshot_id": "mdb-389-202511230128", "capture_date": "2025-11-23", "url": "https://files.mobilitydatabase.org/mdb-389/mdb-389-202511230128/mdb-389-202511230128.zip"},
    {"snapshot_id": "mdb-389-202512190112", "capture_date": "2025-12-19", "url": "https://files.mobilitydatabase.org/mdb-389/mdb-389-202512190112/mdb-389-202512190112.zip"},
    {"snapshot_id": "mdb-389-202601080131", "capture_date": "2026-01-08", "url": "https://files.mobilitydatabase.org/mdb-389/mdb-389-202601080131/mdb-389-202601080131.zip"},
    {"snapshot_id": "mdb-389-202602100132", "capture_date": "2026-02-10", "url": "https://files.mobilitydatabase.org/mdb-389/mdb-389-202602100132/mdb-389-202602100132.zip"},
    {"snapshot_id": "mdb-389-202603260020", "capture_date": "2026-03-26", "url": "https://files.mobilitydatabase.org/mdb-389/mdb-389-202603260020/mdb-389-202603260020.zip"},
    {"snapshot_id": "mdb-389-202604240144", "capture_date": "2026-04-24", "url": "https://files.mobilitydatabase.org/mdb-389/mdb-389-202604240144/mdb-389-202604240144.zip"},
    {"snapshot_id": "mdb-389-202605300003", "capture_date": "2026-05-30", "url": "https://files.mobilitydatabase.org/mdb-389/mdb-389-202605300003/mdb-389-202605300003.zip"},
    {"snapshot_id": "mdb-389-202607110020", "capture_date": "2026-07-11", "url": "https://files.mobilitydatabase.org/mdb-389/mdb-389-202607110020/mdb-389-202607110020.zip"},
]

def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def download_file(url: str, dest: str) -> None:
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)

def run():
    manifest = {"generated_at": datetime.now(timezone.utc).isoformat(), "ridership": {}, "gtfs": []}

    # 1. Download Ridership CSV
    csv_path = os.path.join(RAW_RIDERSHIP_DIR, "cta_daily_bus_ridership.csv")
    if not os.path.exists(csv_path):
        print("Downloading CTA 25-year bus ridership CSV...")
        download_file(RIDERSHIP_URL, csv_path)
    manifest["ridership"] = {
        "source_url": RIDERSHIP_URL,
        "local_path": csv_path,
        "sha256": sha256_file(csv_path),
        "byte_size": os.path.getsize(csv_path),
    }

    # 2. Download & Extract GTFS Archives
    for item in GTFS_ARCHIVES:
        sid = item["snapshot_id"]
        zip_path = os.path.join(RAW_GTFS_DIR, sid, "original.zip")
        extract_dir = os.path.join(RAW_GTFS_DIR, sid, "extracted")
        if not os.path.exists(zip_path):
            print(f"Downloading GTFS {sid}...")
            download_file(item["url"], zip_path)
        os.makedirs(extract_dir, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)

        manifest["gtfs"].append({
            "snapshot_id": sid,
            "capture_date": item["capture_date"],
            "source_url": item["url"],
            "zip_path": zip_path,
            "extracted_dir": extract_dir,
            "sha256": sha256_file(zip_path),
            "byte_size": os.path.getsize(zip_path),
        })

    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"Source manifest saved to {MANIFEST_PATH}")

if __name__ == "__main__":
    run()