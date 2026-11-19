import os
import numpy as np
import pandas as pd

OUT_DIR = "data/processed/v1"


def _normalize_route_col(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["route"] = out["route"].astype(str).str.strip()
    return out


def build_exact_lags(rides_df: pd.DataFrame) -> pd.DataFrame:
    df = _normalize_route_col(rides_df)
    df["service_date"] = pd.to_datetime(df["service_date"])

    # Lookup map keyed by (route, service_date)
    lookup = df.set_index(["route", "service_date"])["rides"]

    for lag in [1, 7, 14, 21, 28]:
        lag_dates = df["service_date"] - pd.to_timedelta(lag, unit="D")
        lag_index = pd.MultiIndex.from_arrays([df["route"], lag_dates])
        df[f"lag_{lag}d_boardings"] = lookup.reindex(lag_index).values

    seasonal_cols = [
        "lag_7d_boardings",
        "lag_14d_boardings",
        "lag_21d_boardings",
        "lag_28d_boardings",
    ]
    df["seasonal_lag_observations"] = df[seasonal_cols].notna().sum(axis=1)
    df["past_four_same_weekdays_mean"] = np.where(
        df["seasonal_lag_observations"] >= 2,
        df[seasonal_cols].mean(axis=1),
        np.nan,
    )

    df["day_of_week"] = df["service_date"].dt.dayofweek
    df["month"] = df["service_date"].dt.month
    df["is_weekend"] = df["day_of_week"].isin([5, 6]).astype(int)
    df["is_sunday_holiday_daytype"] = (df["daytype"] == "U").astype(int)

    # Rename to backend/model contract names (Section 9.9.1)
    df = df.rename(
        columns={
            "service_date": "date",
            "lag_1d_boardings": "rides_1_day_before",
            "lag_7d_boardings": "rides_7_days_before",
            "lag_14d_boardings": "rides_14_days_before",
            "lag_21d_boardings": "rides_21_days_before",
            "lag_28d_boardings": "rides_28_days_before",
            "seasonal_lag_observations": "available_same_weekday_observations",
        }
    )
    return df


def assign_splits(df: pd.DataFrame, train_end: str, val_end: str) -> pd.Series:
    d = df["date"]
    return np.where(
        d <= pd.Timestamp(train_end),
        "train",
        np.where(d <= pd.Timestamp(val_end), "validation", "test"),
    )


def run():
    rides_df = pd.read_csv(
        os.path.join(OUT_DIR, "validated_daily_ridership.csv"),
        dtype={"route": str},
    )
    sched_df = pd.read_csv(
        os.path.join(OUT_DIR, "expanded_scheduled_route_day_service.csv"),
        dtype={"route": str},
    )

    rides_df = _normalize_route_col(rides_df)
    sched_df = _normalize_route_col(sched_df)
    sched_df["service_date"] = pd.to_datetime(sched_df["service_date"])

    # Compute exact lags across full history BEFORE restricting target window (Section 9.9.4)
    full_features = build_exact_lags(rides_df)

    # 1. Demand-only feature table (2024-08-01 to 2026-07-31)
    demand_only = full_features[
        (full_features["date"] >= "2024-08-01") & (full_features["date"] <= "2026-07-31")
    ].copy()
    demand_only["split"] = assign_splits(demand_only, "2026-01-31", "2026-04-30")
    demand_only.to_csv(os.path.join(OUT_DIR, "daily_forecasting_features.csv"), index=False)

    # 2. Matched demand + schedule feature table (2025-11-23 to 2026-07-31)
    matched_feat = full_features.merge(
        sched_df,
        left_on=["route", "date"],
        right_on=["route", "service_date"],
        how="inner",
    )
    matched_feat["split"] = assign_splits(matched_feat, "2026-03-31", "2026-05-31")
    matched_feat.to_csv(
        os.path.join(OUT_DIR, "expanded_demand_service_features.csv"), index=False
    )

    print(
        "Feature tables saved:",
        len(demand_only),
        "demand-only rows;",
        len(matched_feat),
        "matched rows;",
        "route 22 matched rows:",
        int((matched_feat["route"] == "22").sum()),
    )


if __name__ == "__main__":
    run()
