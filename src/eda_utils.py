"""
Milestone 2: Exploratory Data Analysis Utilities
Shared definitions, typical day filtering, and calculation helpers.
"""

from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "processed"
FIG_DIR = ROOT / "reports" / "figures"
TAB_DIR = ROOT / "reports" / "tables"

# Single centralized definition of transit time bands matching Milestone 1 (src/build_matched_table.py)
TIME_BANDS = {
    "early_morning": {
        "hours": [4, 5, 6],
        "label": "Early Morning (04:00–06:59)",
    },
    "morning_peak": {
        "hours": [7, 8, 9],
        "label": "Morning Peak (07:00–09:59)",
    },
    "midday": {
        "hours": [10, 11, 12, 13, 14, 15],
        "label": "Midday (10:00–15:59)",
    },
    "evening_peak": {
        "hours": [16, 17, 18],
        "label": "Evening Peak (16:00–18:59)",
    },
    "night": {
        "hours": [19, 20, 21, 22, 23, 0, 1, 2, 3],
        "label": "Night (19:00–03:59)",
    },
}
TIME_BAND_ORDER = list(TIME_BANDS.keys())


def get_time_band_label(time_band: str) -> str:
    """Return descriptive time band label with exact hours from Milestone 1."""
    if time_band in TIME_BANDS:
        return TIME_BANDS[time_band]["label"]
    return time_band

DAY_TYPE_COLORS = {
    "weekday": "#1d4ed8",   # Blue
    "saturday": "#ea580c",  # Orange
    "sunday": "#16a34a",    # Green
}


def typical_days(df: pd.DataFrame, day_type: str) -> pd.DataFrame:
    """Filter dataset to typical days.
    day_type: 'weekday', 'saturday', or 'sunday'.
    Excludes public holidays, holiday schedules, storm disruptions, and outlier hours.
    """
    normal = (
        ~df["is_public_holiday"]
        & ~df["holiday_schedule"]
        & ~df["is_storm"]
        & ~df["is_outlier"]
    )
    if not pd.api.types.is_datetime64_any_dtype(df["date"]):
        dt_series = pd.to_datetime(df["date"])
    else:
        dt_series = df["date"]

    dow = dt_series.dt.dayofweek  # Monday = 0, Sunday = 6
    pick = {
        "weekday": dow < 5,
        "saturday": dow == 5,
        "sunday": dow == 6
    }[day_type.lower()]

    return df[normal & pick].copy()


def calc_period_ratio(riders: pd.Series, denominator: pd.Series) -> float:
    """Calculate period efficiency dividing total riders by total trips or service hours.
    Always divides totals by totals (all riders ÷ all trips/service-hours).
    """
    tot_riders = riders.sum()
    tot_denom = denominator.sum()
    return float(tot_riders / tot_denom) if tot_denom > 0 else np.nan


def calc_cv(series: pd.Series) -> float:
    """Calculate Coefficient of Variation: std / mean."""
    m = series.mean()
    s = series.std()
    return float(s / m) if (m > 0 and len(series) > 1) else np.nan
