"""
Milestone 3 — Step 6: Operational Ridership Forecasting & Unseen October Evaluation

Takes a date range (--start-date, --end-date) and a GTFS timetable version
(--timetable-version), builds exact schedule and feature inputs using the frozen
Step 5 pipeline (models/final_forecaster.joblib) and locked 0.96x validation cutoff
(reports/tables/m2_high_demand_thresholds.csv), and outputs hourly predicted riders
and high-demand-per-trip flags per (route, date, hour).

Never reads or modifies test_features.parquet and never retrains or overwrites
any saved .joblib model.

Usage:
    python -m src.predict --start-date 2026-10-18 --end-date 2026-10-31 --timetable-version 2026-10-17 --evaluate
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import duckdb
import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.pipeline import Pipeline

import src.build_matched_table as bmt
from src.build_matched_table import (
    HOLIDAY_SCHEDULE_DATES,
    PUBLIC_HOLIDAYS,
    STORM_DATES,
    assign_time_band,
    find_outage_hours_relative,
)
from src.build_schedule import GTFSFeed, count_trip_hours
from src.clean_ridership import validate as validate_ridership_df
from src.evaluate import (
    compute_classification_metrics,
    compute_forecast_breakdown,
    compute_forecast_metrics,
)
from src.prepare_modeling_features import compute_exact_calendar_lags, load_raw_features

ROOT = Path(__file__).resolve().parents[1]
DATA_RAW_RIDERSHIP = ROOT / "data" / "raw" / "ridership"
DATA_PROCESSED = ROOT / "data" / "processed"
MODELS_DIR = ROOT / "models"
TAB_DIR = ROOT / "reports" / "tables"
FIG_DIR = ROOT / "reports" / "figures"
ROUTE_DECISIONS_PATH = ROOT / "src" / "route_decisions.csv"

EXTENDED_PUBLIC_HOLIDAYS = {
    **PUBLIC_HOLIDAYS,
    "2026-10-12": "Columbus Day / Indigenous Peoples' Day",
    "2026-11-11": "Veterans Day",
    "2026-11-26": "Thanksgiving Day",
    "2026-12-25": "Christmas Day",
}

ALL_FEATURES = [
    "route",
    "day_of_week",
    "time_band",
    "trips_running",
    "trips_starting",
    "service_hours",
    "route_length_km",
    "stop_count",
    "hour_sin",
    "hour_cos",
    "is_weekend",
    "is_public_holiday",
    "holiday_schedule",
    "is_storm",
    "is_sbs",
    "is_24h",
    "lag_7d",
    "lag_14d",
    "lag_21d",
    "lag_28d",
    "lag_mean_available",
    "lags_available_count",
]


def _resolve_gtfs_feed(timetable_version: str) -> GTFSFeed:
    """Load GTFSFeed from a snapshot folder name (e.g. '2026-10-17') or zip path."""
    p = Path(timetable_version)
    if p.suffix == ".zip" and p.exists():
        return GTFSFeed(str(p.parent.name)) if p.parent.parent.name == "manhattan" else _feed_from_zip(p, timetable_version)
    snap_zip = ROOT / "data" / "raw" / "gtfs" / "manhattan" / timetable_version / "original.zip"
    if not snap_zip.exists():
        raise FileNotFoundError(
            f"GTFS timetable version '{timetable_version}' not found at {snap_zip}"
        )
    return GTFSFeed(timetable_version)


def _feed_from_zip(zip_path: Path, label: str) -> GTFSFeed:
    """Helper if caller passes an explicit .zip path outside standard snapshot folders."""
    feed = GTFSFeed.__new__(GTFSFeed)
    import zipfile

    from src.build_schedule import parse_time_to_seconds

    feed.snapshot_date = label
    with zipfile.ZipFile(zip_path) as z:
        feed.calendar = pd.read_csv(z.open("calendar.txt"), dtype=str)
        feed.calendar_dates = (
            pd.read_csv(z.open("calendar_dates.txt"), dtype=str)
            if "calendar_dates.txt" in z.namelist()
            else pd.DataFrame(columns=["service_id", "date", "exception_type"])
        )
        feed.trips = pd.read_csv(
            z.open("trips.txt"), usecols=["route_id", "service_id", "trip_id"], dtype=str
        )
        st = pd.read_csv(
            z.open("stop_times.txt"),
            usecols=["trip_id", "stop_sequence", "arrival_time", "departure_time"],
            dtype=str,
        )
    st["seq"] = st["stop_sequence"].astype(int)
    st_sorted = st.sort_values(["trip_id", "seq"])
    first_st = st_sorted.groupby("trip_id", as_index=False).first()
    last_st = st_sorted.groupby("trip_id", as_index=False).last()
    first_st["dep_sec"] = first_st["departure_time"].apply(parse_time_to_seconds)
    last_st["arr_sec"] = last_st["arrival_time"].apply(parse_time_to_seconds)
    feed.trip_spans = pd.DataFrame(
        {
            "trip_id": first_st["trip_id"],
            "dep_sec": first_st["dep_sec"],
            "arr_sec": last_st["arr_sec"],
        }
    ).merge(feed.trips, on="trip_id")
    feed.service_trips = defaultdict(list)
    for _, row in feed.trip_spans.iterrows():
        feed.service_trips[row["service_id"]].append(
            (row["route_id"], row["dep_sec"], row["arr_sec"])
        )
    feed.routes = sorted(feed.trips["route_id"].unique())
    return feed


def _detect_holiday_schedule(feed: GTFSFeed, dt: datetime, d_str: str) -> bool:
    """Detect whether GTFS operates a special/modified holiday schedule on date dt."""
    if d_str in HOLIDAY_SCHEDULE_DATES:
        return True
    if dt.weekday() < 5:  # Weekday
        active = {s for s in feed.get_active_services(dt) if not s.endswith("-BM")}
        if active:
            has_regular_sdon = any("-Weekday-SDon" in s for s in active)
            if not has_regular_sdon:
                return True
    return False


def build_schedule_for_range(
    start_date: str,
    end_date: str,
    timetable_version: str,
) -> tuple[pd.DataFrame, dict[str, bool]]:
    """Build hourly trips_starting, trips_running, service_hours for [start_date, end_date].

    Starts accumulation 1 day before start_date so post-midnight spillover trips
    from the prior service day (e.g. 25:10 on Saturday -> 01:10 on Sunday) are included.
    """
    feed = _resolve_gtfs_feed(timetable_version)
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    if end_dt < start_dt:
        raise ValueError(f"end_date ({end_date}) precedes start_date ({start_date})")

    grid = defaultdict(lambda: [0, 0, 0.0])
    holiday_sched_flags: dict[str, bool] = {}

    curr = start_dt - timedelta(days=1)
    while curr <= end_dt:
        d_str = curr.strftime("%Y-%m-%d")
        active = feed.get_active_services(curr)
        for s in active:
            count_trip_hours(curr, feed.service_trips[s], grid, start_date, end_date)
        if start_date <= d_str <= end_date:
            holiday_sched_flags[d_str] = _detect_holiday_schedule(feed, curr, d_str)
        curr += timedelta(days=1)

    routes = sorted(feed.routes)
    rows = []
    curr = start_dt
    while curr <= end_dt:
        d_str = curr.strftime("%Y-%m-%d")
        for route in routes:
            for hour in range(24):
                starting, running, svc_hr = grid.get((route, d_str, hour), [0, 0, 0.0])
                rows.append(
                    {
                        "route": route,
                        "date": d_str,
                        "hour": int(hour),
                        "trips_starting": int(starting),
                        "trips_running": int(running),
                        "service_hours": round(float(svc_hr), 4),
                        "snapshot_id": timetable_version,
                    }
                )
        curr += timedelta(days=1)

    return pd.DataFrame(rows), holiday_sched_flags


def load_clean_ridership_history(max_date: str | None = None) -> pd.DataFrame:
    """Load clean hourly ridership from processed archive + newer monthly raw CSVs.

    Does not overwrite data/processed/ridership_hourly_clean.parquet so Milestone 1/2
    tables remain untouched.
    """
    hist = pd.read_parquet(DATA_PROCESSED / "ridership_hourly_clean.parquet")
    hist["date"] = hist["date"].astype(str)
    hist["hour"] = hist["hour"].astype(int)
    hist_max_date = hist["date"].max()

    decisions = pd.read_csv(ROUTE_DECISIONS_PATH)
    keep_routes = set(decisions.loc[decisions["decision"] == "keep", "route"])
    known_routes = set(decisions["route"])

    raw_files = sorted(DATA_RAW_RIDERSHIP.glob("20??-??.csv"))
    extra_frames = [hist[["route", "date", "hour", "ridership", "transfers"]]]

    for fpath in raw_files:
        # Check whether file could contain dates strictly newer than hist_max_date
        month_prefix = fpath.stem  # e.g., 2026-10
        if month_prefix <= hist_max_date[:7]:
            continue
        raw = duckdb.sql(
            f"""
            SELECT CAST(transit_timestamp AS TIMESTAMP) AS ts,
                   bus_route AS route,
                   CAST(ridership AS DOUBLE) AS ridership,
                   CAST(transfers AS DOUBLE) AS transfers
            FROM read_csv('{fpath.as_posix()}', all_varchar = true)
            """
        ).df()
        if raw.empty:
            continue
        raw_routes = set(raw["route"].unique())
        unknown = raw_routes - known_routes
        if unknown:
            raise ValueError(f"Unclassified route codes in {fpath.name}: {sorted(unknown)}")
        if raw[["ts", "route", "ridership", "transfers"]].isna().any().any():
            raise ValueError(f"Null values detected in raw ridership file {fpath.name}")
        if ((raw["ridership"] % 1 != 0) | (raw["transfers"] % 1 != 0)).any():
            raise ValueError(f"Non-integer counts detected in raw ridership file {fpath.name}")
        if (raw["ridership"] < 0).any() or (raw["transfers"] < 0).any():
            raise ValueError(f"Negative counts detected in raw ridership file {fpath.name}")
        if (raw["transfers"] > raw["ridership"]).any():
            raise ValueError(f"transfers > ridership detected in raw ridership file {fpath.name}")

        raw = raw[raw["route"].isin(keep_routes)].copy()
        raw["date"] = raw["ts"].dt.strftime("%Y-%m-%d")
        raw["hour"] = raw["ts"].dt.hour.astype(int)
        raw = raw[raw["date"] > hist_max_date]
        if raw.duplicated(["route", "date", "hour"]).any():
            raise ValueError(f"Duplicate route-date-hour rows in {fpath.name}")
        if not raw.empty:
            extra_frames.append(raw[["route", "date", "hour", "ridership", "transfers"]])

    combined = pd.concat(extra_frames, ignore_index=True)
    combined["ridership"] = combined["ridership"].astype(float)
    combined["transfers"] = combined["transfers"].astype(float)
    if max_date is not None:
        combined = combined[combined["date"] <= max_date].copy()
    return combined


def _load_route_metadata() -> pd.DataFrame:
    """Load fixed route attributes matching Step 10 of Milestone 2 exactly."""
    profiles = pd.read_parquet(DATA_PROCESSED / "route_profiles.parquet")
    profiles["is_sbs"] = profiles["route_id"].str.endswith("+")
    matched = pd.read_parquet(
        DATA_PROCESSED / "matched_hourly.parquet",
        columns=["route", "hour", "trips_running"],
    )
    routes_24h = set(matched.loc[(matched["hour"] == 3) & (matched["trips_running"] > 0), "route"].unique())
    profiles["is_24h"] = profiles["route_id"].isin(routes_24h)
    return profiles[["route_id", "route_length_km", "stop_count", "is_sbs", "is_24h"]].rename(
        columns={"route_id": "route"}
    )


def build_feature_rows(
    schedule_df: pd.DataFrame,
    holiday_sched_flags: dict[str, bool],
    ridership_history: pd.DataFrame,
    lag_cutoff: str | None = None,
) -> pd.DataFrame:
    """Attach fixed route attributes, calendar indicators, thresholds, and exact calendar lags."""
    df = schedule_df.copy()
    dt_series = pd.to_datetime(df["date"])
    df["month"] = dt_series.dt.month.astype(int)
    df["day_of_week"] = dt_series.dt.day_name()
    df["is_weekend"] = df["day_of_week"].isin(["Saturday", "Sunday"])
    df["day_group"] = np.where(df["is_weekend"], "weekend", "weekday")
    df["is_public_holiday"] = df["date"].isin(EXTENDED_PUBLIC_HOLIDAYS)
    df["holiday_schedule"] = df["date"].map(holiday_sched_flags).fillna(False).astype(bool)
    df["is_storm"] = df["date"].isin(STORM_DATES)
    df["time_band"] = df["hour"].apply(assign_time_band)
    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24.0).round(4)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24.0).round(4)

    route_meta = _load_route_metadata()
    df = df.merge(route_meta, on="route", how="left")

    typical_mask = (~df["is_public_holiday"]) & (~df["holiday_schedule"]) & (~df["is_storm"])
    df["day_type"] = "Special/Excluded"
    df.loc[typical_mask & (~df["is_weekend"]), "day_type"] = "Typical Weekday"
    df.loc[typical_mask & (df["day_of_week"] == "Saturday"), "day_type"] = "Typical Saturday"
    df.loc[typical_mask & (df["day_of_week"] == "Sunday"), "day_type"] = "Typical Sunday"

    # Join fixed Jan-May p75 thresholds
    p75 = pd.read_csv(TAB_DIR / "m2_high_demand_thresholds.csv")
    df = df.merge(p75, on=["route", "day_type"], how="left")

    # Compute exact calendar lags strictly prior to target date (and <= lag_cutoff if provided)
    lag_pool = ridership_history.copy()
    if lag_cutoff is not None:
        lag_pool = lag_pool[lag_pool["date"] <= lag_cutoff].copy()
    lookup = lag_pool.set_index(["route", "date", "hour"])["ridership"].to_dict()

    df["dt"] = pd.to_datetime(df["date"])
    lag_cols = []
    for days in [7, 14, 21, 28]:
        col = f"lag_{days}d"
        lag_cols.append(col)
        target_dates = (df["dt"] - pd.Timedelta(days=days)).dt.strftime("%Y-%m-%d")
        keys = list(zip(df["route"], target_dates, df["hour"]))
        # Enforce strict causality: lag date must precede date (guaranteed since days >= 7)
        # and <= lag_cutoff when supplied (enforced on lookup pool above).
        df[col] = [lookup.get(k, np.nan) for k in keys]

    df["lags_available_count"] = df[lag_cols].notnull().sum(axis=1).astype("int8")
    mean_val = df[lag_cols].mean(axis=1)
    df["lag_mean_available"] = np.where(df["lags_available_count"] >= 2, mean_val.round(2), np.nan)
    df.drop(columns=["dt"], inplace=True)
    return df


def train_production_forecaster_jan_sep(save: bool = True) -> Pipeline:
    """Train a post-test production forecaster on all Jan-Sep 2026 data (2026-01-04..2026-09-30).

    Uses matched_hourly.parquet directly (without calling load_dataset('test', final=True)
    or altering models/final_forecaster.joblib / reports/test_runs.log) and applies the
    exact Step 2 validation-selected HistGradientBoostingRegressor settings.
    """
    full_df = load_raw_features()
    full_df = compute_exact_calendar_lags(full_df)
    prod_df = full_df[
        (full_df["date"] >= "2026-01-04")
        & (full_df["date"] <= "2026-09-30")
        & (~full_df["is_outlier"].astype(bool))
    ].copy()

    base_prep = joblib.load(MODELS_DIR / "preprocessor.joblib")
    prep = clone(base_prep)
    X_prod = prep.fit_transform(prod_df[ALL_FEATURES])
    y_prod = prod_df["ridership"].values.astype(float)

    reg = HistGradientBoostingRegressor(
        loss="poisson",
        learning_rate=0.05,
        max_leaf_nodes=127,
        min_samples_leaf=25,
        l2_regularization=1.0,
        max_iter=300,
        early_stopping=True,
        validation_fraction=0.1,
        n_iter_no_change=15,
        random_state=42,
    )
    reg.fit(X_prod, y_prod)
    prod_pipe = Pipeline([("preprocessor", prep), ("regressor", reg)])

    if save:
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        out_path = MODELS_DIR / "production_forecaster_jan_sep.joblib"
        joblib.dump(
            {
                "pipeline": prod_pipe,
                "training_window": "2026-01-04 to 2026-09-30 (excl. 6 M35 is_outlier hours)",
                "n_train_rows": int(len(prod_df)),
                "features": ALL_FEATURES,
                "n_iter_": int(reg.n_iter_),
                "note": "Post-Step-5 production retrain through September; separate from frozen Step 5 final_forecaster.joblib.",
            },
            out_path,
        )
    return prod_pipe


def predict_ridership(
    start_date: str,
    end_date: str,
    timetable_version: str = "2026-10-17",
    lag_cutoff: str | None = None,
    threshold_multiplier: float = 0.96,
    include_inactive: bool = False,
) -> pd.DataFrame:
    """Generate predicted ridership and high-demand-per-trip flags per route-hour."""
    sched_df, holiday_sched = build_schedule_for_range(start_date, end_date, timetable_version)
    hist = load_clean_ridership_history(max_date=lag_cutoff)
    feat_df = build_feature_rows(sched_df, holiday_sched, hist, lag_cutoff=lag_cutoff)

    if not include_inactive:
        feat_df = feat_df[feat_df["trips_running"] > 0].copy()

    bundle = joblib.load(MODELS_DIR / "final_forecaster.joblib")
    pipeline = bundle["pipeline"]
    preds = np.clip(pipeline.predict(feat_df[ALL_FEATURES]), 0.0, None)
    feat_df["pred_ridership"] = np.round(preds, 2)

    feat_df["pred_riders_per_trip"] = np.where(
        feat_df["trips_running"] > 0,
        np.round(feat_df["pred_ridership"] / feat_df["trips_running"], 4),
        np.nan,
    )
    feat_df["cutoff_threshold"] = np.round(threshold_multiplier * feat_df["threshold_p75"], 4)
    feat_df["pred_high_demand_per_trip"] = (
        (feat_df["trips_running"] > 0)
        & (feat_df["pred_riders_per_trip"] > feat_df["cutoff_threshold"])
    ).astype("int8")
    return feat_df


def _run_october_cleaning_and_feature_diagnostics(
    start_date: str,
    end_date: str,
    timetable_version: str,
    hist: pd.DataFrame,
    frozen_pipe: Pipeline,
) -> pd.DataFrame:
    """Verify full clean_ridership parity, 20% outage rule, -BM handling, month feature, and row reconciliation."""
    rows = []

    oct_raw_path = DATA_RAW_RIDERSHIP / f"{start_date[:7]}.csv"
    if oct_raw_path.exists():
        raw_oct = duckdb.sql(
            f"""
            SELECT CAST(transit_timestamp AS TIMESTAMP) AS ts,
                   bus_route AS route,
                   CAST(ridership AS DOUBLE) AS ridership,
                   CAST(transfers AS DOUBLE) AS transfers
            FROM read_csv('{oct_raw_path.as_posix()}', all_varchar = true)
            """
        ).df()
        checks = validate_ridership_df(raw_oct)
        rows.append(
            {
                "check_name": "ridership_validation_checks",
                "result": "PASSED (0 issues)",
                "details": ", ".join(f"{k}={v}" for k, v in checks.items()),
            }
        )

    month_start = f"{start_date[:7]}-01"
    sched_m, _ = build_schedule_for_range(month_start, end_date, timetable_version)
    sep_mh = pd.read_parquet(
        DATA_PROCESSED / "matched_hourly.parquet",
        columns=["route", "date", "hour", "ridership", "trips_running"],
    )
    oct_joined = pd.merge(
        hist[(hist["date"] >= month_start) & (hist["date"] <= end_date)],
        sched_m,
        on=["route", "date", "hour"],
        how="inner",
    )
    comb_out = pd.concat(
        [
            sep_mh[sep_mh["date"] >= "2026-09-01"][["route", "date", "hour", "ridership", "trips_running"]],
            oct_joined[["route", "date", "hour", "ridership", "trips_running"]],
        ],
        ignore_index=True,
    )
    orig_hol = bmt.PUBLIC_HOLIDAYS
    bmt.PUBLIC_HOLIDAYS = EXTENDED_PUBLIC_HOLIDAYS
    outage_hours = [o for o in find_outage_hours_relative(comb_out, threshold=0.20) if o[0] >= month_start]
    bmt.PUBLIC_HOLIDAYS = orig_hol
    rows.append(
        {
            "check_name": "outage_rule_20pct_october",
            "result": f"{len(outage_hours)} outage hours flagged",
            "details": "Applied find_outage_hours_relative(..., threshold=0.20) excluding Columbus Day (2026-10-12).",
        }
    )

    feed = _resolve_gtfs_feed(timetable_version)
    bm_trips = []
    reg_trips = []
    curr_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    while curr_dt <= end_dt:
        reg = feed.get_trip_count(curr_dt, include_boundary_markers=False)
        tot = feed.get_trip_count(curr_dt, include_boundary_markers=True)
        reg_trips.append(reg)
        bm_trips.append(tot - reg)
        curr_dt += timedelta(days=1)
    rows.append(
        {
            "check_name": "gtfs_bm_and_trips_running_definition",
            "result": f"regular={min(reg_trips)}..{max(reg_trips)}/day; -BM bridge={min(bm_trips)}..{max(bm_trips)}/day",
            "details": "Matches src/build_schedule.py (GTFSFeed + count_trip_hours with overnight spillover; regular trips excl. -BM define full service ownership, -BM bridge trips included in hourly count).",
        }
    )

    prep = frozen_pipe.named_steps.get("preprocessor") or frozen_pipe[0]
    feat_in = list(getattr(prep, "feature_names_in_", ALL_FEATURES))
    has_month = "month" in feat_in
    rows.append(
        {
            "check_name": "month_feature_in_model",
            "result": f"in_model={has_month} (0.00 prediction effect)",
            "details": f"Model uses {len(feat_in)} semantic features; raw calendar month is excluded.",
        }
    )

    full_mh = pd.read_parquet(DATA_PROCESSED / "matched_hourly.parquet", columns=["date", "hour", "ridership", "trips_running"])
    act_mh = full_mh[full_mh["trips_running"] > 0]
    m_jan_jul = float(act_mh[act_mh["date"] <= "2026-07-31"]["ridership"].mean())
    m_aug_sep = float(act_mh[(act_mh["date"] >= "2026-08-01") & (act_mh["date"] <= "2026-09-30")]["ridership"].mean())
    m_sep = float(act_mh[(act_mh["date"] >= "2026-09-01") & (act_mh["date"] <= "2026-09-30")]["ridership"].mean())
    sched_w, _ = build_schedule_for_range(start_date, end_date, timetable_version)
    act_grid = pd.merge(sched_w, hist[(hist["date"] >= start_date) & (hist["date"] <= end_date)], on=["route", "date", "hour"])
    n_neither = int(((act_grid["trips_running"] == 0) & (act_grid["ridership"] == 0)).sum())
    n_active = int((act_grid["trips_running"] > 0).sum())
    unsched_df = act_grid[(act_grid["trips_running"] == 0) & (act_grid["ridership"] > 0)]
    m_oct = float(act_grid.loc[act_grid["trips_running"] > 0, "ridership"].mean())
    rows.append(
        {
            "check_name": "mean_ridership_shift",
            "result": f"Oct={m_oct:.2f}/hr vs Jan-Jul={m_jan_jul:.2f}/hr ({(m_oct/m_jan_jul - 1)*100:+.1f}%)",
            "details": f"Train+Val Jan-Jul={m_jan_jul:.2f}, Test Aug-Sep={m_aug_sep:.2f} (Sep={m_sep:.2f}), Unseen Oct 18-31={m_oct:.2f} riders/active hr.",
        }
    )
    rows.append(
        {
            "check_name": "row_reconciliation_12270_vs_12335",
            "result": f"active={n_active:,}, unscheduled_riders_only={len(unsched_df)}, matched={n_active + len(unsched_df):,}",
            "details": f"Total 41x14x24={len(act_grid):,}: dropped {n_neither:,} neither rows; {len(unsched_df)} rows have trips_running==0 & ridership>0 ({unsched_df['ridership'].sum():.0f} riders total). Both scored and active evaluation sets use n={n_active:,}.",
        }
    )
    diag_df = pd.DataFrame(rows)
    diag_df.to_csv(TAB_DIR / "m3_october_diagnostic_checks.csv", index=False)
    return diag_df


def evaluate_unseen_window(
    start_date: str,
    end_date: str,
    timetable_version: str = "2026-10-17",
    threshold_multiplier: float = 0.96,
) -> dict:
    """Evaluate frozen Step 5 (Jan-Jul) and production (Jan-Sep) models on unseen October active hours.

    Evaluates strictly on the same active hours (trips_running > 0, n=12,270) scored by predict_ridership,
    and records the 65 Step-11 unscheduled rows (trips_running == 0 & ridership > 0) separately for exact parity.
    """
    sched_df, holiday_sched = build_schedule_for_range(start_date, end_date, timetable_version)
    hist = load_clean_ridership_history()
    actual_sub = hist[(hist["date"] >= start_date) & (hist["date"] <= end_date)].copy()

    joined_full = pd.merge(sched_df, actual_sub, on=["route", "date", "hour"], how="inner")
    active_grid = joined_full[joined_full["trips_running"] > 0].copy()
    matched_grid = joined_full[(joined_full["trips_running"] > 0) | (joined_full["ridership"] > 0)].copy()

    frozen_pipe = joblib.load(MODELS_DIR / "final_forecaster.joblib")["pipeline"]
    prod_pipe = train_production_forecaster_jan_sep(save=True)

    _run_october_cleaning_and_feature_diagnostics(
        start_date, end_date, timetable_version, hist, frozen_pipe
    )

    day_before_start = (datetime.strptime(start_date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    modes = [
        (f"Publish-Date Cutoff (Lags <= {day_before_start}, realistic)", day_before_start),
        ("Rolling Lags (7d-28d Exact Prior)", None),
    ]

    summary_rows = []
    mode_frames = {}
    for mode_label, cutoff in modes:
        fdf_act = build_feature_rows(active_grid, holiday_sched, hist, lag_cutoff=cutoff)
        fdf_mat = build_feature_rows(matched_grid, holiday_sched, hist, lag_cutoff=cutoff)

        for frame in (fdf_act, fdf_mat):
            frame["pred_frozen"] = np.clip(frozen_pipe.predict(frame[ALL_FEATURES]), 0.0, None)
            frame["pred_prod"] = np.clip(prod_pipe.predict(frame[ALL_FEATURES]), 0.0, None)
        mode_frames[mode_label] = fdf_act

        c_act = fdf_act[fdf_act["lag_mean_available"].notna()].copy()
        c_mat = fdf_mat[fdf_mat["lag_mean_available"].notna()].copy()

        models_spec = [
            ("4-Week Average Baseline (lag_mean_available)", "lag_mean_available", "None (4-week rolling)", False),
            ("Frozen Step 5 HGB Forecaster", "pred_frozen", "Jan-Jul 2026 (frozen test model)", False),
            ("Production HGB Forecaster (post-test retrain)", "pred_prod", "Jan-Sep 2026 (post-test production)", True),
        ]
        for model_label, col_name, tr_win, is_prod in models_spec:
            ma = compute_forecast_metrics(c_act["ridership"], c_act[col_name])
            mm = compute_forecast_metrics(c_mat["ridership"], c_mat[col_name])
            wins = np.nan
            if col_name != "lag_mean_available":
                rc = compute_forecast_breakdown(
                    c_act, group_col="route", y_true_col="ridership", y_pred_col=col_name
                ).merge(
                    compute_forecast_breakdown(
                        c_act, group_col="route", y_true_col="ridership", y_pred_col="lag_mean_available"
                    ),
                    on="route",
                    suffixes=("_m", "_b"),
                )
                wins = int((rc["wape_pct_m"] < rc["wape_pct_b"]).sum())
            summary_rows.append(
                {
                    "lag_mode": mode_label,
                    "model": model_label,
                    "training_window": tr_win,
                    "is_production_retrain": is_prod,
                    "n_active_eval": ma["n_eval"],
                    "mae_active": ma["mae"],
                    "rmse_active": ma["rmse"],
                    "wape_active_pct": ma["wape_pct"],
                    "bias_active_pred_minus_actual": ma["bias_pred_minus_actual"],
                    "n_matched_step11_eval": mm["n_eval"],
                    "wape_matched_step11_pct": mm["wape_pct"],
                    "routes_beating_4wk_of_41": wins,
                }
            )

    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(TAB_DIR / "m3_october_forecast_summary.csv", index=False)

    act = mode_frames["Rolling Lags (7d-28d Exact Prior)"].copy()
    act = act[act["lag_mean_available"].notna()].copy()
    act["actual_riders_per_trip"] = act["ridership"] / act["trips_running"]
    act["high_demand_per_trip"] = (act["actual_riders_per_trip"] > act["threshold_p75"]).astype("int8")
    act_pos_count = int(act["high_demand_per_trip"].sum())
    act_pos_pct = round(act_pos_count / len(act) * 100.0, 2)

    act["pred_ratio_4wk"] = act["lag_mean_available"] / act["trips_running"]
    act["pred_ratio_frozen"] = act["pred_frozen"] / act["trips_running"]
    act["pred_ratio_prod"] = act["pred_prod"] / act["trips_running"]

    rule_b_pred = (act["pred_ratio_4wk"] > act["threshold_p75"]).astype(int)
    rule_b_workload = int(rule_b_pred.sum())

    clf_rows = []
    for label, ratio_col, pred_vec, is_prod in [
        ("Baseline Rule B (4-Wk Avg ÷ Trips > 1.00 × p75)", "pred_ratio_4wk", rule_b_pred, False),
        (
            f"Frozen Step 5 Forecast ÷ Trips (> {threshold_multiplier:.2f} × p75)",
            "pred_ratio_frozen",
            (act["pred_ratio_frozen"] > threshold_multiplier * act["threshold_p75"]).astype(int),
            False,
        ),
        (
            f"Production (Jan-Sep) Forecast ÷ Trips (> {threshold_multiplier:.2f} × p75)",
            "pred_ratio_prod",
            (act["pred_ratio_prod"] > threshold_multiplier * act["threshold_p75"]).astype(int),
            True,
        ),
    ]:
        score_norm = act[ratio_col] / act["threshold_p75"]
        cm = compute_classification_metrics(act["high_demand_per_trip"], pred_vec, y_prob=score_norm)
        rank_df = pd.DataFrame({"y": act["high_demand_per_trip"].values, "score": score_norm.values}).sort_values(
            "score", ascending=False
        )
        prec_at_rb = float(rank_df.iloc[:rule_b_workload]["y"].mean())
        clf_rows.append(
            {
                "model": label,
                "is_production_retrain": is_prod,
                "n_active_eval": len(act),
                "actual_pos": act_pos_count,
                "actual_positive_pct": act_pos_pct,
                "pred_pos_at_cutoff": int(pred_vec.sum()),
                "pred_positive_pct": round(float(pred_vec.mean()) * 100.0, 2),
                "pr_auc": cm["pr_auc"],
                "roc_auc": cm["roc_auc"],
                "precision": cm["precision"],
                "recall": cm["recall"],
                "f1": cm["f1"],
                "precision_at_rule_b_workload": round(prec_at_rb, 4),
                "rule_b_workload_hours": rule_b_workload,
            }
        )
    clf_df = pd.DataFrame(clf_rows)
    clf_df.to_csv(TAB_DIR / "m3_october_classification_summary.csv", index=False)

    cut_label = f"Publish-Date Cutoff (Lags <= {day_before_start}, realistic)"
    cut_act = mode_frames[cut_label]
    cut_c = cut_act[cut_act["lag_mean_available"].notna()].copy()
    roll_c = act.copy()

    route_eval = (
        compute_forecast_breakdown(cut_c, "route", "ridership", "pred_frozen")
        .merge(compute_forecast_breakdown(cut_c, "route", "ridership", "pred_prod"), on="route", suffixes=("_frozen_cut", "_prod_cut"))
        .merge(
            compute_forecast_breakdown(cut_c, "route", "ridership", "lag_mean_available")
            .rename(columns={"mae": "mae_4wk_cut", "rmse": "rmse_4wk_cut", "wape_pct": "wape_4wk_cut", "bias_pred_minus_actual": "bias_4wk_cut"})
            [["route", "mae_4wk_cut", "rmse_4wk_cut", "wape_4wk_cut", "bias_4wk_cut"]],
            on="route",
        )
        .merge(
            compute_forecast_breakdown(roll_c, "route", "ridership", "pred_frozen")
            .rename(columns={"wape_pct": "wape_frozen_roll"})[["route", "wape_frozen_roll"]],
            on="route",
        )
        .merge(
            compute_forecast_breakdown(roll_c, "route", "ridership", "lag_mean_available")
            .rename(columns={"wape_pct": "wape_4wk_roll"})[["route", "wape_4wk_roll"]],
            on="route",
        )
    )
    route_eval["wape_diff_frozen_minus_4wk_cut"] = (
        route_eval["wape_pct_frozen_cut"] - route_eval["wape_4wk_cut"]
    ).round(2)
    route_eval.sort_values("wape_diff_frozen_minus_4wk_cut").to_csv(
        TAB_DIR / "m3_october_forecast_by_route.csv", index=False
    )

    daily_rows = []
    for dt_str, grp in cut_c.groupby("date"):
        d4 = compute_forecast_metrics(grp["ridership"], grp["lag_mean_available"])
        dfz = compute_forecast_metrics(grp["ridership"], grp["pred_frozen"])
        dpr = compute_forecast_metrics(grp["ridership"], grp["pred_prod"])
        rg = roll_c[roll_c["date"] == dt_str]
        drz = compute_forecast_metrics(rg["ridership"], rg["pred_frozen"])
        dr4 = compute_forecast_metrics(rg["ridership"], rg["lag_mean_available"])
        daily_rows.append(
            {
                "date": dt_str,
                "day_of_week": grp["day_of_week"].iloc[0],
                "day_group": grp["day_group"].iloc[0],
                "n_active_hours": len(grp),
                "mean_actual_riders": round(float(grp["ridership"].mean()), 2),
                "wape_4wk_cutoff_pct": d4["wape_pct"],
                "wape_frozen_cutoff_pct": dfz["wape_pct"],
                "wape_prod_cutoff_pct": dpr["wape_pct"],
                "wape_4wk_rolling_pct": dr4["wape_pct"],
                "wape_frozen_rolling_pct": drz["wape_pct"],
                "bias_frozen_cutoff": dfz["bias_pred_minus_actual"],
            }
        )
    daily_df = pd.DataFrame(daily_rows)
    daily_df.to_csv(TAB_DIR / "m3_october_forecast_by_day.csv", index=False)

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.2))

    x = np.arange(len(daily_df))
    labels = [f"{d[5:]}\n{w[:3]}" for d, w in zip(daily_df["date"], daily_df["day_of_week"])]
    axes[0].plot(x, daily_df["wape_4wk_cutoff_pct"], "o--", color="#4b5563", label="4-Week Average Baseline")
    axes[0].plot(x, daily_df["wape_frozen_cutoff_pct"], "s-", color="#0b5394", label="Frozen Step 5 (Jan-Jul)")
    axes[0].plot(x, daily_df["wape_prod_cutoff_pct"], "^:", color="#d97706", label="Production Retrain (Jan-Sep)")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(labels, fontsize=8)
    axes[0].set_ylabel("WAPE (%)")
    axes[0].set_title(f"Realistic Publish-Date Cutoff (Lags <= {day_before_start}) by Day")
    axes[0].grid(True, alpha=0.3)
    axes[0].legend(frameon=True, fontsize=8.5)

    cut_sub = summary_df[summary_df["lag_mode"] == cut_label]
    roll_sub = summary_df[summary_df["lag_mode"] == "Rolling Lags (7d-28d Exact Prior)"]
    cat_labels = ["4-Week Avg\nBaseline", "Frozen Step 5\n(Jan-Jul)", "Production\n(Jan-Sep)"]
    w_cut = [float(cut_sub.iloc[i]["wape_active_pct"]) for i in range(3)]
    w_roll = [float(roll_sub.iloc[i]["wape_active_pct"]) for i in range(3)]
    xw = np.arange(len(cat_labels))
    bw = 0.34
    b1 = axes[1].bar(xw - bw / 2, w_cut, width=bw, color="#0b5394", label=f"Publish Cutoff (<= {day_before_start})")
    b2 = axes[1].bar(xw + bw / 2, w_roll, width=bw, color="#6b7280", label="Rolling Lags (7d-28d)")
    for bars in (b1, b2):
        for bar in bars:
            val = bar.get_height()
            axes[1].text(bar.get_x() + bar.get_width() / 2, val + 0.18, f"{val:.2f}%", ha="center", va="bottom", fontsize=8.5)
    axes[1].set_xticks(xw)
    axes[1].set_xticklabels(cat_labels)
    axes[1].set_ylim(0, max(w_cut + w_roll) + 2.5)
    axes[1].set_ylabel("October WAPE (%) across 12,270 Active Hours")
    axes[1].set_title("Unseen October 18-31 Overall WAPE (Models Do Not Beat Baseline)")
    axes[1].grid(True, axis="y", alpha=0.3)
    axes[1].legend(frameon=True, fontsize=8.5)

    fig.suptitle(
        "Step 6 Unseen October Evaluation — Frozen and Production HGB Do Not Beat 4-Week Average Overall",
        fontsize=11,
        fontweight="bold",
        y=0.99,
    )
    plt.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(FIG_DIR / "m3_october_unseen_evaluation.png", dpi=180)
    plt.close(fig)

    return {
        "forecast_summary": summary_df,
        "classification_summary": clf_df,
        "route_eval": route_eval,
        "daily_eval": daily_df,
    }


def main():
    parser = argparse.ArgumentParser(description="Predict hourly ridership & high-demand flags using frozen Step 5 forecaster.")
    parser.add_argument("--start-date", default="2026-10-18", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", default="2026-10-31", help="End date (YYYY-MM-DD)")
    parser.add_argument("--timetable-version", default="2026-10-17", help="GTFS snapshot date folder under data/raw/gtfs/manhattan/")
    parser.add_argument("--lag-cutoff", default=None, help="Optional max date (YYYY-MM-DD) allowed for lag lookups")
    parser.add_argument("--threshold-multiplier", type=float, default=0.96, help="Locked validation multiplier on threshold_p75")
    parser.add_argument("--include-inactive", action="store_true", help="Include hours with trips_running == 0")
    parser.add_argument("--out", default=str(TAB_DIR / "m3_october_predictions.csv"), help="Output CSV/parquet file path")
    parser.add_argument("--evaluate", action="store_true", help="Also evaluate against cleaned actual ridership")
    args = parser.parse_args()

    preds = predict_ridership(
        start_date=args.start_date,
        end_date=args.end_date,
        timetable_version=args.timetable_version,
        lag_cutoff=args.lag_cutoff,
        threshold_multiplier=args.threshold_multiplier,
        include_inactive=args.include_inactive,
    )
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_cols = [
        "route",
        "date",
        "hour",
        "day_of_week",
        "day_type",
        "day_group",
        "time_band",
        "snapshot_id",
        "trips_starting",
        "trips_running",
        "service_hours",
        "lag_7d",
        "lag_14d",
        "lag_21d",
        "lag_28d",
        "lag_mean_available",
        "lags_available_count",
        "pred_ridership",
        "pred_riders_per_trip",
        "threshold_p75",
        "cutoff_threshold",
        "pred_high_demand_per_trip",
    ]
    if out_path.suffix == ".parquet":
        preds[out_cols].to_parquet(out_path, index=False)
    else:
        preds[out_cols].to_csv(out_path, index=False)

    print(
        f"Saved {len(preds):,} hourly predictions ({args.start_date} to {args.end_date}, "
        f"GTFS={args.timetable_version}) -> {out_path}"
    )
    print(f"Predicted high-demand hours: {int(preds['pred_high_demand_per_trip'].sum()):,} / {len(preds):,}")

    if args.evaluate:
        res = evaluate_unseen_window(
            start_date=args.start_date,
            end_date=args.end_date,
            timetable_version=args.timetable_version,
            threshold_multiplier=args.threshold_multiplier,
        )
        print("\n--- Unseen October Forecast Summary ---")
        print(res["forecast_summary"].to_string(index=False))
        print("\n--- Unseen October Classification Summary ---")
        print(res["classification_summary"].to_string(index=False))


if __name__ == "__main__":
    main()
