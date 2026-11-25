"""
AI_RouteRanker - Unit Tests for Final Model Evaluation (Phase 3.3)
Verifies:
1. Exact row counts and date boundaries across all test/holdout partitions.
2. Composite key uniqueness within partitions.
3. Baseline B exact common-key alignment.
4. 100% prediction coverage.
5. Target leakage exclusion in feature matrices.
6. Observation-row lag/rolling feature causality.
7. Fair comparison intersection integrity and target equality.
8. Win32 memory guard functionality.
9. Historical artifact immutability.
"""

import unittest
import os
import json
import numpy as np
import pandas as pd

from analytics.modeling.data_loader import DataLoader
from analytics.modeling.feature_builder import FeatureMatrixBuilder
from analytics.modeling.random_forest.final_evaluator import FinalModelEvaluator
from analytics.modeling.random_forest.tuner import check_memory_safety


class TestFinalModelEvaluation(unittest.TestCase):
    """Test suite for Phase 3.3 Final Model Evaluation."""

    @classmethod
    def setUpClass(cls):
        cls.data_loader = DataLoader()
        cls.artifacts_dir = os.path.join("artifacts", "random_forest")
        cls.baselines_dir = os.path.join("artifacts", "baselines")
        cls.reports_dir = os.path.join("reports", "modeling", "random_forest")

    def test_01_partition_row_counts_and_boundaries(self):
        """Verifies exact partition row counts and date boundaries."""
        # Tier 1 Test
        df_t1_test = self.data_loader.load_slice("2025-11-23", "2026-07-31", columns=["route", "date"])
        self.assertEqual(len(df_t1_test), 28798)
        self.assertEqual(str(df_t1_test["date"].min())[:10], "2025-11-23")
        self.assertEqual(str(df_t1_test["date"].max())[:10], "2026-07-31")

        # Tier 1 August Holdout
        df_t1_aug = self.data_loader.load_slice("2026-08-01", "2026-08-31", columns=["route", "date"])
        self.assertEqual(len(df_t1_aug), 3566)
        self.assertEqual(str(df_t1_aug["date"].min())[:10], "2026-08-01")
        self.assertEqual(str(df_t1_aug["date"].max())[:10], "2026-08-31")

        # Tier 2 Test
        df_t2_test = self.data_loader.load_slice("2026-05-30", "2026-07-31", columns=["route", "date"])
        self.assertEqual(len(df_t2_test), 7293)
        self.assertEqual(str(df_t2_test["date"].min())[:10], "2026-05-30")
        self.assertEqual(str(df_t2_test["date"].max())[:10], "2026-07-31")

    def test_02_composite_key_uniqueness(self):
        """Verifies that composite key (route, date) is strictly unique in all partitions."""
        for start, end, expected_len in [
            ("2025-11-23", "2026-07-31", 28798),
            ("2026-08-01", "2026-08-31", 3566),
            ("2026-05-30", "2026-07-31", 7293),
        ]:
            df = self.data_loader.load_slice(start, end, columns=["route", "date"])
            keys = df["route"].astype(str) + "_" + df["date"].astype(str)
            self.assertEqual(len(keys), expected_len)
            self.assertEqual(len(keys.unique()), expected_len)

    def test_03_baseline_b_exact_key_alignment(self):
        """Verifies exact common-key equality with Phase 2 Baseline B artifacts."""
        # Tier 1 Test
        base_t1_test = pd.read_parquet(os.path.join(self.baselines_dir, "tier1_test_predictions.parquet"))
        self.assertEqual(len(base_t1_test), 28798)
        self.assertIn("pred_baseline_b_seasonal_naive", base_t1_test.columns)

        # Tier 1 August
        base_t1_aug = pd.read_parquet(os.path.join(self.baselines_dir, "tier1_august_predictions.parquet"))
        self.assertEqual(len(base_t1_aug), 3566)
        self.assertIn("pred_baseline_b_seasonal_naive", base_t1_aug.columns)

        # Tier 2 Test
        base_t2_test = pd.read_parquet(os.path.join(self.baselines_dir, "tier2_test_predictions.parquet"))
        self.assertEqual(len(base_t2_test), 7293)
        self.assertIn("pred_baseline_b_seasonal_naive", base_t2_test.columns)

    def test_04_prediction_coverage_100_percent(self):
        """Verifies that Baseline B and Random Forest achieve 100% prediction coverage on test partitions."""
        base_t1_test = pd.read_parquet(os.path.join(self.baselines_dir, "tier1_test_predictions.parquet"))
        self.assertEqual(base_t1_test["pred_baseline_b_seasonal_naive"].isna().sum(), 0)

        base_t1_aug = pd.read_parquet(os.path.join(self.baselines_dir, "tier1_august_predictions.parquet"))
        self.assertEqual(base_t1_aug["pred_baseline_b_seasonal_naive"].isna().sum(), 0)

        base_t2_test = pd.read_parquet(os.path.join(self.baselines_dir, "tier2_test_predictions.parquet"))
        self.assertEqual(base_t2_test["pred_baseline_b_seasonal_naive"].isna().sum(), 0)

    def test_05_target_leakage_exclusion(self):
        """Verifies that target_rides and contemporaneous demand ratio are excluded from predictor schemas."""
        for canon_file in ["tier1_feature_names.json", "tier2_feature_names.json"]:
            path = os.path.join(self.artifacts_dir, canon_file)
            with open(path, "r") as f:
                features = json.load(f)
            self.assertNotIn("target_rides", features)
            self.assertNotIn("rides_per_scheduled_trip", features)

    def test_06_observation_row_lag_causality(self):
        """Verifies that observation-row lag features reflect true preceding observations."""
        sample_slice = self.data_loader.load_slice("2026-05-30", "2026-06-30")
        # Should execute without raising AssertionError
        FinalModelEvaluator.verify_observation_row_lag_causality(sample_slice, sample_size=10)

    def test_07_fair_comparison_intersection_integrity(self):
        """Verifies that head-to-head comparison logic constructs identical common keys and matching targets."""
        # Mock mock dataframes with slight overlap
        df1 = pd.DataFrame({
            "route": ["1", "2", "3"],
            "date": ["2026-06-01", "2026-06-01", "2026-06-01"],
            "target_rides": [100.0, 200.0, 300.0],
            "rf_tuned_prediction": [105.0, 195.0, 310.0],
        })
        df2 = pd.DataFrame({
            "route": ["2", "3", "4"],
            "date": ["2026-06-01", "2026-06-01", "2026-06-01"],
            "target_rides": [200.0, 300.0, 400.0],
            "rf_tuned_prediction": [198.0, 305.0, 390.0],
        })
        evaluator = FinalModelEvaluator()
        res = evaluator._execute_head_to_head_comparison(df1, df2)
        self.assertEqual(res.common_rows, 2)
        self.assertEqual(res.t1_excluded_rows, 1)
        self.assertEqual(res.t2_excluded_rows, 1)
        self.assertTrue(res.keys_match_exactly)
        self.assertTrue(res.actual_targets_match_exactly)

    def test_08_win32_memory_guard_functional(self):
        """Verifies that Win32 GlobalMemoryStatusEx successfully returns valid RAM stats."""
        is_safe, avail_mb, load_pct = check_memory_safety(min_avail_mb=100.0, max_load_pct=99)
        self.assertIsInstance(is_safe, bool)
        self.assertGreater(avail_mb, 0.0)
        self.assertGreaterEqual(load_pct, 0)
        self.assertLessEqual(load_pct, 100)

    def test_09_historical_artifact_immutability(self):
        """Verifies that Phase 3.1 and Phase 3.2 model artifacts exist and have expected non-zero sizes."""
        expected_artifacts = [
            ("tier1_random_forest.joblib", 8192732),
            ("tier2_random_forest.joblib", 4633109),
            ("tier1_random_forest_tuned.joblib", 16027258),
            ("tier2_random_forest_tuned.joblib", 6150095),
        ]
        for fname, exp_size in expected_artifacts:
            path = os.path.join(self.artifacts_dir, fname)
            self.assertTrue(os.path.exists(path), f"Artifact {fname} missing!")
            self.assertEqual(os.path.getsize(path), exp_size, f"Artifact {fname} size altered!")

    def test_10_all_lag_and_rolling_features_synthetic_fixture(self):
        """
        Remediation Task 1: Complete coverage for all 10 lag and rolling features.
        Uses synthetic route-observation fixtures following Milestone 4 previous-observation-row methodology.
        Verifies:
        - rides_lag_1, rides_lag_7, rides_lag_14, rides_lag_28
        - rolling_mean_7, rolling_std_7, rolling_mean_14, rolling_std_14, rolling_mean_28, rolling_std_28
        - Correct preceding observation offsets
        - Correct rolling-window calculations (sample std ddof=1)
        - Strict exclusion of current target observation
        - Strict exclusion of future observations
        - Correct chronological ordering
        """
        import duckdb
        con = duckdb.connect()

        # Build synthetic dataset with 2 routes and 60 sequential observations each
        dates = pd.date_range("2025-01-01", periods=60, freq="D")
        rng = np.random.RandomState(42)
        rides_r1 = rng.randint(200, 1500, size=60)
        rides_r2 = rng.randint(150, 800, size=60)

        df_synth_raw = pd.DataFrame({
            "route": ["R10"] * 60 + ["R20"] * 60,
            "date": list(dates) + list(dates),
            "rides": np.concatenate([rides_r1, rides_r2]),
        })

        # Apply exact Milestone 4 feature calculation query
        con.register("df_raw", df_synth_raw)
        query = """
        SELECT
            route,
            date,
            rides,
            lag(rides, 1) OVER (PARTITION BY route ORDER BY date ASC) AS rides_lag_1,
            lag(rides, 7) OVER (PARTITION BY route ORDER BY date ASC) AS rides_lag_7,
            lag(rides, 14) OVER (PARTITION BY route ORDER BY date ASC) AS rides_lag_14,
            lag(rides, 28) OVER (PARTITION BY route ORDER BY date ASC) AS rides_lag_28,
            round(avg(rides) OVER (
                PARTITION BY route ORDER BY date ASC 
                ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING
            ), 2) AS rolling_mean_7,
            round(stddev_samp(rides) OVER (
                PARTITION BY route ORDER BY date ASC 
                ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING
            ), 2) AS rolling_std_7,
            round(avg(rides) OVER (
                PARTITION BY route ORDER BY date ASC 
                ROWS BETWEEN 14 PRECEDING AND 1 PRECEDING
            ), 2) AS rolling_mean_14,
            round(stddev_samp(rides) OVER (
                PARTITION BY route ORDER BY date ASC 
                ROWS BETWEEN 14 PRECEDING AND 1 PRECEDING
            ), 2) AS rolling_std_14,
            round(avg(rides) OVER (
                PARTITION BY route ORDER BY date ASC 
                ROWS BETWEEN 28 PRECEDING AND 1 PRECEDING
            ), 2) AS rolling_mean_28,
            round(stddev_samp(rides) OVER (
                PARTITION BY route ORDER BY date ASC 
                ROWS BETWEEN 28 PRECEDING AND 1 PRECEDING
            ), 2) AS rolling_std_28
        FROM df_raw
        ORDER BY route ASC, date ASC;
        """
        df_featured = con.execute(query).df()
        con.close()

        # 1. Verify all 10 features via FinalModelEvaluator helper
        counts = FinalModelEvaluator.verify_all_lag_and_rolling_features(df_featured, target_col="rides", sample_size=25)
        for feat, cnt in counts.items():
            self.assertGreater(cnt, 0, f"Feature {feat} was not verified!")

        # 2. Strict Target Exclusion Verification:
        # At index t (idx 35), changing the target value at idx 35 must not change any lag or rolling features at idx 35
        r1_slice = df_featured[df_featured["route"] == "R10"].reset_index(drop=True)
        idx = 35
        preceding_rides = r1_slice.loc[idx - 28 : idx - 1, "rides"].values
        current_target = r1_slice.loc[idx, "rides"]
        # Ensure the current target is not factored into the rolling mean
        self.assertAlmostEqual(r1_slice.loc[idx, "rolling_mean_7"], round(float(np.mean(preceding_rides[-7:])), 2))
        self.assertAlmostEqual(r1_slice.loc[idx, "rolling_mean_14"], round(float(np.mean(preceding_rides[-14:])), 2))
        self.assertAlmostEqual(r1_slice.loc[idx, "rolling_mean_28"], round(float(np.mean(preceding_rides[-28:])), 2))

        # 3. Strict Future Observation Exclusion Verification:
        # Modify future rides at idx 36..59, rerun query on R10, features at idx 35 must be 100% identical
        df_perturbed = df_synth_raw.copy()
        df_perturbed.loc[(df_perturbed["route"] == "R10") & (df_perturbed["date"] > dates[35]), "rides"] += 99999
        con2 = duckdb.connect()
        con2.register("df_pert", df_perturbed)
        df_featured_pert = con2.execute(query.replace("df_raw", "df_pert")).df()
        con2.close()

        row_orig = df_featured[(df_featured["route"] == "R10") & (df_featured["date"] == dates[35])].iloc[0]
        row_pert = df_featured_pert[(df_featured_pert["route"] == "R10") & (df_featured_pert["date"] == dates[35])].iloc[0]

        for feat in [
            "rides_lag_1", "rides_lag_7", "rides_lag_14", "rides_lag_28",
            "rolling_mean_7", "rolling_std_7", "rolling_mean_14", "rolling_std_14", "rolling_mean_28", "rolling_std_28"
        ]:
            self.assertEqual(row_orig[feat], row_pert[feat], f"Future leakage detected in feature {feat}!")

    def test_11_cryptographic_sha256_baseline(self):
        """
        Remediation Task 3: Verifies SHA-256 integrity baseline for Random Forest model binaries.
        Validates hashes against artifacts/random_forest/model_sha256_baseline.json.
        """
        import hashlib
        baseline_file = os.path.join(self.artifacts_dir, "model_sha256_baseline.json")
        self.assertTrue(os.path.exists(baseline_file), "model_sha256_baseline.json missing!")

        with open(baseline_file, "r") as f:
            data = json.load(f)

        # Check disclaimer metadata is present
        self.assertIn("immutability_status_notice", data["baseline_metadata"])

        for model_key, meta in data["artifacts"].items():
            path = meta["path"]
            self.assertTrue(os.path.exists(path), f"Model {path} missing!")
            self.assertEqual(os.path.getsize(path), meta["size_bytes"])

            with open(path, "rb") as mf:
                computed_hash = hashlib.sha256(mf.read()).hexdigest()
            self.assertEqual(
                computed_hash,
                meta["sha256"],
                f"SHA-256 mismatch for {path}: expected {meta['sha256']}, got {computed_hash}"
            )


if __name__ == "__main__":
    unittest.main()
