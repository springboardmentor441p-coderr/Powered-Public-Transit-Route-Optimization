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

from src.build_matched_table import (
    HOLIDAY_SCHEDULE_DATES,
    PUBLIC_HOLIDAYS,
    STORM_DATES,
    assign_time_band,
)
from src.build_schedule import GTFSFeed, count_trip_hours
from src.evaluate import (
    compute_classification_metrics,
    compute_forecast_breakdown,
    compute_forecast_metrics,
)

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
        if (raw["ridership"] < 0).any() or (raw["transfers"] < 0).any():
            raise ValueError(f"Negative counts detected in raw ridership file {fpath.name}")

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


def evaluate_unseen_window(
    start_date: str,
    end_date: str,
    timetable_version: str = "2026-10-17",
    threshold_multiplier: float = 0.96,
) -> dict:
    """Evaluate frozen forecaster on unseen October dates against matched actual ridership.

    Matches schedule with cleaned actual ridership using Step 11 rule ((trips_running > 0) | (ridership > 0)).
    Evaluates both rolling 7-day-prior lags and strict Day-0 cutoff lags (--lag-cutoff=day_before_start).
    """
    sched_df, holiday_sched = build_schedule_for_range(start_date, end_date, timetable_version)
    hist = load_clean_ridership_history()
    actual_sub = hist[(hist["date"] >= start_date) & (hist["date"] <= end_date)].copy()

    matched_grid = pd.merge(sched_df, actual_sub, on=["route", "date", "hour"], how="inner")
    matched_grid = matched_grid[
        (matched_grid["trips_running"] > 0) | (matched_grid["ridership"] > 0)
    ].copy()

    # Mode 1: Exact rolling calendar lags (all 7/14/21/28d observed prior to date)
    feat_rolling = build_feature_rows(matched_grid, holiday_sched, hist, lag_cutoff=None)
    # Mode 2: Strict publish-date lag cutoff (day before start_date)
    day_before_start = (datetime.strptime(start_date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    feat_day0 = build_feature_rows(matched_grid, holiday_sched, hist, lag_cutoff=day_before_start)

    bundle = joblib.load(MODELS_DIR / "final_forecaster.joblib")
    pipeline = bundle["pipeline"]

    for fdf in (feat_rolling, feat_day0):
        fdf["pred_hgb"] = np.clip(pipeline.predict(fdf[ALL_FEATURES]), 0.0, None)
        fdf["actual_riders_per_trip"] = np.where(
            fdf["trips_running"] > 0, fdf["ridership"] / fdf["trips_running"], np.nan
        )
        fdf["high_demand_per_trip"] = (
            (fdf["trips_running"] > 0) & (fdf["actual_riders_per_trip"] > fdf["threshold_p75"])
        ).astype("int8")
        fdf["pred_ratio_hgb"] = np.where(
            fdf["trips_running"] > 0, fdf["pred_hgb"] / fdf["trips_running"], np.nan
        )
        fdf["pred_ratio_4wk"] = np.where(
            fdf["trips_running"] > 0, fdf["lag_mean_available"] / fdf["trips_running"], np.nan
        )

    # Evaluate forecasting on common non-null-lag rows and all matched rows
    summary_rows = []
    for mode_label, fdf in [
        ("Rolling Lags (7d–28d Exact Prior)", feat_rolling),
        (f"Publish-Date Cutoff (Lags <= {day_before_start})", feat_day0),
    ]:
        common = fdf[fdf["lag_mean_available"].notna()].copy()
        m_4wk = compute_forecast_metrics(common["ridership"], common["lag_mean_available"])
        m_hgb_c = compute_forecast_metrics(common["ridership"], common["pred_hgb"])
        m_hgb_all = compute_forecast_metrics(fdf["ridership"], fdf["pred_hgb"])

        route_comp = compute_forecast_breakdown(
            common, group_col="route", y_true_col="ridership", y_pred_col="pred_hgb", model_name="HGB"
        ).merge(
            compute_forecast_breakdown(
                common,
                group_col="route",
                y_true_col="ridership",
                y_pred_col="lag_mean_available",
                model_name="4wk",
            ),
            on="route",
            suffixes=("_hgb", "_4wk"),
        )
        hgb_route_wins = int((route_comp["wape_pct_hgb"] < route_comp["wape_pct_4wk"]).sum())

        summary_rows.append(
            {
                "lag_mode": mode_label,
                "model": "4-Week Average Baseline (lag_mean_available)",
                "n_eval_common": m_4wk["n_eval"],
                "mae_common": m_4wk["mae"],
                "rmse_common": m_4wk["rmse"],
                "wape_common_pct": m_4wk["wape_pct"],
                "bias_common_pred_minus_actual": m_4wk["bias_pred_minus_actual"],
                "n_eval_all": m_4wk["n_eval"],
                "wape_all_pct": m_4wk["wape_pct"],
                "hgb_route_wins_of_41": np.nan,
            }
        )
        summary_rows.append(
            {
                "lag_mode": mode_label,
                "model": "Frozen Step 5 HistGradientBoosting Forecaster",
                "n_eval_common": m_hgb_c["n_eval"],
                "mae_common": m_hgb_c["mae"],
                "rmse_common": m_hgb_c["rmse"],
                "wape_common_pct": m_hgb_c["wape_pct"],
                "bias_common_pred_minus_actual": m_hgb_c["bias_pred_minus_actual"],
                "n_eval_all": m_hgb_all["n_eval"],
                "wape_all_pct": m_hgb_all["wape_pct"],
                "hgb_route_wins_of_41": hgb_route_wins,
            }
        )

    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(TAB_DIR / "m3_october_forecast_summary.csv", index=False)

    # Classification evaluation on rolling active common rows using threshold-normalized margins
    act = feat_rolling[
        (feat_rolling["trips_running"] > 0) & (feat_rolling["lag_mean_available"].notna())
    ].copy()
    act["score_4wk_norm"] = act["pred_ratio_4wk"] / act["threshold_p75"]
    act["score_hgb_norm"] = act["pred_ratio_hgb"] / act["threshold_p75"]

    rule_b_pred = (act["pred_ratio_4wk"] > act["threshold_p75"]).astype(int)
    rule_b_workload = int(rule_b_pred.sum())
    clf_4wk = compute_classification_metrics(
        act["high_demand_per_trip"], rule_b_pred, y_prob=act["score_4wk_norm"]
    )
    hgb_flag = (act["pred_ratio_hgb"] > threshold_multiplier * act["threshold_p75"]).astype(int)
    clf_hgb = compute_classification_metrics(
        act["high_demand_per_trip"], hgb_flag, y_prob=act["score_hgb_norm"]
    )
    # Fair Precision @ Rule B Workload: precision in top `rule_b_workload` rows by normalized ratio
    rank_df = pd.DataFrame(
        {"y": act["high_demand_per_trip"].values, "score": act["score_hgb_norm"].values}
    ).sort_values("score", ascending=False)
    prec_at_rb = float(rank_df.iloc[:rule_b_workload]["y"].mean())

    clf_df = pd.DataFrame(
        [
            {
                "model": "Baseline Rule B (4-Wk Avg ÷ Trips > 1.00 × p75)",
                "n_active_common": len(act),
                "actual_pos": int(act["high_demand_per_trip"].sum()),
                "pred_pos_at_cutoff": int(rule_b_pred.sum()),
                "pr_auc": clf_4wk["pr_auc"],
                "roc_auc": clf_4wk["roc_auc"],
                "precision": clf_4wk["precision"],
                "recall": clf_4wk["recall"],
                "f1": clf_4wk["f1"],
                "precision_at_rule_b_workload": clf_4wk["precision"],
                "rule_b_workload_hours": rule_b_workload,
            },
            {
                "model": f"Frozen Forecast ÷ Trips (> {threshold_multiplier:.2f} × p75)",
                "n_active_common": len(act),
                "actual_pos": int(act["high_demand_per_trip"].sum()),
                "pred_pos_at_cutoff": int(hgb_flag.sum()),
                "pr_auc": clf_hgb["pr_auc"],
                "roc_auc": clf_hgb["roc_auc"],
                "precision": clf_hgb["precision"],
                "recall": clf_hgb["recall"],
                "f1": clf_hgb["f1"],
                "precision_at_rule_b_workload": round(prec_at_rb, 4),
                "rule_b_workload_hours": rule_b_workload,
            },
        ]
    )
    clf_df.to_csv(TAB_DIR / "m3_october_classification_summary.csv", index=False)

    # Save route-level and daily breakdown on rolling lags
    common_roll = feat_rolling[feat_rolling["lag_mean_available"].notna()].copy()
    route_eval = compute_forecast_breakdown(
        common_roll, group_col="route", y_true_col="ridership", y_pred_col="pred_hgb", model_name="HGB"
    ).merge(
        compute_forecast_breakdown(
            common_roll,
            group_col="route",
            y_true_col="ridership",
            y_pred_col="lag_mean_available",
            model_name="4wk",
        ),
        on="route",
        suffixes=("_hgb", "_4wk"),
    )
    route_eval["wape_diff_hgb_minus_4wk"] = (
        route_eval["wape_pct_hgb"] - route_eval["wape_pct_4wk"]
    ).round(2)
    route_eval["hgb_beats_4wk"] = route_eval["wape_pct_hgb"] < route_eval["wape_pct_4wk"]
    route_eval.sort_values("wape_diff_hgb_minus_4wk").to_csv(
        TAB_DIR / "m3_october_forecast_by_route.csv", index=False
    )

    daily_rows = []
    for dt_str, grp in common_roll.groupby("date"):
        d4 = compute_forecast_metrics(grp["ridership"], grp["lag_mean_available"])
        dh = compute_forecast_metrics(grp["ridership"], grp["pred_hgb"])
        daily_rows.append(
            {
                "date": dt_str,
                "day_of_week": grp["day_of_week"].iloc[0],
                "n_hours": len(grp),
                "mean_actual_riders": round(float(grp["ridership"].mean()), 2),
                "wape_4wk_pct": d4["wape_pct"],
                "wape_hgb_pct": dh["wape_pct"],
                "bias_4wk": d4["bias_pred_minus_actual"],
                "bias_hgb": dh["bias_pred_minus_actual"],
            }
        )
    daily_df = pd.DataFrame(daily_rows)
    daily_df.to_csv(TAB_DIR / "m3_october_forecast_by_day.csv", index=False)

    # Save figure comparing Validation -> Test -> Unseen October
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    # Panel 1: Daily WAPE across Oct 18-31
    x = np.arange(len(daily_df))
    labels = [f"{d[5:]}\n{w[:3]}" for d, w in zip(daily_df["date"], daily_df["day_of_week"])]
    axes[0].plot(x, daily_df["wape_4wk_pct"], "o--", color="#6c757d", label="4-Week Average Baseline")
    axes[0].plot(x, daily_df["wape_hgb_pct"], "s-", color="#0b5394", label="Frozen Step 5 HGB Forecaster")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(labels, fontsize=8)
    axes[0].set_ylabel("WAPE (%)")
    axes[0].set_title(f"Unseen October Daily Forecast Error ({start_date} to {end_date})")
    axes[0].grid(True, alpha=0.3)
    axes[0].legend(frameon=True)

    # Panel 2: Window progression (Val -> Test -> Unseen Oct)
    windows = ["Val\n(Jun-Jul)", "Test\n(Aug-Sep)", "Unseen Oct\n(Oct 18-31)"]
    hgb_wapes = [13.03, 14.06, float(summary_df.iloc[1]["wape_common_pct"])]
    base_wapes = [14.08, 15.41, float(summary_df.iloc[0]["wape_common_pct"])]
    xw = np.arange(len(windows))
    w = 0.34
    b1 = axes[1].bar(xw - w / 2, base_wapes, width=w, color="#6c757d", label="4-Week Average Baseline")
    b2 = axes[1].bar(xw + w / 2, hgb_wapes, width=w, color="#0b5394", label="Frozen Step 5 HGB Forecaster")
    for bars in (b1, b2):
        for bar in bars:
            val = bar.get_height()
            axes[1].text(bar.get_x() + bar.get_width() / 2, val + 0.25, f"{val:.2f}%", ha="center", va="bottom", fontsize=9)
    axes[1].set_xticks(xw)
    axes[1].set_xticklabels(windows)
    axes[1].set_ylim(0, max(base_wapes) + 3.0)
    axes[1].set_ylabel("WAPE (%)")
    axes[1].set_title("Forecast Error Progression Across Out-of-Sample Windows")
    axes[1].grid(True, axis="y", alpha=0.3)
    axes[1].legend(frameon=True)

    plt.tight_layout()
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
