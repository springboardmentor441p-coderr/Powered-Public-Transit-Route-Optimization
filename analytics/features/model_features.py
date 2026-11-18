"""The ONLY place model inputs are built (notebook steps 10, 16-19). Training, evaluation and the backend replay
all call `build_features`; nobody writes a second version of these rules.

Target rows are every route/day in the FORECAST-TIME schedule: the latest archive captured strictly before the
target date (spec 9.14.3). Recorded boardings are attached afterwards; a scheduled day with no record is withheld
as "no recorded boardings", never scored as zero.

For each target (route, D), using only boardings from earlier dates:
  boardings_<k>d_ago     same route's boardings on the exact date D-k, k in 1/7/14/21/28 (missing stays missing,
                         a recorded 0 stays 0; a lag shorter than the reporting delay is not available)
  seasonal_count/mean    available 7/14/21/28-day values; the mean only when at least two exist
  boardings_28d_available / boardings_28d_filled   Option 2: fill ONLY the 28-day value with the 7/14/21 mean
  calendar facts, is_sunday_like_day (schedule-based), scheduled_trips / scheduled_hours (forecast archive)
A row is eligible only when every REQUIRED field exists; otherwise excluded_reason names the missing fields.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .naming import LAG_MODEL, LAGS, NO_ACTUAL_REASON, REQUIRED

KEY = ["route", "date"]
SEASONAL = [7, 14, 21, 28]
DONORS = [7, 14, 21]


def _ts(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s).astype("datetime64[ns]")


def issue_schedule(pairs: pd.DataFrame, schedule: pd.DataFrame, boundary_service: pd.DataFrame) -> pd.DataFrame:
    """Forecast-time schedule rows: Stage 2 rows on ordinary dates (same archive in both selections) and rows
    rebuilt from the earlier archive on boundary dates. Dates with no earlier archive have no rows."""
    p = pairs[pairs["forecast_snapshot"].notna()]
    ordinary = p.loc[~p["boundary"], ["date", "forecast_snapshot"]]
    s = schedule.merge(ordinary, on="date", how="inner", validate="many_to_one")
    if not (s["snapshot_id"] == s["forecast_snapshot"]).all():
        raise ValueError("on a non-boundary date the descriptive and forecast archives must be the same")
    b = boundary_service.merge(p.loc[p["boundary"], ["date", "forecast_snapshot"]], on="date", how="inner")
    if not (b["snapshot_id"] == b["forecast_snapshot"]).all():
        raise ValueError("boundary rows must come from the forecast archive")
    cols = ["route", "date", "scheduled_trips", "scheduled_service_hours", "snapshot_id"]
    out = pd.concat([s[cols], b[cols]], ignore_index=True).rename(
        columns={"scheduled_service_hours": "scheduled_hours", "snapshot_id": "schedule_saved"})
    out["date"] = _ts(out["date"])
    out["scheduled_trips"] = out["scheduled_trips"].astype("float64")
    out["scheduled_hours"] = out["scheduled_hours"].astype("Float64").astype("float64")  # <NA> -> NaN
    if out.duplicated(KEY).any():
        raise ValueError("each route/date must have exactly one forecast-time schedule")
    return out.sort_values(KEY).reset_index(drop=True)


def add_sunday_like(sched: pd.DataFrame, days: pd.DataFrame) -> pd.DataFrame:
    d = days[["date", "sunday_like_day"]].assign(date=_ts(days["date"]))
    out = sched.merge(d, on="date", how="left", validate="many_to_one")
    if out["sunday_like_day"].isna().any():
        raise ValueError("a scheduled date has no Sunday-like flag")
    return out


def build_features(target_rows: pd.DataFrame, history: pd.DataFrame, reporting_delay_days: int = 1,
                   seasonal_min_observations: int = 2) -> pd.DataFrame:
    """`target_rows`: route, date, scheduled_trips, scheduled_hours, sunday_like_day (known before the day).
    `history`: route, date, rides, unique per route/date (only earlier dates are ever looked up)."""
    frame = target_rows.copy()
    frame["date"] = _ts(frame["date"])
    hist = history[KEY + ["rides"]].copy()
    hist["date"] = _ts(hist["date"])
    hist["rides"] = hist["rides"].astype("Float64").astype("float64")  # a recorded 0 stays 0; <NA> -> NaN
    if hist.duplicated(KEY).any():
        raise ValueError("history must have one row per route/date")

    frame["day_of_week"] = frame["date"].dt.day_of_week.astype("int64")  # Monday 0
    frame["month"] = frame["date"].dt.month.astype("int64")
    frame["is_weekend"] = frame["day_of_week"].ge(5).astype("int64")
    frame["is_sunday_like_day"] = frame["sunday_like_day"].astype("int64")
    for k in LAGS:
        col = LAG_MODEL[k]
        earlier = hist.assign(date=hist["date"] + pd.Timedelta(days=k)).rename(columns={"rides": col})
        frame = frame.merge(earlier, on=KEY, how="left", validate="many_to_one")  # exact date, never "previous row"
        if k < reporting_delay_days:  # not yet published at the issue time (spec 9.10.4)
            frame[col] = np.nan
    seasonal = [LAG_MODEL[k] for k in SEASONAL]
    frame["seasonal_count"] = frame[seasonal].notna().sum(axis=1).astype("int64")  # counted BEFORE any filling
    frame["seasonal_mean"] = frame[seasonal].mean(axis=1).where(frame["seasonal_count"].ge(seasonal_min_observations))
    frame["boardings_28d_available"] = frame[LAG_MODEL[28]].notna().astype("int64")
    donor = frame[[LAG_MODEL[k] for k in DONORS]].mean(axis=1)  # mean of the AVAILABLE 7/14/21-day values
    frame["boardings_28d_filled"] = frame[LAG_MODEL[28]].fillna(donor)
    missing = frame[REQUIRED].isna()
    reason = missing.apply(lambda r: ", ".join(c for c in REQUIRED if r[c]), axis=1) if len(frame) else \
        pd.Series(dtype="object")
    frame["excluded_reason"] = reason.replace("", np.nan).astype("object")
    frame["eligible"] = frame["excluded_reason"].isna()
    return frame


def attach_actuals(features: pd.DataFrame, rides: pd.DataFrame) -> pd.DataFrame:
    """Attach recorded boardings and the reported daytype (reporting only). A scheduled day with no record is
    withheld as "no recorded boardings"; `forecastable` keeps the history-only status for the replay."""
    r = rides[KEY + ["rides", "daytype"]].copy()
    r["date"] = _ts(r["date"])
    r["rides"] = r["rides"].astype("Float64").astype("float64")
    out = features.merge(r, on=KEY, how="left", validate="one_to_one")
    out["forecastable"] = out["eligible"]
    no_actual = out["rides"].isna()
    out.loc[no_actual, "excluded_reason"] = out.loc[no_actual, "excluded_reason"].fillna(NO_ACTUAL_REASON)
    out["eligible"] = out["excluded_reason"].isna()
    return out


FEATURE_ROW_COLUMNS = ["route", "date", "split", "schedule_saved", "daytype", "rides", "day_of_week", "month",
                       "is_weekend", "sunday_like_day", "is_sunday_like_day",
                       *[LAG_MODEL[k] for k in LAGS], "seasonal_count", "seasonal_mean", "boardings_28d_available",
                       "boardings_28d_filled", "scheduled_trips", "scheduled_hours", "forecastable", "eligible",
                       "excluded_reason"]
