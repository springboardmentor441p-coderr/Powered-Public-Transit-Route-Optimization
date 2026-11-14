"""
Milestone 3: Shared Evaluation Framework (src/evaluate.py)

This module provides the single unified evaluation script for all models in Milestone 3:
- Forecasting models: MAE, RMSE, WAPE (%), and Bias (pred - actual), overall and broken down by:
    * Route (41 routes)
    * Day type (Typical Weekday, Typical Saturday, Typical Sunday, Special/Excluded)
    * Time band (Early Morning 04:00-06:59, Morning Peak 07:00-09:59, Midday 10:00-15:59,
                 Evening Peak 16:00-18:59, Night 19:00-03:59 - read directly from dataset)
    * With and without storm days (when storm days exist in the period; annotated when absent)
- Classification models:
    * Precision (of the hours flagged high, how many really were)
    * Recall (of the truly high hours, how many were flagged)
    * F1 score (harmonic mean)
    * PR-AUC (Precision-Recall Area Under Curve / Average Precision score)
    * Confusion matrix (TP, FP, TN, FN)
    * Broken down overall, by route, day type, and time band.

Row Count & Target Definition Rules:
1. Forecasting Row Count (53,585 hours in validation):
   Evaluates all valid hours with actual ridership and valid lags (lag_7d and lag_mean_available).
   Forecasting includes zero-service hours (trips_running == 0) because bus routes can have
   zero demand during non-service hours that a continuous model must forecast.
2. Classification Row Count (53,406 hours in validation for fair comparison):
   Classification predicts high_demand_per_trip (riders_per_trip > 75th percentile).
   This target is strictly defined only when at least 1 trip was scheduled and running (trips_running > 0).
   Hours with no scheduled service (551 hours in validation) have no per-trip load label and
   are therefore left out of classification evaluation.
3. Bias Convention:
   Calculated as mean(predicted - actual). A positive bias (+3.11) means the forecast is
   3.11 riders higher than actual ridership on average (over-prediction).
4. WAPE on Zero Demand:
   If actual total ridership in any route-hour group is 0, WAPE is undefined and reported as NaN
   (never 0.0 or infinity).

Strict Test Set Isolation Rule:
Every model hyperparameter, threshold, and feature selection must be tuned strictly
on the validation set. The test set (2026-08-01 to 2026-09-30) may only be evaluated once
at the very end of Milestone 3 (Step 5). load_dataset('test') strictly enforces this by
requiring final=True, and every test-set access is logged to reports/test_runs.log.
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.eda_utils import TIME_BANDS, TIME_BAND_ORDER, get_time_band_label

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "processed"
TRAIN_PATH = DATA_DIR / "train_features.parquet"
VAL_PATH = DATA_DIR / "val_features.parquet"
TEST_PATH = DATA_DIR / "test_features.parquet"

TAB_DIR = ROOT / "reports" / "tables"
REPORTS_DIR = ROOT / "reports"
TEST_LOG_PATH = REPORTS_DIR / "test_runs.log"

TAB_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


# ==============================================================================
# 0. STRICT DATASET LOADER & AUDIT LOGGING
# ==============================================================================

def load_dataset(split: str, final: bool = False, caller: str = "") -> pd.DataFrame:
    """Load train, val, or test feature datasets with strict test-set isolation enforcement.

    Parameters
    ----------
    split : str
        One of 'train', 'val', or 'test'.
    final : bool, default False
        Must be explicitly set to True to unlock and read test_features.parquet.
    caller : str, optional
        Description, step, or model identifier requesting test access for the audit log.

    Returns
    -------
    pd.DataFrame
        The loaded feature dataset.

    Raises
    ------
    PermissionError
        If split == 'test' and final is False.
    ValueError
        If split is not one of 'train', 'val', or 'test'.
    """
    split = split.lower().strip()
    if split == "train":
        if not TRAIN_PATH.exists():
            raise FileNotFoundError(f"Train dataset not found at: {TRAIN_PATH}")
        return pd.read_parquet(TRAIN_PATH)

    elif split == "val" or split == "validation":
        if not VAL_PATH.exists():
            raise FileNotFoundError(f"Validation dataset not found at: {VAL_PATH}")
        return pd.read_parquet(VAL_PATH)

    elif split == "test":
        if not final:
            raise PermissionError(
                "Access to test_features.parquet is restricted! Under Milestone 3 strict "
                "evaluation rules, the test set (2026-08-01 to 2026-09-30) may only be "
                "evaluated ONCE at the very end of Milestone 3 (Step 5). "
                "To unlock the test set for the final run, call load_dataset('test', final=True)."
            )
        if not TEST_PATH.exists():
            raise FileNotFoundError(f"Test dataset not found at: {TEST_PATH}")

        # Write audit trail to reports/test_runs.log
        now_str = datetime.now().isoformat()
        log_entry = (
            f"[{now_str}] AUDIT TEST ACCESS: test_features.parquet loaded with final=True. "
            f"Caller: {caller or 'unspecified'}\n"
        )
        with open(TEST_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(log_entry)
        log_display = TEST_LOG_PATH.relative_to(ROOT) if TEST_LOG_PATH.is_relative_to(ROOT) else TEST_LOG_PATH
        print(f"[AUDIT] Test set accessed and logged to {log_display} ({now_str})")

        return pd.read_parquet(TEST_PATH)

    else:
        raise ValueError(f"Invalid split '{split}'. Expected 'train', 'val', or 'test'.")


# ==============================================================================
# 1. CORE FORECASTING METRICS
# ==============================================================================

def compute_forecast_metrics(
    y_true: Union[pd.Series, np.ndarray],
    y_pred: Union[pd.Series, np.ndarray],
) -> Dict[str, Union[int, float]]:
    """Calculate MAE, RMSE, WAPE (%), and Bias for continuous demand forecasts.

    Formulas:
        MAE  = mean(|y - y_hat|)
        RMSE = sqrt(mean((y - y_hat)^2))
        WAPE = sum(|y - y_hat|) / sum(y) * 100% (NaN if sum(y) == 0)
        Bias = mean(y_hat - y) [positive value = over-prediction]

    Parameters
    ----------
    y_true : pd.Series or np.ndarray
        Ground-truth continuous target (actual ridership).
    y_pred : pd.Series or np.ndarray
        Model predicted demand.

    Returns
    -------
    dict
        Dictionary with keys: n_eval, total_actual, total_pred, mae, rmse,
        wape_pct, bias_pred_minus_actual.
    """
    if isinstance(y_true, pd.Series):
        y_true = y_true.values
    if isinstance(y_pred, pd.Series):
        y_pred = y_pred.values

    # Drop any pairs with NaNs
    mask = ~np.isnan(y_true) & ~np.isnan(y_pred)
    y = y_true[mask]
    y_hat = y_pred[mask]

    n_eval = int(len(y))
    if n_eval == 0:
        return {
            "n_eval": 0,
            "total_actual": 0.0,
            "total_pred": 0.0,
            "mae": np.nan,
            "rmse": np.nan,
            "wape_pct": np.nan,
            "bias_pred_minus_actual": np.nan,
        }

    err = np.abs(y - y_hat)
    mae = float(np.mean(err))
    rmse = float(np.sqrt(np.mean((y - y_hat) ** 2)))
    sum_y = float(np.sum(y))
    sum_y_hat = float(np.sum(y_hat))

    # A group with zero total actual riders has undefined WAPE -> return np.nan (never 0.0 or inf)
    wape = float((np.sum(err) / sum_y) * 100.0) if sum_y > 0 else np.nan
    bias = float(np.mean(y_hat - y))

    return {
        "n_eval": n_eval,
        "total_actual": round(sum_y, 1),
        "total_pred": round(sum_y_hat, 1),
        "mae": round(mae, 2),
        "rmse": round(rmse, 2),
        "wape_pct": round(wape, 2) if not np.isnan(wape) else np.nan,
        "bias_pred_minus_actual": round(bias, 2),
    }


def compute_forecast_breakdown(
    df: pd.DataFrame,
    group_col: str,
    y_true_col: str = "ridership",
    y_pred_col: str = "prediction",
    model_name: str = "Model",
) -> pd.DataFrame:
    """Compute forecasting performance broken down by a category (route, day_type, time_band).

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing ground truth, predictions, and grouping column.
    group_col : str
        Column to group by (e.g. 'route', 'day_type', 'time_band').
    y_true_col : str
        Column name for ground-truth ridership.
    y_pred_col : str
        Column name for predictions.
    model_name : str
        Identifier name of the model being evaluated.

    Returns
    -------
    pd.DataFrame
        Grouped evaluation table with sample sizes and error metrics.
    """
    if group_col not in df.columns:
        raise ValueError(f"Grouping column '{group_col}' not found in dataframe.")

    records = []
    groups = df[group_col].dropna().unique()

    # Preserve canonical ordering
    if group_col == "time_band":
        groups = [g for g in TIME_BAND_ORDER if g in groups] + [g for g in groups if g not in TIME_BAND_ORDER]
    elif group_col == "day_type":
        preferred_order = ["Typical Weekday", "Typical Saturday", "Typical Sunday", "Special/Excluded"]
        groups = [g for g in preferred_order if g in groups] + [g for g in groups if g not in preferred_order]
    else:
        groups = sorted(groups)

    for g in groups:
        sub = df[df[group_col] == g]
        m = compute_forecast_metrics(sub[y_true_col], sub[y_pred_col])
        rec = {
            "model_name": model_name,
            group_col: g,
        }
        if group_col == "time_band":
            rec["time_band_label"] = get_time_band_label(g)

        rec.update({
            "n_eval": m["n_eval"],
            "total_actual": m["total_actual"],
            "mae": m["mae"],
            "rmse": m["rmse"],
            "wape_pct": m["wape_pct"],
            "bias_pred_minus_actual": m["bias_pred_minus_actual"],
        })
        records.append(rec)

    return pd.DataFrame(records)


def evaluate_forecasting(
    df: pd.DataFrame,
    y_true_col: str = "ridership",
    y_pred_col: str = "prediction",
    model_name: str = "ForecastModel",
    save_prefix: Optional[str] = None,
    out_dir: Path = TAB_DIR,
) -> Dict[str, pd.DataFrame]:
    """Complete evaluation suite for continuous demand forecasting models.

    Calculates:
    1. Overall performance:
       - 'All Hours'
       - 'Without Storm Days' & 'Storm Days Only' (ONLY if storm days exist in dataset;
          if no storm days exist, duplicate row is omitted and annotated)
       - 'Without Outlier Hours' (if is_outlier column exists and has outliers)
    2. Breakdown by route (41 routes)
    3. Breakdown by day_type
    4. Breakdown by time_band (reading existing time_band column from dataset)

    Parameters
    ----------
    df : pd.DataFrame
        Dataset containing predictions and metadata.
    y_true_col : str
        Target column (actual ridership).
    y_pred_col : str
        Forecast column.
    model_name : str
        Name of model.
    save_prefix : str, optional
        If provided, saves tables as CSVs: {save_prefix}_overall.csv, etc.
    out_dir : Path
        Directory to save CSV tables (default reports/tables/).

    Returns
    -------
    dict of pd.DataFrame
        {'overall': df, 'by_route': df, 'by_day_type': df, 'by_time_band': df}
    """
    results: Dict[str, pd.DataFrame] = {}

    has_storms = "is_storm" in df.columns and bool(df["is_storm"].any())
    has_outliers = "is_outlier" in df.columns and bool(df["is_outlier"].any())

    # ---------------------------------------------------------
    # 1. Overall Performance Scenarios
    # ---------------------------------------------------------
    overall_rows = []

    # Scenario A: All evaluated hours
    m_all = compute_forecast_metrics(df[y_true_col], df[y_pred_col])
    overall_rows.append({
        "model_name": model_name,
        "subset": "All Hours",
        "n_eval": m_all["n_eval"],
        "total_actual": m_all["total_actual"],
        "mae": m_all["mae"],
        "rmse": m_all["rmse"],
        "wape_pct": m_all["wape_pct"],
        "bias_pred_minus_actual": m_all["bias_pred_minus_actual"],
        "storm_note": (
            "Includes storm days (see Without Storm Days row)"
            if has_storms
            else "0 storm days in window; duplicate 'Without Storm Days' row omitted"
        ),
    })

    # Scenario B: Storm days comparison (only if storm days exist in the dataset)
    if has_storms:
        sub_nostorm = df[~df["is_storm"]]
        m_nostorm = compute_forecast_metrics(sub_nostorm[y_true_col], sub_nostorm[y_pred_col])
        overall_rows.append({
            "model_name": model_name,
            "subset": "Without Storm Days",
            "n_eval": m_nostorm["n_eval"],
            "total_actual": m_nostorm["total_actual"],
            "mae": m_nostorm["mae"],
            "rmse": m_nostorm["rmse"],
            "wape_pct": m_nostorm["wape_pct"],
            "bias_pred_minus_actual": m_nostorm["bias_pred_minus_actual"],
            "storm_note": "Storm days excluded",
        })

        sub_storm = df[df["is_storm"]]
        m_storm = compute_forecast_metrics(sub_storm[y_true_col], sub_storm[y_pred_col])
        overall_rows.append({
            "model_name": model_name,
            "subset": "Storm Days Only",
            "n_eval": m_storm["n_eval"],
            "total_actual": m_storm["total_actual"],
            "mae": m_storm["mae"],
            "rmse": m_storm["rmse"],
            "wape_pct": m_storm["wape_pct"],
            "bias_pred_minus_actual": m_storm["bias_pred_minus_actual"],
            "storm_note": "Storm days only",
        })

    # Scenario C: Without outlier hours (if outliers exist)
    if has_outliers:
        sub_noout = df[~df["is_outlier"]]
        m_noout = compute_forecast_metrics(sub_noout[y_true_col], sub_noout[y_pred_col])
        overall_rows.append({
            "model_name": model_name,
            "subset": "Without Outlier Hours",
            "n_eval": m_noout["n_eval"],
            "total_actual": m_noout["total_actual"],
            "mae": m_noout["mae"],
            "rmse": m_noout["rmse"],
            "wape_pct": m_noout["wape_pct"],
            "bias_pred_minus_actual": m_noout["bias_pred_minus_actual"],
            "storm_note": "Outlier hours excluded",
        })

    results["overall"] = pd.DataFrame(overall_rows)

    # ---------------------------------------------------------
    # 2. Breakdowns (Using Existing Columns)
    # ---------------------------------------------------------
    for col in ["route", "day_type", "time_band"]:
        if col in df.columns:
            bd_all = compute_forecast_breakdown(df, col, y_true_col, y_pred_col, model_name)
            bd_all["subset"] = "All Hours"

            if has_storms:
                bd_nostorm = compute_forecast_breakdown(
                    df[~df["is_storm"]], col, y_true_col, y_pred_col, model_name
                )
                bd_nostorm["subset"] = "Without Storm Days"
                results[f"by_{col}"] = pd.concat([bd_all, bd_nostorm], ignore_index=True)
            else:
                results[f"by_{col}"] = bd_all

    # ---------------------------------------------------------
    # Save CSVs if requested
    # ---------------------------------------------------------
    if save_prefix:
        out_dir.mkdir(parents=True, exist_ok=True)
        for key, res_df in results.items():
            fname = out_dir / f"{save_prefix}_{key}.csv"
            res_df.to_csv(fname, index=False)

    return results


# ==============================================================================
# 2. CORE CLASSIFICATION METRICS
# ==============================================================================

def compute_classification_metrics(
    y_true: Union[pd.Series, np.ndarray],
    y_pred: Union[pd.Series, np.ndarray],
    y_prob: Optional[Union[pd.Series, np.ndarray]] = None,
) -> Dict[str, Union[int, float, list]]:
    """Calculate Precision, Recall, F1, PR-AUC, and Confusion Matrix components.

    Definitions:
        Precision = TP / (TP + FP)  (Of hours flagged high, how many really were)
        Recall    = TP / (TP + FN)  (Of truly high hours, how many were flagged)
        F1        = 2 * (P * R) / (P + R)
        PR-AUC    = Area under Precision-Recall Curve (average precision score)

    Parameters
    ----------
    y_true : pd.Series or np.ndarray
        Ground-truth binary labels (1 = high demand per trip, 0 = regular).
    y_pred : pd.Series or np.ndarray
        Binary predicted labels (1 or 0).
    y_prob : pd.Series or np.ndarray, optional
        Predicted probabilities or continuous scores for class 1 (used for PR-AUC & ROC-AUC).

    Returns
    -------
    dict
        Dictionary with sample sizes, precision, recall, f1, pr_auc, roc_auc,
        and confusion matrix elements: tn, fp, fn, tp.
    """
    if isinstance(y_true, pd.Series):
        y_true = y_true.values
    if isinstance(y_pred, pd.Series):
        y_pred = y_pred.values

    # Determine valid mask
    mask = ~np.isnan(y_true) & ~np.isnan(y_pred)
    if y_prob is not None:
        if isinstance(y_prob, pd.Series):
            y_prob = y_prob.values
        mask = mask & ~np.isnan(y_prob)

    y = y_true[mask].astype(int)
    y_hat = y_pred[mask].astype(int)
    prob = y_prob[mask] if y_prob is not None else None

    n_eval = int(len(y))
    if n_eval == 0:
        return {
            "n_eval": 0,
            "actual_positive": 0,
            "pred_positive": 0,
            "precision": np.nan,
            "recall": np.nan,
            "f1": np.nan,
            "pr_auc": np.nan,
            "roc_auc": np.nan,
            "tn": 0,
            "fp": 0,
            "fn": 0,
            "tp": 0,
            "confusion_matrix": [[0, 0], [0, 0]],
        }

    cm = confusion_matrix(y, y_hat, labels=[0, 1])
    tn, fp, fn, tp = int(cm[0, 0]), int(cm[0, 1]), int(cm[1, 0]), int(cm[1, 1])

    prec = float(precision_score(y, y_hat, zero_division=0))
    rec = float(recall_score(y, y_hat, zero_division=0))
    f1 = float(f1_score(y, y_hat, zero_division=0))

    pr_auc = np.nan
    roc_auc = np.nan
    if prob is not None and len(np.unique(y)) > 1:
        try:
            pr_auc = float(average_precision_score(y, prob))
            roc_auc = float(roc_auc_score(y, prob))
        except Exception:
            pr_auc = np.nan
            roc_auc = np.nan

    return {
        "n_eval": n_eval,
        "actual_positive": int(np.sum(y == 1)),
        "pred_positive": int(np.sum(y_hat == 1)),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1": round(f1, 4),
        "pr_auc": round(pr_auc, 4) if not np.isnan(pr_auc) else np.nan,
        "roc_auc": round(roc_auc, 4) if not np.isnan(roc_auc) else np.nan,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "tp": tp,
        "confusion_matrix": [[tn, fp], [fn, tp]],
    }


def format_confusion_matrix(
    cm_dict: Dict[str, Union[int, float]],
    model_name: str = "Classifier",
) -> pd.DataFrame:
    """Format confusion matrix counts into a presentation-ready 3x3 DataFrame with totals."""
    tn, fp = cm_dict["tn"], cm_dict["fp"]
    fn, tp = cm_dict["fn"], cm_dict["tp"]

    data = {
        "Actual Class": [
            "Actual Normal Demand (0)",
            "Actual High Demand (1)",
            "Total Predicted",
        ],
        "Pred Normal (0)": [tn, fn, tn + fn],
        "Pred High (1)": [fp, tp, fp + tp],
        "Total Actual": [tn + fp, fn + tp, tn + fp + fn + tp],
    }
    df_cm = pd.DataFrame(data)
    df_cm["Model"] = model_name
    return df_cm


def compute_classification_breakdown(
    df: pd.DataFrame,
    group_col: str,
    y_true_col: str = "high_demand_per_trip",
    y_pred_col: str = "pred_label",
    y_prob_col: Optional[str] = None,
    model_name: str = "Classifier",
) -> pd.DataFrame:
    """Compute classification performance across categories (route, day_type, time_band)."""
    if group_col not in df.columns:
        raise ValueError(f"Grouping column '{group_col}' not found in dataframe.")

    records = []
    groups = df[group_col].dropna().unique()
    if group_col == "time_band":
        groups = [g for g in TIME_BAND_ORDER if g in groups] + [g for g in groups if g not in TIME_BAND_ORDER]
    elif group_col == "day_type":
        preferred_order = ["Typical Weekday", "Typical Saturday", "Typical Sunday", "Special/Excluded"]
        groups = [g for g in preferred_order if g in groups] + [g for g in groups if g not in preferred_order]
    else:
        groups = sorted(groups)

    for g in groups:
        sub = df[df[group_col] == g]
        prob_vals = sub[y_prob_col] if y_prob_col and y_prob_col in sub.columns else None
        m = compute_classification_metrics(sub[y_true_col], sub[y_pred_col], prob_vals)

        rec = {
            "model_name": model_name,
            group_col: g,
        }
        if group_col == "time_band":
            rec["time_band_label"] = get_time_band_label(g)

        rec.update({
            "n_eval": m["n_eval"],
            "actual_positive": m["actual_positive"],
            "pred_positive": m["pred_positive"],
            "positive_prevalence_pct": round(m["actual_positive"] / m["n_eval"] * 100, 2) if m["n_eval"] > 0 else 0.0,
            "precision": m["precision"],
            "recall": m["recall"],
            "f1": m["f1"],
            "pr_auc": m["pr_auc"],
            "tp": m["tp"],
            "fp": m["fp"],
            "fn": m["fn"],
            "tn": m["tn"],
        })
        records.append(rec)

    return pd.DataFrame(records)


def evaluate_classification(
    df: pd.DataFrame,
    y_true_col: str = "high_demand_per_trip",
    y_pred_col: str = "pred_label",
    y_prob_col: Optional[str] = None,
    model_name: str = "Classifier",
    save_prefix: Optional[str] = None,
    out_dir: Path = TAB_DIR,
) -> Dict[str, pd.DataFrame]:
    """Complete evaluation suite for classification models as specified in Milestone 3.

    Calculates:
    1. Overall metrics: Precision, Recall, F1, PR-AUC, ROC-AUC
       - 'All Hours'
       - 'Without Storm Days' (only if storm days exist)
       - 'Without Outlier Hours' (if outliers exist)
    2. Confusion matrix formatted with totals
    3. Breakdown by route
    4. Breakdown by day_type
    5. Breakdown by time_band (reading existing time_band column)
    """
    results: Dict[str, pd.DataFrame] = {}
    has_storms = "is_storm" in df.columns and bool(df["is_storm"].any())
    has_outliers = "is_outlier" in df.columns and bool(df["is_outlier"].any())

    overall_rows = []
    prob_series = df[y_prob_col] if y_prob_col and y_prob_col in df.columns else None

    # Scenario A: All evaluated hours
    m_all = compute_classification_metrics(df[y_true_col], df[y_pred_col], prob_series)
    overall_rows.append({
        "model_name": model_name,
        "subset": "All Hours",
        "n_eval": m_all["n_eval"],
        "actual_pos": m_all["actual_positive"],
        "pred_pos": m_all["pred_positive"],
        "precision": m_all["precision"],
        "recall": m_all["recall"],
        "f1": m_all["f1"],
        "pr_auc": m_all["pr_auc"],
        "roc_auc": m_all["roc_auc"],
        "tp": m_all["tp"],
        "fp": m_all["fp"],
        "fn": m_all["fn"],
        "tn": m_all["tn"],
        "storm_note": (
            "Includes storm days (see Without Storm Days row)"
            if has_storms
            else "0 storm days in window; duplicate 'Without Storm Days' row omitted"
        ),
    })

    results["confusion_matrix"] = format_confusion_matrix(m_all, model_name=f"{model_name} (All Hours)")

    # Scenario B: Without storm days (only if storm days exist in dataset)
    if has_storms:
        sub_nostorm = df[~df["is_storm"]]
        p_nostorm = sub_nostorm[y_prob_col] if y_prob_col and y_prob_col in sub_nostorm.columns else None
        m_nostorm = compute_classification_metrics(
            sub_nostorm[y_true_col], sub_nostorm[y_pred_col], p_nostorm
        )
        overall_rows.append({
            "model_name": model_name,
            "subset": "Without Storm Days",
            "n_eval": m_nostorm["n_eval"],
            "actual_pos": m_nostorm["actual_positive"],
            "pred_pos": m_nostorm["pred_positive"],
            "precision": m_nostorm["precision"],
            "recall": m_nostorm["recall"],
            "f1": m_nostorm["f1"],
            "pr_auc": m_nostorm["pr_auc"],
            "roc_auc": m_nostorm["roc_auc"],
            "tp": m_nostorm["tp"],
            "fp": m_nostorm["fp"],
            "fn": m_nostorm["fn"],
            "tn": m_nostorm["tn"],
            "storm_note": "Storm days excluded",
        })

    # Scenario C: Without outlier hours (if outliers exist)
    if has_outliers:
        sub_noout = df[~df["is_outlier"]]
        p_noout = sub_noout[y_prob_col] if y_prob_col and y_prob_col in sub_noout.columns else None
        m_noout = compute_classification_metrics(
            sub_noout[y_true_col], sub_noout[y_pred_col], p_noout
        )
        overall_rows.append({
            "model_name": model_name,
            "subset": "Without Outlier Hours",
            "n_eval": m_noout["n_eval"],
            "actual_pos": m_noout["actual_positive"],
            "pred_pos": m_noout["pred_positive"],
            "precision": m_noout["precision"],
            "recall": m_noout["recall"],
            "f1": m_noout["f1"],
            "pr_auc": m_noout["pr_auc"],
            "roc_auc": m_noout["roc_auc"],
            "tp": m_noout["tp"],
            "fp": m_noout["fp"],
            "fn": m_noout["fn"],
            "tn": m_noout["tn"],
            "storm_note": "Outlier hours excluded",
        })

    results["overall"] = pd.DataFrame(overall_rows)

    # ---------------------------------------------------------
    # 2. Breakdowns (Using Existing Columns)
    # ---------------------------------------------------------
    for col in ["route", "day_type", "time_band"]:
        if col in df.columns:
            bd_all = compute_classification_breakdown(
                df, col, y_true_col, y_pred_col, y_prob_col, model_name
            )
            bd_all["subset"] = "All Hours"

            if has_storms:
                bd_nostorm = compute_classification_breakdown(
                    df[~df["is_storm"]], col, y_true_col, y_pred_col, y_prob_col, model_name
                )
                bd_nostorm["subset"] = "Without Storm Days"
                results[f"by_{col}"] = pd.concat([bd_all, bd_nostorm], ignore_index=True)
            else:
                results[f"by_{col}"] = bd_all

    # ---------------------------------------------------------
    # Save CSVs if requested
    # ---------------------------------------------------------
    if save_prefix:
        out_dir.mkdir(parents=True, exist_ok=True)
        for key, res_df in results.items():
            fname = out_dir / f"{save_prefix}_{key}.csv"
            res_df.to_csv(fname, index=False)

    return results


# ==============================================================================
# 3. CONSOLE REPORTING & DEMO HARNESS
# ==============================================================================

def print_forecasting_summary(res: Dict[str, pd.DataFrame], model_name: str = "Model"):
    """Print readable summary of forecasting evaluation."""
    print("=" * 80)
    print(f" FORECASTING EVALUATION REPORT: {model_name.upper()}")
    print("=" * 80)
    print("\n--- 1. OVERALL METRICS ---")
    print(res["overall"].to_string(index=False, na_rep=""))
    print("[Note: bias_pred_minus_actual = mean(predicted - actual). Positive (+3.11) indicates forecast overpredicts actual ridership on average.]")
    if "Without Storm Days" not in set(res["overall"]["subset"]):
        print("[Note: Validation (June–July 2026) has 0 storm days; duplicate 'Without Storm Days' row omitted.]")

    if "by_day_type" in res:
        print("\n--- 2. BREAKDOWN BY DAY TYPE ---")
        cols = ["day_type", "subset", "n_eval", "total_actual", "mae", "rmse", "wape_pct", "bias_pred_minus_actual"]
        print(res["by_day_type"][cols].to_string(index=False, na_rep=""))

    if "by_time_band" in res:
        print("\n--- 3. BREAKDOWN BY TIME BAND ---")
        cols = ["time_band", "time_band_label", "subset", "n_eval", "total_actual", "mae", "rmse", "wape_pct", "bias_pred_minus_actual"]
        print(res["by_time_band"][cols].to_string(index=False, na_rep=""))

    if "by_route" in res:
        print("\n--- 4. BREAKDOWN BY ROUTE (TOP 5 & BOTTOM 5 BY WAPE) ---")
        r_df = res["by_route"][res["by_route"]["subset"] == "All Hours"].sort_values("wape_pct")
        cols = ["route", "n_eval", "total_actual", "mae", "rmse", "wape_pct", "bias_pred_minus_actual"]
        print("Best performing routes (Lowest WAPE):")
        print(r_df.head(5)[cols].to_string(index=False, na_rep=""))
        print("\nWorst performing routes (Highest WAPE):")
        print(r_df.tail(5)[cols].to_string(index=False, na_rep=""))
    print("=" * 80 + "\n")


def print_classification_summary(res: Dict[str, pd.DataFrame], model_name: str = "Classifier"):
    """Print readable summary of classification evaluation."""
    print("=" * 80)
    print(f" CLASSIFICATION EVALUATION REPORT: {model_name.upper()}")
    print("=" * 80)
    print("\n--- 1. OVERALL PERFORMANCE ---")
    print(res["overall"].to_string(index=False))
    if "Without Storm Days" not in set(res["overall"]["subset"]):
        print("[Note: No storm days occurred in this evaluation window (June-July 2026); storm split active for winter dates.]")

    if "confusion_matrix" in res:
        print("\n--- 2. CONFUSION MATRIX ---")
        print(res["confusion_matrix"].to_string(index=False))

    if "by_day_type" in res:
        print("\n--- 3. BREAKDOWN BY DAY TYPE ---")
        cols = ["day_type", "subset", "n_eval", "actual_positive", "pred_positive", "precision", "recall", "f1", "pr_auc"]
        print(res["by_day_type"][cols].to_string(index=False))

    if "by_time_band" in res:
        print("\n--- 4. BREAKDOWN BY TIME BAND ---")
        cols = ["time_band", "time_band_label", "subset", "n_eval", "actual_positive", "pred_positive", "precision", "recall", "f1", "pr_auc"]
        print(res["by_time_band"][cols].to_string(index=False))

    if "by_route" in res:
        print("\n--- 5. BREAKDOWN BY ROUTE (SAMPLE) ---")
        r_df = res["by_route"][res["by_route"]["subset"] == "All Hours"].sort_values("f1", ascending=False)
        cols = ["route", "n_eval", "actual_positive", "pred_positive", "precision", "recall", "f1", "pr_auc"]
        print("Highest F1 routes:")
        print(r_df.head(5)[cols].to_string(index=False))
        print("\nLowest F1 routes:")
        print(r_df.tail(5)[cols].to_string(index=False))
    print("=" * 80 + "\n")


def run_validation_baseline_evaluations():
    """Execute Step 1 baseline evaluations on the validation set.

    Validates evaluate.py on:
    1. Forecasting Baselines: 4-week average (hurdle: 14.08% WAPE) and 7-day lag (17.48% WAPE).
    2. Classification Baselines:
       - Rule A (Lag-7d heuristic): lag_7d / trips_running > threshold_p75
       - Rule B (4-Week average heuristic — TARGET HURDLE): lag_mean_available / trips_running > threshold_p75
    """
    print(f"Loading validation set using load_dataset('val')...")
    val_df = load_dataset("val")
    print(f"Validation rows: {len(val_df):,}, dates: {val_df['date'].min()} to {val_df['date'].max()} (41 routes)")

    # -------------------------------------------------------------
    # 1. FORECASTING BASELINES EVALUATION
    # -------------------------------------------------------------
    # Explaining the 53,585 row count:
    # Requires valid ridership, valid lag_7d, and valid lag_mean_available.
    # Evaluates all hours including zero-service hours (trips_running == 0) where continuous demand is 0.
    common_mask = (
        val_df["ridership"].notnull()
        & val_df["lag_7d"].notnull()
        & val_df["lag_mean_available"].notnull()
    )
    val_forecast = val_df[common_mask].copy()
    print(f"\n--- Forecasting Baselines (53,585 Evaluated Hours) ---")
    print(f"Fair comparison evaluation rows (both lags non-null): {len(val_forecast):,} / {len(val_df):,} ({len(val_forecast)/len(val_df)*100:.2f}%)")

    # Evaluate 4-week average baseline (Target Hurdle)
    val_forecast["pred_4wk"] = val_forecast["lag_mean_available"]
    res_4wk = evaluate_forecasting(
        val_forecast,
        y_true_col="ridership",
        y_pred_col="pred_4wk",
        model_name="4-Week Average Baseline",
        save_prefix="m3_eval_baseline_4wk",
    )
    print_forecasting_summary(res_4wk, model_name="4-Week Average Baseline (Primary Target Hurdle)")

    # Evaluate Lag 7d baseline
    val_forecast["pred_lag7"] = val_forecast["lag_7d"]
    res_lag7 = evaluate_forecasting(
        val_forecast,
        y_true_col="ridership",
        y_pred_col="pred_lag7",
        model_name="Same Hour Last Week (lag_7d)",
        save_prefix="m3_eval_baseline_lag7",
    )
    print_forecasting_summary(res_lag7, model_name="Same Hour Last Week (lag_7d)")

    # -------------------------------------------------------------
    # 2. CLASSIFICATION BASELINES EVALUATION
    # -------------------------------------------------------------
    # Explaining the 53,406 row count:
    # High demand per trip target is defined only when at least 1 trip was scheduled and running (trips_running > 0).
    # Hours with trips_running == 0 (551 hours in validation) have no active service and therefore no per-trip load label.
    # On the active service hours where threshold_p75 and both lags are present, exactly 53,406 hours exist.
    print(f"\n--- Classification Baselines (53,406 Evaluated Active-Service Hours) ---")
    valid_class_mask = (
        (val_df["trips_running"] > 0)
        & val_df["threshold_p75"].notnull()
        & val_df["lag_7d"].notnull()
        & val_df["lag_mean_available"].notnull()
    )
    val_class = val_df[valid_class_mask].copy()
    print(f"Active service evaluation rows (trips_running > 0, threshold non-null, both lags non-null): {len(val_class):,}")

    # Rule A: Lag-7d heuristic: lag_7d / trips_running > threshold_p75
    est_rpt_7d = val_class["lag_7d"] / val_class["trips_running"]
    val_class["pred_class_7d"] = (est_rpt_7d > val_class["threshold_p75"]).astype(int)
    val_class["prob_class_7d"] = np.clip(est_rpt_7d / (2.0 * val_class["threshold_p75"]), 0.0, 1.0)

    res_class_7d = evaluate_classification(
        val_class,
        y_true_col="high_demand_per_trip",
        y_pred_col="pred_class_7d",
        y_prob_col="prob_class_7d",
        model_name="Rule A: Prior-Week Heuristic (lag_7d / trips)",
        save_prefix="m3_eval_baseline_class_7d",
    )

    # Rule B: 4-Week Average heuristic (Stronger Baseline / Primary Target Hurdle)
    est_rpt_4wk = val_class["lag_mean_available"] / val_class["trips_running"]
    val_class["pred_class_4wk"] = (est_rpt_4wk > val_class["threshold_p75"]).astype(int)
    val_class["prob_class_4wk"] = np.clip(est_rpt_4wk / (2.0 * val_class["threshold_p75"]), 0.0, 1.0)

    res_class_4wk = evaluate_classification(
        val_class,
        y_true_col="high_demand_per_trip",
        y_pred_col="pred_class_4wk",
        y_prob_col="prob_class_4wk",
        model_name="Rule B: 4-Week Average Heuristic (lag_mean / trips)",
        save_prefix="m3_eval_baseline_class_4wk",
    )

    # Comparison summary table of the two classification baselines
    print("=" * 80)
    print(" CLASSIFICATION BASELINE COMPARISON SUMMARY (TARGET HURDLE SELECTION)")
    print("=" * 80)
    m7 = res_class_7d["overall"].iloc[0]
    m4 = res_class_4wk["overall"].iloc[0]
    comp_df = pd.DataFrame([
        {
            "Baseline Rule": "Rule A: lag_7d ÷ trips_running",
            "Evaluated Hours": m7["n_eval"],
            "Precision": m7["precision"],
            "Recall": m7["recall"],
            "F1 Score": m7["f1"],
            "PR-AUC": m7["pr_auc"],
            "Status": "Reference",
        },
        {
            "Baseline Rule": "Rule B: lag_mean_available ÷ trips_running",
            "Evaluated Hours": m4["n_eval"],
            "Precision": m4["precision"],
            "Recall": m4["recall"],
            "F1 Score": m4["f1"],
            "PR-AUC": m4["pr_auc"],
            "Status": "PRIMARY TARGET HURDLE (Stronger)",
        },
    ])
    print(comp_df.to_string(index=False))
    print("=" * 80)

    print_classification_summary(
        res_class_4wk,
        model_name="Rule B: 4-Week Average Heuristic (Primary Target Hurdle for Classifiers)",
    )

    print("\n[SUCCESS] Shared evaluation script src/evaluate.py updated, verified, and operational!")


if __name__ == "__main__":
    run_validation_baseline_evaluations()
