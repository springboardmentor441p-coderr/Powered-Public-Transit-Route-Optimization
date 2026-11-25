"""
AI_RouteRanker - Model Evaluator Module
Calculates standard regression evaluation metrics with zero-denominator safety
and evaluates validation predictions against Phase 2 baseline benchmarks.
"""

from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


@dataclass
class EvaluationResult:
    """Container for model validation metrics and coverage."""
    tier: int
    partition: str
    model_name: str
    expected_rows: int
    rows_evaluated: int
    prediction_coverage_pct: float
    mae: float
    rmse: float
    r2: float
    wape: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ModelEvaluator:
    """Calculates regression metrics and comparative benchmark differentials."""

    # Approved Baseline Reference Metrics on Validation Partitions
    BASELINE_BENCHMARKS = {
        1: {
            "historical_mean": {"mae": 977.5079, "rmse": 1487.9412, "r2": 0.8904, "wape": 20.4461},
            "seasonal_naive": {"mae": 447.4613, "rmse": 861.0832, "r2": 0.9633, "wape": 9.3594},
        },
        2: {
            "historical_mean": {"mae": 664.8767, "rmse": 947.9668, "r2": 0.9614, "wape": 12.8074},
            "seasonal_naive": {"mae": 346.7800, "rmse": 625.1827, "r2": 0.9832, "wape": 6.6800},
        },
    }

    @staticmethod
    def calculate_wape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
        """
        Calculates Weighted Absolute Percentage Error (WAPE) with zero-denominator guard.
        WAPE = sum(|y_true - y_pred|) / sum(y_true) * 100
        """
        sum_actual = float(np.sum(y_true))
        if abs(sum_actual) < 1e-9:
            return 0.0 if float(np.sum(np.abs(y_pred))) < 1e-9 else 100.0
        return float(np.sum(np.abs(y_true - y_pred)) / sum_actual * 100.0)

    @classmethod
    def evaluate(
        cls,
        y_true: np.ndarray | pd.Series,
        y_pred: np.ndarray | pd.Series,
        tier: int,
        partition_name: str = "Validation",
        model_name: str = "Random Forest (Phase 3.1)",
        expected_rows: Optional[int] = None,
    ) -> EvaluationResult:
        """
        Calculates MAE, RMSE, R2, WAPE, and coverage over valid predictions.
        Filters out NaNs in y_pred if any exist.
        """
        y_t = np.asarray(y_true, dtype=np.float64)
        y_p = np.asarray(y_pred, dtype=np.float64)

        total_expected = expected_rows if expected_rows is not None else len(y_t)

        valid_mask = ~np.isnan(y_p) & ~np.isnan(y_t)
        rows_eval = int(np.sum(valid_mask))
        coverage_pct = round((rows_eval / total_expected * 100.0), 4) if total_expected > 0 else 0.0

        if rows_eval == 0:
            return EvaluationResult(
                tier=tier,
                partition=partition_name,
                model_name=model_name,
                expected_rows=total_expected,
                rows_evaluated=0,
                prediction_coverage_pct=0.0,
                mae=float("nan"),
                rmse=float("nan"),
                r2=float("nan"),
                wape=float("nan"),
            )

        y_t_valid = y_t[valid_mask]
        y_p_valid = y_p[valid_mask]

        mae_val = float(mean_absolute_error(y_t_valid, y_p_valid))
        rmse_val = float(np.sqrt(mean_squared_error(y_t_valid, y_p_valid)))
        r2_val = float(r2_score(y_t_valid, y_p_valid))
        wape_val = cls.calculate_wape(y_t_valid, y_p_valid)

        return EvaluationResult(
            tier=tier,
            partition=partition_name,
            model_name=model_name,
            expected_rows=total_expected,
            rows_evaluated=rows_eval,
            prediction_coverage_pct=coverage_pct,
            mae=round(mae_val, 4),
            rmse=round(rmse_val, 4),
            r2=round(r2_val, 4),
            wape=round(wape_val, 4),
        )

    @classmethod
    def compare_with_baselines(cls, result: EvaluationResult) -> Dict[str, Any]:
        """Compares evaluation result against historical mean and seasonal naive benchmarks."""
        benchmarks = cls.BASELINE_BENCHMARKS.get(result.tier, {})
        base_a = benchmarks.get("historical_mean", {})
        base_b = benchmarks.get("seasonal_naive", {})

        return {
            "tier": result.tier,
            "partition": result.partition,
            "rf_mae": result.mae,
            "rf_rmse": result.rmse,
            "rf_r2": result.r2,
            "rf_wape": result.wape,
            "base_a_mae": base_a.get("mae"),
            "base_a_wape": base_a.get("wape"),
            "diff_vs_base_a_wape": round(result.wape - base_a.get("wape", 0.0), 4),
            "base_b_mae": base_b.get("mae"),
            "base_b_wape": base_b.get("wape"),
            "diff_vs_base_b_wape": round(result.wape - base_b.get("wape", 0.0), 4),
            "beats_base_a": result.wape < base_a.get("wape", float("inf")),
            "beats_base_b": result.wape < base_b.get("wape", float("inf")),
        }
