"""Module 1 - Data Collection.

Downloads the MTA open datasets from the Socrata SODA API (data.ny.gov).
Heavy tables are aggregated server-side with SoQL so that only the
granularity we need (route x hour) travels over the network.

Run directly:  python -m routeranker.data_collection
"""
from __future__ import annotations

import io
import json
import logging
import time
from datetime import datetime, timedelta

import pandas as pd
import requests

from . import config as C

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


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    collect_all()
