"""The ONE place for feature names.

Stage 4a alignment: the mentor's notebook overrides the spec where they differ, so the MODEL names are the notebook's
(`boardings_7d_ago`, `seasonal_mean`, ...). The exported Stage 3 reference CSVs keep their spec 9.9.1 export names
(`lag_7d_boardings`, ...); `EXPORT_TO_MODEL` maps them once. `NOTEBOOK_TO_SPEC` records the spec's descriptive
names for the same fields (notebook section 4.1), for documentation and the backend.
Training, evaluation and the backend must all import from here, never re-type the names.
"""
from __future__ import annotations

import pandas as pd

LAGS = (1, 7, 14, 21, 28)
LAG_EXPORT = {k: f"lag_{k}d_boardings" for k in LAGS}  # Stage 3 export names (spec 9.9.1)
LAG_MODEL = {k: f"boardings_{k}d_ago" for k in LAGS}  # notebook names

# Stage 3 export name -> model (notebook) name
EXPORT_TO_MODEL = {
    **{LAG_EXPORT[k]: LAG_MODEL[k] for k in LAGS},
    "seasonal_lag_observations": "seasonal_count",
    "past_four_same_weekdays_mean": "seasonal_mean",
    "scheduled_service_hours": "scheduled_hours",
}

# notebook name -> spec 9.9.1 / 9.9.5 descriptive name (notebook section 4.1)
NOTEBOOK_TO_SPEC = {
    "route": "route", "day_of_week": "day_of_week", "month": "month", "is_weekend": "is_weekend",
    "is_sunday_like_day": "is_sunday_holiday_daytype (the notebook replaces it with a schedule-based flag)",
    "boardings_1d_ago": "rides_1_day_before", "boardings_7d_ago": "rides_7_days_before",
    "boardings_14d_ago": "rides_14_days_before", "boardings_21d_ago": "rides_21_days_before",
    "boardings_28d_filled": "rides_28_days_before (filled, Option 2)",
    "boardings_28d_available": "rides_28_days_before_available",
    "seasonal_count": "available_same_weekday_observations", "seasonal_mean": "past_four_same_weekdays_mean",
    "scheduled_trips": "scheduled_trips", "scheduled_hours": "scheduled_service_hours",
}

# spec 9.9.5, verbatim (documentation only; superseded by the notebook lists below)
SPEC_DEMAND_FEATURES = [
    "route", "day_of_week", "month", "is_weekend",
    "is_sunday_holiday_daytype",
    "rides_1_day_before", "rides_7_days_before", "rides_14_days_before",
    "rides_21_days_before", "rides_28_days_before",
    "available_same_weekday_observations", "past_four_same_weekdays_mean",
]

# notebook cell 45, in the notebook's order (the order affects Random Forest tie-breaking)
SUNDAY_LIKE_PREDICTOR = "is_sunday_like_day"
REQUIRED = ["boardings_1d_ago", "boardings_7d_ago", "boardings_14d_ago", "boardings_21d_ago",
            "boardings_28d_filled", "scheduled_trips", "scheduled_hours"]
DEMAND_FEATURES = ["route", "day_of_week", "month", "is_weekend", SUNDAY_LIKE_PREDICTOR,
                   "boardings_1d_ago", "boardings_7d_ago", "boardings_14d_ago", "boardings_21d_ago",
                   "boardings_28d_filled", "boardings_28d_available", "seasonal_count", "seasonal_mean"]
SERVICE_FEATURES = DEMAND_FEATURES + ["scheduled_trips", "scheduled_hours"]
TARGET = "rides"
NO_ACTUAL_REASON = "no recorded boardings"

# Audit-only calendar flag from Stage 3 (Sundays + observed federal holidays). No longer a predictor; kept so the
# report can compare it with the schedule-based flag and the reported daytype.
CALENDAR_HOLIDAY_PREDICTOR = "is_sunday_holiday_service_day"

# never predictors: same-day rides and anything derived from them, provenance, split labels, status columns
NEVER_PREDICTORS = ["rides", "daytype", "is_sunday_holiday_daytype", CALENDAR_HOLIDAY_PREDICTOR, "date",
                    "service_date", "split", "source_snapshot", "schedule_saved", "archive_available_from",
                    "duration_complete", "boardings_28d_ago", "sunday_like_day", "eligible", "forecastable",
                    "excluded_reason"]


def to_model_names(df: pd.DataFrame) -> pd.DataFrame:
    return df.rename(columns=EXPORT_TO_MODEL)


def predictor_columns(with_schedule: bool) -> list[str]:
    return list(SERVICE_FEATURES if with_schedule else DEMAND_FEATURES)
