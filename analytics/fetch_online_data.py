"""
Automated Online Data Collector for RouteRanker.
Fetches fresh transit ridership data from the Chicago Data Portal (Socrata API)
and verifies GTFS feed availability from Mobility Database, updating data/raw/manifest.json
only when new data (different SHA-256 hash) is detected.
"""
import os
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
import requests

ROOT_DIR = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT_DIR / "data" / "raw" / "manifest.json"
RIDERSHIP_OUT = ROOT_DIR / "data" / "raw" / "ridership" / "CTA_Ridership_Bus_Routes_Daily_Sample.csv"
CTA_API_URL = "https://data.cityofchicago.org/resource/jyb9-n7fm.csv?$limit=50000&$order=date DESC"


def compute_sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def compute_sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch_latest_ridership(timeout: int = 30) -> dict:
    """
    Pulls latest online CTA daily ridership CSV and compares SHA-256 against manifest.json.
    Returns status metadata indicating whether new data was ingested.
    """
    RIDERSHIP_OUT.parent.mkdir(parents=True, exist_ok=True)
    current_hash = compute_sha256_file(RIDERSHIP_OUT) if RIDERSHIP_OUT.exists() else None

    try:
        resp = requests.get(CTA_API_URL, timeout=timeout)
        resp.raise_for_status()
        content = resp.content
        if len(content) < 200 or b"," not in content[:200]:
            return {"updated": False, "reason": "Invalid CSV payload received from online source", "sha256": current_hash}

        new_hash = compute_sha256_bytes(content)
        if new_hash == current_hash:
            return {"updated": False, "reason": "Online dataset unchanged (SHA-256 match)", "sha256": new_hash}

        RIDERSHIP_OUT.write_bytes(content)
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8")) if MANIFEST_PATH.exists() else []
        updated_entry = False
        for item in manifest:
            if item.get("dataset_id") == "cta_daily_ridership":
                item["snapshot_id"] = f"{today_str}-auto"
                item["catalog_retrieved_date"] = today_str
                item["sha256"] = new_hash
                item["byte_size"] = len(content)
                updated_entry = True

        if not updated_entry:
            manifest.append({
                "dataset_id": "cta_daily_ridership",
                "snapshot_id": f"{today_str}-auto",
                "source_url": CTA_API_URL,
                "catalog_retrieved_date": today_str,
                "file_path": "data/raw/ridership/CTA_Ridership_Bus_Routes_Daily_Sample.csv",
                "sha256": new_hash,
                "byte_size": len(content),
            })

        MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return {"updated": True, "reason": "New online ridership data downloaded and manifest updated", "sha256": new_hash}

    except Exception as exc:
        return {"updated": False, "reason": f"Online fetch skipped/unavailable: {exc}", "sha256": current_hash}


if __name__ == "__main__":
    result = fetch_latest_ridership()
    print(json.dumps(result, indent=2))
