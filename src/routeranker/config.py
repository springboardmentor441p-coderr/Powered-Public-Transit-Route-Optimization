"""Central configuration for RouteRanker.

Every path, data-source identifier and modelling assumption lives here so the
pipeline, the Streamlit frontend and the FastAPI backend all agree on them.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
MODELS_DIR = ROOT_DIR / "models"
REPORTS_DIR = ROOT_DIR / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"
METRICS_DIR = REPORTS_DIR / "metrics"

for _p in (RAW_DIR, PROCESSED_DIR, MODELS_DIR, FIGURES_DIR, METRICS_DIR):
    _p.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------- #
# Time zones
# --------------------------------------------------------------------------- #
IST = ZoneInfo("Asia/Kolkata")          # every date/time shown to the user
TRANSIT_TZ = ZoneInfo("America/New_York")  # local time of the bus network (MTA NYC)

# --------------------------------------------------------------------------- #
# Data sources (Socrata open-data API, data.ny.gov)
# --------------------------------------------------------------------------- #
SOCRATA_BASE = "https://data.ny.gov/resource"


@dataclass(frozen=True)
class Source:
    """Metadata of one open-data source (Socrata dataset)."""
    key: str
    dataset_id: str
    name: str
    granularity: str
    role: str

    @property
    def url(self) -> str:
        """Public portal URL of the dataset."""
        return f"https://data.ny.gov/d/{self.dataset_id}"


SOURCES: dict[str, Source] = {
    s.key: s
    for s in [
        Source("ridership", "gxb3-akrn", "MTA Bus Hourly Ridership: Beginning 2025",
               "Hourly x route x fare class", "Target variable - boardings per route per hour"),
        Source("schedules", "4fnn-qsea", "MTA Bus Schedules: 2026 (GTFS-derived)",
               "Stop-level scheduled trips", "Scheduled trips per route per hour, route length, stops"),
        Source("segment_speeds", "kufs-yh3x", "MTA Bus Route Segment Speeds: Beginning 2025",
               "Hourly x route x day-of-week x segment", "Hourly operating speed per route"),
        Source("route_speeds", "cudb-vcni", "MTA Bus Speeds: Beginning 2015",
               "Monthly x route x peak/off-peak", "Fallback route speed"),
        Source("wait_assessment", "v4z4-2h6n", "MTA Bus Wait Assessment: Beginning 2015",
               "Monthly x route x peak/off-peak", "Service reliability"),
        Source("fare_evasion", "uv5h-dfhp", "MTA Bus Fare Evasion: Beginning 2019",
               "Quarterly x trip type", "Paid-to-actual rider correction (ridership counts paid boardings)"),
        Source("routes", "bzwk-3hb4", "MTA Bus Routes (GTFS routes + shapes)",
               "Route x direction x shape", "Route names, type, colour, geometry"),
        Source("stops", "2ucp-7wg5", "MTA Bus Stops (GTFS stops)",
               "Route x stop", "Stop locations, overlap detection, maps"),
    ]
}

# Training window for the hourly ridership pull (inclusive start).
RIDERSHIP_START = "2025-10-01T00:00:00"
# Representative schedule dates (latest bundle available in the 2026 schedule table)
SCHEDULE_DATES = {"Weekday": "2026-08-25", "Saturday": "2026-08-22", "Sunday": "2026-08-23"}
SPEED_START = "2026-03-01T00:00:00"
MONTHLY_START = "2026-01-01T00:00:00"

# --------------------------------------------------------------------------- #
# Modelling assumptions (documented in the report)
# --------------------------------------------------------------------------- #
VEHICLE_CAPACITY = {          # practical (seated + comfortable standing) capacity
    "Local": 65,
    "Limited": 65,
    "Select Bus Service": 95,  # mostly articulated 60-ft buses
    "Express": 57,             # over-the-road coaches, seated only
    "Other": 65,
}
PEAK_LOAD_FACTOR = 0.55   # share of a trip's boardings on board at the max-load point
# Class thresholds on estimated occupancy. Defaults are absolute; the pipeline
# re-calibrates them from the data (25th / 90th percentile of service hours) and
# stores them in data/processed/thresholds.json, which is loaded below.
UNDERUTILIZED_MAX = 0.25  # occupancy below this -> Underutilized
OVERCROWDED_MIN = 0.85    # occupancy above this -> Overcrowded
TARGET_OCCUPANCY = 0.70   # occupancy the optimiser aims for
UNDER_QUANTILE, OVER_QUANTILE = 0.25, 0.90
EVASION_DEFAULT = {"Local": 0.45, "Limited": 0.45, "Select Bus Service": 0.45, "Express": 0.05, "Other": 0.45}
MIN_TRIPS_PER_HOUR = 2    # policy floor: trips/hour (both directions) during service hours
DIRECTIONS = 2            # scheduled trip counts include both directions
CLASS_LABELS = ["Underutilized", "Balanced", "Overcrowded"]

AM_PEAK = range(6, 10)
PM_PEAK = range(16, 20)

VALIDATION_DAYS = 28      # last N days held out for time-based validation
RANDOM_STATE = 42


THRESHOLDS_FILE = PROCESSED_DIR / "thresholds.json"


def set_thresholds(under: float, over: float) -> None:
    """Override class thresholds at runtime (used after data calibration)."""
    global UNDERUTILIZED_MAX, OVERCROWDED_MIN, TARGET_OCCUPANCY
    UNDERUTILIZED_MAX, OVERCROWDED_MIN = float(under), float(over)
    TARGET_OCCUPANCY = UNDERUTILIZED_MAX + 0.75 * (OVERCROWDED_MIN - UNDERUTILIZED_MAX)


if THRESHOLDS_FILE.exists():
    import json as _json
    _t = _json.loads(THRESHOLDS_FILE.read_text())
    set_thresholds(_t["underutilized_max"], _t["overcrowded_min"])


@dataclass
class ScoreWeights:
    """Weights of the composite RouteRank score (normalised to sum to 1)."""
    productivity: float = 0.25
    speed: float = 0.20
    reliability: float = 0.20
    frequency: float = 0.15
    comfort: float = 0.20
    extra: dict = field(default_factory=dict)

    def as_dict(self) -> dict[str, float]:
        """Return the five component weights normalised to sum to 1."""
        d = {"productivity": self.productivity, "speed": self.speed,
             "reliability": self.reliability, "frequency": self.frequency,
             "comfort": self.comfort}
        s = sum(d.values()) or 1.0
        return {k: v / s for k, v in d.items()}
