"""RouteRanker - BACKEND (single main file).

Everything server-side lives here:

  1. configuration            7. classification + forecasting models
  2. data collection          8. optimisation + scenario simulator
  3. data cleaning            9. inference / RouteRank service
  4. feature engineering     10. GTFS upload analyser
  5. preprocessing           11. diagrams (architecture, pipeline, model figures)
  6. clustering              12. training pipeline
                             13. FastAPI REST API
                             14. command-line interface

Usage (from the project root):
    python backend/main.py collect          # download / refresh MTA data
    python backend/main.py train            # clean -> features -> models -> artefacts
    python backend/main.py train --refresh  # re-download every source first
    python backend/main.py serve            # REST API on http://localhost:8000/docs
    uvicorn backend.main:app --port 8000    # same API via uvicorn
"""
from __future__ import annotations

import argparse
import gc
import io
import itertools
import json
import logging
import re
import sys
import time
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from functools import cached_property, lru_cache
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import holidays
import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import requests  # noqa: E402
import seaborn as sns  # noqa: E402
from fastapi import FastAPI, HTTPException, Query  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402
from sklearn.cluster import DBSCAN, KMeans  # noqa: E402
from sklearn.decomposition import PCA  # noqa: E402
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor  # noqa: E402
from sklearn.metrics import (accuracy_score, balanced_accuracy_score, calinski_harabasz_score,  # noqa: E402
                             classification_report, confusion_matrix, davies_bouldin_score, f1_score,
                             mean_absolute_error, mean_squared_error, r2_score, silhouette_score)
from sklearn.neighbors import NearestNeighbors  # noqa: E402
from sklearn.preprocessing import LabelEncoder, RobustScaler, StandardScaler  # noqa: E402
from sklearn.utils.class_weight import compute_sample_weight  # noqa: E402
from xgboost import XGBClassifier, XGBRegressor  # noqa: E402


# ====================================================================================================
# SECTION 1. CONFIGURATION - paths, data sources, time zones, modelling assumptions
# ====================================================================================================
# Central configuration for RouteRanker.
#
# Every path, data-source identifier and modelling assumption lives here so the
# pipeline, the Streamlit frontend and the FastAPI backend all agree on them.

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
MODELS_DIR = ROOT_DIR / "models"
REPORTS_DIR = ROOT_DIR / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"
METRICS_DIR = REPORTS_DIR / "metrics"
EDA_DIR = ROOT_DIR / "eda"             # outputs of eda/main.py

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


# All sections below refer to configuration values as C.<NAME> (C = this module).
C = sys.modules[__name__]

# ====================================================================================================
# SECTION 2. DATA COLLECTION - MTA open data via Socrata SODA / SoQL
# ====================================================================================================
# Module 1 - Data Collection.
#
# Downloads the MTA open datasets from the Socrata SODA API (data.ny.gov).
# Heavy tables are aggregated server-side with SoQL so that only the
# granularity we need (route x hour) travels over the network.
#
# Run directly:  python -m routeranker.data_collection

log = logging.getLogger(__name__)
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "RouteRanker/1.0 (open-data research client)"})
PAGE = 50_000


# --------------------------------------------------------------------------- #
# Low-level SODA helpers
# --------------------------------------------------------------------------- #
def soql_request(dataset_id: str, params: dict, fmt: str = "csv", retries: int = 4) -> requests.Response:
    """Issue one SODA request with exponential back-off retries."""
    url = f"{C.SOCRATA_BASE}/{dataset_id}.{fmt}"
    for attempt in range(retries):
        try:
            r = SESSION.get(url, params=params, timeout=300)
            if r.status_code == 200:
                return r
            log.warning("HTTP %s for %s: %s", r.status_code, dataset_id, r.text[:300])
        except requests.RequestException as exc:  # network hiccup
            log.warning("Request error %s (attempt %d)", exc, attempt + 1)
        time.sleep(2 ** attempt)
    raise RuntimeError(f"SODA request failed for {dataset_id} with {params}")


def soql_fetch(dataset_id: str, params: dict, fmt: str = "csv", page_size: int = PAGE) -> pd.DataFrame:
    """Fetch every page of a SoQL query and return one DataFrame."""
    frames, offset = [], 0
    while True:
        p = {**params, "$limit": page_size, "$offset": offset}
        r = soql_request(dataset_id, p, fmt)
        if fmt == "csv":
            df = pd.read_csv(io.StringIO(r.text), low_memory=False)
        else:
            df = pd.DataFrame(r.json())
        frames.append(df)
        log.info("  %s: fetched %d rows (offset %d)", dataset_id, len(df), offset)
        if len(df) < page_size:
            break
        offset += page_size
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def latest_timestamp(dataset_id: str = C.SOURCES["ridership"].dataset_id,
                     column: str = "transit_timestamp") -> pd.Timestamp | None:
    """Return the most recent timestamp published for a dataset (data freshness check)."""
    try:
        r = soql_request(dataset_id, {"$select": f"max({column}) as m"}, "json", retries=2)
        return pd.Timestamp(r.json()[0]["m"])
    except Exception:  # offline
        return None


# --------------------------------------------------------------------------- #
# Dataset-specific collectors
# --------------------------------------------------------------------------- #
def _month_starts(start: str, end: pd.Timestamp) -> list[pd.Timestamp]:
    """First day of every month from ``start`` up to ``end`` (download chunks)."""
    s = pd.Timestamp(start).normalize().replace(day=1)
    return list(pd.date_range(s, end, freq="MS"))


def collect_hourly_ridership(start: str = C.RIDERSHIP_START, force: bool = False) -> pd.DataFrame:
    """Hourly boardings per route (summed over payment method and fare class).

    Pulled month by month; completed months are cached as parquet files so a
    re-run only refreshes the current month (incremental / near-real-time update).
    """
    ds = C.SOURCES["ridership"].dataset_id
    out_dir = C.RAW_DIR / "ridership"
    out_dir.mkdir(exist_ok=True)
    latest = latest_timestamp() or pd.Timestamp.now()
    months = _month_starts(start, latest)
    for i, m in enumerate(months):
        nxt = m + pd.offsets.MonthBegin(1)
        f = out_dir / f"ridership_{m:%Y_%m}.parquet"
        is_open_month = nxt > latest
        if f.exists() and not force and not is_open_month:
            continue
        log.info("Ridership %s ...", f"{m:%Y-%m}")
        df = soql_fetch(ds, {
            "$select": "transit_timestamp, bus_route, sum(ridership) as ridership, sum(transfers) as transfers",
            "$where": f"transit_timestamp >= '{m:%Y-%m-%dT%H:%M:%S}' AND transit_timestamp < '{nxt:%Y-%m-%dT%H:%M:%S}'",
            "$group": "transit_timestamp, bus_route",
            "$order": "transit_timestamp, bus_route",
        })
        if not df.empty:
            df.to_parquet(f, index=False)
    files = sorted(out_dir.glob("ridership_*.parquet"))
    return pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)


