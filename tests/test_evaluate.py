"""
Unit tests for Milestone 3 evaluation framework (src/evaluate.py).
Tests core metrics calculation, zero-demand WAPE edge cases, test-set access enforcement,
canonical time-band breakdown labeling, and baseline hurdles.
"""

from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from src.evaluate import (
    compute_forecast_metrics,
    compute_forecast_breakdown,
    evaluate_forecasting,
    compute_classification_metrics,
    compute_classification_breakdown,
    evaluate_classification,
    format_confusion_matrix,
    load_dataset,
    TEST_LOG_PATH,
)
from src.eda_utils import TIME_BANDS, get_time_band_label

ROOT = Path(__file__).resolve().parents[1]
VAL_PATH = ROOT / "data" / "processed" / "val_features.parquet"


# ==============================================================================
# 1. FORECASTING METRICS TESTS
# ==============================================================================

def test_compute_forecast_metrics_exact():
    y_true = np.array([100.0, 200.0, 300.0])
    y_pred = np.array([110.0, 190.0, 330.0])  # errors: 10, 10, 30 -> sum = 50
    # sum_y = 600
    # MAE = 50 / 3 = 16.67
    # RMSE = sqrt((100 + 100 + 900)/3) = sqrt(1100/3) = sqrt(366.67) = 19.15
    # WAPE = 50 / 600 * 100 = 8.33%
    # Bias = (10 - 10 + 30)/3 = +10.0
    m = compute_forecast_metrics(y_true, y_pred)
    assert m["n_eval"] == 3
    assert m["total_actual"] == 600.0
    assert m["total_pred"] == 630.0
    assert m["mae"] == 16.67
    assert m["rmse"] == 19.15
    assert m["wape_pct"] == 8.33
    assert m["bias_pred_minus_actual"] == 10.0


def test_compute_forecast_metrics_handles_nans_and_empty():
    y_true = np.array([10.0, np.nan, 20.0])
    y_pred = np.array([np.nan, 15.0, 25.0])
    m = compute_forecast_metrics(y_true, y_pred)
    assert m["n_eval"] == 1
    assert m["mae"] == 5.0
    assert m["wape_pct"] == 25.0

    empty_m = compute_forecast_metrics(np.array([]), np.array([]))
    assert empty_m["n_eval"] == 0
    assert np.isnan(empty_m["mae"])


def test_wape_zero_riders_is_nan():
    """Verify that when actual ridership total is 0, WAPE is reported as NaN, never 0.0 or inf."""
    y_true = np.array([0.0, 0.0, 0.0])
    y_pred = np.array([5.0, 2.0, 1.0])
    m = compute_forecast_metrics(y_true, y_pred)
    assert m["n_eval"] == 3
    assert m["total_actual"] == 0.0
    assert np.isnan(m["wape_pct"]), "WAPE with 0 actual riders must be NaN"


def test_evaluate_forecasting_with_breakdowns_and_storms():
    df = pd.DataFrame({
        "route": ["M1", "M1", "M2", "M2"],
        "day_type": ["Typical Weekday", "Typical Weekday", "Typical Sunday", "Typical Sunday"],
        "time_band": ["morning_peak", "evening_peak", "morning_peak", "evening_peak"],
        "is_storm": [False, True, False, False],
        "ridership": [100, 50, 200, 150],
        "pred": [90, 40, 210, 160],
    })
    res = evaluate_forecasting(df, y_true_col="ridership", y_pred_col="pred", model_name="TestModel")
    assert "overall" in res
    assert "by_route" in res
    assert "by_day_type" in res
    assert "by_time_band" in res

    # Because df contains storm days, overall must contain All Hours, Without Storm Days, and Storm Days Only
    subsets = set(res["overall"]["subset"])
    assert "All Hours" in subsets
    assert "Without Storm Days" in subsets
    assert "Storm Days Only" in subsets


def test_time_band_breakdown_uses_canonical_labels():
    """Verify that time_band breakdown reads existing column and attaches Milestone 1 hour labels."""
    df = pd.DataFrame({
        "route": ["M1", "M1", "M2", "M2"],
        "day_type": ["Typical Weekday"] * 4,
        "time_band": ["early_morning", "morning_peak", "midday", "night"],
        "is_storm": [False] * 4,
        "ridership": [20, 80, 120, 30],
        "pred": [22, 75, 130, 28],
    })
    bd = compute_forecast_breakdown(df, group_col="time_band", y_true_col="ridership", y_pred_col="pred")
    assert "time_band_label" in bd.columns
    early_row = bd[bd["time_band"] == "early_morning"].iloc[0]
    assert "04:00–06:59" in early_row["time_band_label"]
    assert "Early Morning" in early_row["time_band_label"]


# ==============================================================================
# 2. CLASSIFICATION METRICS TESTS
# ==============================================================================

