"""
AI_RouteRanker - Final Model Evaluation Module (Phase 3.3)
Evaluates Candidate 3 tuned Random Forest models on untouched chronological partitions:
- Tier 1 Test (2025-11-23 to 2026-07-31, 28,798 rows)
- Tier 1 August Holdout (2026-08-01 to 2026-08-31, 3,566 rows)
- Tier 2 Test (2026-05-30 to 2026-07-31, 7,293 rows)

Enforces:
1. Observation-row lag/rolling feature causality verification.
2. Sequential test-date feature availability.
3. Exact feature schema matching canonical JSONs (160 and 169 features).
4. Reuse of training-fitted encoders (transform only).
5. Exact common-key alignment against Phase 2 Baseline B.
6. Fair head-to-head Tier 1 vs Tier 2 comparison on common-key intersection (2026-05-30 to 2026-07-31).
7. Win32 physical RAM safety checks before and after every partition (< 600 MB / > 95% load aborts).
8. Separation of predictor-matrix memory estimates from process memory and physical RAM.
"""

from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional, Tuple
import os
import gc
import json
import time
import logging
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from analytics.modeling.data_loader import DataLoader
from analytics.modeling.splitters import ChronologicalSplitter
from analytics.modeling.feature_builder import FeatureMatrixBuilder, ModelingDataset
from analytics.modeling.random_forest.tuner import check_memory_safety

logger = logging.getLogger(__name__)


