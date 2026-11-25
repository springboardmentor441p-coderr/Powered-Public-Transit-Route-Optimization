#!/usr/bin/env python3
"""
AI_RouteRanker - Unit Tests for Milestone 5.2 Phase 2 Naive Baselines
Tests:
1. Historical mean uses only observations before target date (< t).
2. Target-date rides are excluded.
3. Future observations are excluded.
4. Calendar t-7 lookup uses exact calendar dates.
5. Missing calendar t-7 uses the correct 28-day fallback.
6. Missing fallback uses historical route/daytype mean.
7. No-history predictions are marked unavailable (NaN, not zero).
8. Rolling predictions do not use future observations.
9. WAPE handles zero denominator safely (returns NaN).
10. Metric calculations are correct on a hand-calculated example.
11. Tier 1 and Tier 2 partitions remain strictly separate.
12. Prediction row counts and coverage are internally consistent.
"""

import os
import sys
import unittest
import numpy as np
import pandas as pd

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from analytics.modeling.baselines.historical_mean import HistoricalMeanBaseline
from analytics.modeling.baselines.seasonal_naive import SeasonalNaiveBaseline
from analytics.modeling.baselines.metrics import (
    calculate_metrics,
    calculate_route_metrics,
    calculate_daytype_metrics,
    MetricResults,
)
from analytics.modeling.splitters import ChronologicalSplitter


