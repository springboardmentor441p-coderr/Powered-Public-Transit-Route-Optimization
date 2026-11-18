"""Step 24: versioned feature schema (column, type, null handling, role) and missing-history classification."""
from __future__ import annotations

import pandas as pd

from .naming import CALENDAR_HOLIDAY_PREDICTOR, EXPORT_TO_MODEL, LAG_EXPORT, LAG_MODEL, NOTEBOOK_TO_SPEC

D, M = "daily_forecasting_features.csv", "expanded_demand_service_features.csv"
F = "feature_rows.csv"  # notebook population, model inputs (Stage 4a alignment)
BOTH = [D, M]

# (column, type, nullable, roles, tables, definition)
COLUMNS = [
    ("route", "string", False, ["key", "predictor"], BOTH, "Public route identifier; join key and categorical predictor (encoded in Stage 4 with unseen-route handling)"),
    ("date", "date", False, ["key", "control"], BOTH, "Target date; key and chronological control"),
    ("daytype", "category W/A/U", False, ["control"], BOTH, "Reported category from the target-date row; auditing only"),
    ("rides", "integer >= 0", False, ["target"], BOTH, "Observed target; never an input to its own row"),
    ("day_of_week", "integer 0-6", False, ["predictor"], BOTH, "Monday 0 ... Sunday 6, from the calendar date"),
    ("month", "integer 1-12", False, ["predictor"], BOTH, "Calendar month"),
    ("is_weekend", "integer 0/1", False, ["predictor"], BOTH, "1 for Saturday/Sunday, from the calendar date"),
    ("is_sunday_holiday_daytype", "integer 0/1", False, ["control"], BOTH,
     "1 if the REPORTED daytype is U. Audit only: it comes from the target-date ridership row (spec 9.9.1), so the "
     "predictor is the schedule-based is_sunday_like_day (feature_rows.csv)"),
    *[(c, "integer, nullable", True, ["predictor"], BOTH,
       f"Same route's rides on the exact calendar date D-{k}; missing if that date has no record or is not available "
       "at issue time; a recorded 0 stays 0") for k, c in LAG_EXPORT.items()],
    ("seasonal_lag_observations", "integer 0-4", False, ["predictor"], BOTH, "Count of non-missing 7/14/21/28-day lags, computed before any filling"),
    ("past_four_same_weekdays_mean", "float, nullable", True, ["predictor"], BOTH, "Mean of available seasonal lags when at least two exist"),
    ("split", "category train/validation/test", False, ["control"], BOTH, "Chronological partition (spec 9.10.3); excluded from predictors"),
    ("service_date", "date", False, ["control"], [M], "GTFS service date; must equal date"),
    ("scheduled_trips", "integer > 0", False, ["predictor"], [M], "Calendar-selected planned trips (descriptive Stage 2 selection)"),
    ("scheduled_service_hours", "float, nullable", True, ["predictor"], [M], "Sum of valid trip durations / 3600; missing is not zero"),
    ("duration_complete", "boolean", False, ["control"], [M], "All active trip durations valid; quality control"),
    ("source_snapshot", "string", False, ["control"], [M], "Archive identifier; provenance, excluded from predictors"),
    ("archive_available_from", "date", False, ["control"], [M], "Capture date + 1 day: first issue date at which the archive may be used (conservative, spec 9.14.3)"),
]
DERIVED = [  # created by the Option 1/2 reference audit (preprocess.prepare), not stored in the reference exports
    (CALENDAR_HOLIDAY_PREDICTOR, "integer 0/1", False, ["control"], ["preprocessing audit"],
     "1 on Sundays and on the observed Sunday-service holiday list (features.json). Audit only since Stage 4a: "
     "the predictor is the schedule-based is_sunday_like_day"),
    ("boardings_28d_filled", "float, nullable", True, ["control"], ["preprocessing audit (option_2)"],
     "28-day value, or the mean of available 7/14/21-day values when it is missing"),
    ("boardings_28d_available", "integer 0/1", False, ["control"], ["preprocessing audit"],
     "1 = original 28-day lag; 0 = missing (filled under option_2)"),
    ("eligible", "boolean", False, ["control"], ["preprocessing audit"], "Row passes the history policy (and schedule check if required)"),
    ("withheld_reason", "string", True, ["control"], ["preprocessing audit"], "Semicolon-separated reason codes when not eligible"),
]


