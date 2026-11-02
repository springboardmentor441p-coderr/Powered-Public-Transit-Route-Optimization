"""Exact-date, leakage-aware features for daily CTA route ridership."""

import pandas as pd


LAG_DAYS = (1, 7, 14, 21, 28)
SEASONAL_LAGS = (7, 14, 21, 28)
FEATURE_COLUMNS = [
    "route", "daytype", "day_of_week", "month", "is_weekend", "is_sunday_holiday",
    *(f"lag_{days}" for days in LAG_DAYS), "seasonal_lag_mean", "seasonal_lag_count",
]


def make_route_features(data: pd.DataFrame) -> pd.DataFrame:
    """Join each route's exact prior calendar dates; absent dates remain missing."""
    required = {"date", "route", "daytype", "rides"}
    if not required.issubset(data.columns):
        raise ValueError(f"Expected columns {sorted(required)}")
    frame = data.copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    if frame.duplicated(["route", "date"]).any():
        raise ValueError("Input must contain at most one observation per route/date")
    frame["day_of_week"] = frame["date"].dt.dayofweek
    frame["month"] = frame["date"].dt.month
    frame["is_weekend"] = (frame["day_of_week"] >= 5).astype("int8")
    frame["is_sunday_holiday"] = frame["daytype"].eq("U").astype("int8")

    keys = frame[["route", "date", "rides"]]
    for days in LAG_DAYS:
        lookup = keys.rename(columns={"date": "source_date", "rides": f"lag_{days}"})
        lookup["date"] = lookup["source_date"] + pd.to_timedelta(days, unit="D")
        frame = frame.merge(lookup[["route", "date", f"lag_{days}"]], on=["route", "date"], how="left", validate="one_to_one")

    seasonal = [f"lag_{days}" for days in SEASONAL_LAGS]
    frame["seasonal_lag_count"] = frame[seasonal].notna().sum(axis=1)
    frame["seasonal_lag_mean"] = frame[seasonal].mean(axis=1).where(frame["seasonal_lag_count"] >= 2)
    return frame