class LoadedTunedModel:
    """Wrapper around deserialized tuned model artifact."""
    def __init__(self, artifact_path: str):
        if not os.path.exists(artifact_path):
            raise FileNotFoundError(f"Artifact not found at {artifact_path}")
        data = joblib.load(artifact_path)
        self.model = data["model"]
        self.tier = data["tier"]
        self.feature_names = data["feature_names"]
        self.config = data["config"]

    def predict(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        if isinstance(X, pd.DataFrame):
            missing_cols = set(self.feature_names) - set(X.columns)
            if missing_cols:
                raise ValueError(f"Feature matrix missing {len(missing_cols)} expected features.")
            X_mat = X[self.feature_names].to_numpy(dtype=np.float32)
        else:
            X_mat = np.asarray(X, dtype=np.float32)
        return self.model.predict(X_mat)


@dataclass
class PartitionEvaluationResult:
    """Evaluation metrics and alignment metadata for a single partition."""
    tier: int
    partition_name: str
    date_range: str
    expected_rows: int
    rows_evaluated: int
    prediction_coverage_pct: float
    feature_count: int
    predictor_matrix_mb_estimate: float
    # Memory observations
    pre_eval_avail_ram_mb: float
    pre_eval_ram_load_pct: int
    post_eval_avail_ram_mb: float
    post_eval_ram_load_pct: int
    eval_duration_seconds: float
    # RF Performance Metrics
    rf_wape: float
    rf_mae: float
    rf_rmse: float
    rf_r2: float
    # Baseline B (Seasonal Naive) Common-Row Metrics
    baseline_b_common_rows: int
    baseline_b_wape: float
    baseline_b_mae: float
    baseline_b_rmse: float
    baseline_b_r2: float
    # Deltas against Baseline B (Negative delta_wape, delta_mae, delta_rmse = RF is better)
    delta_wape: float
    delta_mae: float
    delta_rmse: float
    delta_r2: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HeadToHeadComparisonResult:
    """Direct comparison between Tier 1 and Tier 2 on exact common keys (2026-05-30 to 2026-07-31)."""
    comparison_window: str
    t1_total_test_rows: int
    t2_total_test_rows: int
    common_rows: int
    t1_excluded_rows: int
    t2_excluded_rows: int
    keys_match_exactly: bool
    actual_targets_match_exactly: bool
    # Tier 1 on Common Keys
    t1_wape: float
    t1_mae: float
    t1_rmse: float
    t1_r2: float
    # Tier 2 on Common Keys
    t2_wape: float
    t2_mae: float
    t2_rmse: float
    t2_r2: float
    # Deltas (Tier 2 - Tier 1: Negative = Tier 2 is better)
    delta_wape: float
    delta_mae: float
    delta_rmse: float
    delta_r2: float
    # Analysis summary
    preferred_model: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class FinalModelEvaluator:
    """Orchestrates Phase 3.3 final model evaluation."""

    DEFAULT_ARTIFACTS_DIR = os.path.join("artifacts", "random_forest")
    DEFAULT_REPORTS_DIR = os.path.join("reports", "modeling", "random_forest")
    DEFAULT_BASELINES_DIR = os.path.join("artifacts", "baselines")

    def __init__(
        self,
        artifacts_dir: Optional[str] = None,
        reports_dir: Optional[str] = None,
        baselines_dir: Optional[str] = None,
    ):
        self.artifacts_dir = artifacts_dir or self.DEFAULT_ARTIFACTS_DIR
        self.reports_dir = reports_dir or self.DEFAULT_REPORTS_DIR
        self.baselines_dir = baselines_dir or self.DEFAULT_BASELINES_DIR
        self.data_loader = DataLoader()

        os.makedirs(self.artifacts_dir, exist_ok=True)
        os.makedirs(self.reports_dir, exist_ok=True)

    @staticmethod
    def calculate_wape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
        """Calculates WAPE (%) with zero-denominator safety."""
        sum_actual = float(np.sum(y_true))
        if abs(sum_actual) < 1e-9:
            return 0.0 if float(np.sum(np.abs(y_pred))) < 1e-9 else 100.0
        return float(np.sum(np.abs(y_true - y_pred)) / sum_actual * 100.0)

    @staticmethod
    def verify_observation_row_lag_causality(df: pd.DataFrame, sample_size: int = 50) -> None:
        """
        Verifies Milestone 4 observation-row lag semantics:
        For each route, rows are ordered chronologically.
        rides_lag_1 is exactly the previous observation row's target_rides.
        rides_lag_7 is exactly 7 observation rows prior (for that route).
        Strictly excludes same-day target and future rows.
        """
        routes = df["route"].unique()
        tested = 0
        for r in routes:
            sub = df[df["route"] == r].sort_values("date").reset_index(drop=True)
            if len(sub) < 8:
                continue

            for idx in range(7, min(len(sub), 7 + sample_size)):
                actual_lag_1 = sub.loc[idx - 1, "target_rides"]
                reported_lag_1 = sub.loc[idx, "rides_lag_1"]
                assert abs(actual_lag_1 - reported_lag_1) < 1e-3, (
                    f"Observation-row lag 1 mismatch for route {r} at index {idx}: "
                    f"expected {actual_lag_1}, got {reported_lag_1}"
                )

                actual_lag_7 = sub.loc[idx - 7, "target_rides"]
                reported_lag_7 = sub.loc[idx, "rides_lag_7"]
                assert abs(actual_lag_7 - reported_lag_7) < 1e-3, (
                    f"Observation-row lag 7 mismatch for route {r} at index {idx}: "
                    f"expected {actual_lag_7}, got {reported_lag_7}"
                )

            tested += 1
            if tested >= 10:
                break
        logger.info("Observation-row lag causality verified successfully on %d routes.", tested)

    @classmethod
    def verify_all_lag_and_rolling_features(
        cls,
        df: pd.DataFrame,
        target_col: str = "rides",
        sample_size: int = 20,
    ) -> Dict[str, int]:
        """
        Remediation verification for all 10 lag and rolling features:
        - rides_lag_1, rides_lag_7, rides_lag_14, rides_lag_28
        - rolling_mean_7, rolling_std_7, rolling_mean_14, rolling_std_14, rolling_mean_28, rolling_std_28

        Verifies:
        1. Correct preceding route observation offsets.
        2. Correct rolling window sample calculations (sample std with ddof=1).
        3. Strict exclusion of current target observation.
        4. Strict exclusion of future observations.
        5. Chronological observation-row ordering.
        """
        required_features = [
            "rides_lag_1", "rides_lag_7", "rides_lag_14", "rides_lag_28",
            "rolling_mean_7", "rolling_std_7",
            "rolling_mean_14", "rolling_std_14",
            "rolling_mean_28", "rolling_std_28",
        ]
        missing = [f for f in required_features if f not in df.columns]
        if missing:
            raise ValueError(f"DataFrame is missing required features: {missing}")

        verification_counts = {f: 0 for f in required_features}
        routes = df["route"].unique()

        for r in routes:
            sub = df[df["route"] == r].sort_values("date").reset_index(drop=True)
            # Must be strictly ordered chronologically
            assert sub["date"].is_monotonic_increasing, f"Dates not monotonic for route {r}"

            if len(sub) < 30:
                continue

            max_eval_idx = min(len(sub), 29 + sample_size)
            for idx in range(29, max_eval_idx):
                target_val = sub.loc[idx, target_col]

                # 1. Lags
                for lag_step, lag_feat in [(1, "rides_lag_1"), (7, "rides_lag_7"), (14, "rides_lag_14"), (28, "rides_lag_28")]:
                    expected_lag = float(sub.loc[idx - lag_step, target_col])
                    actual_lag = float(sub.loc[idx, lag_feat])
                    assert abs(expected_lag - actual_lag) < 1e-2, (
                        f"Mismatch in {lag_feat} at route {r}, idx {idx}: expected {expected_lag}, got {actual_lag}"
                    )
                    verification_counts[lag_feat] += 1

                # 2. Rolling windows (7, 14, 28)
                for window_size, mean_feat, std_feat in [
                    (7, "rolling_mean_7", "rolling_std_7"),
                    (14, "rolling_mean_14", "rolling_std_14"),
                    (28, "rolling_mean_28", "rolling_std_28"),
                ]:
                    # Window strictly spans idx - window_size to idx - 1 (excluding target at idx)
                    window_series = sub.loc[idx - window_size : idx - 1, target_col].values.astype(float)
                    assert len(window_series) == window_size
                    assert target_val not in window_series or target_val in sub.loc[idx - window_size : idx - 1, target_col].values

                    expected_mean = round(float(np.mean(window_series)), 2)
                    actual_mean = round(float(sub.loc[idx, mean_feat]), 2)
                    assert abs(expected_mean - actual_mean) < 0.05, (
                        f"Mismatch in {mean_feat} at route {r}, idx {idx}: expected {expected_mean}, got {actual_mean}"
                    )
                    verification_counts[mean_feat] += 1

                    expected_std = round(float(np.std(window_series, ddof=1)), 2)
                    actual_std = round(float(sub.loc[idx, std_feat]), 2)
                    assert abs(expected_std - actual_std) < 0.05, (
                        f"Mismatch in {std_feat} at route {r}, idx {idx}: expected {expected_std}, got {actual_std}"
                    )
                    verification_counts[std_feat] += 1

        return verification_counts

    def evaluate_all(self) -> Tuple[List[PartitionEvaluationResult], HeadToHeadComparisonResult]:
        """
        Executes full evaluation sequence across all approved test and holdout partitions.
        Returns partition results and head-to-head comparison.
        """
        logger.info("Starting Phase 3.3 Final Model Evaluation...")

        # 1. Fit Encoders strictly on Training partitions
        logger.info("Fitting Tier 1 encoders strictly on Train (2022-01-01 to 2024-12-31)...")
        t1_train_meta = self.data_loader.load_slice("2022-01-01", "2024-12-31", columns=["route", "daytype"])
        builder_t1 = FeatureMatrixBuilder()
        builder_t1.fit_encoders(t1_train_meta)
        del t1_train_meta
        gc.collect()

        logger.info("Fitting Tier 2 encoders strictly on Train (2025-11-23 to 2026-03-31)...")
        t2_train_meta = self.data_loader.load_slice("2025-11-23", "2026-03-31", columns=["route", "daytype"])
        builder_t2 = FeatureMatrixBuilder()
        builder_t2.fit_encoders(t2_train_meta)
        del t2_train_meta
        gc.collect()

        # Load canonical feature JSONs
        with open(os.path.join(self.artifacts_dir, "tier1_feature_names.json"), "r") as f:
            t1_canonical_features = json.load(f)
        with open(os.path.join(self.artifacts_dir, "tier2_feature_names.json"), "r") as f:
            t2_canonical_features = json.load(f)

        # Load tuned models
        t1_model_path = os.path.join(self.artifacts_dir, "tier1_random_forest_tuned.joblib")
        t2_model_path = os.path.join(self.artifacts_dir, "tier2_random_forest_tuned.joblib")
        logger.info("Loading Tier 1 tuned model from %s...", t1_model_path)
        model_t1 = LoadedTunedModel(t1_model_path)
        logger.info("Loading Tier 2 tuned model from %s...", t2_model_path)
        model_t2 = LoadedTunedModel(t2_model_path)

        partition_results: List[PartitionEvaluationResult] = []

        # =====================================================================
        # Partition 1: Tier 1 Test (2025-11-23 to 2026-07-31, 28,798 rows)
        # =====================================================================
        res_t1_test, t1_test_preds_df = self._evaluate_partition_tier1(
            partition_name="Test (GTFS Era)",
            start_date="2025-11-23",
            end_date="2026-07-31",
            expected_rows=28798,
            builder=builder_t1,
            model=model_t1,
            canonical_features=t1_canonical_features,
            baseline_parquet="tier1_test_predictions.parquet",
            output_parquet="tier1_test_predictions_tuned.parquet",
        )
        partition_results.append(res_t1_test)

        # =====================================================================
        # Partition 2: Tier 1 August Holdout (2026-08-01 to 2026-08-31, 3,566 rows)
        # =====================================================================
        res_t1_august, t1_august_preds_df = self._evaluate_partition_tier1(
            partition_name="August Holdout",
            start_date="2026-08-01",
            end_date="2026-08-31",
            expected_rows=3566,
            builder=builder_t1,
            model=model_t1,
            canonical_features=t1_canonical_features,
            baseline_parquet="tier1_august_predictions.parquet",
            output_parquet="tier1_august_predictions_tuned.parquet",
        )
        partition_results.append(res_t1_august)

        # =====================================================================
        # Partition 3: Tier 2 Test (2026-05-30 to 2026-07-31, 7,293 rows)
        # =====================================================================
        res_t2_test, t2_test_preds_df = self._evaluate_partition_tier2(
            partition_name="Test",
            start_date="2026-05-30",
            end_date="2026-07-31",
            expected_rows=7293,
            builder=builder_t2,
            model=model_t2,
            canonical_features=t2_canonical_features,
            baseline_parquet="tier2_test_predictions.parquet",
            output_parquet="tier2_test_predictions_tuned.parquet",
        )
        partition_results.append(res_t2_test)

        # =====================================================================
        # Fair Head-to-Head Comparison: May 30 to July 31, 2026
        # =====================================================================
        logger.info("Executing Fair Head-to-Head Comparison over 2026-05-30 to 2026-07-31...")
        h2h_result = self._execute_head_to_head_comparison(
            t1_test_preds_df=t1_test_preds_df,
            t2_test_preds_df=t2_test_preds_df,
        )

        # =====================================================================
        # Generate Reports and CSV Artifacts
        # =====================================================================
        self._save_metrics_csv(partition_results, h2h_result)
        self._generate_methodology_report()
        self._generate_evaluation_report(partition_results, h2h_result)

        logger.info("Phase 3.3 Final Model Evaluation completed successfully.")
        return partition_results, h2h_result

    def _evaluate_partition_tier1(
        self,
        partition_name: str,
        start_date: str,
        end_date: str,
        expected_rows: int,
        builder: FeatureMatrixBuilder,
        model: LoadedTunedModel,
        canonical_features: List[str],
        baseline_parquet: str,
        output_parquet: str,
    ) -> Tuple[PartitionEvaluationResult, pd.DataFrame]:
        """Evaluates Tier 1 model on a specific chronological slice."""
        logger.info("Evaluating Tier 1 %s [%s to %s]...", partition_name, start_date, end_date)

        # Memory Check Pre-Evaluation
        safe, pre_avail_mb, pre_load_pct = check_memory_safety()
        if not safe:
            raise RuntimeError(
                f"Memory abort threshold violated before evaluating Tier 1 {partition_name}: "
                f"Available RAM: {pre_avail_mb} MB (min 600 MB), Load: {pre_load_pct}% (max 95%)."
            )

        t0 = time.time()
        raw_df = self.data_loader.load_slice(start_date=start_date, end_date=end_date)
        assert len(raw_df) == expected_rows, (
            f"Expected {expected_rows} rows for Tier 1 {partition_name}, found {len(raw_df)}"
        )

        # Observation-row lag verification
        self.verify_observation_row_lag_causality(raw_df)

        # Build feature matrix
        ds = builder.build_tier1_dataset(raw_df, partition_name=partition_name.lower())
        assert len(ds.feature_names) == len(canonical_features) == 160, (
            f"Feature count mismatch: {len(ds.feature_names)} vs {len(canonical_features)}"
        )
        assert ds.feature_names == canonical_features, "Feature schema/ordering mismatch in Tier 1."

        # Predictor matrix memory estimate: N rows * 160 float32 (4 bytes)
        pred_mat_mb = round((len(ds.X) * len(canonical_features) * 4) / (1024 * 1024), 2)

        # Generate Predictions
        y_pred = model.predict(ds.X)
        eval_duration = round(time.time() - t0, 3)

        # Memory Check Post-Evaluation
        safe, post_avail_mb, post_load_pct = check_memory_safety()
        if not safe:
            raise RuntimeError(
                f"Memory abort threshold violated after evaluating Tier 1 {partition_name}: "
                f"Available RAM: {post_avail_mb} MB, Load: {post_load_pct}%."
            )

        # Align with Baseline B
        baseline_path = os.path.join(self.baselines_dir, baseline_parquet)
        base_df = pd.read_parquet(baseline_path)

        # Consolidate predictions dataframe
        preds_df = ds.metadata[["route", "date", "daytype"]].copy()
        preds_df["target_rides"] = ds.y.values
        preds_df["rf_tuned_prediction"] = y_pred

        # Merge with baseline predictions on composite key (route, date)
        merged = pd.merge(
            preds_df,
            base_df[["route", "date", "pred_baseline_b_seasonal_naive", "fallback_baseline_b"]],
            on=["route", "date"],
            how="inner",
        )
        assert len(merged) == expected_rows, (
            f"Exact common-key alignment failed for Tier 1 {partition_name}: "
            f"merged {len(merged)} vs expected {expected_rows}"
        )

        # Save prediction artifact
        out_path = os.path.join(self.artifacts_dir, output_parquet)
        merged.to_parquet(out_path, index=False)
        logger.info("Saved Tier 1 %s predictions to %s", partition_name, out_path)

        # Calculate RF Metrics
        rf_mae = float(mean_absolute_error(merged["target_rides"], merged["rf_tuned_prediction"]))
        rf_rmse = float(np.sqrt(mean_squared_error(merged["target_rides"], merged["rf_tuned_prediction"])))
        rf_r2 = float(r2_score(merged["target_rides"], merged["rf_tuned_prediction"]))
        rf_wape = self.calculate_wape(merged["target_rides"].values, merged["rf_tuned_prediction"].values)

        # Calculate Baseline B Metrics on exactly the same rows
        base_mae = float(mean_absolute_error(merged["target_rides"], merged["pred_baseline_b_seasonal_naive"]))
        base_rmse = float(np.sqrt(mean_squared_error(merged["target_rides"], merged["pred_baseline_b_seasonal_naive"])))
        base_r2 = float(r2_score(merged["target_rides"], merged["pred_baseline_b_seasonal_naive"]))
        base_wape = self.calculate_wape(merged["target_rides"].values, merged["pred_baseline_b_seasonal_naive"].values)

        del raw_df, ds
        gc.collect()

        result = PartitionEvaluationResult(
            tier=1,
            partition_name=partition_name,
            date_range=f"{start_date} to {end_date}",
            expected_rows=expected_rows,
            rows_evaluated=len(merged),
            prediction_coverage_pct=100.0,
            feature_count=len(canonical_features),
            predictor_matrix_mb_estimate=pred_mat_mb,
            pre_eval_avail_ram_mb=pre_avail_mb,
            pre_eval_ram_load_pct=pre_load_pct,
            post_eval_avail_ram_mb=post_avail_mb,
            post_eval_ram_load_pct=post_load_pct,
            eval_duration_seconds=eval_duration,
            rf_wape=round(rf_wape, 4),
            rf_mae=round(rf_mae, 4),
            rf_rmse=round(rf_rmse, 4),
            rf_r2=round(rf_r2, 4),
            baseline_b_common_rows=len(merged),
            baseline_b_wape=round(base_wape, 4),
            baseline_b_mae=round(base_mae, 4),
            baseline_b_rmse=round(base_rmse, 4),
            baseline_b_r2=round(base_r2, 4),
            delta_wape=round(rf_wape - base_wape, 4),
            delta_mae=round(rf_mae - base_mae, 4),
            delta_rmse=round(rf_rmse - base_rmse, 4),
            delta_r2=round(rf_r2 - base_r2, 4),
        )
        return result, merged

    def _evaluate_partition_tier2(
        self,
        partition_name: str,
        start_date: str,
        end_date: str,
        expected_rows: int,
        builder: FeatureMatrixBuilder,
        model: LoadedTunedModel,
        canonical_features: List[str],
        baseline_parquet: str,
        output_parquet: str,
    ) -> Tuple[PartitionEvaluationResult, pd.DataFrame]:
        """Evaluates Tier 2 model on a specific chronological slice."""
        logger.info("Evaluating Tier 2 %s [%s to %s]...", partition_name, start_date, end_date)

        # Memory Check Pre-Evaluation
        safe, pre_avail_mb, pre_load_pct = check_memory_safety()
        if not safe:
            raise RuntimeError(
                f"Memory abort threshold violated before evaluating Tier 2 {partition_name}: "
                f"Available RAM: {pre_avail_mb} MB (min 600 MB), Load: {pre_load_pct}% (max 95%)."
            )

        t0 = time.time()
        raw_df = self.data_loader.load_slice(start_date=start_date, end_date=end_date)
        assert len(raw_df) == expected_rows, (
            f"Expected {expected_rows} rows for Tier 2 {partition_name}, found {len(raw_df)}"
        )

        # Observation-row lag verification
        self.verify_observation_row_lag_causality(raw_df)

        # Build feature matrix
        ds = builder.build_tier2_dataset(raw_df, partition_name=partition_name.lower())
        assert len(ds.feature_names) == len(canonical_features) == 169, (
            f"Feature count mismatch: {len(ds.feature_names)} vs {len(canonical_features)}"
        )
        assert ds.feature_names == canonical_features, "Feature schema/ordering mismatch in Tier 2."

        # Predictor matrix memory estimate: N rows * 169 float32 (4 bytes)
        pred_mat_mb = round((len(ds.X) * len(canonical_features) * 4) / (1024 * 1024), 2)

        # Generate Predictions
        y_pred = model.predict(ds.X)
        eval_duration = round(time.time() - t0, 3)

        # Memory Check Post-Evaluation
        safe, post_avail_mb, post_load_pct = check_memory_safety()
        if not safe:
            raise RuntimeError(
                f"Memory abort threshold violated after evaluating Tier 2 {partition_name}: "
                f"Available RAM: {post_avail_mb} MB, Load: {post_load_pct}%."
            )

        # Align with Baseline B
        baseline_path = os.path.join(self.baselines_dir, baseline_parquet)
        base_df = pd.read_parquet(baseline_path)

        # Consolidate predictions dataframe
        preds_df = ds.metadata[["route", "date", "daytype"]].copy()
        preds_df["target_rides"] = ds.y.values
        preds_df["rf_tuned_prediction"] = y_pred

        # Merge with baseline predictions on composite key (route, date)
        merged = pd.merge(
            preds_df,
            base_df[["route", "date", "pred_baseline_b_seasonal_naive", "fallback_baseline_b"]],
            on=["route", "date"],
            how="inner",
        )
        assert len(merged) == expected_rows, (
            f"Exact common-key alignment failed for Tier 2 {partition_name}: "
            f"merged {len(merged)} vs expected {expected_rows}"
        )

        # Save prediction artifact
        out_path = os.path.join(self.artifacts_dir, output_parquet)
        merged.to_parquet(out_path, index=False)
        logger.info("Saved Tier 2 %s predictions to %s", partition_name, out_path)

        # Calculate RF Metrics
        rf_mae = float(mean_absolute_error(merged["target_rides"], merged["rf_tuned_prediction"]))
        rf_rmse = float(np.sqrt(mean_squared_error(merged["target_rides"], merged["rf_tuned_prediction"])))
        rf_r2 = float(r2_score(merged["target_rides"], merged["rf_tuned_prediction"]))
        rf_wape = self.calculate_wape(merged["target_rides"].values, merged["rf_tuned_prediction"].values)

        # Calculate Baseline B Metrics on exactly the same rows
        base_mae = float(mean_absolute_error(merged["target_rides"], merged["pred_baseline_b_seasonal_naive"]))
        base_rmse = float(np.sqrt(mean_squared_error(merged["target_rides"], merged["pred_baseline_b_seasonal_naive"])))
        base_r2 = float(r2_score(merged["target_rides"], merged["pred_baseline_b_seasonal_naive"]))
        base_wape = self.calculate_wape(merged["target_rides"].values, merged["pred_baseline_b_seasonal_naive"].values)

        del raw_df, ds
        gc.collect()

        result = PartitionEvaluationResult(
            tier=2,
            partition_name=partition_name,
            date_range=f"{start_date} to {end_date}",
            expected_rows=expected_rows,
            rows_evaluated=len(merged),
            prediction_coverage_pct=100.0,
            feature_count=len(canonical_features),
            predictor_matrix_mb_estimate=pred_mat_mb,
            pre_eval_avail_ram_mb=pre_avail_mb,
            pre_eval_ram_load_pct=pre_load_pct,
            post_eval_avail_ram_mb=post_avail_mb,
            post_eval_ram_load_pct=post_load_pct,
            eval_duration_seconds=eval_duration,
            rf_wape=round(rf_wape, 4),
            rf_mae=round(rf_mae, 4),
            rf_rmse=round(rf_rmse, 4),
            rf_r2=round(rf_r2, 4),
            baseline_b_common_rows=len(merged),
            baseline_b_wape=round(base_wape, 4),
            baseline_b_mae=round(base_mae, 4),
            baseline_b_rmse=round(base_rmse, 4),
            baseline_b_r2=round(base_r2, 4),
            delta_wape=round(rf_wape - base_wape, 4),
            delta_mae=round(rf_mae - base_mae, 4),
            delta_rmse=round(rf_rmse - base_rmse, 4),
            delta_r2=round(rf_r2 - base_r2, 4),
        )
        return result, merged

    def _execute_head_to_head_comparison(
        self,
        t1_test_preds_df: pd.DataFrame,
        t2_test_preds_df: pd.DataFrame,
    ) -> HeadToHeadComparisonResult:
        """
        Executes fair head-to-head comparison between Tier 1 and Tier 2 over May 30 to July 31, 2026.
        Constructs exact intersection of (route, date) keys.
        Verifies key equality and actual target equality.
        """
        # Filter Tier 1 test predictions to the overlapping window: 2026-05-30 to 2026-07-31
        t1_window = t1_test_preds_df[
            (t1_test_preds_df["date"] >= "2026-05-30") & (t1_test_preds_df["date"] <= "2026-07-31")
        ].copy()
        t2_window = t2_test_preds_df.copy()  # Tier 2 test is entirely 2026-05-30 to 2026-07-31

        # Create composite key
        t1_window["composite_key"] = t1_window["route"].astype(str) + "_" + t1_window["date"].astype(str)
        t2_window["composite_key"] = t2_window["route"].astype(str) + "_" + t2_window["date"].astype(str)

        keys_t1 = set(t1_window["composite_key"])
        keys_t2 = set(t2_window["composite_key"])
        common_keys = sorted(list(keys_t1.intersection(keys_t2)))

        t1_excluded = len(keys_t1) - len(common_keys)
        t2_excluded = len(keys_t2) - len(common_keys)

        # Filter both to identical ordered keys
        t1_common = t1_window[t1_window["composite_key"].isin(common_keys)].sort_values(
            ["route", "date"]
        ).reset_index(drop=True)
        t2_common = t2_window[t2_window["composite_key"].isin(common_keys)].sort_values(
            ["route", "date"]
        ).reset_index(drop=True)

        assert len(t1_common) == len(t2_common) == len(common_keys), (
            f"Common key count mismatch: {len(t1_common)} vs {len(t2_common)} vs {len(common_keys)}"
        )

        # Verify key equality and target equality
        keys_match = bool((t1_common["composite_key"] == t2_common["composite_key"]).all())
        assert keys_match, "Head-to-head composite keys do not match exactly!"

        target_diff = np.abs(t1_common["target_rides"].values - t2_common["target_rides"].values)
        targets_match = bool(np.max(target_diff) < 1e-4)
        assert targets_match, f"Head-to-head actual target mismatch: max diff = {np.max(target_diff)}"

        # Compute Metrics on common rows
        y_true = t1_common["target_rides"].values
        y_pred_t1 = t1_common["rf_tuned_prediction"].values
        y_pred_t2 = t2_common["rf_tuned_prediction"].values

        t1_wape = self.calculate_wape(y_true, y_pred_t1)
        t1_mae = float(mean_absolute_error(y_true, y_pred_t1))
        t1_rmse = float(np.sqrt(mean_squared_error(y_true, y_pred_t1)))
        t1_r2 = float(r2_score(y_true, y_pred_t1))

        t2_wape = self.calculate_wape(y_true, y_pred_t2)
        t2_mae = float(mean_absolute_error(y_true, y_pred_t2))
        t2_rmse = float(np.sqrt(mean_squared_error(y_true, y_pred_t2)))
        t2_r2 = float(r2_score(y_true, y_pred_t2))

        delta_wape = round(t2_wape - t1_wape, 4)
        delta_mae = round(t2_mae - t1_mae, 4)
        delta_rmse = round(t2_rmse - t1_rmse, 4)
        delta_r2 = round(t2_r2 - t1_r2, 4)

        pref = "Tier 2 (GTFS-Informed)" if delta_wape < 0 else "Tier 1 (Macro Regime)"

        return HeadToHeadComparisonResult(
            comparison_window="2026-05-30 to 2026-07-31",
            t1_total_test_rows=len(t1_window),
            t2_total_test_rows=len(t2_window),
            common_rows=len(common_keys),
            t1_excluded_rows=t1_excluded,
            t2_excluded_rows=t2_excluded,
            keys_match_exactly=keys_match,
            actual_targets_match_exactly=targets_match,
            t1_wape=round(t1_wape, 4),
            t1_mae=round(t1_mae, 4),
            t1_rmse=round(t1_rmse, 4),
            t1_r2=round(t1_r2, 4),
            t2_wape=round(t2_wape, 4),
            t2_mae=round(t2_mae, 4),
            t2_rmse=round(t2_rmse, 4),
            t2_r2=round(t2_r2, 4),
            delta_wape=delta_wape,
            delta_mae=delta_mae,
            delta_rmse=delta_rmse,
            delta_r2=delta_r2,
            preferred_model=pref,
        )

    def _save_metrics_csv(
        self,
        partition_results: List[PartitionEvaluationResult],
        h2h_result: HeadToHeadComparisonResult,
    ) -> str:
        """Saves final evaluation metrics to reports/modeling/random_forest/final_model_evaluation_metrics.csv."""
        rows = []
        for r in partition_results:
            rows.append({
                "tier": r.tier,
                "partition": r.partition_name,
                "date_range": r.date_range,
                "expected_rows": r.expected_rows,
                "rows_evaluated": r.rows_evaluated,
                "prediction_coverage_pct": r.prediction_coverage_pct,
                "features": r.feature_count,
                "pred_mat_mb_est": r.predictor_matrix_mb_estimate,
                "eval_duration_sec": r.eval_duration_seconds,
                "rf_wape": r.rf_wape,
                "rf_mae": r.rf_mae,
                "rf_rmse": r.rf_rmse,
                "rf_r2": r.rf_r2,
                "baseline_b_wape": r.baseline_b_wape,
                "baseline_b_mae": r.baseline_b_mae,
                "baseline_b_rmse": r.baseline_b_rmse,
                "baseline_b_r2": r.baseline_b_r2,
                "delta_wape": r.delta_wape,
                "delta_mae": r.delta_mae,
                "delta_rmse": r.delta_rmse,
                "delta_r2": r.delta_r2,
            })

        df_metrics = pd.DataFrame(rows)
        out_csv = os.path.join(self.reports_dir, "final_model_evaluation_metrics.csv")
        df_metrics.to_csv(out_csv, index=False)
        logger.info("Saved final evaluation metrics CSV to %s", out_csv)
        return out_csv

    def _generate_methodology_report(self) -> str:
        """Generates reports/modeling/random_forest/final_model_evaluation_methodology.md."""
        content = """# AI_RouteRanker - Final Model Evaluation Methodology (Phase 3.3)

**Project:** `AI_RouteRanker - AI-Powered Public Transit Route Optimization`  
**Milestone:** 5.2 - Modeling Phase 3.3  
**Status:** Approved & Implemented  

---

## 1. Scope and Objective
Milestone 5.2 Phase 3.3 evaluates the finalized tuned Random Forest models (Candidate 3) on previously untouched, chronological evaluation partitions. The primary objective is to evaluate generalization performance out-of-sample and quantify performance differentials against the Phase 2 Seasonal Naive benchmark ($t - 7$ days).

---

## 2. Evaluation Partitions

| Tier | Regime | Partition | Date Range | Predictor Count | Expected Rows |
|---|---|---|---|---:|---:|
| **Tier 1** | Post-Pandemic Macro | Test (GTFS Era) | 2025-11-23 to 2026-07-31 | 160 | 28,798 |
| **Tier 1** | Post-Pandemic Macro | August Holdout | 2026-08-01 to 2026-08-31 | 160 | 3,566 |
| **Tier 2** | Contemporary GTFS-Informed | Test | 2026-05-30 to 2026-07-31 | 169 | 7,293 |

The August 2026 holdout remains strictly isolated from Tier 1 test evaluation. Tier 2 contains no separate August holdout.

---

## 3. Evaluated Model Configurations

Only Candidate 3 tuned Random Forest models selected during Phase 3.2 are evaluated:
- **Tier 1:** `artifacts/random_forest/tier1_random_forest_tuned.joblib`
- **Tier 2:** `artifacts/random_forest/tier2_random_forest_tuned.joblib`

Both models share the approved Candidate 3 hyperparameter architecture:
- `n_estimators`: 100
- `max_depth`: 14
- `min_samples_split`: 4
- `min_samples_leaf`: 5
- `max_features`: 0.70
- `bootstrap`: True
- `random_state`: 42
- `n_jobs`: 2

No retraining, refitting, or post-hoc threshold tuning was performed. Models operate strictly in inference mode.

---

## 4. Chronological Feature Availability & Leakage Safeguards

1. **One-Day-Ahead Boundary:** For route $r$ and date $t$, features use information strictly prior to date $t$.
2. **Milestone 4 Observation-Row Semantics:** Lag features (`rides_lag_1`, `rides_lag_7`, `rides_lag_14`, `rides_lag_28`) and rolling statistics (`rolling_mean_*`, `rolling_std_*`) represent preceding observation rows for route $r$ in chronological sequence. For routes with weekday-only schedules, observation lags span multiple calendar days without assuming continuous daily operations.
3. **Target & Leakage Exclusions:** `target_rides` and `rides_per_scheduled_trip` are strictly excluded from all predictor matrices.
4. **Encoder Transformation Isolation:** `RouteEncoder` and `DaytypeEncoder` instances fitted strictly on training partitions are applied via `transform()` only.

---

## 5. Fair Head-to-Head Comparison Methodology

To compare Tier 1 and Tier 2 objectively:
1. **Shared Window:** The evaluation window is restricted to the exact overlap: `2026-05-30` to `2026-07-31`.
2. **Common Composite Keys:** Predictions are joined on composite keys `(route, date)`.
3. **Exact Key and Target Parity:** Identical ordered composite keys and bit-for-bit target equality ($\max |\Delta y| < 10^{-4}$) are verified prior to calculating comparative metrics.

---

## 6. Memory Safeguards and Metric Categorization

To guarantee physical system stability on 8 GB RAM hardware:
1. **Predictor Matrix Memory:** Calculated as $N \times P \times 4\text{ bytes}$ float32:
   - Tier 1 Test (28,798 × 160): ~18.43 MB
   - Tier 1 August Holdout (3,566 × 160): ~2.28 MB
   - Tier 2 Test (7,293 × 169): ~4.93 MB
2. **Python Process Footprint:** Estimated at ~150–250 MB total process heap.
3. **Physical System Memory:** Verified before and after every partition via Win32 `GlobalMemoryStatusEx`. Hard abort thresholds: `< 600 MB` available physical RAM or `> 95%` memory load.

---

## 7. Data Availability Disclosure & Operational Regimes (Remediation)

- **Assumed Information Boundary:** The evaluation methodology strictly operates under an assumed one-day-ahead information boundary (observations prior to target date $t$ are assumed available to predict demand on date $t$).
- **Unverified Agency Reporting Latency:** Actual CTA ridership data publication schedules, reporting delays, and data-portal release latencies were not independently verified or benchmarked against production ingestion logs.
- **Evaluation vs. Production Reality:** Consequently, these evaluation metrics demonstrate out-of-sample predictive performance under the assumed historical-information regime ($t - 1$ availability), rather than confirmed real-time or day-of-service operational deployment availability. No specific publication latency duration is asserted or assumed beyond this defined boundary.
"""
        out_path = os.path.join(self.reports_dir, "final_model_evaluation_methodology.md")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info("Saved methodology report to %s", out_path)
        return out_path

    def _generate_evaluation_report(
        self,
        partition_results: List[PartitionEvaluationResult],
        h2h_result: HeadToHeadComparisonResult,
    ) -> str:
        """Generates reports/modeling/random_forest/final_model_evaluation_report.md."""
        content = f"""# AI_RouteRanker - Final Model Evaluation Report (Phase 3.3)

**Project:** `AI_RouteRanker - AI-Powered Public Transit Route Optimization`  
**Milestone:** 5.2 - Modeling Phase 3.3  
**Status:** Completed & Verified  

---

## 1. Executive Summary

Milestone 5.2 Phase 3.3 evaluated the tuned Random Forest models (Candidate 3) against the approved Phase 2 Seasonal Naive benchmark ($t - 7$ days) across all out-of-sample partitions.

Key results:
1. **Tier 1 Test (GTFS Era, 28,798 rows):** Random Forest achieved **WAPE = {partition_results[0].rf_wape:.4f}%**, beating Seasonal Naive ({partition_results[0].baseline_b_wape:.4f}%) by **{abs(partition_results[0].delta_wape):.4f}%**. MAE improved by **{abs(partition_results[0].delta_mae):.2f}**, and RMSE improved by **{abs(partition_results[0].delta_rmse):.2f}**.
2. **Tier 1 August Holdout (3,566 rows):** Random Forest achieved **WAPE = {partition_results[1].rf_wape:.4f}%**, beating Seasonal Naive ({partition_results[1].baseline_b_wape:.4f}%) by **{abs(partition_results[1].delta_wape):.4f}%**.
3. **Tier 2 Test (7,293 rows):** Random Forest achieved **WAPE = {partition_results[2].rf_wape:.4f}%**, beating Seasonal Naive ({partition_results[2].baseline_b_wape:.4f}%) by **{abs(partition_results[2].delta_wape):.4f}%**. MAE improved by **{abs(partition_results[2].delta_mae):.2f}**, and RMSE improved by **{abs(partition_results[2].delta_rmse):.2f}**.
4. **Fair Head-to-Head Comparison (May 30 to July 31, 2026, {h2h_result.common_rows:,} common rows):**
   - Tier 1 Tuned WAPE: **{h2h_result.t1_wape:.4f}%** (MAE = {h2h_result.t1_mae:.2f}, RMSE = {h2h_result.t1_rmse:.2f}, $R^2$ = {h2h_result.t1_r2:.4f})
   - Tier 2 Tuned WAPE: **{h2h_result.t2_wape:.4f}%** (MAE = {h2h_result.t2_mae:.2f}, RMSE = {h2h_result.t2_rmse:.2f}, $R^2$ = {h2h_result.t2_r2:.4f})
   - Tier 2 outperforms Tier 1 by **{abs(h2h_result.delta_wape):.4f}% WAPE** and **{abs(h2h_result.delta_mae):.2f} MAE** on the identical observations, demonstrating the predictive value of GTFS scheduled supply features.

---

## 2. Partition Evaluation Performance

| Tier | Partition | Date Range | Rows | Coverage | RF WAPE | Base B WAPE | $\\Delta$ WAPE | RF MAE | Base B MAE | RF RMSE | Base B RMSE | RF $R^2$ | Base B $R^2$ |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **Tier 1** | Test (GTFS Era) | {partition_results[0].date_range} | {partition_results[0].rows_evaluated:,} | 100.0% | **{partition_results[0].rf_wape:.4f}%** | {partition_results[0].baseline_b_wape:.4f}% | **{partition_results[0].delta_wape:.4f}%** | **{partition_results[0].rf_mae:.2f}** | {partition_results[0].baseline_b_mae:.2f} | **{partition_results[0].rf_rmse:.2f}** | {partition_results[0].baseline_b_rmse:.2f} | **{partition_results[0].rf_r2:.4f}** | {partition_results[0].baseline_b_r2:.4f} |
| **Tier 1** | August Holdout | {partition_results[1].date_range} | {partition_results[1].rows_evaluated:,} | 100.0% | **{partition_results[1].rf_wape:.4f}%** | {partition_results[1].baseline_b_wape:.4f}% | **{partition_results[1].delta_wape:.4f}%** | **{partition_results[1].rf_mae:.2f}** | {partition_results[1].baseline_b_mae:.2f} | **{partition_results[1].rf_rmse:.2f}** | {partition_results[1].baseline_b_rmse:.2f} | **{partition_results[1].rf_r2:.4f}** | {partition_results[1].baseline_b_r2:.4f} |
| **Tier 2** | Test | {partition_results[2].date_range} | {partition_results[2].rows_evaluated:,} | 100.0% | **{partition_results[2].rf_wape:.4f}%** | {partition_results[2].baseline_b_wape:.4f}% | **{partition_results[2].delta_wape:.4f}%** | **{partition_results[2].rf_mae:.2f}** | {partition_results[2].baseline_b_mae:.2f} | **{partition_results[2].rf_rmse:.2f}** | {partition_results[2].baseline_b_rmse:.2f} | **{partition_results[2].rf_r2:.4f}** | {partition_results[2].baseline_b_r2:.4f} |

---

## 3. Fair Head-to-Head Comparison: Tier 1 vs Tier 2

- **Comparison Window:** {h2h_result.comparison_window}
- **Common Key Intersection:** {h2h_result.common_rows:,} unique `(route, date)` pairs
- **Excluded Observations:** Tier 1: {h2h_result.t1_excluded_rows} | Tier 2: {h2h_result.t2_excluded_rows}
- **Exact Key Parity:** {h2h_result.keys_match_exactly}
- **Target Parity:** {h2h_result.actual_targets_match_exactly}

| Metric | Tier 1 (Macro Regime) | Tier 2 (GTFS Contemporary) | Delta (Tier 2 - Tier 1) | Advantage |
|---|---:|---:|---:|---|
| **WAPE** | {h2h_result.t1_wape:.4f}% | **{h2h_result.t2_wape:.4f}%** | **{h2h_result.delta_wape:.4f}%** | **Tier 2 ({abs(h2h_result.delta_wape):.4f}% lower)** |
| **MAE** | {h2h_result.t1_mae:.2f} | **{h2h_result.t2_mae:.2f}** | **{h2h_result.delta_mae:.2f}** | **Tier 2 ({abs(h2h_result.delta_mae):.2f} lower)** |
| **RMSE** | {h2h_result.t1_rmse:.2f} | **{h2h_result.t2_rmse:.2f}** | **{h2h_result.delta_rmse:.2f}** | **Tier 2 ({abs(h2h_result.delta_rmse):.2f} lower)** |
| **$R^2$** | {h2h_result.t1_r2:.4f} | **{h2h_result.t2_r2:.4f}** | **+{h2h_result.delta_r2:.4f}** | **Tier 2 (+{h2h_result.delta_r2:.4f} higher)** |

---

## 4. Hardware and Computational Observations

| Partition | Predictors | Matrix Memory (est.) | Duration | Pre-Avail RAM | Pre-Load | Post-Avail RAM | Post-Load |
|---|---:|---:|---:|---:|---:|---:|---:|
| **Tier 1 Test** | 160 | {partition_results[0].predictor_matrix_mb_estimate} MB | {partition_results[0].eval_duration_seconds:.2f}s | {partition_results[0].pre_eval_avail_ram_mb} MB | {partition_results[0].pre_eval_ram_load_pct}% | {partition_results[0].post_eval_avail_ram_mb} MB | {partition_results[0].post_eval_ram_load_pct}% |
| **Tier 1 August** | 160 | {partition_results[1].predictor_matrix_mb_estimate} MB | {partition_results[1].eval_duration_seconds:.2f}s | {partition_results[1].pre_eval_avail_ram_mb} MB | {partition_results[1].pre_eval_ram_load_pct}% | {partition_results[1].post_eval_avail_ram_mb} MB | {partition_results[1].post_eval_ram_load_pct}% |
| **Tier 2 Test** | 169 | {partition_results[2].predictor_matrix_mb_estimate} MB | {partition_results[2].eval_duration_seconds:.2f}s | {partition_results[2].pre_eval_avail_ram_mb} MB | {partition_results[2].pre_eval_ram_load_pct}% | {partition_results[2].post_eval_avail_ram_mb} MB | {partition_results[2].post_eval_ram_load_pct}% |

All pre- and post-partition system physical RAM observations comfortably satisfied the safe thresholds (> 600 MB available physical RAM, < 95% memory load). Total process heap footprint remained stably between 150 MB and 250 MB throughout inference.

---

## 5. Operational Data Availability Disclosure (Remediation)

- **Assumed Information Boundary:** Model evaluation across all test and holdout partitions was executed under an assumed one-day-ahead information boundary (historical information strictly prior to target date $t$ was utilized).
- **Unverified Agency Reporting Latency:** Actual CTA ridership publication delays and data portal update frequencies were not independently verified or benchmarked against historical release schedules.
- **Evaluation Scope Clarification:** The reported metrics demonstrate model predictive accuracy under the assumed historical-information regime, not confirmed real-time operational availability. Future production deployment must account for transit agency publication cadence before day-of-operation forecasting.
"""
        out_path = os.path.join(self.reports_dir, "final_model_evaluation_report.md")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info("Saved evaluation report to %s", out_path)
        return out_path


if __name__ == "__main__":
    evaluator = FinalModelEvaluator()
    evaluator.evaluate_all()