def test_compute_classification_metrics_exact():
    # 2 TP, 1 FP, 1 FN, 2 TN -> total 6
    # y_true = [1, 1, 1, 0, 0, 0]
    # y_pred = [1, 1, 0, 1, 0, 0]
    y_true = np.array([1, 1, 1, 0, 0, 0])
    y_pred = np.array([1, 1, 0, 1, 0, 0])
    y_prob = np.array([0.9, 0.8, 0.4, 0.7, 0.2, 0.1])

    m = compute_classification_metrics(y_true, y_pred, y_prob)
    assert m["n_eval"] == 6
    assert m["tp"] == 2
    assert m["fp"] == 1
    assert m["fn"] == 1
    assert m["tn"] == 2
    assert m["precision"] == 0.6667
    assert m["recall"] == 0.6667
    assert m["f1"] == 0.6667
    assert not np.isnan(m["pr_auc"])
    assert m["pr_auc"] > 0.5


def test_format_confusion_matrix():
    cm_dict = {"tn": 100, "fp": 10, "fn": 5, "tp": 50}
    df_cm = format_confusion_matrix(cm_dict, model_name="TestClf")
    assert df_cm.shape == (3, 5)
    assert df_cm.loc[df_cm["Actual Class"] == "Actual High Demand (1)", "Pred High (1)"].iloc[0] == 50
    assert df_cm.loc[df_cm["Actual Class"] == "Total Predicted", "Total Actual"].iloc[0] == 165


# ==============================================================================
# 3. TEST SET ACCESS ENFORCEMENT & AUDIT TRAIL
# ==============================================================================

def test_load_dataset_test_isolation_enforcement():
    """Verify that load_dataset('test') raises PermissionError without final=True,
    and succeeds with an audit log when final=True.
    """
    with pytest.raises(PermissionError) as exc_info:
        load_dataset("test")
    assert "Access to test_features.parquet is restricted" in str(exc_info.value)

    with pytest.raises(PermissionError) as exc_info_flag:
        load_dataset("test", final=False)
    assert "Access to test_features.parquet is restricted" in str(exc_info_flag.value)

    # Calling with final=True must succeed and append to test_runs.log
    test_df = load_dataset("test", final=True, caller="test_load_dataset_test_isolation_enforcement")
    assert isinstance(test_df, pd.DataFrame)
    assert len(test_df) == 53736
    assert TEST_LOG_PATH.exists()
    
    with open(TEST_LOG_PATH, "r", encoding="utf-8") as f:
        log_content = f.read()
    assert "AUDIT TEST ACCESS" in log_content
    assert "test_load_dataset_test_isolation_enforcement" in log_content


# ==============================================================================
# 4. VALIDATION SET REPRODUCTION & BASELINE HURDLES
# ==============================================================================

def test_validation_4wk_baseline_hurdle():
    """Verify that 4-week average baseline evaluated on validation matches 14.08% WAPE."""
    val_df = load_dataset("val")
    common_mask = (
        val_df["ridership"].notnull()
        & val_df["lag_7d"].notnull()
        & val_df["lag_mean_available"].notnull()
    )
    val_eval = val_df[common_mask].copy()
    assert len(val_eval) == 53585

    m_4wk = compute_forecast_metrics(val_eval["ridership"], val_eval["lag_mean_available"])
    assert m_4wk["wape_pct"] == 14.08, f"Expected 14.08% WAPE, got {m_4wk['wape_pct']}"

    m_lag7 = compute_forecast_metrics(val_eval["ridership"], val_eval["lag_7d"])
    assert m_lag7["wape_pct"] == 17.48, f"Expected 17.48% WAPE, got {m_lag7['wape_pct']}"
    assert m_4wk["wape_pct"] < m_lag7["wape_pct"]


def test_stronger_classification_baseline_hurdle():
    """Verify that the 4-week average heuristic classification rule outperforms lag_7d."""
    val_df = load_dataset("val")
    valid_mask = (
        (val_df["trips_running"] > 0)
        & val_df["threshold_p75"].notnull()
        & val_df["lag_7d"].notnull()
        & val_df["lag_mean_available"].notnull()
    )
    val_eval = val_df[valid_mask].copy()
    assert len(val_eval) == 53406

    y = val_eval["high_demand_per_trip"].values

    rpt_7d = val_eval["lag_7d"] / val_eval["trips_running"]
    pred_7d = (rpt_7d > val_eval["threshold_p75"]).astype(int)
    prob_7d = np.clip(rpt_7d / (2.0 * val_eval["threshold_p75"]), 0.0, 1.0)
    m_7d = compute_classification_metrics(y, pred_7d, prob_7d)

    rpt_4wk = val_eval["lag_mean_available"] / val_eval["trips_running"]
    pred_4wk = (rpt_4wk > val_eval["threshold_p75"]).astype(int)
    prob_4wk = np.clip(rpt_4wk / (2.0 * val_eval["threshold_p75"]), 0.0, 1.0)
    m_4wk = compute_classification_metrics(y, pred_4wk, prob_4wk)

    # 4-week rule must be strictly superior to 7-day rule on F1, Precision, and PR-AUC
    assert m_4wk["f1"] > m_7d["f1"], f"4wk F1 {m_4wk['f1']} should exceed 7d F1 {m_7d['f1']}"
    assert m_4wk["precision"] > m_7d["precision"]
    assert m_4wk["pr_auc"] > m_7d["pr_auc"]
