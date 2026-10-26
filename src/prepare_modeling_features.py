"""
Milestone 2: Week 4 — Prepare Data for Modelling (Steps 9, 10, 11, 12)

Step 9: Model Task Definitions & Classification Label
- Forecasting target: ridership (continuous)
- Classification target: high_demand_per_trip (binary)
  Defined as riders_per_trip > 75th percentile for that route and day type,
  calculated strictly from training dates only.

Step 10: Build Feature Table
- One row per route, date, and hour from matched_hourly.parquet.
- Calendar & timetable features (known in advance).
- Fixed route features (length, stop count, SBS flag, 24-hour flag).
- Exact calendar lags: 7d, 14d, 21d, 28d; mean of available (when >= 2 present); count of available lags.
  Missing past hours left as NaN (never zero-filled). No 1-day lag in main model.

Step 11: Date Splits
- Training: 2026-01-04 to 2026-05-31
- Validation: 2026-06-01 to 2026-07-31
- Test: 2026-08-01 to 2026-09-30
- Chronological split, no row shuffling. Exclude is_outlier from training.

Step 12: Encoding and Scaling Pipeline
- Scikit-learn Pipeline with ColumnTransformer fitted strictly on training data.
- One-hot encoding for routes and day types.
- Sine and cosine encoding for clock hours.
- StandardScaler for numerical features.
- Median imputation with missing indicators for lags.
- Saved to models/preprocessor.joblib.
"""

from pathlib import Path
import numpy as np
import pandas as pd
import joblib
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler, FunctionTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

ROOT = Path(__file__).resolve().parents[1]
MATCHED_PATH = ROOT / "data" / "processed" / "matched_hourly.parquet"
PROFILES_PATH = ROOT / "data" / "processed" / "route_profiles.parquet"
MODELS_DIR = ROOT / "models"
DATA_PROCESSED_DIR = ROOT / "data" / "processed"
TAB_DIR = ROOT / "reports" / "tables"

MODELS_DIR.mkdir(parents=True, exist_ok=True)
TAB_DIR.mkdir(parents=True, exist_ok=True)


def load_raw_features():
    print("Loading matched hourly dataset and route profiles...")
    df = pd.read_parquet(MATCHED_PATH)
    profiles = pd.read_parquet(PROFILES_PATH)

    # 1. Fixed route features from route profiles
    profiles["is_sbs"] = profiles["route_id"].str.endswith("+")
    
    # 24-hour service flag: check if route operates at 03:00
    routes_24h = set(df[(df["hour"] == 3) & (df["trips_running"] > 0)]["route"].unique())
    profiles["is_24h"] = profiles["route_id"].isin(routes_24h)

    route_meta = profiles[["route_id", "route_length_km", "stop_count", "is_sbs", "is_24h"]].rename(
        columns={"route_id": "route"}
    )
    df = pd.merge(df, route_meta, on="route", how="left")

    # Add day_type categorization for Step 9 thresholding
    typical_mask = (
        (~df["is_public_holiday"])
        & (~df["holiday_schedule"])
        & (~df["is_storm"])
        & (~df["is_outlier"])
    )
    df["day_type"] = "Special/Excluded"
    df.loc[typical_mask & (~df["is_weekend"]), "day_type"] = "Typical Weekday"
    df.loc[typical_mask & (df["day_of_week"] == "Saturday"), "day_type"] = "Typical Saturday"
    df.loc[typical_mask & (df["day_of_week"] == "Sunday"), "day_type"] = "Typical Sunday"

    # Add cyclical hour features: hour_sin, hour_cos
    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24.0).round(4)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24.0).round(4)

    return df


def compute_exact_calendar_lags(df: pd.DataFrame) -> pd.DataFrame:
    """Step 10: Compute exact calendar date lags (7, 14, 21, 28 days).
    Missing or excluded past dates remain NaN.
    """
    print("Computing exact calendar date lags (7, 14, 21, 28 days)...")
    df["dt"] = pd.to_datetime(df["date"])
    
    # Create fast lookup dictionary: (route, date_str, hour) -> ridership
    lookup = df.set_index(["route", "date", "hour"])["ridership"].to_dict()

    lag_cols = []
    for days in [7, 14, 21, 28]:
        col = f"lag_{days}d"
        lag_cols.append(col)
        target_dates = (df["dt"] - pd.Timedelta(days=days)).dt.strftime("%Y-%m-%d")
        keys = list(zip(df["route"], target_dates, df["hour"]))
        df[col] = [lookup.get(k, np.nan) for k in keys]

    # Count of available lags
    df["lags_available_count"] = df[lag_cols].notnull().sum(axis=1).astype("int8")

    # Lag mean of available (when at least 2 are present)
    mean_val = df[lag_cols].mean(axis=1)
    df["lag_mean_available"] = np.where(df["lags_available_count"] >= 2, mean_val.round(2), np.nan)

    df.drop(columns=["dt"], inplace=True)
    return df


