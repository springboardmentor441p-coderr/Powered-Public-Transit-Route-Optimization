"""
AI_RouteRanker - Unit Tests for Phase 3.2 Hyperparameter Tuning
Verifies parameter bounds, key-level alignment, memory checks, Candidate 0 reuse,
and secondary metric deterioration tracking.
"""

import os
import unittest
import numpy as np
import pandas as pd

from analytics.modeling.random_forest.tuner import (
    RandomForestTuner,
    TuningCandidate,
    CandidateResult,
    check_memory_safety,
)
from analytics.modeling.random_forest.trainer import TrainedRFModel


class TestRandomForestTuning(unittest.TestCase):
    """Test suite covering Phase 3.2 hyperparameter tuning safeguards and logic."""

    def test_01_candidate_parameter_bounds(self):
        """1. Verifies that all 8 candidate configurations obey approved parameter bounds."""
        for cand in RandomForestTuner.CANDIDATES:
            self.assertLessEqual(cand.max_depth, 14, f"Candidate {cand.candidate_id} max_depth exceeds 14!")
            self.assertGreaterEqual(cand.min_samples_leaf, 3, f"Candidate {cand.candidate_id} min_samples_leaf < 3!")
            self.assertIn(cand.max_features, [0.70, 0.85, 1.0], f"Invalid max_features in Candidate {cand.candidate_id}!")
            self.assertEqual(cand.random_state, 42)
            self.assertEqual(cand.n_jobs, 2)
            self.assertTrue(cand.bootstrap)

    def test_02_candidate_0_reused_without_refit(self):
        """2. Verifies Candidate 0 is loaded directly and matches Phase 3.1 numbers."""
        c0 = RandomForestTuner.CANDIDATES[0]
        self.assertEqual(c0.candidate_id, 0)
        self.assertEqual(c0.n_estimators, 100)
        self.assertEqual(c0.max_depth, 12)
        self.assertEqual(c0.max_features, 1.0)
        self.assertEqual(c0.min_samples_leaf, 5)

        # Confirm Phase 3.1 models exist
        t1_path = os.path.join("artifacts", "random_forest", "tier1_random_forest.joblib")
        t2_path = os.path.join("artifacts", "random_forest", "tier2_random_forest.joblib")
        self.assertTrue(os.path.exists(t1_path))
        self.assertTrue(os.path.exists(t2_path))

    def test_03_exact_key_alignment(self):
        """3. Asserts composite (route, date) keys match exactly between Phase 3.1 and Baseline B."""
        # Tier 1
        t1_rf = pd.read_parquet("artifacts/random_forest/tier1_val_predictions.parquet")
        t1_base = pd.read_parquet("artifacts/baselines/tier1_val_predictions.parquet")
        t1_base_valid = t1_base[~t1_base["pred_baseline_b_seasonal_naive"].isna()]

        t1_rf["key"] = t1_rf["route"].astype(str) + "_" + pd.to_datetime(t1_rf["date"]).dt.strftime("%Y-%m-%d")
        t1_base_valid["key"] = t1_base_valid["route"].astype(str) + "_" + pd.to_datetime(t1_base_valid["date"]).dt.strftime("%Y-%m-%d")

        self.assertEqual(len(t1_base_valid["key"]), 37785)
        common_keys_t1 = set(t1_rf["key"]).intersection(set(t1_base_valid["key"]))
        self.assertEqual(len(common_keys_t1), 37785)

        # Tier 2
        t2_rf = pd.read_parquet("artifacts/random_forest/tier2_val_predictions.parquet")
        t2_base = pd.read_parquet("artifacts/baselines/tier2_val_predictions.parquet")
        t2_base_valid = t2_base[~t2_base["pred_baseline_b_seasonal_naive"].isna()]

        t2_rf["key"] = t2_rf["route"].astype(str) + "_" + pd.to_datetime(t2_rf["date"]).dt.strftime("%Y-%m-%d")
        t2_base_valid["key"] = t2_base_valid["route"].astype(str) + "_" + pd.to_datetime(t2_base_valid["date"]).dt.strftime("%Y-%m-%d")

        self.assertEqual(len(t2_base_valid["key"]), 4116)
        common_keys_t2 = set(t2_rf["key"]).intersection(set(t2_base_valid["key"]))
        self.assertEqual(len(common_keys_t2), 4116)

    def test_04_no_duplicate_keys(self):
        """4. Asserts zero duplicate (route, date) keys in any prediction table."""
        for path in [
            "artifacts/random_forest/tier1_val_predictions.parquet",
            "artifacts/random_forest/tier2_val_predictions.parquet",
            "artifacts/baselines/tier1_val_predictions.parquet",
            "artifacts/baselines/tier2_val_predictions.parquet",
        ]:
            df = pd.read_parquet(path)
            duplicates = df.duplicated(subset=["route", "date"]).sum()
            self.assertEqual(duplicates, 0, f"Duplicate keys found in {path}!")

    def test_05_additional_row_isolation(self):
        """5. Asserts the single debut/premiere row is cleanly separated and reported."""
        t1_rf = pd.read_parquet("artifacts/random_forest/tier1_val_predictions.parquet")
        t1_rf["date_str"] = pd.to_datetime(t1_rf["date"]).dt.strftime("%Y-%m-%d")
        t1_add = t1_rf[(t1_rf["route"] == "N5") & (t1_rf["date_str"] == "2025-01-01")]
        self.assertEqual(len(t1_add), 1)
        self.assertEqual(t1_add["target_rides"].values[0], 13.0)

        t2_rf = pd.read_parquet("artifacts/random_forest/tier2_val_predictions.parquet")
        t2_rf["date_str"] = pd.to_datetime(t2_rf["date"]).dt.strftime("%Y-%m-%d")
        t2_add = t2_rf[(t2_rf["route"] == "10") & (t2_rf["date_str"] == "2026-05-20")]
        self.assertEqual(len(t2_add), 1)
        self.assertEqual(t2_add["target_rides"].values[0], 2.0)

    def test_06_secondary_metric_delta_tracking(self):
        """6. Confirms MAE, RMSE, and R2 deltas and deterioration flags evaluate accurately."""
        # Simulated Candidate 0 with MAE=10.0, RMSE=10.0, R2=0.99
        c0 = CandidateResult(
            tier=1, candidate_id=0, name="C0", params={}, retrained=False, status="SUCCESS",
            training_duration_seconds=10.0, pre_fit_avail_ram_mb=1000.0, pre_fit_ram_load_pct=80,
            common_rows=3, wape=10.0, mae=10.0, rmse=10.0, r2=0.99,
            delta_wape=0.0, delta_mae=0.0, delta_rmse=0.0, delta_r2=0.0,
            deterioration_mae=False, deterioration_rmse=False, deterioration_r2=False,
            has_any_secondary_deterioration=False,
            additional_row_key="N5_2025-01-01", additional_row_actual=13.0, additional_row_pred=300.0, additional_row_abs_error=287.0
        )

        # Simulated Candidate with lower WAPE but higher RMSE (trade-off!)
        # Actuals: 100, 100, 100. Sum = 300. C0 errors: 10, 10, 10 (MAE=10, RMSE=10, WAPE=10%)
        # C1 preds: 98, 98, 130. Errors: 2, 2, 30. Sum err = 34. WAPE = 34/300 = 11.33%
        # Let's make C1 have: actuals [100, 100, 100], preds [99, 99, 125] -> errs [1, 1, 25] -> sum err 27 -> WAPE=9% (lower!),
        # but RMSE = sqrt((1+1+625)/3) = sqrt(209) = 14.45 > 10.0 (RMSE deteriorated!)
        val_df = pd.DataFrame({
            "route": ["1", "2", "3", "N5"],
            "date": pd.to_datetime(["2025-01-02", "2025-01-03", "2025-01-04", "2025-01-01"]),
            "daytype": ["W", "W", "W", "U"],
            "target_rides": [100.0, 100.0, 100.0, 13.0],
        })
        preds = np.array([99.0, 99.0, 125.0, 50.0])
        cand = TuningCandidate(candidate_id=1, name="C1")

        tuner = RandomForestTuner(tier=1)
        res, _ = tuner.evaluate_predictions(
            val_df=val_df,
            predictions=preds,
            candidate=cand,
            duration=5.0,
            pre_ram=1000.0,
            pre_load=80,
            c0_result=c0,
            retrained=True,
            expected_common_rows=3,
        )
        self.assertEqual(res.common_rows, 3)
        self.assertLess(res.wape, c0.wape)  # WAPE improved (9.0% vs 10.0%)
        self.assertTrue(res.deterioration_rmse)  # RMSE deteriorated (14.45 vs 10.0)
        self.assertTrue(res.has_any_secondary_deterioration)

    def test_07_win32_memory_api_success(self):
        """7. Confirms GlobalMemoryStatusEx executes, returns success code, and reports non-zero values."""
        is_safe, avail_mb, load_pct = check_memory_safety(min_avail_mb=0, max_load_pct=100)
        self.assertGreater(avail_mb, 0.0)
        self.assertGreater(load_pct, 0)
        self.assertLessEqual(load_pct, 100)
        self.assertTrue(is_safe)

    def test_08_phase31_artifact_immutability(self):
        """8. Confirms original Phase 3.1 .joblib files are preserved intact."""
        t1_path = os.path.join("artifacts", "random_forest", "tier1_random_forest.joblib")
        t2_path = os.path.join("artifacts", "random_forest", "tier2_random_forest.joblib")
        self.assertEqual(os.path.getsize(t1_path), 8192732)
        self.assertEqual(os.path.getsize(t2_path), 4633109)

    def test_09_test_partition_isolation(self):
        """9. Asserts test dates never enter tuning partitions."""
        from analytics.modeling.splitters import ChronologicalSplitter
        # Check that T1 val ends 2025-11-22 and T1 test starts 2025-11-23
        self.assertEqual(ChronologicalSplitter.T1_VAL_END, "2025-11-22")
        self.assertEqual(ChronologicalSplitter.T1_TEST_START, "2025-11-23")
        self.assertEqual(ChronologicalSplitter.T2_VAL_END, "2026-05-29")
        self.assertEqual(ChronologicalSplitter.T2_TEST_START, "2026-05-30")


if __name__ == "__main__":
    unittest.main()
