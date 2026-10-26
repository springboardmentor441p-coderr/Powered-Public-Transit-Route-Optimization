"""
Milestone 2 Automated Test Suite
Validates all outputs, data splits, pipeline objects, and baseline benchmarks for Milestone 2.
"""

from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
MATCHED_PATH = ROOT / "data" / "processed" / "matched_hourly.parquet"
TRAIN_PATH = ROOT / "data" / "processed" / "train_features.parquet"
VAL_PATH = ROOT / "data" / "processed" / "val_features.parquet"
TEST_PATH = ROOT / "data" / "processed" / "test_features.parquet"
CLUSTERING_PATH = ROOT / "data" / "processed" / "clustering_features.parquet"
PREPROCESSOR_PATH = ROOT / "models" / "preprocessor.joblib"

FIG_DIR = ROOT / "reports" / "figures"
TAB_DIR = ROOT / "reports" / "tables"


def test_service_hours_and_matched_integrity():
    df = pd.read_parquet(MATCHED_PATH)
    assert "service_hours" in df.columns
    assert "riders_per_service_hour" in df.columns
    assert (df["service_hours"] >= 0).all()

    with_sh = df[df["service_hours"] > 0]
    expected_rpsh = (with_sh["ridership"] / with_sh["service_hours"]).round(4)
    assert np.allclose(with_sh["riders_per_service_hour"], expected_rpsh, equal_nan=True)


def test_generated_figures_and_tables_exist():
    expected_figs = [
        "m2_network_daily_ridership.png",
        "m2_network_hourly_profiles.png",
        "m2_network_monthly_ridership.png",
        "m2_heatmap_riders_weekday.png",
        "m2_heatmap_riders_saturday.png",
        "m2_heatmap_riders_sunday.png",
        "m2_heatmap_rpt_weekday.png",
        "m2_heatmap_rpt_saturday.png",
        "m2_heatmap_rpt_sunday.png",
        "m2_demand_variability.png",
        "route_overlaps.html",
    ]
    for fig in expected_figs:
        p = FIG_DIR / fig
        assert p.exists(), f"Figure missing: {fig}"
        assert p.stat().st_size > 0, f"Figure empty: {fig}"

    expected_tabs = [
        "m2_top_10_busiest_clock_hours.csv",
        "m2_route_performance_table.csv",
        "m2_route_demand_variability.csv",
        "m2_route_stop_coverage.csv",
        "m2_route_overlap_all_pairs.csv",
        "m2_top_15_route_overlaps.csv",
        "m2_low_riders_per_trip.csv",
        "m2_data_splits_summary.csv",
        "m2_clustering_features_scaled.csv",
        "m2_baseline_forecast_overall.csv",
        "m2_baseline_forecast_per_route.csv",
    ]
    for tab in expected_tabs:
        p = TAB_DIR / tab
        assert p.exists(), f"Table missing: {tab}"
        assert p.stat().st_size > 0, f"Table empty: {tab}"


def test_top_15_route_overlap_analysis():
    top15 = pd.read_csv(TAB_DIR / "m2_top_15_route_overlaps.csv")
    assert len(top15) == 15
    assert list(top15["rank"]) == list(range(1, 16))
    
    # Check that planned pairs (e.g. M101/M103, M34+/M34A+, M15/M15+) are labeled Planned Pair
    m101_m103 = top15[((top15["route_1"] == "M101") & (top15["route_2"] == "M103")) | ((top15["route_1"] == "M103") & (top15["route_2"] == "M101"))]
    assert len(m101_m103) == 1
    assert m101_m103.iloc[0]["design_classification"] == "Planned Pair"


def test_route_stop_coverage_metrics():
    cov = pd.read_csv(TAB_DIR / "m2_route_stop_coverage.csv")
    assert len(cov) == 41
    assert (cov["exclusive_stop_share"] >= 0.0).all() and (cov["exclusive_stop_share"] <= 1.0).all()

    # M35 serves Randall's Island and has 100% exclusive stops
    m35_row = cov[cov["route"] == "M35"]
    assert len(m35_row) == 1
    assert m35_row.iloc[0]["exclusive_stop_share"] == 1.0


def test_low_demand_screening_rules():
    low = pd.read_csv(TAB_DIR / "m2_low_riders_per_trip.csv")
    assert len(low) > 0
    # Must satisfy avg_trips >= 2.0 and days_count >= 20
    assert (low["avg_trips_per_day"] >= 2.0).all()
    assert (low["days_count"] >= 20).all()


def test_date_splits_and_modeling_features():
    train_df = pd.read_parquet(TRAIN_PATH)
    val_df = pd.read_parquet(VAL_PATH)
    test_df = pd.read_parquet(TEST_PATH)

    assert len(train_df) == 125445
    assert len(val_df) == 54046
    assert len(test_df) == 53736
    assert len(train_df) + len(val_df) + len(test_df) == 233227

    # Assert date bounds
    assert train_df["date"].min() == "2026-01-04" and train_df["date"].max() == "2026-05-31"
    assert val_df["date"].min() == "2026-06-01" and val_df["date"].max() == "2026-07-31"
    assert test_df["date"].min() == "2026-08-01" and test_df["date"].max() == "2026-09-30"

    # Training set must exclude is_outlier
    assert (train_df["is_outlier"] == False).all()

    # Classification label is binary (0 or 1)
    assert set(train_df["high_demand_per_trip"].unique()).issubset({0, 1})
    assert set(val_df["high_demand_per_trip"].unique()).issubset({0, 1})

    # Exact calendar lags exist
    for col in ["lag_7d", "lag_14d", "lag_21d", "lag_28d", "lag_mean_available", "lags_available_count"]:
        assert col in train_df.columns


def test_sklearn_pipeline_fitted():
    assert PREPROCESSOR_PATH.exists()
    preprocessor = joblib.load(PREPROCESSOR_PATH)
    train_df = pd.read_parquet(TRAIN_PATH).head(50)
    
    # Transform test
    transformed = preprocessor.transform(train_df)
    assert isinstance(transformed, np.ndarray)
    assert transformed.shape[0] == 50
    assert transformed.shape[1] > 0


def test_clustering_table_features():
    cf = pd.read_parquet(CLUSTERING_PATH)
    assert len(cf) == 41
    expected_features = [
        "route",
        "weekday_riders_log",
        "weekend_to_weekday_ratio",
        "morning_peak_share",
        "night_share",
        "peak_riders_per_service_hour",
        "route_length_km",
        "scheduled_speed_kmh",
        "demand_variability",
        "exclusive_stop_share",
    ]
    assert list(cf.columns) == expected_features

    # Check correlations are < 0.85
    num_cols = [c for c in expected_features if c != "route"]
    corr = cf[num_cols].corr().abs()
    np.fill_diagonal(corr.values, 0.0)
    assert (corr < 0.85).all().all(), "Clustering features must have pairwise correlation < 0.85"


def test_baseline_forecast_benchmarks():
    base = pd.read_csv(TAB_DIR / "m2_baseline_forecast_overall.csv")
    assert len(base) == 2
    row_lag7 = base[base["model_name"].str.contains("lag_7d")].iloc[0]
    row_4wk = base[base["model_name"].str.contains("lag_mean_available")].iloc[0]

    # Verify benchmark performance hurdles
    assert row_lag7["wape_pct"] < 20.0
    assert row_4wk["wape_pct"] < 15.0
    assert row_4wk["wape_pct"] < row_lag7["wape_pct"], "4-week average should beat lag-7d"
