"""Step 19: exact calendar-date lags, seasonal summary and calendar fields (spec 9.9.1, 9.9.3, 9.9.4, 9.10.4).

A lag of k days for (route, D) is the SAME route's rides on the calendar date D - k, found by an exact date join.
It is never "the previous row": if D - k has no record, the lag is missing. A recorded 0 is valid history.
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from .naming import LAG_EXPORT

KEY = ["route", "date"]


class DuplicateObservationError(ValueError):
    pass


def to_history(rides: pd.DataFrame) -> pd.DataFrame:
    """route (str), date (datetime64), daytype, rides (Int64); validated unique route/date (9.9.4 step 1)."""
    h = rides[["route", "date", "daytype", "rides"]].copy()
    h["date"] = pd.to_datetime(h["date"])
    h["rides"] = h["rides"].astype("Int64")
    dup = h.duplicated(KEY, keep=False)
    if dup.any():
        raise DuplicateObservationError(f"{int(dup.sum())} rows share a route/date key; validate before lags")
    return h.sort_values(KEY).reset_index(drop=True)


def add_exact_lags(history: pd.DataFrame, lags: list[int], reporting_delay_days: int) -> pd.DataFrame:
    """Add lag_<k>d_boardings for every k. A lag shorter than the reporting delay is not available at issue
    time (spec 9.10.4) and is set missing, even though the offline file contains it."""
    base = history[KEY + ["rides"]]
    out = history.copy()
    for k in lags:
        col = LAG_EXPORT[k]
        donor = base.assign(date=base["date"] + pd.Timedelta(days=k)).rename(columns={"rides": col})
        out = out.merge(donor, on=KEY, how="left", validate="one_to_one")
        if k < reporting_delay_days:
            out[col] = pd.array([pd.NA] * len(out), dtype="Int64")
    return out


def add_seasonal(df: pd.DataFrame, seasonal_lags: list[int], min_obs: int) -> pd.DataFrame:
    """seasonal_lag_observations = count of available 7/14/21/28-day lags; the mean exists only if count >= min_obs."""
    cols = [LAG_EXPORT[k] for k in seasonal_lags]
    vals = df[cols].astype("Float64")
    df["seasonal_lag_observations"] = vals.notna().sum(axis=1).astype("int64")
    mean = vals.mean(axis=1, skipna=True)
    df["past_four_same_weekdays_mean"] = mean.where(df["seasonal_lag_observations"] >= min_obs).astype("Float64")
    return df


def add_calendar(df: pd.DataFrame) -> pd.DataFrame:
    df["day_of_week"] = df["date"].dt.day_of_week.astype("int64")  # Monday 0 ... Sunday 6
    df["month"] = df["date"].dt.month.astype("int64")
    df["is_weekend"] = (df["day_of_week"] >= 5).astype("int64")
    # audit copy of the REPORTED category (target-date ridership row); not used as a predictor
    df["is_sunday_holiday_daytype"] = (df["daytype"] == "U").astype("int64")
    return df


OBSERVANCE_RULES = ("actual_date", "us_federal_observed")


def observed_date(d: date, rule: str) -> date:
    """US federal observed-holiday rule: Saturday -> Friday before, Sunday -> Monday after."""
    if rule not in OBSERVANCE_RULES:
        raise ValueError(f"unknown observance rule {rule}")
    if rule == "us_federal_observed":
        if d.weekday() == 5:
            return d - timedelta(days=1)
        if d.weekday() == 6:
            return d + timedelta(days=1)
    return d


def observed_holidays(holidays: dict[date, str], rule: str) -> dict[date, str]:
    """{actual date: name} -> {observed date: name (with the actual date noted when it moved)}."""
    out = {}
    for d, name in holidays.items():
        o = observed_date(d, rule)
        out[o] = name if o == d else f"{name} (observed; actual {d.isoformat()})"
    return out


def sunday_holiday_service_day(dates: pd.Series, holidays: set[date]) -> pd.Series:
    """Issue-time predictor: 1 on Sundays and on the fixed Sunday-service holiday list, else 0.
    Uses only the calendar date, so it is known before the day and never reads the ridership row."""
    d = pd.to_datetime(dates)
    hol = pd.to_datetime(sorted(holidays))
    return ((d.dt.day_of_week == 6) | d.isin(hol)).astype("int64")
