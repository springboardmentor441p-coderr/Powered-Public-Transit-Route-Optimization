"""Module 2b - Feature Engineering.

Builds the hourly *route-hour* analytical table and the *route profile* table.

Granularity: one row per route per clock hour (America/New_York local time).
Daily figures are derived by summing hours.
"""
from __future__ import annotations

import logging

import holidays
import numpy as np
import pandas as pd

from . import config as C

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