def collect_schedules() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Scheduled trip starts per route per hour for each day type + route length/stops.

    Returns (trips_per_hour, route_geometry_stats).
    """
    ds = C.SOURCES["schedules"].dataset_id
    tph_frames = []
    for day_type, d in C.SCHEDULE_DATES.items():
        log.info("Schedules %s (%s) ...", day_type, d)
        df = soql_fetch(ds, {
            "$select": "route_id, borough, trip_type, date_extract_hh(schedule_time) as hour, count(*) as trips",
            "$where": f"schedule_date = '{d}T00:00:00' AND origin = '1'",
            "$group": "route_id, borough, trip_type, hour",
        })
        df["day_type"] = day_type
        tph_frames.append(df)
    tph = pd.concat(tph_frames, ignore_index=True)

    d = C.SCHEDULE_DATES["Weekday"]
    log.info("Schedules - route length & stops ...")
    geo = soql_fetch(ds, {
        "$select": "route_id, shape_id, max(distance_from_start::number) as length_ft, "
                   "count(distinct stop_id) as n_stops",
        "$where": f"schedule_date = '{d}T00:00:00'",
        "$group": "route_id, shape_id",
    })
    tph.to_parquet(C.RAW_DIR / "schedule_trips_per_hour.parquet", index=False)
    geo.to_parquet(C.RAW_DIR / "schedule_route_geometry.parquet", index=False)
    return tph, geo


def collect_segment_speeds(start: str = C.SPEED_START) -> pd.DataFrame:
    """Trip-weighted hourly operating speed (mph) per route x day-of-week x hour."""
    ds = C.SOURCES["segment_speeds"].dataset_id
    log.info("Segment speeds ...")
    df = soql_fetch(ds, {
        "$select": "route_id, route_type, borough, day_of_week, hour_of_day, "
                   "sum(road_distance * bus_trip_count) as dist_x_trips, "
                   "sum(average_travel_time * bus_trip_count) as min_x_trips, "
                   "sum(bus_trip_count) as trips_observed",
        "$where": f"timestamp >= '{start}'",
        "$group": "route_id, route_type, borough, day_of_week, hour_of_day",
    })
    df.to_parquet(C.RAW_DIR / "segment_speeds.parquet", index=False)
    return df


def collect_route_speeds(start: str = C.MONTHLY_START) -> pd.DataFrame:
    """Monthly average speed per route and period (fallback speed source)."""
    ds = C.SOURCES["route_speeds"].dataset_id
    log.info("Monthly route speeds ...")
    df = soql_fetch(ds, {
        "$select": "route_id, borough, trip_type, period, day_type, avg(average_speed) as avg_speed",
        "$where": f"month >= '{start}'",
        "$group": "route_id, borough, trip_type, period, day_type",
    })
    df.to_parquet(C.RAW_DIR / "route_speeds.parquet", index=False)
    return df


def collect_wait_assessment(start: str = C.MONTHLY_START) -> pd.DataFrame:
    """Wait assessment (share of headways within the standard) per route/period."""
    ds = C.SOURCES["wait_assessment"].dataset_id
    log.info("Wait assessment ...")
    df = soql_fetch(ds, {
        "$select": "route_id, period, sum(number_of_trips_passing_wait) as passing, "
                   "sum(number_of_scheduled_trips) as scheduled",
        "$where": f"month >= '{start}'",
        "$group": "route_id, period",
    })
    df.to_parquet(C.RAW_DIR / "wait_assessment.parquet", index=False)
    return df


def collect_fare_evasion() -> pd.DataFrame:
    """Quarterly fare-evasion rate by trip type (Local / SBS / Express / Total)."""
    ds = C.SOURCES["fare_evasion"].dataset_id
    log.info("Fare evasion ...")
    df = soql_fetch(ds, {"$select": "time_period, trip_type, fare_evasion", "$order": "time_period DESC"})
    df.to_parquet(C.RAW_DIR / "fare_evasion.parquet", index=False)
    return df


def collect_routes() -> pd.DataFrame:
    """Current route catalogue (GTFS routes.txt + shapes.txt equivalent) with geometry."""
    ds = C.SOURCES["routes"].dataset_id
    log.info("Routes & shapes ...")
    df = soql_fetch(ds, {
        "$select": "route_id, route_short_name, route_long_name, route_description, route_type, "
                   "route_color, direction_id, shape_id, shape_length, geometry",
        "$where": "in_effect = 'true'",
    }, fmt="json", page_size=5000)
    # simplify geometry -> list of [lon, lat] keeping every 4th vertex (enough for maps)
    def _simplify(g):
        """Flatten a GeoJSON MultiLineString and keep every 4th vertex (lighter map paths)."""
        try:
            coords = [pt for line in g["coordinates"] for pt in line]
            return json.dumps(coords[::4] + [coords[-1]])
        except Exception:
            return None
    df["path"] = df["geometry"].apply(_simplify)
    df = df.drop(columns=["geometry"])
    df.to_parquet(C.RAW_DIR / "routes.parquet", index=False)
    return df


def collect_stops() -> pd.DataFrame:
    """Current stops served by each route (GTFS stops.txt equivalent)."""
    ds = C.SOURCES["stops"].dataset_id
    log.info("Stops ...")
    df = soql_fetch(ds, {
        "$select": "route_id, stop_id, stop_name, direction_id, latitude, longitude, is_cbd",
        "$where": "in_effect = 'true'",
    })
    df.to_parquet(C.RAW_DIR / "stops.parquet", index=False)
    return df


def collect_all(force: bool = False) -> dict[str, pd.DataFrame]:
    """Run every collector and write a small manifest describing what was pulled."""
    started = datetime.now(C.IST)
    out = {
        "ridership": collect_hourly_ridership(force=force),
        "segment_speeds": collect_segment_speeds(),
        "route_speeds": collect_route_speeds(),
        "wait_assessment": collect_wait_assessment(),
        "fare_evasion": collect_fare_evasion(),
        "routes": collect_routes(),
        "stops": collect_stops(),
    }
    tph, geo = collect_schedules()
    out["schedule_tph"], out["schedule_geo"] = tph, geo
    manifest = {
        "collected_at_ist": started.strftime("%Y-%m-%d %H:%M:%S IST"),
        "tables": {k: int(len(v)) for k, v in out.items()},
        "sources": {k: {"id": s.dataset_id, "name": s.name, "url": s.url,
                        "granularity": s.granularity} for k, s in C.SOURCES.items()},
    }
    (C.RAW_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return out

# ====================================================================================================
# SECTION 3. DATA CLEANING
# ====================================================================================================
# Module 2a - Data Cleaning.
#
# Turns the raw open-data pulls into tidy, validated tables:
# missing-value handling, type coercion, ID normalisation, duplicate removal,
# outlier capping and completion of the hourly grid.

log = logging.getLogger(__name__)

BOROUGH_BY_PREFIX = [  # order matters: longest prefix first
    ("BXM", "Bronx (Express)"), ("BM", "Brooklyn (Express)"), ("QM", "Queens (Express)"),
    ("SIM", "Staten Island (Express)"), ("X", "Express"),
    ("BX", "Bronx"), ("B", "Brooklyn"), ("M", "Manhattan"), ("Q", "Queens"), ("S", "Staten Island"),
]


def normalize_route_id(x) -> str | None:
    """Canonical route id: upper-case, no spaces, SBS suffix kept as '+'."""
    if pd.isna(x):
        return None
    s = str(x).strip().upper().replace(" ", "")
    s = re.sub(r"-?SBS$", "+", s)
    return s or None


def borough_of(route_id: str) -> str:
    """Infer the operating borough from the route prefix (MTA naming convention)."""
    for p, b in BOROUGH_BY_PREFIX:
        if route_id.startswith(p) and (len(route_id) == len(p) or route_id[len(p)].isdigit()):
            return b
    return "Other"


def clean_ridership(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Clean hourly ridership and complete the route x hour grid.

    Steps
    1. parse timestamps and numerics, drop rows with no route/timestamp
    2. normalise route ids, sum duplicates (same route + hour)
    3. negative counts -> 0
    4. build a complete hourly grid per route between its first and last
       observation; missing hours are filled with 0 and flagged ``imputed``
    5. cap extreme spikes at 3x the route's 99.9th percentile
    6. drop routes with negligible ridership (< 20 boardings/day on average)
    """
    rep: dict = {"raw_rows": int(len(raw))}
    df = raw.rename(columns={"bus_route": "route_id", "transit_timestamp": "ts"}).copy()
    df["ts"] = pd.to_datetime(df["ts"], errors="coerce")
    for c in ("ridership", "transfers"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    rep["missing_values"] = {c: int(df[c].isna().sum()) for c in ("ts", "route_id", "ridership", "transfers")}
    df["route_id"] = df["route_id"].map(normalize_route_id)
    df = df.dropna(subset=["ts", "route_id"])
    df[["ridership", "transfers"]] = df[["ridership", "transfers"]].fillna(0)
    rep["negative_values"] = int((df[["ridership", "transfers"]] < 0).sum().sum())
    df[["ridership", "transfers"]] = df[["ridership", "transfers"]].clip(lower=0)

    before = len(df)
    df = df.groupby(["route_id", "ts"], as_index=False)[["ridership", "transfers"]].sum()
    rep["duplicates_merged"] = int(before - len(df))

    # complete hourly grid
    grids = []
    for rid, g in df.groupby("route_id"):
        idx = pd.date_range(g["ts"].min(), g["ts"].max(), freq="h")
        g = g.set_index("ts").reindex(idx)
        g["imputed"] = g["ridership"].isna()
        g[["ridership", "transfers"]] = g[["ridership", "transfers"]].fillna(0)
        g["route_id"] = rid
        grids.append(g.rename_axis("ts").reset_index())
    df = pd.concat(grids, ignore_index=True)
    rep["imputed_hours"] = int(df["imputed"].sum())

    # outlier capping
    p999 = df.groupby("route_id")["ridership"].transform(lambda s: s.quantile(0.999))
    cap = 3 * p999.clip(lower=10)
    rep["outliers_capped"] = int((df["ridership"] > cap).sum())
    df["ridership"] = np.minimum(df["ridership"], cap)

    # drop negligible routes
    days = df.groupby("route_id")["ts"].agg(lambda s: max((s.max() - s.min()).days, 1))
    daily = df.groupby("route_id")["ridership"].sum() / days
    keep = daily[daily >= 20].index
    rep["routes_dropped_low_ridership"] = sorted(set(daily.index) - set(keep))
    df = df[df["route_id"].isin(keep)]
    rep["clean_rows"] = int(len(df))
    rep["routes"] = int(df["route_id"].nunique())
    rep["date_min"], rep["date_max"] = str(df["ts"].min()), str(df["ts"].max())
    df["ridership"] = df["ridership"].astype("float32")
    df["transfers"] = df["transfers"].astype("float32")
    return df, rep


def clean_schedule(tph: pd.DataFrame, geo: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Trips per route/day-type/hour (complete 24h grid) and route length/stop counts."""
    tph = tph.copy()
    tph["route_id"] = tph["route_id"].map(normalize_route_id)
    tph["hour"] = pd.to_numeric(tph["hour"], errors="coerce") % 24
    tph["trips"] = pd.to_numeric(tph["trips"], errors="coerce").fillna(0)
    tph = tph.dropna(subset=["route_id", "hour"])
    trips = tph.groupby(["route_id", "day_type", "hour"], as_index=False)["trips"].sum()
    grid = pd.MultiIndex.from_product(
        [trips["route_id"].unique(), list(C.SCHEDULE_DATES), range(24)],
        names=["route_id", "day_type", "hour"]).to_frame(index=False)
    trips = grid.merge(trips, how="left").fillna({"trips": 0})
    trips["hour"] = trips["hour"].astype(int)

    geo = geo.copy()
    geo["route_id"] = geo["route_id"].map(normalize_route_id)
    geo["length_ft"] = pd.to_numeric(geo["length_ft"], errors="coerce")
    geo["n_stops"] = pd.to_numeric(geo["n_stops"], errors="coerce")
    g = geo.groupby("route_id").agg(length_ft=("length_ft", lambda s: s.quantile(0.75)),
                                    n_stops=("n_stops", "max"),
                                    n_patterns=("shape_id", "nunique")).reset_index()
    g["length_mi"] = (g["length_ft"] / 5280).round(2)
    # route type as published in schedule ("trip_type") is coarse; keep borough too
    meta = tph.groupby("route_id").agg(sched_borough=("borough", "first")).reset_index()
    g = g.merge(meta, how="left")
    return trips, g.drop(columns=["length_ft"])


def clean_speeds(seg: pd.DataFrame, monthly: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Hourly route speed (mph) by day-of-week/hour + route-level fallback speed."""
    seg = seg.copy()
    seg["route_id"] = seg["route_id"].map(normalize_route_id)
    for c in ("dist_x_trips", "min_x_trips", "trips_observed", "hour_of_day"):
        seg[c] = pd.to_numeric(seg[c], errors="coerce")
    seg = seg[(seg["min_x_trips"] > 0) & seg["route_id"].notna()]
    seg["speed_mph"] = seg["dist_x_trips"] / (seg["min_x_trips"] / 60)
    seg = seg[seg["speed_mph"].between(1, 45)]
    seg["dow"] = pd.to_datetime(seg["day_of_week"], format="%A", errors="coerce").dt.dayofweek
    dow_map = {d: i for i, d in enumerate(["Monday", "Tuesday", "Wednesday", "Thursday",
                                           "Friday", "Saturday", "Sunday"])}
    seg["dow"] = seg["day_of_week"].map(dow_map)
    hourly = (seg.groupby(["route_id", "dow", "hour_of_day"])
                 .apply(lambda g: np.average(g["speed_mph"], weights=g["trips_observed"].clip(lower=1)),
                        include_groups=False)
                 .rename("speed_mph").reset_index().rename(columns={"hour_of_day": "hour"}))
    hourly["hour"] = hourly["hour"].astype(int)
    rtype = seg.groupby("route_id")["route_type"].agg(lambda s: s.mode().iat[0] if len(s.mode()) else None)

    monthly = monthly.copy()
    monthly["route_id"] = monthly["route_id"].map(normalize_route_id)
    monthly["avg_speed"] = pd.to_numeric(monthly["avg_speed"], errors="coerce")
    route_speed = monthly.groupby("route_id")["avg_speed"].mean().rename("route_speed_mph").reset_index()
    route_speed = route_speed.merge(rtype.rename("seg_route_type").reset_index(), how="outer")
    return hourly, route_speed


def clean_wait(wait: pd.DataFrame) -> pd.DataFrame:
    """Reliability (wait assessment) overall and at peak per route."""
    w = wait.copy()
    w["route_id"] = w["route_id"].map(normalize_route_id)
    for c in ("passing", "scheduled"):
        w[c] = pd.to_numeric(w[c], errors="coerce")
    w = w.dropna(subset=["route_id"])
    tot = w.groupby("route_id")[["passing", "scheduled"]].sum()
    out = (tot["passing"] / tot["scheduled"]).rename("reliability").to_frame()
    peak = w[w["period"].str.lower() == "peak"].groupby("route_id")[["passing", "scheduled"]].sum()
    out["reliability_peak"] = peak["passing"] / peak["scheduled"]
    return out.reset_index()


def clean_evasion(ev: pd.DataFrame, quarters: int = 4) -> dict[str, float]:
    """Average fare-evasion rate of the latest ``quarters`` quarters per route type.

    The hourly ridership table counts PAID boardings only, so estimated total
    riders = paid / (1 - evasion).
    """
    out = dict(C.EVASION_DEFAULT)
    if ev is None or ev.empty:
        return out
    ev = ev.copy()
    ev["fare_evasion"] = pd.to_numeric(ev["fare_evasion"], errors="coerce")
    latest = sorted(ev["time_period"].dropna().unique())[-quarters:]
    m = ev[ev["time_period"].isin(latest)].groupby("trip_type")["fare_evasion"].mean()
    if "Local" in m:
        out.update({"Local": m["Local"], "Limited": m["Local"], "Other": m.get("Total", m["Local"])})
    if "SBS" in m:
        out["Select Bus Service"] = m["SBS"]
    if "Express" in m:
        out["Express"] = m["Express"]
    return {k: round(float(v), 4) for k, v in out.items()}


def _route_type(row) -> str:
    """Classify a route as Local / Limited / Select Bus Service / Express from its id and descriptions."""
    rid, desc, rt = row["route_id"], str(row.get("route_type") or ""), str(row.get("seg_route_type") or "")
    txt = f"{desc} {rt}".lower()
    if rid.endswith("+") or "select" in txt or "sbs" in txt:
        return "Select Bus Service"
    if "express" in txt or rid.startswith(("BXM", "BM", "QM", "SIM", "X")):
        return "Express"
    if "limited" in txt:
        return "Limited"
    return "Local"


def clean_routes(routes: pd.DataFrame, stops: pd.DataFrame, route_speed: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Route catalogue (one row per route), route paths for maps, and stop table."""
    r = routes.copy()
    r["route_id"] = r["route_id"].map(normalize_route_id)
    r = r.dropna(subset=["route_id"])
    r["shape_length"] = pd.to_numeric(r["shape_length"], errors="coerce")
    paths = (r.sort_values("shape_length", ascending=False)
               .drop_duplicates(["route_id", "direction_id"])[["route_id", "direction_id", "path"]])
    cat = (r.sort_values("shape_length", ascending=False).drop_duplicates("route_id")
             [["route_id", "route_short_name", "route_long_name", "route_description", "route_type", "route_color"]])
    cat = cat.merge(route_speed[["route_id", "seg_route_type"]], how="left")
    cat["route_type"] = cat.apply(_route_type, axis=1)
    cat["borough"] = cat["route_id"].map(borough_of)
    cat["route_color"] = "#" + cat["route_color"].fillna("666666").astype(str).str.lstrip("#")
    cat = cat.drop(columns=["seg_route_type"])

    s = stops.copy()
    s["route_id"] = s["route_id"].map(normalize_route_id)
    s["latitude"] = pd.to_numeric(s["latitude"], errors="coerce")
    s["longitude"] = pd.to_numeric(s["longitude"], errors="coerce")
    s = s.dropna(subset=["route_id", "latitude", "longitude"]).drop_duplicates(["route_id", "stop_id"])
    s["stop_id"] = s["stop_id"].astype(str)
    return cat, paths, s

# ====================================================================================================
# SECTION 4. FEATURE ENGINEERING - route x hour table and route profiles
# ====================================================================================================
# Module 2b - Feature Engineering.
#
# Builds the hourly *route-hour* analytical table and the *route profile* table.
#
# Granularity: one row per route per clock hour (America/New_York local time).
# Daily figures are derived by summing hours.

log = logging.getLogger(__name__)
US_HOLIDAYS = holidays.US(subdiv="NY", years=range(2019, 2031))
DOW_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def day_type_of(d) -> str:
    """MTA day type: holidays run on a Sunday schedule."""
    d = pd.Timestamp(d)
    if d.date() in US_HOLIDAYS or d.dayofweek == 6:
        return "Sunday"
    return "Saturday" if d.dayofweek == 5 else "Weekday"


def add_time_features(df: pd.DataFrame, ts_col: str = "ts") -> pd.DataFrame:
    """Calendar features: hour, day-of-week, weekend/holiday flags, peak period,
    cyclical (sin/cos) encodings, month, week of year and day type."""
    ts = df[ts_col]
    df["date"] = ts.dt.normalize()
    df["hour"] = ts.dt.hour.astype("int8")
    df["dow"] = ts.dt.dayofweek.astype("int8")
    df["month"] = ts.dt.month.astype("int8")
    df["weekofyear"] = ts.dt.isocalendar().week.astype("int16").values
    df["is_weekend"] = (df["dow"] >= 5).astype("int8")
    dates = pd.Series(df["date"].unique())
    hol = {d: int(d.date() in US_HOLIDAYS) for d in dates}
    df["is_holiday"] = df["date"].map(hol).astype("int8")
    dt = {d: day_type_of(d) for d in dates}
    df["day_type"] = df["date"].map(dt)
    df["is_am_peak"] = df["hour"].isin(C.AM_PEAK).astype("int8")
    df["is_pm_peak"] = df["hour"].isin(C.PM_PEAK).astype("int8")
    df["is_peak"] = ((df["is_am_peak"] + df["is_pm_peak"]) * (1 - df["is_weekend"]) * (1 - df["is_holiday"])).astype("int8")
    df["is_night"] = df["hour"].isin([0, 1, 2, 3, 4, 5]).astype("int8")
    df["is_summer"] = df["month"].isin([7, 8]).astype("int8")
    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24).astype("float32")
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24).astype("float32")
    df["dow_sin"] = np.sin(2 * np.pi * df["dow"] / 7).astype("float32")
    df["dow_cos"] = np.cos(2 * np.pi * df["dow"] / 7).astype("float32")
    return df


def attach_service_features(df: pd.DataFrame, trips: pd.DataFrame, speeds_hourly: pd.DataFrame,
                            route_info: pd.DataFrame) -> pd.DataFrame:
    """Join scheduled trips, hourly speed, route length/type/capacity and reliability,
    filling speed gaps hierarchically (route-hour-dow -> route -> type-hour -> global)."""
    df = df.merge(trips, on=["route_id", "day_type", "hour"], how="left")
    df["trips"] = df["trips"].fillna(0).astype("float32")
    df = df.merge(speeds_hourly, on=["route_id", "dow", "hour"], how="left")
    df = df.merge(route_info, on="route_id", how="left")
    df["route_type"] = df["route_type"].fillna("Local")
    df["borough"] = df["borough"].fillna("Other")
    # speed fallbacks
    df["speed_mph"] = df["speed_mph"].fillna(df["route_speed_mph"])
    type_hour = df.groupby(["route_type", "hour"])["speed_mph"].transform("median")
    df["speed_mph"] = df["speed_mph"].fillna(type_hour).fillna(df["speed_mph"].median()).astype("float32")
    for c, default in (("length_mi", df["length_mi"].median()), ("n_stops", df["n_stops"].median()),
                       ("reliability", df["reliability"].median()),
                       ("reliability_peak", df["reliability"].median())):
        df[c] = df[c].fillna(default).astype("float32")
    df["reliability_peak"] = df["reliability_peak"].fillna(df["reliability"])
    df["capacity"] = df["route_type"].map(C.VEHICLE_CAPACITY).fillna(65).astype("float32")
    if "evasion_factor" not in df:
        df["evasion_factor"] = 1.0
    df["evasion_factor"] = df["evasion_factor"].fillna(1.0).astype("float32")
    df["stop_density"] = (df["n_stops"] / df["length_mi"].clip(lower=0.5)).astype("float32")
    df["trip_minutes"] = (60 * df["length_mi"] / df["speed_mph"].clip(lower=2)).astype("float32")
    return df


def add_performance_metrics(df: pd.DataFrame, ridership_col: str = "ridership") -> pd.DataFrame:
    """Operational KPIs derived from ridership + service:

    * est_riders     - paid boardings x fare-evasion factor (estimated total riders)
    * load_per_trip  - estimated riders per scheduled trip
    * occupancy      - estimated max-load / vehicle capacity
    * productivity   - boardings per revenue vehicle-hour
    * headway_min    - minutes between buses, avg_wait_min = headway / 2
    * transfer_rate  - transfers / boardings
    * perf_class     - Underutilized / Balanced / Overcrowded (NaN when no service)
    """
    paid = df[ridership_col].astype("float32")
    # paid boardings -> estimated total riders (fare-evasion correction)
    r = paid * (df["evasion_factor"] if "evasion_factor" in df else 1.0)
    df["est_riders"] = r.astype("float32")
    service = df["trips"] > 0
    trips_eff = df["trips"].where(service, np.nan)
    df["load_per_trip"] = (r / trips_eff).astype("float32")
    df["occupancy"] = (df["load_per_trip"] * C.PEAK_LOAD_FACTOR / df["capacity"]).astype("float32")
    rev_hours = trips_eff * df["trip_minutes"] / 60
    df["revenue_hours"] = rev_hours.fillna(0).astype("float32")
    df["productivity"] = (r / rev_hours).astype("float32")
    # trips are counted over both directions -> headway in one direction
    df["headway_min"] = (60 * C.DIRECTIONS / trips_eff).clip(upper=120).astype("float32")
    df["avg_wait_min"] = (df["headway_min"] / 2).astype("float32")
    if "transfers" in df:
        df["transfer_rate"] = (df["transfers"] / paid.replace(0, np.nan)).fillna(0).clip(0, 1).astype("float32")
    df["perf_class"] = classify_occupancy(df["occupancy"])
    return df


def classify_occupancy(occ: pd.Series) -> pd.Series:
    """Map occupancy ratio to the three performance classes used by the classifiers."""
    lab = pd.Series(pd.NA, index=occ.index, dtype="object")
    lab[occ < C.UNDERUTILIZED_MAX] = "Underutilized"
    lab[(occ >= C.UNDERUTILIZED_MAX) & (occ <= C.OVERCROWDED_MIN)] = "Balanced"
    lab[occ > C.OVERCROWDED_MIN] = "Overcrowded"
    return lab


def build_route_hour_table(ridership: pd.DataFrame, trips: pd.DataFrame, speeds_hourly: pd.DataFrame,
                           route_info: pd.DataFrame) -> pd.DataFrame:
    """Full feature table: cleaned hourly ridership + time + service + KPI features."""
    df = ridership.copy()
    df = add_time_features(df)
    df = attach_service_features(df, trips, speeds_hourly, route_info)
    df = add_performance_metrics(df)
    df["log_ridership"] = np.log1p(df["ridership"]).astype("float32")
    log.info("route-hour table: %s rows x %s cols", *df.shape)
    return df


def build_route_profiles(rh: pd.DataFrame) -> pd.DataFrame:
    """Aggregate the hourly table into one behavioural profile per route.

    Used for clustering, ranking and the network overview.
    """
    days = rh.groupby("route_id")["date"].nunique()
    wk = rh[rh["day_type"] == "Weekday"]
    we = rh[rh["day_type"] != "Weekday"]
    g = rh.groupby("route_id")
    prof = pd.DataFrame({
        "avg_daily_ridership": g["ridership"].sum() / days,
        "avg_weekday_ridership": wk.groupby("route_id")["ridership"].sum() / wk.groupby("route_id")["date"].nunique(),
        "avg_weekend_ridership": we.groupby("route_id")["ridership"].sum() / we.groupby("route_id")["date"].nunique(),
        "am_peak_share": rh[rh["is_am_peak"] == 1].groupby("route_id")["ridership"].sum() / g["ridership"].sum(),
        "pm_peak_share": rh[rh["is_pm_peak"] == 1].groupby("route_id")["ridership"].sum() / g["ridership"].sum(),
        "night_share": rh[rh["is_night"] == 1].groupby("route_id")["ridership"].sum() / g["ridership"].sum(),
        "daily_trips": wk.groupby(["route_id", "date"])["trips"].sum().groupby("route_id").mean(),
        "mean_load_per_trip": g["load_per_trip"].mean(),
        "mean_occupancy": g["occupancy"].mean(),
        "p90_occupancy": g["occupancy"].quantile(0.9),
        "pct_hours_overcrowded": g["perf_class"].apply(lambda s: (s == "Overcrowded").mean()),
        "pct_hours_underutilized": g["perf_class"].apply(lambda s: (s == "Underutilized").mean()),
        "productivity": g["est_riders"].sum() / g["revenue_hours"].sum().replace(0, np.nan),
        "mean_speed_mph": g["speed_mph"].mean(),
        "transfer_rate": g["transfer_rate"].mean(),
        "cv_hourly": g["ridership"].std() / g["ridership"].mean().replace(0, np.nan),
    })
    stat = g[["length_mi", "n_stops", "reliability", "reliability_peak", "capacity", "stop_density"]].first()
    meta = g[["route_type", "borough"]].first()
    prof = prof.join(stat).join(meta)
    prof["weekend_ratio"] = prof["avg_weekend_ridership"] / prof["avg_weekday_ridership"]
    prof["riders_per_mile"] = prof["avg_daily_ridership"] / prof["length_mi"].clip(lower=0.5)
    # trend: last 4 weeks vs previous 4 weeks
    end = rh["date"].max()
    last = rh[rh["date"] > end - pd.Timedelta(days=28)].groupby("route_id")["ridership"].sum()
    prev = rh[(rh["date"] <= end - pd.Timedelta(days=28)) & (rh["date"] > end - pd.Timedelta(days=56))] \
        .groupby("route_id")["ridership"].sum()
    prof["trend_4w_pct"] = (100 * (last / prev.replace(0, np.nan) - 1)).clip(-100, 300)
    num = prof.select_dtypes("number").columns
    prof[num] = prof[num].replace([np.inf, -np.inf], np.nan)
    prof[num] = prof[num].fillna(prof[num].median())
    return prof.reset_index()


def hourly_profile_matrix(rh: pd.DataFrame, day_type: str = "Weekday") -> pd.DataFrame:
    """Route x hour matrix of mean ridership (used for heatmaps and shape clustering)."""
    sub = rh[rh["day_type"] == day_type]
    return sub.pivot_table(index="route_id", columns="hour", values="ridership", aggfunc="mean").fillna(0)

# ====================================================================================================
# SECTION 5. DATA PREPROCESSING - split, encoding, scaling
# ====================================================================================================
# Module 4 - Data Preprocessing.
#
# * chronological train / validation split (no look-ahead leakage)
# * categorical encoding: route-id label + target (historical-profile) encoding,
#   one-hot encoding of route type and borough
# * scaling (StandardScaler / RobustScaler) for distance-based models
# * model-ready matrices for the clustering, classification and forecasting models

CALENDAR_FEATURES = ["hour", "dow", "month", "is_weekend", "is_holiday", "is_peak", "is_am_peak",
                     "is_pm_peak", "is_night", "is_summer", "hour_sin", "hour_cos", "dow_sin", "dow_cos"]
SERVICE_FEATURES = ["trips", "speed_mph", "length_mi", "n_stops", "stop_density", "reliability",
                    "capacity", "trip_minutes"]
ENCODED_FEATURES = ["te_route_dow_hour", "te_route_daytype_hour", "te_route_hour", "te_route",
                    "te_occ_route_hour", "route_code"]
ROUTE_TYPES = ["Local", "Limited", "Select Bus Service", "Express"]
BOROUGHS = ["Bronx", "Brooklyn", "Manhattan", "Queens", "Staten Island", "Express",
            "Bronx (Express)", "Brooklyn (Express)", "Queens (Express)", "Staten Island (Express)"]
ONEHOT_FEATURES = [f"rt_{t}" for t in ROUTE_TYPES] + [f"boro_{b}" for b in BOROUGHS]
MODEL_FEATURES = CALENDAR_FEATURES + SERVICE_FEATURES + ENCODED_FEATURES + ONEHOT_FEATURES

CLUSTER_FEATURES = ["avg_daily_ridership", "am_peak_share", "pm_peak_share", "night_share", "weekend_ratio",
                    "mean_occupancy", "p90_occupancy", "productivity", "mean_speed_mph", "length_mi",
                    "stop_density", "reliability", "daily_trips", "riders_per_mile", "cv_hourly"]


def time_split(df: pd.DataFrame, valid_days: int = C.VALIDATION_DAYS, date_col: str = "date"):
    """Chronological split: the last ``valid_days`` days form the validation set."""
    cutoff = df[date_col].max() - pd.Timedelta(days=valid_days - 1)
    return df[df[date_col] < cutoff].copy(), df[df[date_col] >= cutoff].copy(), cutoff


@dataclass
class ProfileEncoder:
    """Target (mean) encoder learned on the TRAINING period only.

    Encodes the route id through its historical ridership profile so that the
    forecaster can predict any future date without lag features.
    """
    tables: dict = field(default_factory=dict)
    route_le: LabelEncoder = field(default_factory=LabelEncoder)
    global_mean: float = 0.0
    global_occ: float = 0.0

    def fit(self, train: pd.DataFrame) -> "ProfileEncoder":
        """Learn the profile (mean) encodings from the training period."""
        t = train
        self.global_mean = float(t["log_ridership"].mean())
        self.global_occ = float(t["occupancy"].mean())
        self.tables = {
            "te_route_dow_hour": t[t["is_holiday"] == 0].groupby(["route_id", "dow", "hour"])["log_ridership"].mean(),
            "te_route_daytype_hour": t.groupby(["route_id", "day_type", "hour"])["log_ridership"].mean(),
            "te_route_hour": t.groupby(["route_id", "hour"])["log_ridership"].mean(),
            "te_route": t.groupby("route_id")["log_ridership"].mean(),
            "te_occ_route_hour": t.groupby(["route_id", "day_type", "hour"])["occupancy"].mean(),
        }
        self.route_le.fit(sorted(t["route_id"].unique()))
        return self

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Attach the learned encodings to any frame, with hierarchical fallbacks for unseen keys."""
        df = df.copy()
        keys = {"te_route_dow_hour": ["route_id", "dow", "hour"],
                "te_route_daytype_hour": ["route_id", "day_type", "hour"],
                "te_route_hour": ["route_id", "hour"], "te_route": ["route_id"],
                "te_occ_route_hour": ["route_id", "day_type", "hour"]}
        for name, k in keys.items():
            df = df.drop(columns=[name], errors="ignore").merge(
                self.tables[name].rename(name).reset_index(), on=k, how="left")
        # hierarchical fallback for unseen combinations
        df["te_route_hour"] = df["te_route_hour"].fillna(df["te_route"]).fillna(self.global_mean)
        df["te_route_daytype_hour"] = df["te_route_daytype_hour"].fillna(df["te_route_hour"])
        df["te_route_dow_hour"] = df["te_route_dow_hour"].fillna(df["te_route_daytype_hour"])
        df["te_route"] = df["te_route"].fillna(self.global_mean)
        df["te_occ_route_hour"] = df["te_occ_route_hour"].fillna(self.global_occ)
        known = set(self.route_le.classes_)
        df["route_code"] = [self.route_le.transform([r])[0] if r in known else -1 for r in df["route_id"]] \
            if len(df) < 5000 else _fast_codes(df["route_id"], self.route_le)
        return df


def _fast_codes(s: pd.Series, le: LabelEncoder) -> np.ndarray:
    """Vectorised label-encoding of route ids (unknown -> -1)."""
    mapping = {c: i for i, c in enumerate(le.classes_)}
    return s.map(mapping).fillna(-1).astype(int).to_numpy()


def one_hot(df: pd.DataFrame) -> pd.DataFrame:
    """Fixed-vocabulary one-hot encoding of route type and borough."""
    for t in ROUTE_TYPES:
        df[f"rt_{t}"] = (df["route_type"] == t).astype("int8")
    for b in BOROUGHS:
        df[f"boro_{b}"] = (df["borough"] == b).astype("int8")
    return df


def model_matrix(df: pd.DataFrame, encoder: ProfileEncoder) -> pd.DataFrame:
    """Encode + one-hot; return (encoded frame, numeric feature matrix with fixed column order)."""
    enc = one_hot(encoder.transform(df))
    return enc, enc[MODEL_FEATURES].astype("float32")


def scale_for_clustering(profiles: pd.DataFrame, robust: bool = False):
    """Log-transform skewed volume features, then standardise (z-score)."""
    X = profiles[CLUSTER_FEATURES].copy()
    for c in ("avg_daily_ridership", "productivity", "riders_per_mile", "daily_trips"):
        X[c] = np.log1p(X[c].clip(lower=0))
    scaler = RobustScaler() if robust else StandardScaler()
    Xs = scaler.fit_transform(X.fillna(X.median()))
    return Xs, scaler

# ====================================================================================================
# SECTION 6. MODEL - CLUSTERING (KMeans + DBSCAN) and route overlap
# ====================================================================================================
# Module 5a - Unsupervised route segmentation (KMeans + DBSCAN) and overlap detection.

def select_k(Xs: np.ndarray, k_range=range(2, 11)) -> pd.DataFrame:
    """Evaluate KMeans for several k with inertia (elbow), silhouette, Davies-Bouldin
    and Calinski-Harabasz scores."""
    rows = []
    for k in k_range:
        km = KMeans(n_clusters=k, n_init=20, random_state=C.RANDOM_STATE).fit(Xs)
        rows.append({"k": k, "inertia": km.inertia_,
                     "silhouette": silhouette_score(Xs, km.labels_),
                     "davies_bouldin": davies_bouldin_score(Xs, km.labels_),
                     "calinski_harabasz": calinski_harabasz_score(Xs, km.labels_)})
    return pd.DataFrame(rows)


def choose_k(scores: pd.DataFrame, k_min: int = 4) -> int:
    """Best silhouette among k >= k_min (fewer than 4 segments is not actionable for planners)."""
    s = scores[scores["k"] >= k_min]
    return int(s.loc[s["silhouette"].idxmax(), "k"])


def dbscan_eps(Xs: np.ndarray, min_samples: int) -> float:
    """Pick eps from the k-distance curve (point of maximum curvature / 90th pct fallback)."""
    nn = NearestNeighbors(n_neighbors=min_samples).fit(Xs)
    d = np.sort(nn.kneighbors(Xs)[0][:, -1])
    # knee: max distance from the chord joining first and last points
    x = np.arange(len(d)); x1, y1, x2, y2 = 0, d[0], len(d) - 1, d[-1]
    dist = np.abs((y2 - y1) * x - (x2 - x1) * d + x2 * y1 - y2 * x1) / np.hypot(y2 - y1, x2 - x1)
    eps = float(d[int(dist.argmax())])
    return eps if eps > 0 else float(np.quantile(d, 0.9))


DESCRIPTORS = {  # feature: (word if above network median, word if below)
    "avg_daily_ridership": ("High-Volume", "Low-Volume"),
    "mean_occupancy": ("Crowded", "Spare-Capacity"),
    "productivity": ("High-Productivity", "Low-Productivity"),
    "am_peak_share": ("AM-Peak Commuter", "Off-Peak"),
    "weekend_ratio": ("All-Week", "Weekday-Focused"),
    "night_share": ("Night-Owl", "Daytime"),
    "mean_speed_mph": ("Fast", "Slow"),
    "length_mi": ("Long-Haul", "Short"),
    "reliability": ("Reliable", "Unreliable"),
}


def name_clusters(profiles: pd.DataFrame, label_col: str = "kmeans_cluster") -> dict[int, str]:
    """Human-readable cluster names: dominant route type (if >= 60 %) + the two
    features whose cluster median deviates most (in robust z-score) from the network."""
    feats = list(DESCRIPTORS)
    med = profiles[feats].median()
    iqr = (profiles[feats].quantile(0.75) - profiles[feats].quantile(0.25)).replace(0, 1)
    names, used = {}, {}
    for cid, grp in profiles.groupby(label_col):
        z = ((grp[feats].median() - med) / iqr).sort_values(key=np.abs, ascending=False)
        words = [DESCRIPTORS[f][0 if z[f] > 0 else 1] for f in z.index[:2]]
        rt = grp["route_type"].value_counts(normalize=True) if "route_type" in grp else pd.Series(dtype=float)
        prefix = (rt.index[0] if len(rt) and rt.iloc[0] >= 0.6 and rt.index[0] != "Local" else "")
        prefix = {"Select Bus Service": "SBS"}.get(prefix, prefix)
        n = " ".join(x for x in [prefix, " / ".join(words)] if x)
        used[n] = used.get(n, 0) + 1
        names[int(cid)] = n if used[n] == 1 else f"{n} ({used[n]})"
    return names


def run_clustering(profiles: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Fit KMeans (k by silhouette) and DBSCAN (eps by k-distance knee) on scaled
    route profiles. Adds cluster labels, names, DBSCAN outlier flag and 2-D PCA coords."""
    Xs, scaler = scale_for_clustering(profiles)
    scores = select_k(Xs)
    k = choose_k(scores)
    km = KMeans(n_clusters=k, n_init=50, random_state=C.RANDOM_STATE).fit(Xs)
    prof = profiles.copy()
    prof["kmeans_cluster"] = km.labels_

    min_samples = max(4, int(np.log(len(Xs))) + 1)
    eps = dbscan_eps(Xs, min_samples)
    db = DBSCAN(eps=eps, min_samples=min_samples).fit(Xs)
    prof["dbscan_cluster"] = db.labels_
    prof["dbscan_outlier"] = (db.labels_ == -1).astype(int)

    pca = PCA(n_components=2, random_state=C.RANDOM_STATE).fit(Xs)
    pcs = pca.transform(Xs)
    prof["pc1"], prof["pc2"] = pcs[:, 0], pcs[:, 1]
    names = name_clusters(prof)
    prof["cluster_name"] = prof["kmeans_cluster"].map(names)

    n_db = len(set(db.labels_)) - (1 if -1 in db.labels_ else 0)
    metrics = {
        "k_selection": scores.round(4).to_dict(orient="records"),
        "kmeans": {"k": k, "silhouette": float(silhouette_score(Xs, km.labels_)),
                   "davies_bouldin": float(davies_bouldin_score(Xs, km.labels_)),
                   "calinski_harabasz": float(calinski_harabasz_score(Xs, km.labels_)),
                   "cluster_sizes": prof["kmeans_cluster"].value_counts().sort_index().to_dict(),
                   "cluster_names": names},
        "dbscan": {"eps": eps, "min_samples": min_samples, "n_clusters": n_db,
                   "n_outliers": int((db.labels_ == -1).sum()),
                   "silhouette_non_noise": float(silhouette_score(Xs[db.labels_ != -1], db.labels_[db.labels_ != -1]))
                   if n_db >= 2 else None},
        "pca_explained_variance": pca.explained_variance_ratio_.round(4).tolist(),
    }
    return prof, {"metrics": metrics, "kmeans": km, "dbscan": db, "scaler": scaler, "pca": pca}


def stop_overlap(stops: pd.DataFrame, routes: list[str], min_jaccard: float = 0.2) -> pd.DataFrame:
    """Pairwise stop-set Jaccard similarity between routes (overlap detection).

    Stops are matched by stop_id and by ~50 m rounded coordinates so that
    opposite-side stops of the same street corner count as shared.
    """
    s = stops[stops["route_id"].isin(routes)].copy()
    s["cell"] = (s["latitude"].round(3).astype(str) + "," + s["longitude"].round(3).astype(str))
    sets = s.groupby("route_id")["cell"].apply(set).to_dict()
    # inverted index to avoid O(n^2) over all pairs
    inv: dict[str, set] = {}
    for r, cells in sets.items():
        for c in cells:
            inv.setdefault(c, set()).add(r)
    pairs: dict[tuple, int] = {}
    for rs in inv.values():
        for a, b in itertools.combinations(sorted(rs), 2):
            pairs[(a, b)] = pairs.get((a, b), 0) + 1
    rows = []
    for (a, b), inter in pairs.items():
        union = len(sets[a]) + len(sets[b]) - inter
        j = inter / union if union else 0
        if j >= min_jaccard:
            rows.append({"route_a": a, "route_b": b, "shared_stops": inter, "jaccard": round(j, 3),
                         "share_of_a": round(inter / len(sets[a]), 3), "share_of_b": round(inter / len(sets[b]), 3)})
    return pd.DataFrame(rows).sort_values("jaccard", ascending=False) if rows else \
        pd.DataFrame(columns=["route_a", "route_b", "shared_stops", "jaccard", "share_of_a", "share_of_b"])

# ====================================================================================================
# SECTION 7. MODEL - CLASSIFICATION and FORECASTING (Random Forest, XGBoost)
# ====================================================================================================
# Module 5b - Supervised models.
#
# * Classification (Random Forest vs XGBoost): route-hour performance class
#   - Underutilized / Balanced / Overcrowded.
# * Regression / forecasting (XGBoost vs Random Forest vs seasonal-profile
#   baseline): hourly boardings per route, used for date-specific prediction.
#
# Both use a chronological split: train = everything before the last
# ``VALIDATION_DAYS`` days, validation = the last ``VALIDATION_DAYS`` days.

log = logging.getLogger(__name__)
CLASS_TO_INT = {c: i for i, c in enumerate(C.CLASS_LABELS)}


def _sample(X: pd.DataFrame, y, n: int, seed: int = C.RANDOM_STATE):
    """Random row sample (without replacement) to bound training time."""
    if len(X) <= n:
        return X, y
    idx = np.random.default_rng(seed).choice(len(X), n, replace=False)
    return X.iloc[idx], (y.iloc[idx] if hasattr(y, "iloc") else y[idx])


# --------------------------------------------------------------------------- #
# Classification
# --------------------------------------------------------------------------- #
def classification_metrics(y_true, y_pred) -> dict:
    """Accuracy, balanced accuracy, macro/weighted F1, per-class report and confusion matrix."""
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "f1_macro": float(f1_score(y_true, y_pred, average="macro")),
        "f1_weighted": float(f1_score(y_true, y_pred, average="weighted")),
        "report": classification_report(y_true, y_pred, labels=[0, 1, 2], target_names=C.CLASS_LABELS,
                                        output_dict=True, zero_division=0),
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=[0, 1, 2]).tolist(),
    }


def train_classifiers(Xtr: pd.DataFrame, ytr: pd.Series, Xva: pd.DataFrame, yva: pd.Series,
                      rf_rows: int = 400_000, xgb_rows: int = 1_500_000) -> dict:
    """Train RandomForestClassifier and XGBClassifier with class balancing,
    evaluate on the chronological validation set, return models + metrics."""
    ytr_i, yva_i = ytr.map(CLASS_TO_INT).astype(int), yva.map(CLASS_TO_INT).astype(int)
    out = {}

    Xs, ys = _sample(Xtr, ytr_i, rf_rows)
    t0 = time.time()
    rf = RandomForestClassifier(n_estimators=200, max_depth=20, min_samples_leaf=5, max_features="sqrt",
                                class_weight="balanced_subsample", n_jobs=-1, random_state=C.RANDOM_STATE)
    rf.fit(Xs, ys)
    pred = rf.predict(Xva)
    out["RandomForest"] = {"model": rf, "train_seconds": round(time.time() - t0, 1),
                           "train_rows": int(len(Xs)), **classification_metrics(yva_i, pred)}
    log.info("RF classifier macro-F1 %.3f", out["RandomForest"]["f1_macro"])

    Xs, ys = _sample(Xtr, ytr_i, xgb_rows)
    t0 = time.time()
    xgb = XGBClassifier(n_estimators=600, max_depth=8, learning_rate=0.08, subsample=0.8,
                        colsample_bytree=0.8, min_child_weight=5, reg_lambda=1.0, tree_method="hist",
                        objective="multi:softprob", eval_metric="mlogloss", n_jobs=-1,
                        random_state=C.RANDOM_STATE, early_stopping_rounds=40)
    xgb.fit(Xs, ys, sample_weight=compute_sample_weight("balanced", ys),
            eval_set=[(Xva, yva_i)], verbose=False)
    pred = xgb.predict(Xva)
    out["XGBoost"] = {"model": xgb, "train_seconds": round(time.time() - t0, 1),
                      "train_rows": int(len(Xs)), "best_iteration": int(xgb.best_iteration),
                      **classification_metrics(yva_i, pred)}
    log.info("XGB classifier macro-F1 %.3f", out["XGBoost"]["f1_macro"])

    best = max(("RandomForest", "XGBoost"), key=lambda k: out[k]["f1_macro"])
    out["best"] = best
    out["feature_importance"] = {
        k: pd.Series(out[k]["model"].feature_importances_, index=MODEL_FEATURES)
              .sort_values(ascending=False).round(5).to_dict()
        for k in ("RandomForest", "XGBoost")}
    return out


# --------------------------------------------------------------------------- #
# Forecasting (regression on log1p ridership)
# --------------------------------------------------------------------------- #
def regression_metrics(y_true, y_pred) -> dict:
    """MAE, RMSE, R^2 and WAPE on the original (boardings) scale."""
    y_true, y_pred = np.asarray(y_true, float), np.asarray(y_pred, float)
    return {"mae": float(mean_absolute_error(y_true, y_pred)),
            "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
            "r2": float(r2_score(y_true, y_pred)),
            "wape": float(np.abs(y_true - y_pred).sum() / max(y_true.sum(), 1))}


def train_forecasters(Xtr: pd.DataFrame, ytr_log: pd.Series, Xva: pd.DataFrame, yva: pd.Series,
                      rf_rows: int = 500_000) -> dict:
    """Train XGBRegressor and RandomForestRegressor on log1p(boardings); compare to the
    seasonal-profile baseline exp(te_route_dow_hour) - 1."""
    out = {}
    base = np.expm1(Xva["te_route_dow_hour"].to_numpy())
    out["SeasonalProfileBaseline"] = regression_metrics(yva, base)

    t0 = time.time()
    xgb = XGBRegressor(n_estimators=1500, max_depth=9, learning_rate=0.05, subsample=0.8,
                       colsample_bytree=0.8, min_child_weight=10, reg_lambda=2.0, tree_method="hist",
                       n_jobs=-1, random_state=C.RANDOM_STATE, early_stopping_rounds=60)
    xgb.fit(Xtr, ytr_log, eval_set=[(Xva, np.log1p(yva))], verbose=False)
    p = np.clip(np.expm1(xgb.predict(Xva)), 0, None)
    out["XGBoost"] = {"model": xgb, "train_seconds": round(time.time() - t0, 1),
                      "best_iteration": int(xgb.best_iteration), **regression_metrics(yva, p)}
    log.info("XGB regressor MAE %.2f", out["XGBoost"]["mae"])

    Xs, ys = _sample(Xtr, ytr_log, rf_rows)
    t0 = time.time()
    rf = RandomForestRegressor(n_estimators=150, max_depth=22, min_samples_leaf=3, max_features=0.5,
                               n_jobs=-1, random_state=C.RANDOM_STATE)
    rf.fit(Xs, ys)
    p_rf = np.clip(np.expm1(rf.predict(Xva)), 0, None)
    out["RandomForest"] = {"model": rf, "train_seconds": round(time.time() - t0, 1),
                           "train_rows": int(len(Xs)), **regression_metrics(yva, p_rf)}
    log.info("RF regressor MAE %.2f", out["RandomForest"]["mae"])

    best = min(("RandomForest", "XGBoost"), key=lambda k: out[k]["mae"])
    out["best"] = best
    out["feature_importance"] = {
        k: pd.Series(out[k]["model"].feature_importances_, index=MODEL_FEATURES)
              .sort_values(ascending=False).round(5).to_dict()
        for k in ("RandomForest", "XGBoost")}
    out["validation_predictions"] = p if best == "XGBoost" else p_rf
    return out

# ====================================================================================================
# SECTION 8. OPTIMISATION - recommendations and scenario simulator
# ====================================================================================================
# Module 6b - Route optimisation suggestions and scenario simulation.
#
# Rules operate on a route-hour frame that contains (predicted or actual)
# ridership, scheduled trips and the KPI columns from
# :func:`feature_engineering.add_performance_metrics`.

def required_trips(ridership: pd.Series, capacity: pd.Series, target: float | None = None) -> pd.Series:
    """Trips/hour needed so that estimated max-load equals ``target`` x capacity
    (``target`` defaults to the calibrated ``config.TARGET_OCCUPANCY`` at call time)."""
    target = target or C.TARGET_OCCUPANCY
    return np.ceil(ridership * C.PEAK_LOAD_FACTOR / (capacity * target))


def optimize_frequencies(frame: pd.DataFrame, ridership_col: str = "ridership") -> pd.DataFrame:
    """Re-size the timetable hour by hour.

    * Overcrowded hours -> add trips up to the target occupancy.
    * Underutilised hours -> remove trips but never below the policy floor
      (``MIN_TRIPS_PER_HOUR``) while the route is in service.
    Returns the frame with ``trips_opt``, ``delta_trips`` and optimised KPIs (suffix ``_opt``).
    """
    f = frame.copy()
    ev = f["evasion_factor"] if "evasion_factor" in f else 1.0
    need = required_trips(f[ridership_col] * ev, f["capacity"])
    in_service = f["trips"] > 0
    opt = f["trips"].copy()
    over = in_service & (f["occupancy"] > C.OVERCROWDED_MIN)
    under = in_service & (f["occupancy"] < C.UNDERUTILIZED_MAX) & (f["trips"] > C.MIN_TRIPS_PER_HOUR)
    opt[over] = np.maximum(f.loc[over, "trips"], need[over])
    opt[under] = np.maximum(need[under], C.MIN_TRIPS_PER_HOUR)
    opt[under] = np.minimum(opt[under], f.loc[under, "trips"])
    f["trips_opt"] = opt
    f["delta_trips"] = f["trips_opt"] - f["trips"]
    keep = [c for c in ("capacity", "trip_minutes", "transfers", "evasion_factor") if c in f]
    tmp = f[keep].copy()
    tmp["trips"] = f["trips_opt"]
    tmp["ridership"] = f[ridership_col]
    tmp = add_performance_metrics(tmp)
    for c in ("occupancy", "load_per_trip", "productivity", "avg_wait_min", "revenue_hours", "perf_class"):
        f[f"{c}_opt"] = tmp[c].values
    return f


def route_recommendations(opt: pd.DataFrame, profiles: pd.DataFrame, overlap: pd.DataFrame) -> pd.DataFrame:
    """Summarise the hourly re-sizing per route and add structural suggestions
    (merge with an overlapping low-demand route, split / short-turn long unreliable routes)."""
    g = opt.groupby("route_id")
    rec = pd.DataFrame({
        "ridership": g["ridership"].sum(),
        "est_riders": g["est_riders"].sum() if "est_riders" in opt else g["ridership"].sum(),
        "trips_now": g["trips"].sum(),
        "trips_opt": g["trips_opt"].sum(),
        "trips_added": g["delta_trips"].apply(lambda s: s[s > 0].sum()),
        "trips_removed": g["delta_trips"].apply(lambda s: -s[s < 0].sum()),
        "veh_hours_now": g["revenue_hours"].sum(),
        "veh_hours_opt": g["revenue_hours_opt"].sum(),
        "overcrowded_hours_now": g["perf_class"].apply(lambda s: (s == "Overcrowded").sum()),
        "overcrowded_hours_opt": g["perf_class_opt"].apply(lambda s: (s == "Overcrowded").sum()),
        "underutilized_hours_now": g["perf_class"].apply(lambda s: (s == "Underutilized").sum()),
        "underutilized_hours_opt": g["perf_class_opt"].apply(lambda s: (s == "Underutilized").sum()),
        "peak_occupancy_now": g["occupancy"].max(),
        "peak_occupancy_opt": g["occupancy_opt"].max(),
        "overcrowded_window": g.apply(lambda d: _window(d, d["perf_class"] == "Overcrowded"), include_groups=False),
        "underutilized_window": g.apply(lambda d: _window(d, d["perf_class"] == "Underutilized"), include_groups=False),
    }).reset_index()
    rec["productivity_now"] = rec["est_riders"] / rec["veh_hours_now"].replace(0, np.nan)
    rec["productivity_opt"] = rec["est_riders"] / rec["veh_hours_opt"].replace(0, np.nan)
    p = profiles.set_index("route_id")
    rec = rec.join(p[["length_mi", "reliability", "route_type", "borough", "pct_hours_underutilized",
                      "cluster_name"]], on="route_id")

    len_p90 = profiles["length_mi"].quantile(0.9)
    rel_med = profiles["reliability"].median()
    low_routes = set(profiles.loc[profiles["pct_hours_underutilized"] > 0.5, "route_id"])
    merge_partner = {}
    for _, row in overlap.iterrows():
        a, b = row["route_a"], row["route_b"]
        if a in low_routes and b not in merge_partner and a not in merge_partner and row["share_of_a"] > 0.4:
            merge_partner[a] = (b, row["share_of_a"])
        elif b in low_routes and b not in merge_partner and row["share_of_b"] > 0.4:
            merge_partner[b] = (a, row["share_of_b"])

    actions, reasons = [], []
    for _, r in rec.iterrows():
        a, why = [], []
        if r["trips_added"] > 0 and r["trips_removed"] > 0:
            a.append("Rebalance frequency")
            why.append(f"add {int(r['trips_added'])} trips in {r['overcrowded_window']} and "
                       f"remove {int(r['trips_removed'])} in {r['underutilized_window']}")
        elif r["trips_added"] > 0:
            a.append("Increase frequency")
            why.append(f"overcrowded {r['overcrowded_window']} (peak occupancy {r['peak_occupancy_now']:.0%}); "
                       f"+{int(r['trips_added'])} trips")
        elif r["trips_removed"] > 0:
            a.append("Reduce frequency")
            why.append(f"underutilised {r['underutilized_window']}; -{int(r['trips_removed'])} trips "
                       f"(saves {r['veh_hours_now'] - r['veh_hours_opt']:.1f} veh-h)")
        if r["route_id"] in merge_partner:
            partner, share = merge_partner[r["route_id"]]
            a.append(f"Merge with {partner}")
            why.append(f"{share:.0%} of its stops are also served by {partner} and it is underutilised most hours")
        if r["length_mi"] >= len_p90 and r["reliability"] < rel_med and r["overcrowded_hours_now"] > 0:
            a.append("Split / short-turn")
            why.append(f"long route ({r['length_mi']:.1f} mi) with below-median reliability "
                       f"({r['reliability']:.0%}) and crowding")
        if not a:
            a.append("Maintain")
            why.append("load stays within the balanced band all day")
        actions.append(" + ".join(a))
        reasons.append("; ".join(why))
    rec["action"] = actions
    rec["rationale"] = reasons
    rec["priority"] = (rec["overcrowded_hours_now"] * 2 + rec["underutilized_hours_now"]
                       + rec["action"].str.contains("Merge|Split").astype(int) * 3)
    return rec.sort_values("priority", ascending=False)


def _window(d: pd.DataFrame, mask: pd.Series) -> str:
    """Compress a set of flagged hours into readable spans such as '07-10h, 16-19h'."""
    hrs = sorted(d.loc[mask, "hour"].astype(int).tolist())
    if not hrs:
        return "-"
    spans, start, prev = [], hrs[0], hrs[0]
    for h in hrs[1:] + [None]:
        if h is None or h != prev + 1:
            spans.append(f"{start:02d}-{prev + 1:02d}h")
            if h is not None:
                start = h
        if h is not None:
            prev = h
    return ", ".join(spans[:3]) + (" ..." if len(spans) > 3 else "")


def impact_summary(opt: pd.DataFrame) -> dict:
    """Network-level current vs optimised comparison (evaluation criterion: optimisation effectiveness)."""
    s = opt[opt["trips"] > 0]
    rcol = "est_riders" if "est_riders" in s else "ridership"

    def share(col, cls):
        """Share of service route-hours whose class column equals ``cls``."""
        return float((s[col] == cls).mean())
    return {
        "route_hours": int(len(s)),
        "overcrowded_share_now": share("perf_class", "Overcrowded"),
        "overcrowded_share_opt": share("perf_class_opt", "Overcrowded"),
        "underutilized_share_now": share("perf_class", "Underutilized"),
        "underutilized_share_opt": share("perf_class_opt", "Underutilized"),
        "balanced_share_now": share("perf_class", "Balanced"),
        "balanced_share_opt": share("perf_class_opt", "Balanced"),
        "trips_now": float(s["trips"].sum()), "trips_opt": float(s["trips_opt"].sum()),
        "veh_hours_now": float(s["revenue_hours"].sum()), "veh_hours_opt": float(s["revenue_hours_opt"].sum()),
        "productivity_now": float(s[rcol].sum() / s["revenue_hours"].sum()),
        "productivity_opt": float(s[rcol].sum() / s["revenue_hours_opt"].sum()),
        "mean_wait_now": float(s["avg_wait_min"].mean()), "mean_wait_opt": float(s["avg_wait_min_opt"].mean()),
    }


def simulate_scenario(frame: pd.DataFrame, demand_change_pct: float = 0.0, frequency_multiplier: float = 1.0,
                      speed_change_pct: float = 0.0, capacity_override: float | None = None,
                      routes: list[str] | None = None, hours: tuple[int, int] = (0, 23),
                      ridership_col: str = "ridership") -> pd.DataFrame:
    """What-if simulator. Applies demand growth, frequency scaling, speed change (e.g. bus lanes)
    and/or a bigger vehicle to the selected routes & hours and recomputes every KPI.

    Returns a frame with baseline columns and ``*_sim`` columns side by side.
    """
    f = frame.copy()
    sel = f["hour"].between(*hours)
    if routes:
        sel &= f["route_id"].isin(routes)
    sim = f[[c for c in ("route_id", "hour", "capacity", "trip_minutes", "trips", "evasion_factor") if c in f]].copy()
    sim["ridership"] = f[ridership_col]
    sim.loc[sel, "ridership"] *= 1 + demand_change_pct / 100
    sim.loc[sel & (sim["trips"] > 0), "trips"] = np.maximum(
        np.round(sim.loc[sel & (sim["trips"] > 0), "trips"] * frequency_multiplier), 1)
    sim.loc[sel, "trip_minutes"] /= 1 + speed_change_pct / 100
    if capacity_override:
        sim.loc[sel, "capacity"] = capacity_override
    sim = add_performance_metrics(sim)
    for c in ("ridership", "trips", "capacity", "trip_minutes", "occupancy", "load_per_trip", "productivity",
              "avg_wait_min", "revenue_hours", "perf_class"):
        f[f"{c}_sim"] = sim[c].values
    f["in_scenario"] = sel
    return f

# ====================================================================================================
# SECTION 9. INFERENCE - prediction, RouteRank score, explanation, validation
# ====================================================================================================
# Module 6a - Inference & route suggestion service.
#
# ``RouteRankerService`` is the single back-end object used by both the
# Streamlit frontend and the FastAPI REST API. It loads the processed tables
# and trained models once, and offers:
#
# * ``predict_day``      - hourly forecast for every route on any date
# * ``rank_routes``      - composite RouteRank score + ranking
# * ``explain``          - natural-language "why is this the best route"
# * ``validate``         - back-test of the recommendation on past same-weekdays
# * ``find_routes_between`` - direct routes linking two stops/areas
# * ``recommendations``  - optimisation actions for a date

STATIC_COLS = ["route_id", "length_mi", "n_stops", "reliability", "reliability_peak", "route_speed_mph",
               "route_type", "borough", "evasion_factor"]
COMPONENTS = ["productivity", "speed", "reliability", "frequency", "comfort"]
PRESETS = {
    "Balanced (default)": C.ScoreWeights(),
    "Rider - fast & comfortable": C.ScoreWeights(productivity=0.05, speed=0.30, reliability=0.25,
                                                frequency=0.20, comfort=0.20),
    "Planner - efficiency first": C.ScoreWeights(productivity=0.45, speed=0.10, reliability=0.15,
                                                frequency=0.10, comfort=0.20),
}


def now_ist() -> datetime:
    """Current date-time in IST (Asia/Kolkata)."""
    return datetime.now(C.IST)


def ist_to_transit(dt_ist: datetime) -> datetime:
    """Convert an IST datetime to the bus network's local time (America/New_York)."""
    if dt_ist.tzinfo is None:
        dt_ist = dt_ist.replace(tzinfo=C.IST)
    return dt_ist.astimezone(C.TRANSIT_TZ)


def transit_to_ist(dt_local) -> datetime:
    """Convert a bus-network local timestamp (America/New_York) to IST."""
    ts = pd.Timestamp(dt_local)
    if ts.tzinfo is None:
        ts = ts.tz_localize(C.TRANSIT_TZ, ambiguous="NaT", nonexistent="shift_forward")
    return ts.tz_convert(C.IST)


class RouteRankerService:
    """Loads artefacts produced by the training pipeline (section 12) and serves predictions."""

    def __init__(self):
        """Load processed tables, trained models, metrics and manifest from disk."""
        P = C.PROCESSED_DIR
        self.route_info = pd.read_parquet(P / "route_info.parquet")
        self.trips = pd.read_parquet(P / "trips.parquet")
        self.speeds = pd.read_parquet(P / "speeds_hourly.parquet")
        self.paths = pd.read_parquet(P / "paths.parquet")
        self.stops = pd.read_parquet(P / "stops.parquet")
        self.overlap = pd.read_parquet(P / "overlap.parquet")
        self.encoder = joblib.load(C.MODELS_DIR / "profile_encoder.joblib")
        self.forecaster = joblib.load(C.MODELS_DIR / "forecaster.joblib")
        self.classifier = joblib.load(C.MODELS_DIR / "classifier.joblib")
        self.metrics = json.loads((C.METRICS_DIR / "model_metrics.json").read_text())
        self.manifest = json.loads((C.METRICS_DIR / "pipeline_manifest.json").read_text())
        self.routes = sorted(self.route_info["route_id"])
        self._cache: dict = {}

    # ------------------------------------------------------------------ data
    @cached_property
    def history(self) -> pd.DataFrame:
        """Slim historical route-hour table (actuals) - loaded lazily."""
        return pd.read_parquet(C.PROCESSED_DIR / "route_hour.parquet")

    @property
    def data_start(self) -> pd.Timestamp:
        """First date of the historical ridership window."""
        return pd.Timestamp(self.manifest["data_start"])

    @property
    def data_end(self) -> pd.Timestamp:
        """Last date of the historical ridership window."""
        return pd.Timestamp(self.manifest["data_end"])

    def route_label(self, rid: str) -> str:
        """'ROUTE - Long name' label for drop-downs."""
        r = self.route_info.set_index("route_id")
        if rid in r.index and isinstance(r.at[rid, "route_long_name"], str):
            return f"{rid} - {r.at[rid, 'route_long_name']}"
        return rid

    # ------------------------------------------------------------ prediction
    def frame_for_date(self, d, routes: list[str] | None = None) -> pd.DataFrame:
        """Feature frame (route x 24 hours) for an arbitrary calendar date."""
        d = pd.Timestamp(d).normalize()
        rids = routes or self.routes
        f = pd.MultiIndex.from_product([rids, range(24)], names=["route_id", "hour"]).to_frame(index=False)
        f["ts"] = d + pd.to_timedelta(f["hour"], unit="h")
        f = add_time_features(f.drop(columns=["hour"]))
        static = self.route_info[STATIC_COLS]
        f = attach_service_features(f, self.trips, self.speeds, static)
        return f

    def predict_day(self, d, routes: list[str] | None = None) -> pd.DataFrame:
        """Hourly ridership forecast + KPIs + class probabilities for one date."""
        key = (str(pd.Timestamp(d).date()), tuple(routes) if routes else None)
        if key in self._cache:
            return self._cache[key].copy()
        f = self.frame_for_date(d, routes)
        enc, X = model_matrix(f, self.encoder)
        f = enc
        f["ridership"] = np.clip(np.expm1(self.forecaster.predict(X)), 0, None).astype("float32")
        f.loc[f["trips"] == 0, "ridership"] *= 0.15  # almost no boardings when no bus is scheduled
        f["transfers"] = 0.0
        f = add_performance_metrics(f)
        proba = self.classifier.predict_proba(X)
        for c, i in CLASS_TO_INT.items():
            f[f"p_{c.lower()}"] = proba[:, i]
        f["pred_class"] = np.array(C.CLASS_LABELS)[proba.argmax(1)]
        f.loc[f["trips"] == 0, "pred_class"] = "No service"
        # attach actuals when the date is inside the historical window
        d0 = pd.Timestamp(d).normalize()
        if self.data_start <= d0 <= self.data_end:
            h = self.history[self.history["date"] == d0][["route_id", "hour", "ridership", "occupancy", "perf_class"]]
            f = f.merge(h.rename(columns={"ridership": "ridership_actual", "occupancy": "occupancy_actual",
                                          "perf_class": "perf_class_actual"}), on=["route_id", "hour"], how="left")
        self._cache[key] = f
        return f.copy()

    # --------------------------------------------------------------- ranking
    @staticmethod
    def _aggregate(f: pd.DataFrame, hours: tuple[int, int], ridership_col: str = "ridership",
                   comfort_from: str = "proba") -> pd.DataFrame:
        """Aggregate route-hour predictions over an hour window into the five score components per route."""
        w = f[f["hour"].between(*hours) & (f["trips"] > 0)].copy()
        if w.empty:
            return pd.DataFrame()
        w["_rev"] = w["trips"] * w["trip_minutes"] / 60
        g = w.groupby("route_id")
        peak = w["is_peak"].mean() > 0.3
        agg = pd.DataFrame({
            "riders": g[ridership_col].sum(),
            "productivity": g[ridership_col].sum() / g["_rev"].sum(),
            "speed": g["speed_mph"].mean(),
            "reliability": g["reliability_peak" if peak else "reliability"].first(),
            "frequency": g["trips"].mean(),
            "mean_occupancy": g["occupancy"].mean(),
            "max_occupancy": g["occupancy"].max(),
            "avg_wait_min": g["avg_wait_min"].mean(),
            "trip_minutes": g["trip_minutes"].mean(),
            "length_mi": g["length_mi"].first(),
        })
        if comfort_from == "proba" and "p_overcrowded" in w:
            agg["comfort"] = 1 - g["p_overcrowded"].mean()
        else:
            agg["comfort"] = 1 - g["occupancy"].apply(lambda s: (s > C.OVERCROWDED_MIN).mean())
        return agg

    def rank_routes(self, f: pd.DataFrame, hours: tuple[int, int] = (6, 22), weights: C.ScoreWeights | None = None,
                    candidates: list[str] | None = None, ridership_col: str = "ridership",
                    comfort_from: str = "proba") -> pd.DataFrame:
        """Composite RouteRank score (0-100). Each component is converted to a
        percentile rank among the candidate routes and combined with the weights."""
        if candidates:
            f = f[f["route_id"].isin(candidates)]
        agg = self._aggregate(f, hours, ridership_col, comfort_from)
        if agg.empty:
            return agg
        w = (weights or C.ScoreWeights()).as_dict()
        for c in COMPONENTS:
            agg[f"{c}_pct"] = agg[c].rank(pct=True) * 100 if len(agg) > 1 else 100.0
        agg["score"] = sum(agg[f"{c}_pct"] * w[c] for c in COMPONENTS)
        agg = agg.sort_values("score", ascending=False)
        agg["rank"] = np.arange(1, len(agg) + 1)
        info = self.route_info.set_index("route_id")[["route_long_name", "route_type", "borough", "cluster_name"]]
        return agg.join(info).reset_index()

    def explain(self, ranking: pd.DataFrame, weights: C.ScoreWeights | None = None) -> list[str]:
        """Plain-language justification of the top-ranked route versus the others."""
        if ranking.empty:
            return ["No candidate route has service in the selected window."]
        top = ranking.iloc[0]
        others = ranking.iloc[1:]
        w = (weights or C.ScoreWeights()).as_dict()
        lines = [f"**{top['route_id']}** ranks #1 of {len(ranking)} candidate routes with a RouteRank score of "
                 f"**{top['score']:.1f}/100**" + (f", {top['score'] - others['score'].iloc[0]:.1f} points ahead of "
                                                  f"{others['route_id'].iloc[0]}." if len(others) else ".")]
        if others.empty:
            return lines
        med = others[COMPONENTS + ["mean_occupancy", "avg_wait_min"]].median()
        label = {"productivity": ("boardings per vehicle-hour", "{:.0f}"), "speed": ("mph average speed", "{:.1f}"),
                 "reliability": ("of buses on an acceptable headway", "{:.0%}"),
                 "frequency": ("buses per hour", "{:.1f}"),
                 "comfort": ("chance of NOT being overcrowded", "{:.0%}")}
        contrib = sorted(COMPONENTS, key=lambda c: -w[c] * top[f"{c}_pct"])
        for c in contrib:
            name, fmt = label[c]
            v, m = top[c], med[c]
            better = v >= m
            lines.append(f"{'✅' if better else '⚠️'} **{c.title()}** (weight {w[c]:.0%}): "
                         f"{fmt.format(v)} {name} vs median {fmt.format(m)} for the alternatives "
                         f"- better than {top[f'{c}_pct']:.0f}% of candidates.")
        lines.append(f"Expected average wait ≈ {top['avg_wait_min']:.1f} min and mean load ≈ "
                     f"{top['mean_occupancy']:.0%} of capacity (alternatives: {med['avg_wait_min']:.1f} min, "
                     f"{med['mean_occupancy']:.0%}).")
        return lines

    def validate(self, route: str, d, hours: tuple[int, int], candidates: list[str] | None,
                 weights: C.ScoreWeights | None = None, weeks: int = 6) -> pd.DataFrame:
        """Back-test: for the last ``weeks`` same-weekday dates in history, rank the candidates on
        ACTUAL ridership and report where the recommended route landed, plus forecast error."""
        d = pd.Timestamp(d).normalize()
        end = self.data_end.normalize()
        # most recent same-weekday date strictly before d that has actuals
        ref = d - pd.Timedelta(days=7) if d - pd.Timedelta(days=7) <= end else             end - pd.Timedelta(days=(end.dayofweek - d.dayofweek) % 7)
        dates = [ref - pd.Timedelta(days=7 * k) for k in range(weeks)]
        dates = [x for x in dates if self.data_start <= x <= end]
        rows = []
        for x in dates:
            hist = self.predict_day(x, None)
            if "ridership_actual" not in hist:
                continue
            hist = hist.dropna(subset=["ridership_actual"]).copy()
            pred_tot = hist.loc[hist["route_id"] == route].query("@hours[0] <= hour <= @hours[1]")["ridership"].sum()
            act = hist.copy()
            act["ridership"] = act["ridership_actual"]
            act = add_performance_metrics(act)
            r = self.rank_routes(act, hours, weights, candidates, comfort_from="actual")
            if r.empty or route not in set(r["route_id"]):
                continue
            me = r[r["route_id"] == route].iloc[0]
            act_tot = me["riders"]
            rows.append({"date": x.date(), "weekday": x.day_name(), "rank_on_actuals": int(me["rank"]),
                         "candidates": len(r), "actual_top_route": r.iloc[0]["route_id"],
                         "score_on_actuals": round(float(me["score"]), 1),
                         "predicted_riders": round(float(pred_tot)), "actual_riders": round(float(act_tot)),
                         "abs_pct_error": round(abs(pred_tot - act_tot) / max(act_tot, 1) * 100, 1)})
        return pd.DataFrame(rows)

    # ------------------------------------------------------------- journeys
    def search_stops(self, text: str, limit: int = 30) -> pd.DataFrame:
        """Find stops whose name contains ``text`` (case-insensitive)."""
        s = self.stops
        m = s[s["stop_name"].str.contains(text.upper().strip(), na=False, regex=False)]
        return m.drop_duplicates("stop_name").head(limit)

    def find_routes_between(self, origin: str, destination: str) -> pd.DataFrame:
        """Direct routes serving a stop matching ``origin`` and one matching ``destination``."""
        s = self.stops
        o = s[s["stop_name"].str.contains(origin.upper().strip(), na=False, regex=False)]
        t = s[s["stop_name"].str.contains(destination.upper().strip(), na=False, regex=False)]
        common = sorted(set(o["route_id"]) & set(t["route_id"]) & set(self.routes))
        rows = [{"route_id": r,
                 "origin_stop": o[o["route_id"] == r]["stop_name"].iloc[0],
                 "destination_stop": t[t["route_id"] == r]["stop_name"].iloc[0]} for r in common]
        return pd.DataFrame(rows)

    # -------------------------------------------------------- optimisation
    def recommendations(self, d) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
        """Hourly re-sizing + route-level actions + network impact for a date (forecast-based)."""
        f = self.predict_day(d)
        opt = optimize_frequencies(f)
        rec = route_recommendations(opt, self.route_info, self.overlap)
        return opt, rec, impact_summary(opt)

# ====================================================================================================
# SECTION 10. GTFS UPLOAD ANALYSER
# ====================================================================================================
# GTFS feed analyser (supply-side) for user-uploaded feeds.
#
# Works with any standard GTFS zip (e.g. Lepton Software feeds for Indian cities,
# or MTA's own GTFS). Reads routes.txt, trips.txt, stop_times.txt, stops.txt,
# calendar.txt (+ optional frequencies.txt / shapes.txt) and builds route
# profiles (length, trips/hour, headway, scheduled speed, service span),
# clusters them and flags overlapping / low-frequency routes.

REQUIRED = ["routes.txt", "trips.txt", "stop_times.txt", "stops.txt"]
OPTIONAL = ["calendar.txt", "frequencies.txt", "shapes.txt"]


def read_gtfs(file_like) -> dict[str, pd.DataFrame]:
    """Load the GTFS tables from a zip file path/bytes into DataFrames."""
    if isinstance(file_like, (bytes, bytearray)):
        file_like = io.BytesIO(file_like)
    with zipfile.ZipFile(file_like) as z:
        names = {n.split("/")[-1]: n for n in z.namelist()}
        missing = [f for f in REQUIRED if f not in names]
        if missing:
            raise ValueError(f"GTFS feed is missing required files: {missing}")
        return {f[:-4]: pd.read_csv(z.open(names[f]), dtype=str, low_memory=False)
                for f in REQUIRED + OPTIONAL if f in names}


def gtfs_time_to_hours(s: pd.Series) -> pd.Series:
    """'25:10:00' -> 25.17 (GTFS allows times past midnight)."""
    p = s.fillna("").str.strip().str.split(":", expand=True)
    p = p.apply(pd.to_numeric, errors="coerce")
    return p[0] + p[1] / 60 + p[2].fillna(0) / 3600


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km between coordinate arrays."""
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * np.arcsin(np.sqrt(a))


def weekday_service_ids(g: dict) -> set | None:
    """Service ids active on a typical weekday (calendar.txt), or None if unknown."""
    cal = g.get("calendar")
    if cal is None or cal.empty:
        return None
    return set(cal.loc[cal["wednesday"] == "1", "service_id"])


def route_profiles_from_gtfs(g: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """One row per route with supply-side features, plus trips per route per hour."""
    trips, st, stops, routes = g["trips"], g["stop_times"].copy(), g["stops"].copy(), g["routes"]
    svc = weekday_service_ids(g)
    if svc:
        trips = trips[trips["service_id"].isin(svc)]
    st = st[st["trip_id"].isin(trips["trip_id"])]
    st["t"] = gtfs_time_to_hours(st["departure_time"].where(st["departure_time"].notna(), st["arrival_time"]))
    st["stop_sequence"] = pd.to_numeric(st["stop_sequence"], errors="coerce")
    stops["stop_lat"] = pd.to_numeric(stops["stop_lat"], errors="coerce")
    stops["stop_lon"] = pd.to_numeric(stops["stop_lon"], errors="coerce")
    st = st.merge(stops[["stop_id", "stop_lat", "stop_lon", "stop_name"]], on="stop_id", how="left")
    st = st.sort_values(["trip_id", "stop_sequence"])
    st["seg_km"] = haversine_km(st["stop_lat"], st["stop_lon"],
                                st.groupby("trip_id")["stop_lat"].shift(-1),
                                st.groupby("trip_id")["stop_lon"].shift(-1))
    tr = st.groupby("trip_id").agg(start=("t", "min"), end=("t", "max"), km=("seg_km", "sum"),
                                   n_stops=("stop_id", "count")).reset_index()
    tr = tr.merge(trips[["trip_id", "route_id"]], on="trip_id")
    tr["dur_h"] = (tr["end"] - tr["start"]).clip(lower=1 / 60)
    tr["hour"] = (tr["start"] // 1 % 24).astype("Int64")

    g_r = tr.groupby("route_id")
    prof = pd.DataFrame({
        "trips_per_day": g_r.size(),
        "route_length_km": g_r["km"].median(),
        "n_stops": g_r["n_stops"].median(),
        "trip_duration_min": g_r["dur_h"].median() * 60,
        "first_departure_h": g_r["start"].min(),
        "last_departure_h": g_r["start"].max(),
    })
    prof["service_span_h"] = prof["last_departure_h"] - prof["first_departure_h"]
    prof["scheduled_speed_kmh"] = prof["route_length_km"] / (prof["trip_duration_min"] / 60)
    peak = tr[tr["hour"].isin([7, 8, 9, 17, 18, 19])].groupby("route_id").size() / 6
    prof["peak_trips_per_hour"] = peak.reindex(prof.index).fillna(0)
    prof["peak_headway_min"] = (60 / prof["peak_trips_per_hour"].replace(0, np.nan)).fillna(120).clip(upper=120)
    prof["stop_spacing_m"] = 1000 * prof["route_length_km"] / prof["n_stops"].clip(lower=2)
    prof = prof.replace([np.inf, -np.inf], np.nan).fillna(prof.median(numeric_only=True))
    names = routes.set_index("route_id")
    for c in ("route_short_name", "route_long_name"):
        if c in names:
            prof[c] = names[c].reindex(prof.index)
    tph = tr.groupby(["route_id", "hour"]).size().rename("trips").reset_index()
    return prof.reset_index(), tph


GTFS_CLUSTER_FEATURES = ["trips_per_day", "route_length_km", "n_stops", "trip_duration_min",
                         "service_span_h", "scheduled_speed_kmh", "peak_headway_min", "stop_spacing_m"]


def analyse_gtfs(file_like) -> dict:
    """Full upload analysis: profiles, KMeans/DBSCAN clusters, overlaps and flags."""
    g = read_gtfs(file_like)
    prof, tph = route_profiles_from_gtfs(g)
    X = StandardScaler().fit_transform(np.log1p(prof[GTFS_CLUSTER_FEATURES].clip(lower=0)))
    best_k, best_s = 2, -1
    for k in range(2, min(8, len(prof) - 1) + 1):
        lab = KMeans(k, n_init=10, random_state=42).fit_predict(X)
        s = silhouette_score(X, lab)
        if s > best_s:
            best_k, best_s = k, s
    prof["kmeans_cluster"] = KMeans(best_k, n_init=20, random_state=42).fit_predict(X) if len(prof) > 3 else 0
    ms = max(3, int(np.log(len(prof))) + 1)
    prof["dbscan_cluster"] = DBSCAN(eps=dbscan_eps(X, ms), min_samples=ms).fit_predict(X) if len(prof) > ms else 0

    stops = g["stops"].rename(columns={"stop_lat": "latitude", "stop_lon": "longitude"})
    stops["latitude"] = pd.to_numeric(stops["latitude"], errors="coerce")
    stops["longitude"] = pd.to_numeric(stops["longitude"], errors="coerce")
    rs = g["stop_times"][["trip_id", "stop_id"]].merge(g["trips"][["trip_id", "route_id"]]) \
        .drop_duplicates(["route_id", "stop_id"]).merge(stops[["stop_id", "latitude", "longitude", "stop_name"]])
    ov = stop_overlap(rs, prof["route_id"].tolist(), min_jaccard=0.3)

    q_low = prof["trips_per_day"].quantile(0.2)
    flags = []
    for _, r in prof.iterrows():
        f = []
        if r["trips_per_day"] <= q_low:
            f.append("Low frequency - consider merging or demand-responsive service")
        if r["peak_headway_min"] > 30:
            f.append("Peak headway > 30 min")
        if r["route_length_km"] > prof["route_length_km"].quantile(0.9):
            f.append("Very long - candidate for splitting")
        if r["scheduled_speed_kmh"] < prof["scheduled_speed_kmh"].quantile(0.1):
            f.append("Slow scheduled speed - bus-priority candidate")
        flags.append("; ".join(f) or "OK")
    prof["flags"] = flags
    return {"tables": {k: len(v) for k, v in g.items()}, "profiles": prof, "overlap": ov,
            "stops": rs, "k": best_k, "silhouette": best_s,
            "trips_per_hour": tph}

# ====================================================================================================
# SECTION 11. DIAGRAMS - architecture, pipeline and model figures
# ====================================================================================================
# Architecture, pipeline and model-result figures (PNG) for the app, README and report.

def _box(ax, x, y, w, h, title, lines, color, title_color="white"):
    """Draw a rounded, titled box with bullet lines (architecture diagram helper)."""
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                                fc=color, ec="none", alpha=.95))
    ax.text(x + w / 2, y + h - 0.18, title, ha="center", va="top", fontsize=9.5, weight="bold", color=title_color)
    for i, ln in enumerate(lines):
        ax.text(x + w / 2, y + h - 0.5 - i * 0.26, ln, ha="center", va="top", fontsize=7.4, color=title_color)


def _arrow(ax, x1, y1, x2, y2, label=None, color="#334155", style="-|>", ls="-"):
    """Draw an arrow between two points with an optional label."""
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, mutation_scale=13, color=color,
                                 lw=1.5, linestyle=ls))
    if label:
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 0.12, label, ha="center", fontsize=6.8, color="#475569")


def architecture_diagram() -> str:
    """Layered system architecture (data -> processing -> ML -> service -> UI/API)."""
    fig, ax = plt.subplots(figsize=(15, 6.2))
    ax.set_xlim(0, 15.4); ax.set_ylim(-0.1, 6.2); ax.axis("off")
    ax.text(7.7, 6.0, "RouteRanker - System Architecture (layered, modular monolith + REST API)",
            ha="center", fontsize=13, weight="bold", color="#0f172a")
    _box(ax, 0.2, 2.1, 2.2, 2.9, "DATA SOURCES", ["data.ny.gov SODA API", "Hourly ridership", "Schedules (GTFS)",
                                                   "Segment speeds", "Wait assessment", "Routes / Stops / Shapes",
                                                   "User GTFS upload (.zip)"], "#1e3a8a")
    _box(ax, 2.9, 2.1, 2.2, 2.9, "INGESTION", ["backend/main.py §2", "SoQL server-side", "aggregation", "monthly parquet cache",
                                               "incremental refresh", "manifest.json"], "#1d4ed8")
    _box(ax, 5.6, 2.1, 2.3, 2.9, "PROCESSING", ["backend/main.py §3-5", "cleaning, features,", "preprocessing",
                                                "eda/main.py", "(EDA figures + JSON)"], "#b45309")
    _box(ax, 8.4, 2.1, 2.4, 2.9, "ML MODELS", ["backend/main.py §6-7", "KMeans + DBSCAN", "RF / XGBoost classifier",
                                               "RF / XGBoost forecaster", "(hourly demand)"], "#7e22ce")
    _box(ax, 11.3, 2.1, 1.9, 2.9, "SERVICE", ["backend/main.py §8-10", "RouteRankerService", "rank + explain",
                                              "validate, optimise", "simulate, GTFS"], "#be185d")
    _box(ax, 13.6, 3.65, 1.65, 1.35, "FRONTEND", ["frontend/main.py", "Streamlit · 11 pages"], "#047857")
    _box(ax, 13.6, 2.1, 1.65, 1.35, "BACKEND API", ["backend/main.py §13", "FastAPI /api/*"], "#0f766e")
    for x1, x2, lab in [(2.4, 2.9, "raw"), (5.1, 5.6, "parquet"), (7.9, 8.4, "features"), (10.8, 11.3, "models")]:
        _arrow(ax, x1, 3.55, x2, 3.55, lab)
    _arrow(ax, 13.2, 3.9, 13.6, 4.3); _arrow(ax, 13.2, 3.2, 13.6, 2.8)
    # storage layer
    ax.add_patch(FancyBboxPatch((2.9, 0.4), 10.3, 1.1, boxstyle="round,pad=0.02,rounding_size=0.08",
                                fc="#f1f5f9", ec="#94a3b8"))
    ax.text(8.05, 1.22, "STORAGE LAYER", ha="center", fontsize=9, weight="bold", color="#0f172a")
    ax.text(8.05, 0.75, "data/raw/*.parquet   ·   data/processed/*.parquet   ·   models/*.joblib   ·   "
            "reports/metrics/*.json   ·   reports/figures/*.png", ha="center", fontsize=7.8, color="#334155")
    for x in (4.0, 6.75, 9.6, 12.25):
        _arrow(ax, x, 2.1, x, 1.5, style="<|-|>", color="#94a3b8")
    _arrow(ax, 14.4, 2.1, 14.4, 0.12, ls="--", color="#16a34a", style="-")
    _arrow(ax, 14.4, 0.12, 1.3, 0.12, ls="--", color="#16a34a", style="-")
    _arrow(ax, 1.3, 0.12, 1.3, 2.1, ls="--", color="#16a34a")
    ax.text(7.7, -0.05, "user input: date/time (IST), GTFS upload, data refresh", ha="center", fontsize=7.5,
            color="#15803d")
    path = C.FIGURES_DIR / "architecture_diagram.png"
    fig.savefig(path, dpi=150, bbox_inches="tight"); plt.close(fig)
    return str(path.relative_to(C.ROOT_DIR))


def pipeline_diagram() -> str:
    """The 10-stage ML pipeline as a flow chart."""
    steps = [("1. Data\nCollection", "#1e40af"), ("2. Cleaning", "#1d4ed8"), ("3. Feature\nEngineering", "#2563eb"),
             ("4. EDA", "#b45309"), ("5. Pre-\nprocessing", "#d97706"), ("6. Clustering\nKMeans +\nDBSCAN", "#7e22ce"),
             ("7. Classifi-\ncation\nRF / XGBoost", "#9333ea"), ("8. Forecasting\nXGBoost / RF", "#a855f7"),
             ("9. Inference &\nOptimisation", "#be185d"), ("10. Dashboard\n& API", "#047857")]
    fig, ax = plt.subplots(figsize=(15, 3.6))
    ax.set_xlim(0, 15); ax.set_ylim(0, 3.6); ax.axis("off")
    ax.text(7.5, 3.35, "RouteRanker end-to-end ML pipeline (python backend/main.py train  ·  python eda/main.py)", ha="center",
            fontsize=12, weight="bold")
    w, gap = 1.3, 0.17
    for i, (t, c) in enumerate(steps):
        x = 0.1 + i * (w + gap)
        ax.add_patch(FancyBboxPatch((x, 1.25), w, 1.3, boxstyle="round,pad=0.02,rounding_size=0.1", fc=c, ec="none"))
        ax.text(x + w / 2, 1.9, t, ha="center", va="center", color="white", fontsize=7.6, weight="bold")
        if i < len(steps) - 1:
            _arrow(ax, x + w, 1.9, x + w + gap, 1.9)
    outs = ["parquet\nper month", "clean\nreport", "route-hour\ntable", "11 figures\n+ JSON", "train/valid\nsplit",
            "segments +\noutliers", "class\nprobabilities", "hourly\nforecast", "ranking +\nactions", "11 pages\n+ REST"]
    for i, o in enumerate(outs):
        ax.text(0.1 + i * (w + gap) + w / 2, 0.75, o, ha="center", va="center", fontsize=7, color="#475569")
    path = C.FIGURES_DIR / "pipeline_diagram.png"
    fig.savefig(path, dpi=150, bbox_inches="tight"); plt.close(fig)
    return str(path.relative_to(C.ROOT_DIR))


def model_figures(cluster_prof: pd.DataFrame, cluster_metrics: dict, clf: dict, reg: dict,
                  val: pd.DataFrame) -> dict[str, str]:
    """K selection, PCA cluster map, confusion matrices, feature importances, forecast fit."""
    out = {}
    ks = pd.DataFrame(cluster_metrics["k_selection"])
    fig, ax = plt.subplots(1, 2, figsize=(11, 3.8))
    ax[0].plot(ks["k"], ks["inertia"], "o-", color="#2563eb"); ax[0].set(title="Elbow (inertia)", xlabel="k")
    ax[1].plot(ks["k"], ks["silhouette"], "o-", color="#16a34a", label="Silhouette")
    ax[1].plot(ks["k"], ks["davies_bouldin"] / ks["davies_bouldin"].max(), "s--", color="#dc2626",
               label="Davies-Bouldin (scaled)")
    ax[1].axvline(cluster_metrics["kmeans"]["k"], color="k", ls=":"); ax[1].legend(fontsize=8)
    ax[1].set(title="Cluster quality vs k", xlabel="k")
    out["k_selection"] = _save(fig, "model_kmeans_k_selection.png")

    fig, ax = plt.subplots(1, 2, figsize=(13, 5))
    sns.scatterplot(data=cluster_prof, x="pc1", y="pc2", hue="cluster_name", ax=ax[0], s=40, palette="tab10")
    ax[0].set(title="KMeans route segments (PCA projection)"); ax[0].legend(fontsize=7)
    sns.scatterplot(data=cluster_prof, x="pc1", y="pc2", hue=cluster_prof["dbscan_outlier"].map({0: "core", 1: "outlier"}),
                    palette={"core": "#94a3b8", "outlier": "#ef4444"}, ax=ax[1], s=40)
    for _, r in cluster_prof[cluster_prof["dbscan_outlier"] == 1].iterrows():
        ax[1].annotate(r["route_id"], (r["pc1"], r["pc2"]), fontsize=6)
    ax[1].set(title="DBSCAN density clusters - outlier routes")
    out["clusters_pca"] = _save(fig, "model_clusters_pca.png")

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.3))
    for a, k in zip(axes, ("RandomForest", "XGBoost")):
        cm = np.array(clf[k]["confusion_matrix"])
        cmn = cm / cm.sum(1, keepdims=True)
        sns.heatmap(cmn, annot=True, fmt=".2f", cmap="Blues", xticklabels=C.CLASS_LABELS,
                    yticklabels=C.CLASS_LABELS, ax=a, cbar=False)
        a.set(title=f"{k} (macro-F1 {clf[k]['f1_macro']:.3f})", xlabel="Predicted", ylabel="Actual")
    out["confusion"] = _save(fig, "model_confusion_matrices.png")

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    for a, (title, imp) in zip(axes, [("Classifier (" + clf["best"] + ")", clf["feature_importance"][clf["best"]]),
                                      ("Forecaster (" + reg["best"] + ")", reg["feature_importance"][reg["best"]])]):
        s = pd.Series(imp).head(15)[::-1]
        a.barh(s.index, s.values, color="#7c3aed"); a.set(title=f"Top features - {title}")
        a.tick_params(axis="y", labelsize=7)
    out["importance"] = _save(fig, "model_feature_importance.png")

    fig, axes = plt.subplots(1, 2, figsize=(13, 4.3))
    net = val.groupby("ts")[["ridership", "pred"]].sum() / 1000
    axes[0].plot(net.index, net["ridership"], lw=1.2, label="Actual", color="#0f172a")
    axes[0].plot(net.index, net["pred"], lw=1.2, label="Forecast", color="#f97316", alpha=.85)
    axes[0].set(title="Validation period - network hourly boardings (thousands)"); axes[0].legend()
    axes[0].tick_params(axis="x", rotation=30, labelsize=7)
    smp = val.sample(min(20000, len(val)), random_state=1)
    axes[1].scatter(smp["ridership"], smp["pred"], s=3, alpha=.25, color="#2563eb")
    m = smp[["ridership", "pred"]].max().max()
    axes[1].plot([0, m], [0, m], "k--", lw=1)
    axes[1].set(title="Route-hour: forecast vs actual", xlabel="Actual", ylabel="Forecast")
    out["forecast_fit"] = _save(fig, "model_forecast_validation.png")

    comp = pd.DataFrame({k: {m: reg[k][m] for m in ("mae", "rmse", "wape")}
                         for k in ("SeasonalProfileBaseline", "RandomForest", "XGBoost")}).T
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.4))
    for a, m in zip(axes, ("mae", "rmse", "wape")):
        a.bar(comp.index, comp[m], color=["#94a3b8", "#22c55e", "#f97316"]); a.set(title=m.upper())
        a.tick_params(axis="x", labelsize=7, rotation=10)
    out["forecast_comparison"] = _save(fig, "model_forecast_comparison.png")
    return out


def _save(fig, name):
    """Save a matplotlib figure to reports/figures and return its relative path."""
    p = C.FIGURES_DIR / name
    fig.tight_layout(); fig.savefig(p, dpi=130); plt.close(fig)
    return str(p.relative_to(C.ROOT_DIR))

# ====================================================================================================
# SECTION 12. TRAINING PIPELINE - orchestrates sections 2-11
# ====================================================================================================
# End-to-end training pipeline.
#
#     python backend/main.py train                  # use cached raw data, download what is missing
#     python backend/main.py train --refresh        # re-download every source first
#     python backend/main.py train --skip-download  # cached raw parquet only
#
# Stages: collect -> clean -> engineer features -> EDA -> preprocess ->
# cluster -> classify -> forecast -> optimise -> persist artefacts.

log = logging.getLogger("routeranker.pipeline")
HISTORY_COLS = ["route_id", "ts", "date", "hour", "dow", "day_type", "is_holiday", "ridership", "est_riders",
                "transfers", "trips",
                "load_per_trip", "occupancy", "perf_class", "productivity", "speed_mph", "avg_wait_min",
                "revenue_hours", "capacity", "trip_minutes"]


def _read(name: str) -> pd.DataFrame:
    """Read one cached raw parquet table."""
    return pd.read_parquet(C.RAW_DIR / f"{name}.parquet")


def load_raw(download: bool, refresh: bool) -> dict[str, pd.DataFrame]:
    """Stage 1 - collect (or read cached) raw tables."""
    if download:
        needed = ["segment_speeds", "route_speeds", "wait_assessment", "fare_evasion", "routes", "stops",
                  "schedule_trips_per_hour", "schedule_route_geometry"]
        if refresh or any(not (C.RAW_DIR / f"{n}.parquet").exists() for n in needed):
            collect_all()
        else:
            collect_hourly_ridership()
    files = sorted((C.RAW_DIR / "ridership").glob("ridership_*.parquet"))
    return {
        "ridership": pd.concat([pd.read_parquet(f) for f in files], ignore_index=True),
        "tph": _read("schedule_trips_per_hour"), "geo": _read("schedule_route_geometry"),
        "seg": _read("segment_speeds"), "monthly": _read("route_speeds"), "wait": _read("wait_assessment"),
        "routes": _read("routes"), "stops": _read("stops"),
        "evasion": _read("fare_evasion") if (C.RAW_DIR / "fare_evasion.parquet").exists() else None,
    }


def run_pipeline(download: bool = True, refresh: bool = False) -> dict:
    """Execute all training stages and persist data, models, metrics and figures."""
    t0 = time.time()
    stage_times = {}

    def mark(name):
        """Record the elapsed time of a finished stage."""
        stage_times[name] = round(time.time() - t0 - sum(stage_times.values()), 1)
        log.info("== stage '%s' done (%.1fs)", name, stage_times[name])

    raw = load_raw(download, refresh); mark("1_data_collection")

    # ---- cleaning
    rid, clean_rep = clean_ridership(raw["ridership"])
    trips, geo = clean_schedule(raw["tph"], raw["geo"])
    speeds_hourly, route_speed = clean_speeds(raw["seg"], raw["monthly"])
    wait = clean_wait(raw["wait"])
    evasion = clean_evasion(raw["evasion"])
    clean_rep["fare_evasion_rates"] = evasion
    catalog, paths, stops = clean_routes(raw["routes"], raw["stops"], route_speed)
    # keep routes that have both ridership and a schedule
    scheduled = set(trips.loc[trips["trips"] > 0, "route_id"])
    clean_rep["routes_without_schedule"] = sorted(set(rid["route_id"]) - scheduled)
    rid = rid[rid["route_id"].isin(scheduled)]
    clean_rep["routes_modelled"] = int(rid["route_id"].nunique())
    raw_rows = {k: int(len(v)) if v is not None else 0 for k, v in raw.items()}
    del raw  # free the raw tables (several hundred MB) before feature engineering
    gc.collect()
    mark("2_cleaning")

    # ---- features
    route_static = (catalog[["route_id", "route_type", "borough"]]
                    .merge(geo[["route_id", "length_mi", "n_stops"]], how="outer")
                    .merge(wait, how="left").merge(route_speed[["route_id", "route_speed_mph"]], how="left"))
    route_static = route_static[route_static["route_id"].isin(rid["route_id"].unique())]
    missing = set(rid["route_id"]) - set(route_static["route_id"])
    if missing:
        route_static = pd.concat([route_static, pd.DataFrame({"route_id": sorted(missing)})], ignore_index=True)
        route_static["borough"] = route_static["borough"].fillna(route_static["route_id"].map(borough_of))
        route_static["route_type"] = route_static["route_type"].fillna(
            route_static["route_id"].map(lambda r: "Select Bus Service" if r.endswith("+") else "Local"))
    route_static["length_mi"] = route_static["length_mi"].fillna(route_static["length_mi"].median())
    route_static["evasion_factor"] = 1 / (1 - route_static["route_type"].map(evasion).fillna(evasion["Other"]))
    rh = build_route_hour_table(rid, trips, speeds_hourly, route_static)
    del rid
    gc.collect()
    # calibrate class thresholds on the training period's service hours
    cutoff_cal = rh["date"].max() - pd.Timedelta(days=C.VALIDATION_DAYS - 1)
    occ = rh.loc[(rh["trips"] > 0) & (rh["date"] < cutoff_cal), "occupancy"].dropna()
    C.set_thresholds(occ.quantile(C.UNDER_QUANTILE), occ.quantile(C.OVER_QUANTILE))
    C.THRESHOLDS_FILE.write_text(json.dumps({"underutilized_max": C.UNDERUTILIZED_MAX,
                                             "overcrowded_min": C.OVERCROWDED_MIN,
                                             "target_occupancy": C.TARGET_OCCUPANCY,
                                             "quantiles": [C.UNDER_QUANTILE, C.OVER_QUANTILE]}, indent=2))
    rh["perf_class"] = classify_occupancy(rh["occupancy"])
    log.info("calibrated thresholds: under < %.3f, over > %.3f", C.UNDERUTILIZED_MAX, C.OVERCROWDED_MIN)
    profiles = build_route_profiles(rh)
    mark("3_feature_engineering")

    # ---- overlap screening (EDA itself is run separately by eda/main.py)
    overlap = stop_overlap(stops, profiles["route_id"].tolist())
    (C.METRICS_DIR / "cleaning_report.json").write_text(json.dumps(clean_rep, indent=2, default=str))
    mark("4_overlap_and_cleaning_report")

    # persist the historical table now and release it (memory-friendly on 8 GB machines)
    rh[HISTORY_COLS].to_parquet(C.PROCESSED_DIR / "route_hour.parquet", index=False)
    rh_info = {"data_start": str(rh["date"].min().date()), "data_end": str(rh["date"].max().date()),
               "last_timestamp_local": str(rh["ts"].max()), "routes": int(rh["route_id"].nunique()),
               "route_hours": int(len(rh))}

    # ---- preprocessing
    train, valid, cutoff = time_split(rh)
    del rh
    split_info = {"train_rows": int(len(train)), "valid_rows": int(len(valid)), "cutoff": str(cutoff.date()),
                  "train_start": str(train["date"].min().date()), "valid_end": str(valid["date"].max().date())}
    enc = ProfileEncoder().fit(train)
    train_e, Xtr = model_matrix(train, enc)
    train_y = train_e[["perf_class", "log_ridership"]].copy()
    del train, train_e
    gc.collect()
    valid_e, Xva = model_matrix(valid, enc)
    del valid
    gc.collect()
    mark("5_preprocessing")

    # ---- clustering
    cl_prof, cl = run_clustering(profiles)
    mark("6_clustering")

    # ---- classification (route-hours with service only)
    mtr, mva = train_y["perf_class"].notna().to_numpy(), valid_e["perf_class"].notna().to_numpy()
    clf = train_classifiers(Xtr[mtr], train_y.loc[mtr, "perf_class"], Xva[mva], valid_e.loc[mva, "perf_class"])
    gc.collect()
    mark("7_classification")

    # ---- forecasting
    reg = train_forecasters(Xtr, train_y["log_ridership"], Xva, valid_e["ridership"])
    valid_e["pred"] = reg["validation_predictions"]
    mark("8_forecasting")

    # ---- optimisation impact on the validation period (actual loads)
    opt = optimize_frequencies(valid_e)
    impact = impact_summary(opt)
    mark("9_optimisation")

    # ---- persist artefacts
    P = C.PROCESSED_DIR
    centroids = stops.groupby("route_id")[["latitude", "longitude"]].mean().reset_index()
    route_info = (cl_prof.merge(catalog.drop(columns=["route_type", "borough"]), on="route_id", how="left")
                  .merge(route_static[["route_id", "route_speed_mph", "evasion_factor"]], on="route_id", how="left")
                  .merge(centroids, on="route_id", how="left"))
    route_info["route_long_name"] = route_info["route_long_name"].fillna(route_info["route_id"])
    route_info.to_parquet(P / "route_info.parquet", index=False)
    trips.to_parquet(P / "trips.parquet", index=False)
    speeds_hourly.to_parquet(P / "speeds_hourly.parquet", index=False)
    paths[paths["route_id"].isin(route_info["route_id"])].to_parquet(P / "paths.parquet", index=False)
    stops.to_parquet(P / "stops.parquet", index=False)
    overlap.to_parquet(P / "overlap.parquet", index=False)
    valid_e[["route_id", "ts", "hour", "ridership", "pred", "perf_class"]].to_parquet(P / "validation_predictions.parquet", index=False)

    joblib.dump(enc, C.MODELS_DIR / "profile_encoder.joblib")
    joblib.dump(clf[clf["best"]]["model"], C.MODELS_DIR / "classifier.joblib")
    joblib.dump(reg[reg["best"]]["model"], C.MODELS_DIR / "forecaster.joblib")
    joblib.dump({k: cl[k] for k in ("kmeans", "dbscan", "scaler", "pca")}, C.MODELS_DIR / "clustering.joblib")
    # alternates kept for comparison in the app
    other_clf = "XGBoost" if clf["best"] == "RandomForest" else "RandomForest"
    joblib.dump(clf[other_clf]["model"], C.MODELS_DIR / f"classifier_{other_clf.lower()}.joblib", compress=3)

    figs = model_figures(cl_prof, cl["metrics"], clf, reg, valid_e)
    figs["architecture"] = architecture_diagram()
    figs["pipeline"] = pipeline_diagram()

    strip = lambda d: {k: v for k, v in d.items() if k not in ("model",)}  # noqa: E731
    metrics = {
        "clustering": cl["metrics"],
        "classification": {"best": clf["best"], "RandomForest": strip(clf["RandomForest"]),
                           "XGBoost": strip(clf["XGBoost"]), "feature_importance": clf["feature_importance"],
                           "class_distribution_train": train_y["perf_class"].value_counts().to_dict(),
                           "class_distribution_valid": valid_e["perf_class"].value_counts().to_dict()},
        "forecasting": {"best": reg["best"], "SeasonalProfileBaseline": reg["SeasonalProfileBaseline"],
                        "RandomForest": strip(reg["RandomForest"]), "XGBoost": strip(reg["XGBoost"]),
                        "feature_importance": reg["feature_importance"]},
        "optimisation_impact_validation": impact,
        "split": split_info,
        "figures": figs,
    }
    (C.METRICS_DIR / "model_metrics.json").write_text(json.dumps(metrics, indent=2, default=str))
    manifest = {
        "built_at_ist": datetime.now(C.IST).strftime("%Y-%m-%d %H:%M:%S IST"),
        **rh_info,
        "granularity": "hourly",
        "stage_seconds": stage_times, "total_seconds": round(time.time() - t0, 1),
        "sources": {k: {"id": s.dataset_id, "name": s.name, "url": s.url, "granularity": s.granularity,
                        "role": s.role} for k, s in C.SOURCES.items()},
        "raw_rows": raw_rows,
        "assumptions": {"vehicle_capacity": C.VEHICLE_CAPACITY, "peak_load_factor": C.PEAK_LOAD_FACTOR,
                        "fare_evasion_rates": evasion, "threshold_quantiles": [C.UNDER_QUANTILE, C.OVER_QUANTILE],
                        "underutilized_max": C.UNDERUTILIZED_MAX, "overcrowded_min": C.OVERCROWDED_MIN,
                        "target_occupancy": C.TARGET_OCCUPANCY, "min_trips_per_hour": C.MIN_TRIPS_PER_HOUR,
                        "validation_days": C.VALIDATION_DAYS},
    }
    mark("10_persist")
    manifest["stage_seconds"] = stage_times
    (C.METRICS_DIR / "pipeline_manifest.json").write_text(json.dumps(manifest, indent=2))
    log.info("Pipeline finished in %.1f min", (time.time() - t0) / 60)
    return {"manifest": manifest, "metrics": metrics}


# ====================================================================================================
# SECTION 13. REST API (FastAPI) - uvicorn backend.main:app --port 8000
# ====================================================================================================
# RouteRanker REST API (FastAPI backend).
#
#     python backend/main.py serve                   # docs at http://localhost:8000/docs
#     uvicorn backend.main:app --reload --port 8000  # same, via uvicorn
#
# All dates/times in requests are IST unless stated; responses include both IST
# and the bus network's local time.




app = FastAPI(title="RouteRanker API", version="1.0.0",
              description="AI-powered public transit route optimisation - forecasts, rankings, recommendations.")


@lru_cache(maxsize=1)
def svc() -> RouteRankerService:
    """Lazily created singleton RouteRankerService."""
    return RouteRankerService()


def _resolve(date_ist: Optional[str], time_ist: Optional[str]):
    """Turn optional IST date/time strings into (IST datetime, network-local datetime)."""
    n = now_ist()
    d = pd.Timestamp(date_ist).date() if date_ist else n.date()
    t = datetime.strptime(time_ist, "%H:%M").time() if time_ist else n.time()
    dt = datetime.combine(d, t).replace(tzinfo=C.IST)
    return dt, ist_to_transit(dt)


def _records(df: pd.DataFrame) -> list[dict]:
    """DataFrame -> JSON-safe list of dicts (NaN -> null)."""
    return df.replace({float("nan"): None}).to_dict(orient="records")


@app.get("/api/health")
def health():
    """Service status, current IST time and data window."""
    s = svc()
    return {"status": "ok", "now_ist": now_ist().isoformat(), "routes": len(s.routes),
            "data_start": str(s.data_start.date()), "data_end": str(s.data_end.date()),
            "models_built_ist": s.manifest["built_at_ist"]}


@app.get("/api/routes")
def routes(borough: Optional[str] = None, route_type: Optional[str] = None):
    """Route catalogue with segment and KPIs, optionally filtered."""
    ri = svc().route_info
    if borough:
        ri = ri[ri["borough"] == borough]
    if route_type:
        ri = ri[ri["route_type"] == route_type]
    cols = ["route_id", "route_long_name", "borough", "route_type", "cluster_name", "avg_daily_ridership",
            "productivity", "mean_occupancy", "mean_speed_mph", "reliability", "dbscan_outlier"]
    return _records(ri[cols])


@app.get("/api/predict")
def predict(route_id: str, date_ist: Optional[str] = Query(None, description="YYYY-MM-DD (IST)")):
    """24-hour forecast for one route on a date (IST)."""
    s = svc()
    if route_id not in s.routes:
        raise HTTPException(404, f"unknown route {route_id}")
    dt, local = _resolve(date_ist, "12:00")
    f = s.predict_day(local.date(), [route_id])
    cols = ["hour", "ridership", "trips", "occupancy", "productivity", "speed_mph", "avg_wait_min", "pred_class",
            "p_underutilized", "p_balanced", "p_overcrowded"] + (["ridership_actual"] if "ridership_actual" in f else [])
    return {"route_id": route_id, "local_date": str(local.date()), "generated_at_ist": now_ist().isoformat(),
            "hours": _records(f[cols])}


@app.get("/api/best-route")
def best_route(date_ist: Optional[str] = None, time_ist: Optional[str] = Query(None, description="HH:MM IST"),
               window: int = Query(1, ge=0, le=12, description="+/- hours around the time"),
               origin: Optional[str] = None, destination: Optional[str] = None,
               borough: Optional[str] = None, preset: str = "Balanced (default)", validate: bool = True):
    """Best route for a date/time window, with explanation, ranking and back-test validation."""
    s = svc()
    dt, local = _resolve(date_ist, time_ist)
    hours = (max(local.hour - window, 0), min(local.hour + window, 23))
    cand = None
    if origin and destination:
        cand = s.find_routes_between(origin, destination)["route_id"].tolist()
        if len(cand) == 0:
            raise HTTPException(404, "no direct route between these places")
    elif borough:
        cand = s.route_info.loc[s.route_info["borough"] == borough, "route_id"].tolist()
    w = PRESETS.get(preset, C.ScoreWeights())
    rank = s.rank_routes(s.predict_day(local.date()), hours, w, cand)
    if rank.empty:
        raise HTTPException(404, "no service in this window")
    out = {"requested_ist": dt.isoformat(), "network_local": local.isoformat(), "hours_local": hours,
           "generated_at_ist": now_ist().isoformat(), "best_route": rank.iloc[0]["route_id"],
           "why": s.explain(rank, w), "ranking": _records(rank.head(20))}
    if validate:
        out["validation"] = _records(s.validate(rank.iloc[0]["route_id"], local.date(), hours, cand, w).astype(str))
    return out


@app.get("/api/ranking")
def ranking(date_ist: Optional[str] = None, start_hour: int = 6, end_hour: int = 22, top: int = 50):
    """RouteRank league table for a date and hour window."""
    s = svc()
    _, local = _resolve(date_ist, "12:00")
    rank = s.rank_routes(s.predict_day(local.date()), (start_hour, end_hour))
    return {"local_date": str(local.date()), "ranking": _records(rank.head(top))}


@app.get("/api/recommendations")
def recommendations(date_ist: Optional[str] = None, top: int = 50):
    """Optimisation actions and network impact for a date."""
    s = svc()
    _, local = _resolve(date_ist, "12:00")
    _, rec, imp = s.recommendations(local.date())
    return {"local_date": str(local.date()), "impact": imp, "actions": _records(rec.head(top))}


class Scenario(BaseModel):
    """Request body of the scenario simulator."""
    date_ist: Optional[str] = None
    routes: Optional[list[str]] = None
    start_hour: int = Field(6, ge=0, le=23)
    end_hour: int = Field(20, ge=0, le=23)
    demand_change_pct: float = 0
    frequency_multiplier: float = 1.0
    speed_change_pct: float = 0
    capacity: Optional[float] = None


@app.post("/api/simulate")
def simulate(sc: Scenario):
    """Run a what-if scenario and return current vs simulated KPIs."""
    s = svc()
    _, local = _resolve(sc.date_ist, "12:00")
    sim = simulate_scenario(s.predict_day(local.date()), sc.demand_change_pct, sc.frequency_multiplier,
                            sc.speed_change_pct, sc.capacity, sc.routes, (sc.start_hour, sc.end_hour))
    x = sim[sim["in_scenario"] & (sim["trips"] > 0)]
    summ = {k: {"current": float(x[k].mean()), "simulated": float(x[f"{k}_sim"].mean())}
            for k in ("occupancy", "avg_wait_min", "productivity")}
    summ["overcrowded_share"] = {"current": float((x["perf_class"] == "Overcrowded").mean()),
                                 "simulated": float((x["perf_class_sim"] == "Overcrowded").mean())}
    return {"local_date": str(local.date()), "summary": summ, "route_hours": int(len(x))}

# ====================================================================================================
# SECTION 14. COMMAND-LINE INTERFACE
# ====================================================================================================

def main(argv: list[str] | None = None) -> None:
    """Command-line entry point: collect | train | serve."""
    ap = argparse.ArgumentParser(description="RouteRanker backend")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("collect", help="download / refresh all MTA datasets")
    t = sub.add_parser("train", help="run the full training pipeline")
    t.add_argument("--refresh", action="store_true", help="re-download every source first")
    t.add_argument("--skip-download", action="store_true", help="use cached raw parquet only")
    s = sub.add_parser("serve", help="start the REST API")
    s.add_argument("--port", type=int, default=8000)
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if a.cmd == "collect":
        collect_all()
    elif a.cmd == "train":
        run_pipeline(download=not a.skip_download, refresh=a.refresh)
        print("\nTraining finished. Next: python eda/main.py   and   streamlit run frontend/main.py")
    else:
        import uvicorn
        uvicorn.run(app, host="127.0.0.1", port=a.port)


if __name__ == "__main__":
    # Re-enter through the importable name ``backend.main`` so that pickled objects
    # (e.g. ProfileEncoder) are saved under a module path the API/frontend can load.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from backend.main import main as _main
    _main()
