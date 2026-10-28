"""
analytics/01_source_register.py
RouteRanker Data Pipeline - Step 1: Source Registration & Integrity Check

Computes SHA-256 hashes, file sizes, and record manifests for raw datasets.
Generates reports/source_manifest.json to guarantee data integrity.
"""

import os
import hashlib
import json
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = WORKSPACE_ROOT / "data"
REPORTS_DIR = WORKSPACE_ROOT / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

def compute_sha256(filepath: Path) -> str:
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(1024 * 1024 * 8):  # 8MB chunks
            hasher.update(chunk)
    return hasher.hexdigest()

def register_sources():
    print("=" * 60)
    print("ROUTERANKER PIPELINE: STEP 1 - SOURCE REGISTRATION")
    print("=" * 60)

    manifest = {
        "workspace": str(WORKSPACE_ROOT),
        "files": {},
        "gtfs_snapshots": {}
    }

    # 1. Locate Ridership CSV
    ridership_files = list(DATA_DIR.glob("*Ridership*.csv"))
    if not ridership_files:
        raise FileNotFoundError(f"No ridership CSV found in {DATA_DIR}")

    ridership_file = ridership_files[0]
    print(f"[FOUND] Ridership CSV: {ridership_file.name}")
    csv_size = ridership_file.stat().st_size
    csv_hash = compute_sha256(ridership_file)

    manifest["files"]["ridership_csv"] = {
        "filename": ridership_file.name,
        "path": str(ridership_file.relative_to(WORKSPACE_ROOT)),
        "size_bytes": csv_size,
        "sha256": csv_hash
    }
    print(f"  Size: {csv_size:,} bytes | SHA256: {csv_hash[:16]}...")

    # 2. GTFS Directories
    gtfs_dirs = [d for d in DATA_DIR.iterdir() if d.is_dir() and (d.name == "google_transit" or "mdb-" in d.name)]

    for gtfs_dir in gtfs_dirs:
        print(f"\n[SCANNING] GTFS Snapshot: {gtfs_dir.name}")
        manifest["gtfs_snapshots"][gtfs_dir.name] = {}
        for txt_file in sorted(gtfs_dir.glob("*.txt")):
            f_size = txt_file.stat().st_size
            f_hash = compute_sha256(txt_file)
            manifest["gtfs_snapshots"][gtfs_dir.name][txt_file.name] = {
                "size_bytes": f_size,
                "sha256": f_hash
            }
            print(f"  - {txt_file.name:<25}: {f_size:>10,} bytes | {f_hash[:12]}...")

    # Save manifest
    manifest_path = REPORTS_DIR / "source_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"\n[SAVED] Source manifest registered at: {manifest_path.relative_to(WORKSPACE_ROOT)}")
    return manifest

if __name__ == "__main__":
    register_sources()
