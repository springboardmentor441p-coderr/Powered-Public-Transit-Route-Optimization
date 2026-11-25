"""
AI_RouteRanker - Baseline Evaluation Orchestrator
Executes rolling one-day-ahead evaluation for Baseline A and Baseline B
across all Tier 1 and Tier 2 evaluation partitions.
Generates metrics, coverage tables, prediction artifacts, and reports.
"""

import os
import sys
import time
import logging
from typing import Dict, Any, List, Tuple
import pandas as pd
import numpy as np

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from analytics.modeling.data_loader import DataLoader
from analytics.modeling.splitters import ChronologicalSplitter, Tier1Partitions, Tier2Partitions
from analytics.modeling.baselines.historical_mean import HistoricalMeanBaseline
from analytics.modeling.baselines.seasonal_naive import SeasonalNaiveBaseline
from analytics.modeling.baselines.metrics import (
    calculate_metrics,
    calculate_route_metrics,
    calculate_daytype_metrics,
    MetricResults,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


class BaselineEvaluator:
    """Orchestrates baseline prediction generation and metric calculation."""

    def __init__(
        self,
        artifacts_dir: str = os.path.join("artifacts", "baselines"),
        reports_dir: str = os.path.join("reports", "modeling", "baselines"),
    ):
        self.artifacts_dir = artifacts_dir
        self.reports_dir = reports_dir
        os.makedirs(self.artifacts_dir, exist_ok=True)
        os.makedirs(self.reports_dir, exist_ok=True)

        self.data_loader = DataLoader()
        self.baseline_a_t1 = HistoricalMeanBaseline(history_start_date=ChronologicalSplitter.T1_TRAIN_START)
        self.baseline_b_t1 = SeasonalNaiveBaseline(history_start_date=ChronologicalSplitter.T1_TRAIN_START)

        self.baseline_a_t2 = HistoricalMeanBaseline(history_start_date=ChronologicalSplitter.T2_TRAIN_START)
        self.baseline_b_t2 = SeasonalNaiveBaseline(history_start_date=ChronologicalSplitter.T2_TRAIN_START)

    def evaluate_partition(
        self,
        partition_name: str,
        tier: int,
        eval_df: pd.DataFrame,
        history_pool_df: pd.DataFrame,
        baseline_a: HistoricalMeanBaseline,
        baseline_b: SeasonalNaiveBaseline,
    ) -> Tuple[pd.DataFrame, Dict[str, Any], Dict[str, Any]]:
        """
        Runs Baseline A and Baseline B on an evaluation partition.
        Returns consolidated predictions and metric summaries.
        """
        logger.info("Evaluating Tier %d %s (Rows: %d)...", tier, partition_name, len(eval_df))
        t0 = time.time()

        # Sort eval_df by route, date to guarantee exact index alignment with generated predictions
        eval_sorted = eval_df.sort_values(["route", "date"]).reset_index(drop=True)

        # 1. Baseline A: Expanding Mean
        pred_a = baseline_a.generate_predictions(eval_sorted, history_pool_df)

        # 2. Baseline B: Seasonal Naive
        pred_b = baseline_b.generate_predictions(eval_sorted, history_pool_df)

        # Consolidate predictions
        consolidated = eval_sorted[["route", "date", "daytype", "target_rides"]].copy()
        consolidated["pred_baseline_a_mean"] = pred_a["prediction"].values
        consolidated["fallback_baseline_a"] = pred_a["fallback_level"].values

        consolidated["pred_baseline_b_seasonal_naive"] = pred_b["prediction"].values
        consolidated["fallback_baseline_b"] = pred_b["fallback_level"].values

        # Calculate metrics using aligned consolidated series
        metrics_a = calculate_metrics(
            consolidated["target_rides"],
            consolidated["pred_baseline_a_mean"],
            expected_rows=len(consolidated),
        )
        metrics_b = calculate_metrics(
            consolidated["target_rides"],
            consolidated["pred_baseline_b_seasonal_naive"],
            expected_rows=len(consolidated),
        )

        logger.info(
            "  Completed Tier %d %s in %.2fs | BaseA MAE: %.2f, WAPE: %.2f%% | BaseB MAE: %.2f, WAPE: %.2f%%",
            tier, partition_name, time.time() - t0,
            metrics_a.mae, metrics_a.wape,
            metrics_b.mae, metrics_b.wape,
        )

        dict_a = metrics_a.to_dict()
        dict_a.update({"tier": tier, "partition": partition_name, "baseline": "Baseline A (Expanding Mean)"})

        dict_b = metrics_b.to_dict()
        dict_b.update({"tier": tier, "partition": partition_name, "baseline": "Baseline B (Seasonal Naive t-7)"})

        return consolidated, dict_a, dict_b

    def run_all_evaluations(self) -> Dict[str, Any]:
        """Runs complete baseline evaluation across all Tier 1 and Tier 2 partitions."""
        logger.info("=" * 80)
        logger.info("AI_RouteRanker - Executing Milestone 5.2 Phase 2 Baseline Evaluation")
        logger.info("=" * 80)

        # Load datasets
        t1_raw = self.data_loader.load_tier1_dataset()
        t2_raw = self.data_loader.load_tier2_dataset()

        t1_splits = ChronologicalSplitter.split_tier1(t1_raw)
        t2_splits = ChronologicalSplitter.split_tier2(t2_raw)

        all_metrics = []
        coverage_records = []

        # ==========================================
        # Tier 1 Evaluations
        # ==========================================
        # 1. Tier 1 Validation
        t1_val_preds, m_a_val, m_b_val = self.evaluate_partition(
            partition_name="Validation",
            tier=1,
            eval_df=t1_splits.validation,
            history_pool_df=t1_raw[t1_raw["date"] <= t1_splits.validation["date"].max()],
            baseline_a=self.baseline_a_t1,
            baseline_b=self.baseline_b_t1,
        )
        all_metrics.extend([m_a_val, m_b_val])
        t1_val_path = os.path.join(self.artifacts_dir, "tier1_val_predictions.parquet")
        t1_val_preds.to_parquet(t1_val_path, index=False, compression="zstd")

        # 2. Tier 1 Test (GTFS Era)
        t1_test_preds, m_a_test, m_b_test = self.evaluate_partition(
            partition_name="Test (GTFS Era)",
            tier=1,
            eval_df=t1_splits.test,
            history_pool_df=t1_raw[t1_raw["date"] <= t1_splits.test["date"].max()],
            baseline_a=self.baseline_a_t1,
            baseline_b=self.baseline_b_t1,
        )
        all_metrics.extend([m_a_test, m_b_test])
        t1_test_path = os.path.join(self.artifacts_dir, "tier1_test_predictions.parquet")
        t1_test_preds.to_parquet(t1_test_path, index=False, compression="zstd")

        # 3. Tier 1 August Holdout
        t1_aug_preds, m_a_aug, m_b_aug = self.evaluate_partition(
            partition_name="August Holdout",
            tier=1,
            eval_df=t1_splits.august_holdout,
            history_pool_df=t1_raw[t1_raw["date"] <= t1_splits.august_holdout["date"].max()],
            baseline_a=self.baseline_a_t1,
            baseline_b=self.baseline_b_t1,
        )
        all_metrics.extend([m_a_aug, m_b_aug])
        t1_aug_path = os.path.join(self.artifacts_dir, "tier1_august_predictions.parquet")
        t1_aug_preds.to_parquet(t1_aug_path, index=False, compression="zstd")

        # ==========================================
        # Tier 2 Evaluations
        # ==========================================
        # 4. Tier 2 Validation
        t2_val_preds, m_a_t2_val, m_b_t2_val = self.evaluate_partition(
            partition_name="Validation",
            tier=2,
            eval_df=t2_splits.validation,
            history_pool_df=t2_raw[t2_raw["date"] <= t2_splits.validation["date"].max()],
            baseline_a=self.baseline_a_t2,
            baseline_b=self.baseline_b_t2,
        )
        all_metrics.extend([m_a_t2_val, m_b_t2_val])
        t2_val_path = os.path.join(self.artifacts_dir, "tier2_val_predictions.parquet")
        t2_val_preds.to_parquet(t2_val_path, index=False, compression="zstd")

        # 5. Tier 2 Test
        t2_test_preds, m_a_t2_test, m_b_t2_test = self.evaluate_partition(
            partition_name="Test",
            tier=2,
            eval_df=t2_splits.test,
            history_pool_df=t2_raw[t2_raw["date"] <= t2_splits.test["date"].max()],
            baseline_a=self.baseline_a_t2,
            baseline_b=self.baseline_b_t2,
        )
        all_metrics.extend([m_a_t2_test, m_b_t2_test])
        t2_test_path = os.path.join(self.artifacts_dir, "tier2_test_predictions.parquet")
        t2_test_preds.to_parquet(t2_test_path, index=False, compression="zstd")

        # ==========================================
        # Export Summaries to CSV & Reports
        # ==========================================
        df_metrics = pd.DataFrame(all_metrics)[
            ["tier", "partition", "baseline", "expected_rows", "predictions_generated",
             "unavailable_predictions", "rows_evaluated", "prediction_coverage_pct",
             "mae", "rmse", "r2", "wape"]
        ]
        csv_metrics_path = os.path.join(self.reports_dir, "baseline_metrics.csv")
        df_metrics.to_csv(csv_metrics_path, index=False)

        # Coverage breakdown for Baseline B fallbacks
        for name, p_df, tier_num in [
            ("Tier 1 Validation", t1_val_preds, 1),
            ("Tier 1 Test", t1_test_preds, 1),
            ("Tier 1 August Holdout", t1_aug_preds, 1),
            ("Tier 2 Validation", t2_val_preds, 2),
            ("Tier 2 Test", t2_test_preds, 2),
        ]:
            counts = p_df["fallback_baseline_b"].value_counts().to_dict()
            total = len(p_df)
            coverage_records.append({
                "tier": tier_num,
                "partition": name,
                "total_rows": total,
                "calendar_t7_count": counts.get("calendar_t7", 0),
                "calendar_t7_pct": round(counts.get("calendar_t7", 0) / total * 100.0, 2),
                "recent_28d_count": counts.get("recent_28d_daytype", 0),
                "recent_28d_pct": round(counts.get("recent_28d_daytype", 0) / total * 100.0, 2),
                "historical_mean_count": counts.get("historical_mean", 0),
                "historical_mean_pct": round(counts.get("historical_mean", 0) / total * 100.0, 2),
                "unavailable_count": counts.get("unavailable", 0),
                "unavailable_pct": round(counts.get("unavailable", 0) / total * 100.0, 2),
            })

        df_coverage = pd.DataFrame(coverage_records)
        csv_cov_path = os.path.join(self.reports_dir, "baseline_prediction_coverage.csv")
        df_coverage.to_csv(csv_cov_path, index=False)

        logger.info("Baseline evaluation finished. Artifacts saved in %s and %s", self.artifacts_dir, self.reports_dir)
        return {
            "metrics_df": df_metrics,
            "coverage_df": df_coverage,
        }


if __name__ == "__main__":
    evaluator = BaselineEvaluator()
    evaluator.run_all_evaluations()
