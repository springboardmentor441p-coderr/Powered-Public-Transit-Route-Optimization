"""
AI_RouteRanker - Forecasting Evaluation Metrics Module
Computes MAE, RMSE, R2, and WAPE with zero-division protection and coverage tracking.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional, List
import numpy as np
import pandas as pd


@dataclass
class MetricResults:
    """Container for forecast evaluation metrics and coverage statistics."""
    mae: float
    rmse: float
    r2: float
    wape: float
    expected_rows: int
    predictions_generated: int
    unavailable_predictions: int
    rows_evaluated: int
    prediction_coverage_pct: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mae": round(self.mae, 4) if not np.isnan(self.mae) else None,
            "rmse": round(self.rmse, 4) if not np.isnan(self.rmse) else None,
            "r2": round(self.r2, 4) if not np.isnan(self.r2) else None,
            "wape": round(self.wape, 4) if not np.isnan(self.wape) else None,
            "expected_rows": self.expected_rows,
            "predictions_generated": self.predictions_generated,
            "unavailable_predictions": self.unavailable_predictions,
            "rows_evaluated": self.rows_evaluated,
            "prediction_coverage_pct": round(self.prediction_coverage_pct, 2),
        }


def calculate_metrics(
    y_true: pd.Series,
    y_pred: pd.Series,
    expected_rows: Optional[int] = None,
) -> MetricResults:
    """
    Computes MAE, RMSE, R2, and WAPE on valid (non-null) prediction pairs.

    Args:
        y_true: Ground truth target ridership.
        y_pred: Predicted ridership (may contain NaNs for unavailable predictions).
        expected_rows: Expected total observations in the evaluation partition.

    Returns:
        MetricResults dataclass with metrics and coverage statistics.
    """
    total_expected = expected_rows if expected_rows is not None else len(y_true)

    # Align series and mask non-null pairs
    df_eval = pd.DataFrame({"y": y_true, "y_hat": y_pred})
    valid_mask = df_eval["y"].notna() & df_eval["y_hat"].notna()

    preds_generated = int(df_eval["y_hat"].notna().sum())
    unavail_preds = int(df_eval["y_hat"].isna().sum())
    rows_eval = int(valid_mask.sum())

    coverage_pct = (preds_generated / total_expected * 100.0) if total_expected > 0 else 0.0

    if rows_eval == 0:
        return MetricResults(
            mae=np.nan,
            rmse=np.nan,
            r2=np.nan,
            wape=np.nan,
            expected_rows=total_expected,
            predictions_generated=preds_generated,
            unavailable_predictions=unavail_preds,
            rows_evaluated=0,
            prediction_coverage_pct=coverage_pct,
        )

    y = df_eval.loc[valid_mask, "y"].astype(float).values
    y_hat = df_eval.loc[valid_mask, "y_hat"].astype(float).values

    # Absolute and squared errors
    abs_errors = np.abs(y - y_hat)
    sq_errors = (y - y_hat) ** 2

    # MAE and RMSE
    mae = float(np.mean(abs_errors))
    rmse = float(np.sqrt(np.mean(sq_errors)))

    # R-squared: 1 - SS_res / SS_tot
    ss_res = np.sum(sq_errors)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    if ss_tot > 0:
        r2 = float(1.0 - (ss_res / ss_tot))
    else:
        r2 = 0.0 if ss_res == 0.0 else -np.inf

    # WAPE: (sum(|y - y_hat|) / sum(y)) * 100
    sum_actual = np.sum(y)
    if sum_actual > 0:
        wape = float((np.sum(abs_errors) / sum_actual) * 100.0)
    else:
        wape = np.nan  # Zero denominator safe handling

    return MetricResults(
        mae=mae,
        rmse=rmse,
        r2=r2,
        wape=wape,
        expected_rows=total_expected,
        predictions_generated=preds_generated,
        unavailable_predictions=unavail_preds,
        rows_evaluated=rows_eval,
        prediction_coverage_pct=coverage_pct,
    )


def calculate_route_metrics(predictions_df: pd.DataFrame) -> pd.DataFrame:
    """Computes baseline metrics grouped by route."""
    routes = predictions_df["route"].unique()
    records = []

    for r in sorted(routes, key=lambda x: str(x)):
        sub = predictions_df[predictions_df["route"] == r]
        res = calculate_metrics(sub["target_rides"], sub["prediction"], expected_rows=len(sub))
        d = res.to_dict()
        d["route"] = r
        records.append(d)

    return pd.DataFrame(records).sort_values("mae")


def calculate_daytype_metrics(predictions_df: pd.DataFrame) -> pd.DataFrame:
    """Computes baseline metrics grouped by daytype."""
    daytypes = predictions_df["daytype"].unique()
    records = []

    for dt in ["W", "A", "U"]:
        sub = predictions_df[predictions_df["daytype"] == dt]
        if len(sub) == 0:
            continue
        res = calculate_metrics(sub["target_rides"], sub["prediction"], expected_rows=len(sub))
        d = res.to_dict()
        d["daytype"] = dt
        records.append(d)

    return pd.DataFrame(records)
