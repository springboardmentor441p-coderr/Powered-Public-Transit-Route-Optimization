"""
analytics/05_feature_engineering.py
RouteRanker Data Pipeline - Step 5: Leakage-Safe Feature Engineering

Constructs strict, leakage-safe features for daily route ridership forecasting:
1. Filters to modern evaluation window (2018-01-01 to 2026-07-31).
2. Expands each route to a continuous daily date index to ensure calendar-accurate lags.
3. Computes calendar features (day_of_week, month, is_weekend, cyclical sine/cosine).
4. Generates historical backward-looking lags (lag_1, lag_7, lag_14, lag_28).
5. Generates backward rolling statistics (rolling_mean_7, rolling_std_7, rolling_mean_28)
   ensuring the current target date t is NEVER included.
6. Enriches with static GTFS route features (stops_count, weekday_trips, exclusivity_pct).
7. Exports data/processed/model_features.parquet.
"""

import pandas as pd
import numpy as np
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = WORKSPACE_ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed"

def engineer_features():
    print("=" * 60)
    print("ROUTERANKER PIPELINE: STEP 5 - LEAKAGE-SAFE FEATURE ENGINEERING")
    print("=" * 60)

    boardings_path = PROCESSED_DIR / "boardings_clean.parquet"
    if not boardings_path.exists():
        raise FileNotFoundError(f"Cleaned boardings not found at {boardings_path}. Run step 02 first.")

    df = pd.read_parquet(boardings_path)
    print(f"[INPUT] Loaded {len(df):,} cleaned boardings records.")

    # 1. Filter to modern horizon (2018-01-01 to 2026-07-31)
    df = df[df["date"] >= "2018-01-01"].copy()
    print(f"[FILTER] Restricting to 2018-2026 horizon: {len(df):,} observations.")

    # 2. Load GTFS route metadata
    service_path = PROCESSED_DIR / "route_scheduled_service.parquet"
    struct_path = PROCESSED_DIR / "route_structure.parquet"

    meta_df = pd.DataFrame()
    if service_path.exists() and struct_path.exists():
        df_serv = pd.read_parquet(service_path)[["route_id", "stops_count", "weekday_scheduled_trips", "saturday_scheduled_trips", "sunday_scheduled_trips"]]
        df_str = pd.read_parquet(struct_path)[["route_id", "exclusivity_pct"]]
        meta_df = pd.merge(df_serv, df_str, on="route_id", how="left")
        meta_df["route_id"] = meta_df["route_id"].astype(str)
        print(f"[METADATA] Loaded GTFS route features for {len(meta_df)} routes.")

    # 3. Calendar & Lag Feature Construction
    feature_dfs = []
    unique_routes = df["route"].unique()
    print(f"[PROCESSING] Constructing calendar and lag features across {len(unique_routes)} routes...")

    # Global calendar range
    full_dates = pd.date_range(start="2018-01-01", end="2026-07-31", freq="D")

    for route in unique_routes:
        sub = df[df["route"] == route].set_index("date")

        # Reindex to full daily grid to guarantee calendar lag integrity
        sub_grid = sub.reindex(full_dates)
        sub_grid["route"] = route

        # Fill daytype based on calendar day of week if missing on reindexed dates
        # 0=Mon ... 4=Fri (W), 5=Sat (A), 6=Sun (U)
        dow = sub_grid.index.dayofweek
        auto_dt = np.where(dow == 5, "A", np.where(dow == 6, "U", "W"))
        sub_grid["daytype"] = sub_grid["daytype"].fillna(pd.Series(auto_dt, index=sub_grid.index))

        # Strict backward lags on target `rides`
        # Using forward-fill on historical rides up to 3 days for missing schedule gaps in lag series
        lag_base = sub_grid["rides"].ffill(limit=3)

        sub_grid["lag_1"] = lag_base.shift(1)
        sub_grid["lag_7"] = lag_base.shift(7)
        sub_grid["lag_14"] = lag_base.shift(14)
        sub_grid["lag_28"] = lag_base.shift(28)

        # Backward-looking rolling statistics (shifted by 1 so current t is excluded)
        sub_grid["rolling_mean_7"] = lag_base.shift(1).rolling(7, min_periods=3).mean()
        sub_grid["rolling_std_7"] = lag_base.shift(1).rolling(7, min_periods=3).std().fillna(0)
        sub_grid["rolling_mean_28"] = lag_base.shift(1).rolling(28, min_periods=7).mean()

        # Only keep rows where original observed rides is present (discarding artificial grid padding)
        sub_clean = sub_grid.dropna(subset=["rides"]).reset_index()
        sub_clean.rename(columns={"index": "date"}, inplace=True)
        feature_dfs.append(sub_clean)

    all_features = pd.concat(feature_dfs, ignore_index=True)

    # 4. Enrich with Calendar & Cyclical Signals
    all_features["day_of_week"] = all_features["date"].dt.dayofweek
    all_features["is_weekend"] = all_features["day_of_week"].isin([5, 6]).astype(int)
    all_features["month"] = all_features["date"].dt.month
    all_features["day_of_month"] = all_features["date"].dt.day
    all_features["day_of_year"] = all_features["date"].dt.dayofyear
    all_features["year"] = all_features["date"].dt.year

    # Cyclical encodings
    all_features["sin_dow"] = np.sin(2 * np.pi * all_features["day_of_week"] / 7)
    all_features["cos_dow"] = np.cos(2 * np.pi * all_features["day_of_week"] / 7)
    all_features["sin_month"] = np.sin(2 * np.pi * all_features["month"] / 12)
    all_features["cos_month"] = np.cos(2 * np.pi * all_features["month"] / 12)

    # 5. Merge GTFS features
    if not meta_df.empty:
        all_features = pd.merge(all_features, meta_df, left_on="route", right_on="route_id", how="left")
        all_features.drop(columns=["route_id"], inplace=True, errors="ignore")
        # Fill non-GTFS historical routes with median values
        all_features["stops_count"] = all_features["stops_count"].fillna(all_features["stops_count"].median())
        all_features["weekday_scheduled_trips"] = all_features["weekday_scheduled_trips"].fillna(all_features["weekday_scheduled_trips"].median())
        all_features["saturday_scheduled_trips"] = all_features["saturday_scheduled_trips"].fillna(all_features["saturday_scheduled_trips"].median())
        all_features["sunday_scheduled_trips"] = all_features["sunday_scheduled_trips"].fillna(all_features["sunday_scheduled_trips"].median())
        all_features["exclusivity_pct"] = all_features["exclusivity_pct"].fillna(all_features["exclusivity_pct"].median())

    # Drop rows at the beginning of the series where lag_28 is NaN (first 28 days of 2018)
    initial_len = len(all_features)
    all_features = all_features.dropna(subset=["lag_28", "rolling_mean_28"]).reset_index(drop=True)
    print(f"[COMPLETED] Preserved {len(all_features):,} feature rows (dropped {initial_len - len(all_features)} initial warm-up rows).")

    # Export
    out_features = PROCESSED_DIR / "model_features.parquet"
    all_features.to_parquet(out_features, engine="pyarrow", index=False)
    print(f"[EXPORTED] {out_features.relative_to(WORKSPACE_ROOT)} ({out_features.stat().st_size / (1024*1024):.2f} MB)")

    return all_features

if __name__ == "__main__":
    engineer_features()
