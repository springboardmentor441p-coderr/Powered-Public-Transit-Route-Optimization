"""Stage 1: download the CTA ridership CSV and the eight GTFS archives (spec 9.4).

Storage (spec 9.4.3):
    data/raw/ridership/<prefix><YYYYMMDD>.csv                (+ .metadata.json, .download_meta.json)
    data/raw/gtfs/<snapshot_id>/original.zip                 (+ download_meta.json)
    data/raw/gtfs/<snapshot_id>/extracted/*.txt

Rules:
- Never overwrite a raw file. If the target already exists, it is skipped.
- Download to a .part file and rename only after the transfer completes.
- Extraction rejects unsafe member paths (absolute paths or '..').

Usage (CMD):
    python -I analytics\\source\\download_sources.py --config analytics\\config\\sources.json --raw data\\raw
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

USER_AGENT = "routeranker-source-import/1.0"
CHUNK = 1024 * 1024


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def fetch(url: str, dest: Path) -> dict:
    """Stream url into dest via a .part file. Returns download metadata."""
    part = dest.with_name(dest.name + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    started = utc_now()
    sha = hashlib.sha256()
    size = 0
    with urllib.request.urlopen(req, timeout=120) as resp, open(part, "wb") as out:
        status = resp.status
        content_type = resp.headers.get("Content-Type")
        last_modified = resp.headers.get("Last-Modified")
        while True:
            block = resp.read(CHUNK)
            if not block:
                break
            out.write(block)
            sha.update(block)
            size += len(block)
            print(f"\r    {size / 1e6:8.1f} MB", end="", flush=True)
    print()
    part.replace(dest)
    return {
        "source_url": url,
        "download_started_at": started,
        "downloaded_at": utc_now(),
        "http_status": status,
        "content_type": content_type,
        "http_last_modified": last_modified,
        "byte_size": size,
        "sha256": sha.hexdigest(),
    }


def write_json(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def safe_extract(zip_path: Path, target: Path) -> int:
    """Extract every member into target, refusing unsafe paths and existing files."""
    target.mkdir(parents=True, exist_ok=True)
    n = 0
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            name = PurePosixPath(info.filename.replace("\\", "/"))
            if name.is_absolute() or ".." in name.parts or ":" in info.filename:
                raise ValueError(f"Unsafe member path in {zip_path}: {info.filename!r}")
            if info.is_dir():
                continue
            out = target.joinpath(*name.parts)
            if out.exists():
                print(f"    skip existing {out.name}")
                continue
            out.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, open(out, "wb") as dst:
                while block := src.read(CHUNK):
                    dst.write(block)
            n += 1
    return n


def download_ridership(cfg: dict, raw: Path) -> None:
    r = cfg["ridership"]
    folder = raw / "ridership"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    stem = f"{r['filename_prefix']}{stamp}"
    csv_path = folder / f"{stem}.csv"
    if csv_path.exists():
        print(f"[ridership] {csv_path.name} already exists - skipped (raw files are never overwritten)")
        return

    print(f"[ridership] metadata {r['metadata_url']}")
    meta_path = folder / f"{stem}.metadata.json"
    meta_dl = fetch(r["metadata_url"], meta_path)

    print(f"[ridership] CSV {r['source_url']}")
    dl = fetch(r["source_url"], csv_path)
    dl.update({"dataset_id": r["dataset_id"], "snapshot_id": stem, "acquisition": "download",
               "metadata_file": meta_path.name, "metadata_downloaded_at": meta_dl["downloaded_at"]})
    write_json(folder / f"{stem}.download_meta.json", dl)
    print(f"    saved {csv_path} ({dl['byte_size']:,} bytes)")


def download_gtfs(cfg: dict, raw: Path) -> None:
    g = cfg["gtfs"]
    ids = [a["snapshot_id"] for a in g["archives"]]
    if len(ids) != 8 or len(set(ids)) != 8:
        sys.exit(f"Manifest must list 8 unique archive IDs, got {ids}")
    for a in g["archives"]:
        sid = a["snapshot_id"]
        url = g["url_template"].format(id=sid)
        folder = raw / "gtfs" / sid
        folder.mkdir(parents=True, exist_ok=True)
        zip_path = folder / "original.zip"
        if zip_path.exists():
            print(f"[gtfs] {sid}: original.zip exists - download skipped")
        else:
            print(f"[gtfs] {sid}: {url}")
            dl = fetch(url, zip_path)
            dl.update({"dataset_id": g["dataset_id"], "snapshot_id": sid, "acquisition": "download"})
            write_json(folder / "download_meta.json", dl)
        n = safe_extract(zip_path, folder / "extracted")
        print(f"    extracted {n} new file(s)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True, type=Path)
    ap.add_argument("--raw", required=True, type=Path)
    ap.add_argument("--only", choices=["ridership", "gtfs"], help="download just one source type")
    args = ap.parse_args()
    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    if args.only in (None, "ridership"):
        download_ridership(cfg, args.raw)
    if args.only in (None, "gtfs"):
        download_gtfs(cfg, args.raw)


if __name__ == "__main__":
    main()