def calculate_classification_target(df: pd.DataFrame) -> pd.DataFrame:
    """Step 9: Calculate 'high demand per trip' threshold strictly from training dates.
    Threshold: 75th percentile of riders_per_trip for each (route, day_type).
    """
    print("Calculating Step 9 classification target from training dates...")
    train_dates_mask = df["date"] <= "2026-05-31"
    train_sub = df[train_dates_mask & (df["trips_running"] > 0)]

    # Compute 75th percentile per route and day_type
    p75 = train_sub.groupby(["route", "day_type"])["riders_per_trip"].quantile(0.75).reset_index()
    p75.rename(columns={"riders_per_trip": "threshold_p75"}, inplace=True)

    # Save thresholds table for report
    p75_csv = TAB_DIR / "m2_high_demand_thresholds.csv"
    p75.to_csv(p75_csv, index=False)
    print(f"Saved: {p75_csv.relative_to(ROOT)} ({len(p75)} threshold values)")

    # Merge thresholds back to complete dataset
    df = pd.merge(df, p75, on=["route", "day_type"], how="left")

    # High demand per trip label: 1 if riders_per_trip > threshold_p75, else 0
    df["high_demand_per_trip"] = (
        (df["trips_running"] > 0) & (df["riders_per_trip"] > df["threshold_p75"])
    ).astype("int8")

    return df


def split_datasets(df: pd.DataFrame):
    """Step 11: Chronological train/val/test splits."""
    print("\n--- Step 11: Date Splits ---")
    train_mask = (df["date"] >= "2026-01-04") & (df["date"] <= "2026-05-31")
    val_mask = (df["date"] >= "2026-06-01") & (df["date"] <= "2026-07-31")
    test_mask = (df["date"] >= "2026-08-01") & (df["date"] <= "2026-09-30")

    # Rows to leave out of training: is_outlier hours
    train_outliers_count = int(df[train_mask]["is_outlier"].sum())
    test_outliers_count = int(df[test_mask]["is_outlier"].sum())
    print(f"Outlier hours check: {train_outliers_count} in training window, {test_outliers_count} in test window.")
    print("Note: The M35 surge (19 Sept 14:00-19:00) falls in the test period. Leaving outliers out of training")
    print("removed 0 rows from training. In Milestone 3, test results must be reported with and without is_outlier hours.")

    train_df = df[train_mask & (~df["is_outlier"])].copy()
    val_df = df[val_mask].copy()
    test_df = df[test_mask].copy()

    split_counts = [
        {"set": "Training", "start_date": "2026-01-04", "end_date": "2026-05-31", "rows": len(train_df), "routes": train_df["route"].nunique()},
        {"set": "Validation", "start_date": "2026-06-01", "end_date": "2026-07-31", "rows": len(val_df), "routes": val_df["route"].nunique()},
        {"set": "Test", "start_date": "2026-08-01", "end_date": "2026-09-30", "rows": len(test_df), "routes": test_df["route"].nunique()},
        {"set": "Total Window", "start_date": "2026-01-04", "end_date": "2026-09-30", "rows": len(train_df) + len(val_df) + len(test_df), "routes": 41},
    ]
    split_summary = pd.DataFrame(split_counts)
    split_summary_csv = TAB_DIR / "m2_data_splits_summary.csv"
    split_summary.to_csv(split_summary_csv, index=False)
    print(f"Saved: {split_summary_csv.relative_to(ROOT)}")
    print(split_summary.to_string())

    # Calculate class balance per split for classification task (Step 9)
    balance_records = []
    for s_name, s_df in [("Training", train_df), ("Validation", val_df), ("Test", test_df)]:
        n_tot = len(s_df)
        n_pos = int((s_df["high_demand_per_trip"] == 1).sum())
        n_neg = n_tot - n_pos
        pct_pos = round((n_pos / n_tot) * 100.0, 2)
        balance_records.append({
            "split": s_name,
            "total_hours": n_tot,
            "positive_hours": n_pos,
            "negative_hours": n_neg,
            "positive_share_pct": pct_pos,
        })
    
    tot_hours = len(df)
    tot_pos = int((df["high_demand_per_trip"] == 1).sum())
    balance_records.append({
        "split": "Total Window",
        "total_hours": tot_hours,
        "positive_hours": tot_pos,
        "negative_hours": tot_hours - tot_pos,
        "positive_share_pct": round((tot_pos / tot_hours) * 100.0, 2),
    })

    balance_df = pd.DataFrame(balance_records)
    balance_csv = TAB_DIR / "m2_class_balance_per_split.csv"
    balance_df.to_csv(balance_csv, index=False)
    print(f"\nSaved class balance: {balance_csv.relative_to(ROOT)}")
    print(balance_df.to_string())

    return train_df, val_df, test_df


