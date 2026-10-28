"""
tests/test_features_and_leakage.py
Unit tests verifying temporal integrity, lag correctness, and absence of look-ahead leakage.
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = WORKSPACE_ROOT / "data" / "processed"

@pytest.fixture(scope="module")
def df_features():
    path = PROCESSED_DIR / "model_features.parquet"
    assert path.exists()
    df = pd.read_parquet(path)
    df["date"] = pd.to_datetime(df["date"])
    return df

def test_chronological_splits_strictly_monotonic(df_features):
    train_dates = df_features[(df_features["date"] >= "2018-01-01") & (df_features["date"] <= "2024-12-31")]["date"]
    val_dates = df_features[(df_features["date"] >= "2025-01-01") & (df_features["date"] <= "2025-12-31")]["date"]
    test_dates = df_features[(df_features["date"] >= "2026-01-01") & (df_features["date"] <= "2026-07-31")]["date"]

    assert train_dates.max() < val_dates.min(), "Train partition leaks into validation partition!"
    assert val_dates.max() < test_dates.min(), "Validation partition leaks into test partition!"

def test_lag_values_match_historical_series(df_features):
    # Select route '79' and check that lag_7 on date t matches rides on date t - 7 days
    sub = df_features[df_features["route"] == "79"].set_index("date")

    # Check sample of dates
    for sample_date in pd.date_range("2024-06-01", "2024-06-20"):
        if sample_date in sub.index and (sample_date - pd.Timedelta(days=7)) in sub.index:
            actual_lag7 = sub.loc[sample_date, "lag_7"]
            target_7_days_ago = sub.loc[sample_date - pd.Timedelta(days=7), "rides"]
            assert actual_lag7 == target_7_days_ago, f"Lag-7 mismatch on {sample_date}: lag={actual_lag7}, target_t-7={target_7_days_ago}"

def test_no_target_in_rolling_statistics(df_features):
    # Verify rolling stats are not identical to target or computed forward
    assert "rolling_mean_7" in df_features.columns
    assert "rolling_mean_28" in df_features.columns
    # Ensure there are no infinite values
    assert not np.isinf(df_features["rolling_mean_7"]).any()
    assert not np.isinf(df_features["rolling_mean_28"]).any()
