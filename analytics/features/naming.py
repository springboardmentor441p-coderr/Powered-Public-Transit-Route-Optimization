"""The ONE place for feature names (spec 9.9.1 mapping, 9.9.5 predictor schema).

The exported reference CSVs keep their existing column names; the shared preprocessing applies this mapping once.
Training, evaluation and the backend must all import from here, never re-type the names.
"""
from __future__ import annotations

import pandas as pd

# spec 9.9.1: existing field -> model/backend name
EXPORT_TO_MODEL = {
    "lag_1d_boardings": "rides_1_day_before",
    "lag_7d_boardings": "rides_7_days_before",
    "lag_14d_boardings": "rides_14_days_before",
    "lag_21d_boardings": "rides_21_days_before",
    "lag_28d_boardings": "rides_28_days_before",
    "seasonal_lag_observations": "available_same_weekday_observations",
    "lag_28_available": "rides_28_days_before_available",
}
LAG_EXPORT = {k: f"lag_{k}d_boardings" for k in (1, 7, 14, 21, 28)}
LAG_MODEL = {k: EXPORT_TO_MODEL[c] for k, c in LAG_EXPORT.items()}

# spec 9.9.5, verbatim
SPEC_DEMAND_FEATURES = [
    "route", "day_of_week", "month", "is_weekend",
    "is_sunday_holiday_daytype",
    "rides_1_day_before", "rides_7_days_before", "rides_14_days_before",
    "rides_21_days_before", "rides_28_days_before",
    "available_same_weekday_observations", "past_four_same_weekdays_mean",
]

# Project decision (Stage 3): spec 9.9.1 says a completed target-date ridership row cannot be the source of an
# operational feature. The exported `is_sunday_holiday_daytype` comes from the target row's daytype, so it is kept
# for auditing only. The predictor in its place is built from a calendar known at issue time.
CALENDAR_HOLIDAY_PREDICTOR = "is_sunday_holiday_service_day"
DEMAND_FEATURES = [CALENDAR_HOLIDAY_PREDICTOR if f == "is_sunday_holiday_daytype" else f
                   for f in SPEC_DEMAND_FEATURES]
SERVICE_FEATURES = DEMAND_FEATURES + ["scheduled_trips", "scheduled_service_hours"]
OPTION_2_EXTRA_FEATURES = ["rides_28_days_before_available"]
TARGET = "rides"

# never predictors: same-day rides and anything derived from them, provenance, split labels (spec 9.9.5)
NEVER_PREDICTORS = ["rides", "daytype", "is_sunday_holiday_daytype", "date", "service_date", "split",
                    "source_snapshot", "archive_available_from", "duration_complete"]


def to_model_names(df: pd.DataFrame) -> pd.DataFrame:
    return df.rename(columns=EXPORT_TO_MODEL)


def predictor_columns(with_schedule: bool, policy: str) -> list[str]:
    cols = list(SERVICE_FEATURES if with_schedule else DEMAND_FEATURES)
    if policy == "option_2":
        cols += OPTION_2_EXTRA_FEATURES
    return cols