def build_and_save_pipeline(train_df: pd.DataFrame):
    """Step 12: Build scikit-learn Pipeline with ColumnTransformer, fitted on training data only."""
    print("\n--- Step 12: Building & Fitting Scikit-Learn Preprocessing Pipeline ---")

    # Feature subsets
    cat_cols = ["route", "day_of_week", "time_band"]
    num_scale_cols = [
        "trips_running", "trips_starting", "service_hours",
        "route_length_km", "stop_count", "hour_sin", "hour_cos"
    ]
    binary_cols = ["is_weekend", "is_public_holiday", "holiday_schedule", "is_storm", "is_sbs", "is_24h"]
    lag_cols = ["lag_7d", "lag_14d", "lag_21d", "lag_28d", "lag_mean_available", "lags_available_count"]

    all_features = cat_cols + num_scale_cols + binary_cols + lag_cols

    # Lag pipeline: median imputation with missing indicator flag + scaling
    lag_pipe = Pipeline([
        ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
        ("scaler", StandardScaler()),
    ])

    # Numeric pipeline: standard scaling
    num_pipe = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])

    # Categorical pipeline: one-hot encoding
    cat_pipe = Pipeline([
        ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
    ])

    preprocessor = ColumnTransformer(
        transformers=[
            ("cat", cat_pipe, cat_cols),
            ("num", num_pipe, num_scale_cols),
            ("binary", "passthrough", binary_cols),
            ("lags", lag_pipe, lag_cols),
        ],
        remainder="drop"
    )

    # Fit pipeline on training data features only
    X_train = train_df[all_features]
    preprocessor.fit(X_train)

    # Save fitted preprocessor
    pipe_path = MODELS_DIR / "preprocessor.joblib"
    joblib.dump(preprocessor, pipe_path)
    print(f"Saved fitted preprocessor -> {pipe_path.relative_to(ROOT)} ({pipe_path.stat().st_size:,} bytes)")

    return preprocessor, all_features


def main():
    df = load_raw_features()
    df = compute_exact_calendar_lags(df)
    df = calculate_classification_target(df)

    train_df, val_df, test_df = split_datasets(df)

    # Save feature tables to parquet
    out_all = DATA_PROCESSED_DIR / "modeling_features_all.parquet"
    out_train = DATA_PROCESSED_DIR / "train_features.parquet"
    out_val = DATA_PROCESSED_DIR / "val_features.parquet"
    out_test = DATA_PROCESSED_DIR / "test_features.parquet"

    df.to_parquet(out_all, index=False)
    train_df.to_parquet(out_train, index=False)
    val_df.to_parquet(out_val, index=False)
    test_df.to_parquet(out_test, index=False)

    print(f"\nSaved modeling datasets:")
    print(f"  All:   {out_all.relative_to(ROOT)} ({len(df):,} rows)")
    print(f"  Train: {out_train.relative_to(ROOT)} ({len(train_df):,} rows)")
    print(f"  Val:   {out_val.relative_to(ROOT)} ({len(val_df):,} rows)")
    print(f"  Test:  {out_test.relative_to(ROOT)} ({len(test_df):,} rows)")

    build_and_save_pipeline(train_df)
    print("\nFeature preparation and pipeline fitting completed successfully!")


if __name__ == "__main__":
    main()
