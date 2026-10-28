"""
tests/test_cleaning.py
Unit tests for data cleaning, route string integrity, duplicate handling, and zero preservation.
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = WORKSPACE_ROOT / "data" / "processed"

@pytest.fixture(scope="module")
def df_boardings():
    parquet_path = PROCESSED_DIR / "boardings_clean.parquet"
    assert parquet_path.exists(), "boardings_clean.parquet missing; run data pipeline first"
    return pd.read_parquet(parquet_path)

def test_row_count_and_completeness(df_boardings):
    assert len(df_boardings) >= 1_120_000, f"Expected >1.12M records, got {len(df_boardings)}"
    assert df_boardings["route"].isnull().sum() == 0, "Route contains nulls"
    assert df_boardings["date"].isnull().sum() == 0, "Date contains nulls"
    assert df_boardings["rides"].isnull().sum() == 0, "Rides contains nulls"

def test_route_id_string_contract(df_boardings):
    # Verify routes are strict string and preserve alphanumeric codes
    assert df_boardings["route"].dtype == object or isinstance(df_boardings["route"].iloc[0], str)
    sample_alphanumeric = ["111A", "J14", "N201", "X49"]
    existing = set(df_boardings["route"].unique())
    for code in sample_alphanumeric:
        assert code in existing, f"Alphanumeric route {code} missing from cleaned dataset"

def test_duplicate_key_uniqueness(df_boardings):
    dupes = df_boardings.duplicated(subset=["route", "date"]).sum()
    assert dupes == 0, f"Found {dupes} duplicate (route, date) records"

def test_zero_boarding_preservation(df_boardings):
    # Valid zero ridership days must be preserved, not dropped or imputed
    zeros = (df_boardings["rides"] == 0).sum()
    assert zeros == 36, f"Expected exactly 36 genuine zero-boarding records, found {zeros}"

def test_valid_daytypes(df_boardings):
    valid_dts = {"W", "A", "U"}
    actual_dts = set(df_boardings["daytype"].unique())
    assert actual_dts.issubset(valid_dts), f"Unexpected daytype values: {actual_dts - valid_dts}"

def test_non_negative_rides(df_boardings):
    assert (df_boardings["rides"] < 0).sum() == 0, "Negative ridership values found"
