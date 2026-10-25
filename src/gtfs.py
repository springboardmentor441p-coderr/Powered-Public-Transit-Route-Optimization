"""Small helpers shared by the Chennai GTFS notebooks."""
from __future__ import annotations
import os
from pathlib import Path
import pandas as pd

REQUIRED_FILES = ("agency.txt", "calendar.txt", "routes.txt", "stop_times.txt", "stops.txt", "trips.txt")

def resolve_gtfs_dir(project_root: Path) -> Path:
    """Find the feed from GTFS_DIR or the project dataset folder."""
    candidates = []
    if os.environ.get("GTFS_DIR"):
        candidates.append(Path(os.environ["GTFS_DIR"]).expanduser())
    candidates.extend([
        project_root / "dataset" / "raw" / "chennai_gtfs",
        project_root / "data" / "raw" / "Chennai_gtfs",  # backward-compatible fallback
    ])
    for candidate in candidates:
        if candidate.is_dir() and all((candidate / name).is_file() for name in REQUIRED_FILES):
            return candidate.resolve()
    tried = "\n".join(f"  - {p}" for p in candidates)
    raise FileNotFoundError(
        "Could not find the Chennai GTFS folder. Set GTFS_DIR or place the seven .txt files in "
        f"{project_root / 'dataset' / 'raw' / 'chennai_gtfs'}. Checked:\n{tried}"
    )

def load_gtfs(gtfs_dir: Path) -> dict[str, pd.DataFrame]:
    """Load the supplied GTFS tables; identifiers remain strings to preserve key integrity."""
    tables = {}
    for name in REQUIRED_FILES:
        key = Path(name).stem
        tables[key] = pd.read_csv(gtfs_dir / name, dtype=str, keep_default_na=False)
    for col in ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"):
        tables["calendar"][col] = pd.to_numeric(tables["calendar"][col], errors="coerce").fillna(0).astype(int)
    tables["calendar"]["start_date"] = pd.to_datetime(tables["calendar"]["start_date"], format="%Y%m%d", errors="coerce")
    tables["calendar"]["end_date"] = pd.to_datetime(tables["calendar"]["end_date"], format="%Y%m%d", errors="coerce")
    tables["stops"]["stop_lat"] = pd.to_numeric(tables["stops"]["stop_lat"], errors="coerce")
    tables["stops"]["stop_lon"] = pd.to_numeric(tables["stops"]["stop_lon"], errors="coerce")
    tables["stop_times"]["stop_sequence"] = pd.to_numeric(tables["stop_times"]["stop_sequence"], errors="coerce")
    return tables

def active_service_ids(calendar: pd.DataFrame, service_date: str) -> set[str]:
    """Return scheduled service IDs active on a date, based on calendar.txt."""
    day = pd.Timestamp(service_date).normalize()
    weekday_col = day.day_name().lower()
    active = calendar[
        (calendar[weekday_col] == 1)
        & (calendar["start_date"] <= day)
        & (calendar["end_date"] >= day)
    ]
    return set(active["service_id"].astype(str))

def first_trip_departures(stop_times: pd.DataFrame) -> pd.DataFrame:
    """Get each trip's first scheduled departure and departure hour."""
    ordered = stop_times.sort_values(["trip_id", "stop_sequence"], kind="stable")
    first = ordered.drop_duplicates("trip_id", keep="first")[["trip_id", "departure_time"]].copy()
    parts = first["departure_time"].str.extract(r"^(?P<hour>\d{1,2}):(?P<minute>\d{2}):(?P<second>\d{2})$")
    first["departure_hour"] = pd.to_numeric(parts["hour"], errors="coerce")
    return first
