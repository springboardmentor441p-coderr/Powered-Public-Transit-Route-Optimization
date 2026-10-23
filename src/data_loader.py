"""Module 1 - Data collection: read GTFS feeds from folders or uploaded zip files."""
import io, zipfile
from pathlib import Path
import pandas as pd
from .config import DATA_DIR

REQUIRED = ["routes", "trips", "stop_times", "stops", "calendar"]
OPTIONAL = ["frequencies", "shapes"]

def _read(buf):
    return pd.read_csv(buf, dtype=str, skipinitialspace=True, low_memory=False)

def read_feed_dir(path):
    path = Path(path); feed = {}
    for name in REQUIRED + OPTIONAL:
        f = path / f"{name}.txt"
        if f.exists(): feed[name] = _read(f)
        elif name in REQUIRED: raise FileNotFoundError(f"{name}.txt missing in {path}")
    rid = path / "ridership.csv"
    return feed, (pd.read_csv(rid) if rid.exists() else None)

def read_feed_zip(file_like):
    """file_like: path or file-like object holding a GTFS .zip (files may sit in a sub-folder)."""
    feed = {}
    with zipfile.ZipFile(file_like) as z:
        names = {Path(n).name: n for n in z.namelist()}
        for name in REQUIRED + OPTIONAL:
            if f"{name}.txt" in names:
                with z.open(names[f"{name}.txt"]) as fh: feed[name] = _read(io.BytesIO(fh.read()))
            elif name in REQUIRED: raise FileNotFoundError(f"{name}.txt not found in the uploaded zip")
    return feed

def load_all(root=DATA_DIR, cities=None):
    """Return {city: (feed, ridership_df | None)} for every sub-folder of `root`."""
    out = {}
    for d in sorted(Path(root).iterdir()):
        if d.is_dir() and (cities is None or d.name in cities):
            out[d.name] = read_feed_dir(d)
    return out

def load_histories(root=DATA_DIR, cities=None):
    """Past monthly ridership: DataFrame[city, route_id, month, boardings] (empty if none available)."""
    parts = []
    for d in sorted(Path(root).iterdir()):
        f = d / "ridership_history.csv"
        if d.is_dir() and f.exists() and (cities is None or d.name in cities):
            parts.append(pd.read_csv(f).assign(city=d.name))
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=["city", "route_id", "month", "boardings"])
