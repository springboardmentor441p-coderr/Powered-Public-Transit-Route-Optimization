"""
Step 1: Inventory and freeze inputs into data/processed/source_register.parquet.
"""
import os
import json
import hashlib
from datetime import datetime, timezone
import pandas as pd

RAW_DIR = "data/raw"
PROCESSED_DIR = "data/processed"

def compute_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def run():
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    manifest_path = os.path.join(RAW_DIR, "manifest.json")
    if not os.path.exists(manifest_path):
        raise FileNotFoundError("Missing data/raw/manifest.json. Run 00_generate_sample_data.py or register your raw downloads.")

    with open(manifest_path) as f:
        entries = json.load(f)

    records = []
    for item in entries:
        fpath = item["file_path"]
        actual_hash = compute_sha256(fpath)
        if item.get("sha256") and item["sha256"] != actual_hash:
            raise ValueError(f"Checksum mismatch for {fpath}: expected {item['sha256']}, got {actual_hash}")
        records.append({
            "dataset_id": item["dataset_id"],
            "snapshot_id": item["snapshot_id"],
            "source_url": item["source_url"],
            "catalog_retrieved_date": item["catalog_retrieved_date"],
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
            "sha256": actual_hash,
            "byte_size": os.path.getsize(fpath),
            "file_path": fpath,
        })

    df = pd.DataFrame(records)
    out_path = os.path.join(PROCESSED_DIR, "source_register.parquet")
    df.to_parquet(out_path, index=False)
    print(f"[01_source_register] Registered {len(df)} verified artifacts -> {out_path}")

if __name__ == "__main__":
    run()
