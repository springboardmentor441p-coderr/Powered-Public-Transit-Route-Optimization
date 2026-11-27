"""Module 2a - Data Cleaning.

Turns the raw open-data pulls into tidy, validated tables:
missing-value handling, type coercion, ID normalisation, duplicate removal,
outlier capping and completion of the hourly grid.
"""
from __future__ import annotations

import logging
import re

import numpy as np
import pandas as pd

from . import config as C

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
