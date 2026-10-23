"""Central configuration for RouteRanker."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "gtfs"
OUT_DIR = ROOT / "outputs"
MODEL_DIR = ROOT / "models"
FIG_DIR = OUT_DIR / "figures"

# --- Operational assumptions (all editable from the Streamlit sidebar) -------
BUS_CAPACITY = 60          # seated + comfortable standing, typical Indian city bus
RIDE_FRAC = 0.45           # avg share of the route an average passenger rides
TARGET_LF = 0.65           # target load factor used when sizing frequency
MIN_TRIPS_PER_HOUR = 2     # policy floor: headway never worse than 30 min
OVER_PEAK_LF = 1.20        # peak load factor above which a route is "overcrowded"
UNDER_AVG_LF = 0.30        # average load factor below which a route is "underutilized"

PEAK_HOURS = (7, 8, 9, 10, 17, 18, 19, 20)
CLASSES = ["underutilized", "balanced", "overcrowded"]

# Demand proxy (used when no ridership file is supplied)
DEMAND_K = 900.0           # boardings/day contributed by one unit of stop attraction

INDIA_BBOX = dict(lat_min=6.0, lat_max=38.0, lon_min=68.0, lon_max=98.0)
RANDOM_STATE = 42