class TestBaselines(unittest.TestCase):
    """Test suite for Phase 2 Naive Baselines & Evaluation Metrics."""

    def setUp(self):
        # Create a controlled synthetic dataset to test edge cases, lags, and fallbacks
        self.sample_history = pd.DataFrame([
            {"route": "1", "date": "2024-01-01", "daytype": "W", "target_rides": 100},
            {"route": "1", "date": "2024-01-02", "daytype": "W", "target_rides": 200},
            {"route": "1", "date": "2024-01-08", "daytype": "W", "target_rides": 300},  # Exactly 7 days after 2024-01-01
            {"route": "1", "date": "2024-01-13", "daytype": "A", "target_rides": 50},   # Saturday
            {"route": "1", "date": "2024-01-14", "daytype": "U", "target_rides": 40},   # Sunday
            {"route": "2", "date": "2024-01-01", "daytype": "W", "target_rides": 500},
            {"route": "2", "date": "2024-01-08", "daytype": "W", "target_rides": 600},
        ])
        self.sample_history["date"] = pd.to_datetime(self.sample_history["date"])

    def test_01_historical_mean_uses_only_prior_observations(self):
        """1. Verify historical mean uses only observations strictly before target date (< t)."""
        baseline = HistoricalMeanBaseline()
        eval_df = pd.DataFrame([
            {"route": "1", "date": "2024-01-08", "daytype": "W", "target_rides": 300}
        ])
        eval_df["date"] = pd.to_datetime(eval_df["date"])

        preds = baseline.generate_predictions(eval_df, self.sample_history)
        # Prior W dates for route 1 before 2024-01-08 are: 2024-01-01 (100) and 2024-01-02 (200)
        # Mean = (100 + 200) / 2 = 150.0
        self.assertEqual(preds.iloc[0]["prediction"], 150.0)
        self.assertEqual(preds.iloc[0]["prior_obs_count"], 2)

    def test_02_target_date_rides_excluded_from_mean(self):
        """2. Verify target-date rides are excluded from its own prediction."""
        baseline = HistoricalMeanBaseline()
        # Even if eval row has target_rides = 99999, it must NOT affect prediction
        eval_df = pd.DataFrame([
            {"route": "1", "date": "2024-01-02", "daytype": "W", "target_rides": 99999}
        ])
        eval_df["date"] = pd.to_datetime(eval_df["date"])

        preds = baseline.generate_predictions(eval_df, self.sample_history)
        # Prior W date before 2024-01-02 is only 2024-01-01 (100). Prediction must be 100.0, NOT (100+99999)/2
        self.assertEqual(preds.iloc[0]["prediction"], 100.0)

    def test_03_future_observations_excluded_from_mean(self):
        """3. Verify future observations are strictly excluded."""
        baseline = HistoricalMeanBaseline()
        eval_df = pd.DataFrame([
            {"route": "1", "date": "2024-01-01", "daytype": "W", "target_rides": 100}
        ])
        eval_df["date"] = pd.to_datetime(eval_df["date"])

        # History contains dates 2024-01-02, 2024-01-08. They must be ignored.
        preds = baseline.generate_predictions(eval_df, self.sample_history)
        # 2024-01-01 is the first date -> no prior observations -> unavailable
        self.assertTrue(pd.isna(preds.iloc[0]["prediction"]))
        self.assertEqual(preds.iloc[0]["fallback_level"], "unavailable")

    def test_04_calendar_t7_exact_match(self):
        """4. Verify calendar t-7 lookup uses exact calendar dates (target_date - 7 days)."""
        baseline = SeasonalNaiveBaseline()
        # Target date 2024-01-08: calendar t-7 is 2024-01-01 (100 rides)
        eval_df = pd.DataFrame([
            {"route": "1", "date": "2024-01-08", "daytype": "W", "target_rides": 300}
        ])
        eval_df["date"] = pd.to_datetime(eval_df["date"])

        preds = baseline.generate_predictions(eval_df, self.sample_history)
        self.assertEqual(preds.iloc[0]["prediction"], 100.0)
        self.assertEqual(preds.iloc[0]["fallback_level"], "calendar_t7")

    def test_05_missing_t7_uses_28d_daytype_fallback(self):
        """5. Verify missing calendar t-7 falls back to most recent observation within preceding 28 days."""
        baseline = SeasonalNaiveBaseline()
        # Route 1 on Saturday 2024-01-20:
        # t - 7 days is 2024-01-13 (Saturday, 50 rides) -> present
        # But for date 2024-01-27 (Saturday): suppose 2024-01-20 was missing, but 2024-01-13 exists
        history = pd.DataFrame([
            {"route": "1", "date": "2024-01-06", "daytype": "A", "target_rides": 45},  # 21 days before Jan 27
            {"route": "1", "date": "2024-01-13", "daytype": "A", "target_rides": 55},  # 14 days before Jan 27
            # Note: 2024-01-20 (exact t-7) is intentionally missing!
        ])
        history["date"] = pd.to_datetime(history["date"])

        eval_df = pd.DataFrame([
            {"route": "1", "date": "2024-01-27", "daytype": "A", "target_rides": 60}
        ])
        eval_df["date"] = pd.to_datetime(eval_df["date"])

        preds = baseline.generate_predictions(eval_df, history)
        # Exact t-7 is absent. Most recent in [t-28, t-1] for (route 1, daytype A) is 2024-01-13 (55)
        self.assertEqual(preds.iloc[0]["prediction"], 55.0)
        self.assertEqual(preds.iloc[0]["fallback_level"], "recent_28d_daytype")

    def test_06_missing_fallback_uses_historical_mean(self):
        """6. Verify missing 28-day window falls back to historical route/daytype mean."""
        baseline = SeasonalNaiveBaseline()
        # History is > 28 days old (e.g. 60 days prior)
        history = pd.DataFrame([
            {"route": "1", "date": "2023-11-01", "daytype": "W", "target_rides": 120},
            {"route": "1", "date": "2023-11-02", "daytype": "W", "target_rides": 140},
        ])
        history["date"] = pd.to_datetime(history["date"])

        eval_df = pd.DataFrame([
            {"route": "1", "date": "2024-01-15", "daytype": "W", "target_rides": 150}
        ])
        eval_df["date"] = pd.to_datetime(eval_df["date"])

        preds = baseline.generate_predictions(eval_df, history)
        # t-7 is absent; no obs in [Jan 15 - 28d, Jan 14]; fallback to historical mean = (120 + 140)/2 = 130.0
        self.assertEqual(preds.iloc[0]["prediction"], 130.0)
        self.assertEqual(preds.iloc[0]["fallback_level"], "historical_mean")

    def test_07_no_history_predictions_marked_unavailable(self):
        """7. Verify predictions with zero prior history are marked unavailable (NaN), not zero."""
        baseline_a = HistoricalMeanBaseline()
        baseline_b = SeasonalNaiveBaseline()

        # Completely new route '999' with no past records
        eval_df = pd.DataFrame([
            {"route": "999", "date": "2024-01-01", "daytype": "W", "target_rides": 100}
        ])
        eval_df["date"] = pd.to_datetime(eval_df["date"])

        preds_a = baseline_a.generate_predictions(eval_df, self.sample_history)
        preds_b = baseline_b.generate_predictions(eval_df, self.sample_history)

        self.assertTrue(pd.isna(preds_a.iloc[0]["prediction"]))
        self.assertEqual(preds_a.iloc[0]["fallback_level"], "unavailable")

        self.assertTrue(pd.isna(preds_b.iloc[0]["prediction"]))
        self.assertEqual(preds_b.iloc[0]["fallback_level"], "unavailable")

    def test_08_rolling_predictions_do_not_use_future(self):
        """8. Verify rolling predictions only incorporate actuals after their occurrence date."""
        baseline = HistoricalMeanBaseline()
        # 3 consecutive days for route 1
        eval_df = pd.DataFrame([
            {"route": "1", "date": "2024-01-02", "daytype": "W", "target_rides": 200},
            {"route": "1", "date": "2024-01-03", "daytype": "W", "target_rides": 300},
        ])
        eval_df["date"] = pd.to_datetime(eval_df["date"])

        # History starts with 2024-01-01 (100)
        history = pd.DataFrame([
            {"route": "1", "date": "2024-01-01", "daytype": "W", "target_rides": 100},
            {"route": "1", "date": "2024-01-02", "daytype": "W", "target_rides": 200},
            {"route": "1", "date": "2024-01-03", "daytype": "W", "target_rides": 300},
        ])
        history["date"] = pd.to_datetime(history["date"])

        preds = baseline.generate_predictions(eval_df, history)
        # On Jan 2: prior obs is Jan 1 (100) -> prediction = 100.0
        self.assertEqual(preds.loc[preds["date"] == "2024-01-02", "prediction"].iloc[0], 100.0)
        # On Jan 3: prior obs are Jan 1 (100) and Jan 2 (200) -> prediction = 150.0
        self.assertEqual(preds.loc[preds["date"] == "2024-01-03", "prediction"].iloc[0], 150.0)

    def test_09_wape_zero_denominator_safe_handling(self):
        """9. Verify WAPE handles zero actual ridership sum without division by zero."""
        y_true = pd.Series([0, 0, 0])
        y_pred = pd.Series([10, 20, 30])
        metrics = calculate_metrics(y_true, y_pred)
        self.assertTrue(np.isnan(metrics.wape))
        self.assertEqual(metrics.rows_evaluated, 3)

    def test_10_hand_calculated_metric_verification(self):
        """10. Verify MAE, RMSE, R2, and WAPE match hand-calculated results on a controlled sample."""
        # y = [100, 200, 300], y_hat = [110, 190, 330]
        # errors: [10, -10, 30]
        # abs_errors: [10, 10, 30] -> MAE = 50 / 3 = 16.6667
        # sq_errors: [100, 100, 900] = 1100 -> MSE = 1100/3 = 366.6667 -> RMSE = sqrt(366.6667) = 19.1485
        # y_mean = 200 -> SS_tot = (100-200)^2 + 0 + (300-200)^2 = 10000 + 10000 = 20000
        # SS_res = 1100 -> R2 = 1 - 1100/20000 = 1 - 0.055 = 0.945
        # sum_y = 600 -> WAPE = (50 / 600) * 100 = 8.3333%
        y_true = pd.Series([100, 200, 300])
        y_pred = pd.Series([110, 190, 330])
        metrics = calculate_metrics(y_true, y_pred)

        self.assertAlmostEqual(metrics.mae, 16.6667, places=4)
        self.assertAlmostEqual(metrics.rmse, 19.1485, places=4)
        self.assertAlmostEqual(metrics.r2, 0.9450, places=4)
        self.assertAlmostEqual(metrics.wape, 8.3333, places=4)
        self.assertEqual(metrics.rows_evaluated, 3)
        self.assertEqual(metrics.prediction_coverage_pct, 100.0)

    def test_11_tier1_and_tier2_partitions_remain_separate(self):
        """11. Verify Tier 1 and Tier 2 chronological boundaries and splits are strictly separated."""
        self.assertEqual(ChronologicalSplitter.T1_TRAIN_START, "2022-01-01")
        self.assertEqual(ChronologicalSplitter.T1_TRAIN_END, "2024-12-31")
        self.assertEqual(ChronologicalSplitter.T2_TRAIN_START, "2025-11-23")
        self.assertEqual(ChronologicalSplitter.T2_TRAIN_END, "2026-04-23")

    def test_12_prediction_coverage_consistency(self):
        """12. Verify rows_evaluated + unavailable_predictions == expected_rows."""
        y_true = pd.Series([100, 200, np.nan, 400])
        y_pred = pd.Series([110, np.nan, 300, 420])
        # valid pairs: index 0 (100, 110) and index 3 (400, 420) -> rows_evaluated = 2
        # predictions_generated = 3 (idx 0, 2, 3)
        # unavailable = 1 (idx 1)
        metrics = calculate_metrics(y_true, y_pred, expected_rows=4)
        self.assertEqual(metrics.expected_rows, 4)
        self.assertEqual(metrics.predictions_generated, 3)
        self.assertEqual(metrics.unavailable_predictions, 1)
        self.assertEqual(metrics.rows_evaluated, 2)
        self.assertEqual(metrics.prediction_coverage_pct, 75.0)


if __name__ == "__main__":
    unittest.main()