# feature_rows.csv (model_features.build_features): (column, type, nullable, roles, definition)
FEATURE_ROWS = [
    ("route", "string", False, ["key", "predictor"], "Public route id; one-hot encoded in the model pipeline, unseen routes ignored"),
    ("date", "date", False, ["key", "control"], "Target date; every route/day in the forecast-time schedule"),
    ("split", "category", False, ["control"], "train <= 2026-03-31 < validation <= 2026-05-31 < test"),
    ("schedule_saved", "string", False, ["control"], "Forecast archive: latest captured strictly before the date"),
    ("daytype", "category W/A/U, nullable", True, ["control"], "Reported passenger daytype; reporting only, never a predictor"),
    ("rides", "float >= 0, nullable", True, ["target"], "Recorded boardings; missing = no record (withheld), never 0"),
    ("day_of_week", "integer 0-6", False, ["predictor"], "Monday 0"),
    ("month", "integer 1-12", False, ["predictor"], "Calendar month"),
    ("is_weekend", "integer 0/1", False, ["predictor"], "Saturday or Sunday"),
    ("sunday_like_day", "integer 0/1", False, ["control"], "Schedule flag for the date (source of is_sunday_like_day)"),
    ("is_sunday_like_day", "integer 0/1", False, ["predictor"], "1 when more than half of the date's scheduled bus trips are Sunday-only services"),
    *[(LAG_MODEL[k], "float, nullable", True, ["predictor"] if k != 28 else ["control"],
       f"Same route's boardings on the exact date D-{k}; missing stays missing, a recorded 0 stays 0")
      for k in (1, 7, 14, 21, 28)],
    ("seasonal_count", "integer 0-4", False, ["predictor"], "Available 7/14/21/28-day values, counted before filling"),
    ("seasonal_mean", "float, nullable", True, ["predictor"], "Mean of available seasonal values when at least two exist"),
    ("boardings_28d_available", "integer 0/1", False, ["predictor"], "1 = the 28-day value was recorded, 0 = filled"),
    ("boardings_28d_filled", "float, nullable", True, ["predictor"], "Option 2: 28-day value or the 7/14/21-day mean"),
    ("scheduled_trips", "float, nullable", True, ["predictor"], "Trips on the date from the forecast archive"),
    ("scheduled_hours", "float, nullable", True, ["predictor"], "Scheduled hours from the forecast archive; missing if any trip duration is invalid"),
    ("forecastable", "boolean", False, ["control"], "History/schedule rules alone pass (what a replay can know)"),
    ("eligible", "boolean", False, ["control"], "forecastable and a recorded target exists"),
    ("excluded_reason", "string, nullable", True, ["control"], "Comma-joined missing required fields, or 'no recorded boardings'"),
]


def build_schema(version: str, settings: dict, data_version: str, fingerprints: dict) -> dict:
    def entry(c):
        name, typ, nullable, roles, tables, definition = c
        return {"column": name, "model_name": EXPORT_TO_MODEL.get(name, name), "type": typ, "nullable": nullable,
                "roles": roles, "tables": tables, "definition": definition}
    return {"schema_version": version, "data_version": data_version, "settings": settings,
            "input_fingerprints": fingerprints,
            "columns": [entry(c) for c in COLUMNS], "derived_in_preprocessing": [entry(c) for c in DERIVED],
            "model_feature_rows": {"file": F, "built_by": "analytics/features/model_features.py::build_features",
                                   "columns": [{"column": c[0], "type": c[1], "nullable": c[2], "roles": c[3],
                                                "spec_name": NOTEBOOK_TO_SPEC.get(c[0]), "definition": c[4]}
                                               for c in FEATURE_ROWS]}}


def export_columns(table: str) -> list[str]:
    return [c[0] for c in COLUMNS if table in c[4]]


# ----------------------------------------------------------------------------- missing-history classification
def classify_missing_lag(route: str, lag_date, descriptive_sid, schedule_keys: set, crosswalks: dict) -> str:
    """Schedule context of an EARLIER lag date whose passenger record is absent (spec 9.6.4.3)."""
    if descriptive_sid is None or pd.isna(descriptive_sid):
        return "lag_date_before_first_archive"
    if (route, lag_date) in schedule_keys:
        return "active_service_no_passenger_record"
    if route in crosswalks[descriptive_sid]:
        return "route_in_feed_no_active_trips"
    return "route_absent_from_feed"


def lag_absence_table(table_name: str, df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (route, split), g in df.groupby(["route", "split"]):
        r = {"table": table_name, "route": route, "split": split, "target_rows": len(g)}
        for k, c in LAG_EXPORT.items():
            r[f"missing_{c}"] = int(g[c].isna().sum())
        r["seasonal_mean_missing"] = int(g["past_four_same_weekdays_mean"].isna().sum())
        rows.append(r)
    return pd.DataFrame(rows)
