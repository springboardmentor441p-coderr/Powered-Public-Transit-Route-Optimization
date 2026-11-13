"""Stage 1: build the source register from the files actually on disk (spec 9.4.3, 2.1).

It scans data/raw, so a file placed manually (e.g. the 2026-10-22 reference export, if it becomes available)
is registered too, with acquisition=manual.

Writes data/raw/source_register.csv and a committed copy at reports/source_register.csv.

Usage (CMD):
    python -I analytics\\source\\build_register.py --config analytics\\config\\sources.json --raw data\\raw --out reports
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

COLUMNS = [
    "dataset_id", "snapshot_id", "source_url", "catalog_retrieved_date", "downloaded_at",
    "sha256", "byte_size",
    # extra provenance columns
    "local_path", "acquisition", "row_count", "source_last_updated",
    "expected_sha256", "fingerprint_match", "is_primary",
]


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while block := f.read(1024 * 1024):
            h.update(block)
    return h.hexdigest()


def csv_data_rows(path: Path) -> int:
    """Count CSV records with the csv module (safe even if a field contains a newline)."""
    with open(path, newline="", encoding="utf-8") as f:
        return sum(1 for _ in csv.reader(f)) - 1


def iso_mtime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")


def read_json(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def ridership_rows(cfg: dict, raw: Path, root: Path) -> list[dict]:
    r = cfg["ridership"]
    spec_snap = r["spec_reference"]["snapshot_id"]
    rows = []
    for csv_path in sorted((raw / "ridership").glob("*.csv")):
        stem = csv_path.stem
        dl = read_json(csv_path.with_name(stem + ".download_meta.json"))
        meta = read_json(csv_path.with_name(stem + ".metadata.json"))
        sha = sha256_of(csv_path)
        if dl and dl["sha256"] != sha:
            raise SystemExit(f"{csv_path}: sha256 changed since download - raw file was modified!")
        last_updated = ""
        if meta and isinstance(meta.get("rowsUpdatedAt"), int):
            last_updated = datetime.fromtimestamp(meta["rowsUpdatedAt"], timezone.utc).isoformat()
        rows.append({
            "dataset_id": r["dataset_id"],
            "snapshot_id": stem,
            "source_url": r["source_url"],
            "catalog_retrieved_date": dl["metadata_downloaded_at"][:10] if dl else "",
            "downloaded_at": dl["downloaded_at"] if dl else iso_mtime(csv_path),
            "sha256": sha,
            "byte_size": csv_path.stat().st_size,
            "local_path": csv_path.relative_to(root).as_posix(),
            "acquisition": "download" if dl else "manual",
            "row_count": csv_data_rows(csv_path),
            "source_last_updated": last_updated,
            "expected_sha256": r["spec_reference"]["sha256"],
            "fingerprint_match": sha == r["spec_reference"]["sha256"],
            "is_primary": False,
        })
    # Primary version: explicit config value, else the spec's file if present, else the newest export.
    wanted = cfg.get("primary_ridership_snapshot")
    names = [x["snapshot_id"] for x in rows]
    if not wanted:
        wanted = spec_snap if spec_snap in names else (max(names) if names else None)
    for x in rows:
        x["is_primary"] = x["snapshot_id"] == wanted
    return rows


def gtfs_rows(cfg: dict, raw: Path, root: Path) -> list[dict]:
    g = cfg["gtfs"]
    rows = []
    for a in g["archives"]:
        sid = a["snapshot_id"]
        zip_path = raw / "gtfs" / sid / "original.zip"
        if not zip_path.exists():
            print(f"WARNING: missing {zip_path}")
            continue
        dl = read_json(zip_path.with_name("download_meta.json"))
        sha = sha256_of(zip_path)
        if dl and dl["sha256"] != sha:
            raise SystemExit(f"{zip_path}: sha256 changed since download - raw file was modified!")
        rows.append({
            "dataset_id": g["dataset_id"],
            "snapshot_id": sid,
            "source_url": g["url_template"].format(id=sid),
            "catalog_retrieved_date": cfg["catalog_retrieved_date"],
            "downloaded_at": dl["downloaded_at"] if dl else iso_mtime(zip_path),
            "sha256": sha,
            "byte_size": zip_path.stat().st_size,
            "local_path": zip_path.relative_to(root).as_posix(),
            "acquisition": "download" if dl else "manual",
            "row_count": "",
            "source_last_updated": "",
            "expected_sha256": a["sha256"],
            "fingerprint_match": sha == a["sha256"],
            "is_primary": True,
        })
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True, type=Path)
    ap.add_argument("--raw", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    root = args.raw.resolve().parent.parent  # data/raw -> project root
    raw = args.raw.resolve()

    rows = ridership_rows(cfg, raw, root) + gtfs_rows(cfg, raw, root)
    keys = [(x["dataset_id"], x["snapshot_id"]) for x in rows]
    assert len(keys) == len(set(keys)), "duplicate (dataset_id, snapshot_id) in register"

    args.out.mkdir(parents=True, exist_ok=True)
    for dest in (raw / "source_register.csv", args.out / "source_register.csv"):
        with open(dest, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=COLUMNS)
            w.writeheader()
            w.writerows(rows)
        print(f"wrote {dest}")

    print("\nFingerprint comparison against spec 9.22.1:")
    for x in rows:
        status = "MATCH" if x["fingerprint_match"] else "MISMATCH"
        print(f"  {status:8}  {x['snapshot_id']}  {x['sha256'][:16]}...  (expected {x['expected_sha256'][:16]}...)")


if __name__ == "__main__":
    main()
