"""
Download the Manhattan Bus GTFS timetable versions (Mobility Database feed mdb-513)
and build an inventory of them.

Each version is saved as data/raw/gtfs/manhattan/<snapshot_date>/original.zip
(write-once: an existing file is never re-downloaded or overwritten).

For each file it records the SHA-256 hash, size, service date range, and route/trip/stop
counts in data/raw/gtfs/manhattan/gtfs_versions.csv (and a tracked copy in
reports/gtfs_versions.csv). Two kinds of copy are flagged:
  - duplicate_of:          identical zip bytes (same SHA-256)
  - schedule_duplicate_of: identical timetable content (trips, stop_times, calendar,
                           calendar_dates, stops, shapes) even if the zip was
                           re-packaged or cosmetic files like route colours changed
The `use` / `reason` columns record which versions feed the pipeline and why.

Usage:
    python src/fetch_gtfs.py
"""

import hashlib
import io
import zipfile
from pathlib import Path

import pandas as pd
import requests

FEED = "mdb-513"
BASE = f"https://files.mobilitydatabase.org/{FEED}"
OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "raw" / "gtfs" / "manhattan"

# Mobility Database dataset IDs (downloaded-on timestamp, UTC) listed in the Milestone 1 guide.
DATASETS = [
    "202512300036",
    "202601090049",
    "202601160047",
    "202602240026",
    "202602250109",
    "202603270138",
    "202604090120",
    "202606240130",
    "202609030140",
]

SCHEDULE_FILES = ["trips.txt", "stop_times.txt", "calendar.txt", "calendar_dates.txt",
                  "stops.txt", "shapes.txt"]

# Decisions for versions that are not used. Anything not listed here is used.
# Reasons are filled in from the checks in inspect(); see reports/gtfs_versions.csv.
EXCLUDE = {
    "2026-01-09": "Same timetable as 2025-12-30 (schedule files identical); only route_color "
                  "values in routes.txt changed and the zip is stored uncompressed (81.7 MB).",
    "2026-01-16": "Same timetable as 2025-12-30 (schedule files identical); only route_color "
                  "values in routes.txt changed.",
    "2026-02-24": "Incomplete: all 41 routes present but only 6,144 trips (vs 37,864) and 5 "
                  "service_ids, all weekday 'P6' services; no Saturday/Sunday service.",
    "2026-02-25": "Byte-identical to 2026-01-16 (same SHA-256).",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(ds: str) -> Path:
    snap = f"{ds[:4]}-{ds[4:6]}-{ds[6:8]}"
    path = OUT_DIR / snap / "original.zip"
    if path.exists():
        print(f"{snap}: exists, skipping download")
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    url = f"{BASE}/{FEED}-{ds}/{FEED}-{ds}.zip"
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        tmp = path.with_suffix(".zip.part")
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    tmp.rename(path)
    print(f"{snap}: downloaded {path.stat().st_size / 1e6:.1f} MB")
    return path


def _read(z: zipfile.ZipFile, name: str, **kw) -> pd.DataFrame | None:
    if name not in z.namelist():
        return None
    return pd.read_csv(io.BytesIO(z.read(name)), dtype=str, **kw)


def inspect(path: Path) -> dict:
    """Summarise one GTFS zip: service dates and network size."""
    with zipfile.ZipFile(path) as z:
        routes = _read(z, "routes.txt")
        trips = _read(z, "trips.txt", usecols=["route_id", "service_id", "trip_id"])
        stops = _read(z, "stops.txt", usecols=["stop_id"])
        cal = _read(z, "calendar.txt")
        cd = _read(z, "calendar_dates.txt")
        fi = _read(z, "feed_info.txt")
        files = sorted(z.namelist())
        h = hashlib.sha256()
        for name in SCHEDULE_FILES:
            if name in files:
                h.update(name.encode())
                h.update(z.read(name))
        schedule_hash = h.hexdigest()

    dates = []
    if cal is not None and len(cal):
        dates += [cal["start_date"].min(), cal["end_date"].max()]
    if cd is not None and len(cd):
        dates += [cd["date"].min(), cd["date"].max()]
    fmt = lambda d: f"{d[:4]}-{d[4:6]}-{d[6:]}" if d else None

    return {
        "service_start": fmt(min(dates)) if dates else None,
        "service_end": fmt(max(dates)) if dates else None,
        "feed_version": fi["feed_version"].iloc[0] if fi is not None and "feed_version" in fi else None,
        "n_routes": len(routes) if routes is not None else 0,
        "n_routes_with_trips": trips["route_id"].nunique() if trips is not None else 0,
        "n_trips": len(trips) if trips is not None else 0,
        "n_stops": len(stops) if stops is not None else 0,
        "n_services": trips["service_id"].nunique() if trips is not None else 0,
        "files": ";".join(files),
        "schedule_hash": schedule_hash,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    records = []
    for ds in DATASETS:
        path = download(ds)
        rec = {
            "snapshot_date": path.parent.name,
            "mdb_dataset_id": f"{FEED}-{ds}",
            "source_url": f"{BASE}/{FEED}-{ds}/{FEED}-{ds}.zip",
            "path": path.relative_to(OUT_DIR.parents[3]).as_posix(),
            "size_mb": round(path.stat().st_size / 1e6, 2),
            "sha256": sha256(path),
        }
        rec.update(inspect(path))
        records.append(rec)

    df = pd.DataFrame(records)
    first = df.groupby("sha256")["snapshot_date"].transform("first")
    df["duplicate_of"] = first.where(first != df["snapshot_date"])
    first = df.groupby("schedule_hash")["snapshot_date"].transform("first")
    df["schedule_duplicate_of"] = first.where(first != df["snapshot_date"])
    df["use"] = ~df["snapshot_date"].isin(EXCLUDE)
    df["reason"] = df["snapshot_date"].map(EXCLUDE).fillna("")

    df.to_csv(OUT_DIR / "gtfs_versions.csv", index=False)
    reports = OUT_DIR.parents[3] / "reports"
    reports.mkdir(exist_ok=True)
    df.drop(columns=["files"]).to_csv(reports / "gtfs_versions.csv", index=False)

    cols = ["snapshot_date", "size_mb", "sha256", "duplicate_of", "schedule_duplicate_of",
            "service_start", "service_end", "n_routes_with_trips", "n_trips", "use"]
    show = df[cols].copy()
    show["sha256"] = show["sha256"].str[:12]
    print()
    print(show.to_string(index=False))
    print(f"\nInventory -> {OUT_DIR / 'gtfs_versions.csv'}")


if __name__ == "__main__":
    main()
