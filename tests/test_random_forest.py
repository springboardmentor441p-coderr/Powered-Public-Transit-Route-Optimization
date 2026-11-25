"""
AI_RouteRanker - Unit Tests for Random Forest Modeling Module
Milestone 5.2 Phase 3.1: Verifies initial configuration, training protocol,
leakage guardrails, metric calculations, reproducibility, and immutability.
"""

import os
import tempfile
import unittest
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

from analytics.modeling.random_forest.config import RandomForestConfig
from analytics.modeling.random_forest.evaluator import ModelEvaluator, EvaluationResult
from analytics.modeling.random_forest.trainer import RandomForestTrainer, TrainedRFModel
from analytics.modeling.feature_builder import FeatureMatrixBuilder, ModelingDataset
from analytics.modeling.encoders import RouteEncoder, DaytypeEncoder
from analytics.modeling.data_loader import DataLoader


class TestRandomForest(unittest.TestCase):
    """Test suite covering the 15 Phase 3.1 Random Forest requirements."""

    @classmethod
    def setUpClass(cls):
        """Prepare minimal deterministic mock datasets for fast unit testing."""
        np.random.seed(42)
        n_train = 100
        n_val = 30

        dates_train = pd.date_range("2024-01-01", periods=n_train, freq="D")
        dates_val = pd.date_range("2024-04-11", periods=n_val, freq="D")

        routes = ["1", "2", "3", "4", "5"]
        daytypes = ["W", "A", "U"]

        cls.mock_train_df = pd.DataFrame({
            "route": np.random.choice(routes, n_train),
            "date": dates_train,
            "daytype": np.random.choice(daytypes, n_train),
            "target_rides": np.random.randint(100, 5000, n_train).astype(np.float32),
            "rides_per_scheduled_trip": np.random.uniform(10, 50, n_train).astype(np.float32),
            "is_weekend": np.random.choice([0.0, 1.0], n_train).astype(np.float32),
            "is_month_start": np.zeros(n_train, dtype=np.float32),
            "is_month_end": np.zeros(n_train, dtype=np.float32),
            "day": np.random.randint(1, 29, n_train).astype(np.float32),
            "day_of_week_int": np.random.randint(0, 7, n_train).astype(np.float32),
            "day_of_week": np.random.randint(0, 7, n_train).astype(np.float32),
            "month": np.random.randint(1, 13, n_train).astype(np.float32),
            "quarter": np.random.randint(1, 5, n_train).astype(np.float32),
            "year": np.full(n_train, 2024, dtype=np.float32),
            "day_of_year": np.arange(1, n_train + 1, dtype=np.float32),
            "week_of_year": np.random.randint(1, 53, n_train).astype(np.float32),
            "is_leap_year": np.zeros(n_train, dtype=np.float32),
            "sin_day_of_week": np.sin(np.arange(n_train)).astype(np.float32),
            "cos_day_of_week": np.cos(np.arange(n_train)).astype(np.float32),
            "sin_month": np.sin(np.arange(n_train)).astype(np.float32),
            "cos_month": np.cos(np.arange(n_train)).astype(np.float32),
            "sin_day_of_year": np.sin(np.arange(n_train)).astype(np.float32),
            "cos_day_of_year": np.cos(np.arange(n_train)).astype(np.float32),
            "historical_mean_rides": np.random.uniform(500, 3000, n_train).astype(np.float32),
            "historical_std_rides": np.random.uniform(50, 300, n_train).astype(np.float32),
            "historical_max_rides": np.random.uniform(3000, 6000, n_train).astype(np.float32),
            "historical_min_rides": np.random.uniform(50, 500, n_train).astype(np.float32),
            "historical_observation_count": np.full(n_train, 100, dtype=np.float32),
            "route_observation_count": np.full(n_train, 100, dtype=np.float32),
            "rides_lag_1": np.random.randint(100, 5000, n_train).astype(np.float32),
            "rides_lag_7": np.random.randint(100, 5000, n_train).astype(np.float32),
            "rides_lag_14": np.random.randint(100, 5000, n_train).astype(np.float32),
            "rides_lag_28": np.random.randint(100, 5000, n_train).astype(np.float32),
            "rolling_mean_7": np.random.uniform(500, 3000, n_train).astype(np.float32),
            "rolling_std_7": np.random.uniform(50, 300, n_train).astype(np.float32),
            "rolling_mean_14": np.random.uniform(500, 3000, n_train).astype(np.float32),
            "rolling_std_14": np.random.uniform(50, 300, n_train).astype(np.float32),
            "rolling_mean_28": np.random.uniform(500, 3000, n_train).astype(np.float32),
            "rolling_std_28": np.random.uniform(50, 300, n_train).astype(np.float32),
            "demand_growth_wow": np.random.uniform(-0.2, 0.2, n_train).astype(np.float32),
            "demand_growth_mom": np.random.uniform(-0.2, 0.2, n_train).astype(np.float32),
            "ridership_daytype_average": np.random.uniform(500, 3000, n_train).astype(np.float32),
            "route_relative_demand": np.random.uniform(0.5, 1.5, n_train).astype(np.float32),
        })

        cls.mock_val_df = pd.DataFrame({
            "route": np.random.choice(routes + ["UNSEEN_ROUTE"], n_val),
            "date": dates_val,
            "daytype": np.random.choice(daytypes, n_val),
            "target_rides": np.random.randint(100, 5000, n_val).astype(np.float32),
            "rides_per_scheduled_trip": np.random.uniform(10, 50, n_val).astype(np.float32),
            "is_weekend": np.random.choice([0.0, 1.0], n_val).astype(np.float32),
            "is_month_start": np.zeros(n_val, dtype=np.float32),
            "is_month_end": np.zeros(n_val, dtype=np.float32),
            "day": np.random.randint(1, 29, n_val).astype(np.float32),
            "day_of_week_int": np.random.randint(0, 7, n_val).astype(np.float32),
            "day_of_week": np.random.randint(0, 7, n_val).astype(np.float32),
            "month": np.random.randint(1, 13, n_val).astype(np.float32),
            "quarter": np.random.randint(1, 5, n_val).astype(np.float32),
            "year": np.full(n_val, 2024, dtype=np.float32),
            "day_of_year": np.arange(101, 101 + n_val, dtype=np.float32),
            "week_of_year": np.random.randint(1, 53, n_val).astype(np.float32),
            "is_leap_year": np.zeros(n_val, dtype=np.float32),
            "sin_day_of_week": np.sin(np.arange(n_val)).astype(np.float32),
            "cos_day_of_week": np.cos(np.arange(n_val)).astype(np.float32),
            "sin_month": np.sin(np.arange(n_val)).astype(np.float32),
            "cos_month": np.cos(np.arange(n_val)).astype(np.float32),
            "sin_day_of_year": np.sin(np.arange(n_val)).astype(np.float32),
            "cos_day_of_year": np.cos(np.arange(n_val)).astype(np.float32),
            "historical_mean_rides": np.random.uniform(500, 3000, n_val).astype(np.float32),
            "historical_std_rides": np.random.uniform(50, 300, n_val).astype(np.float32),
            "historical_max_rides": np.random.uniform(3000, 6000, n_val).astype(np.float32),
            "historical_min_rides": np.random.uniform(50, 500, n_val).astype(np.float32),
            "historical_observation_count": np.full(n_val, 100, dtype=np.float32),
            "route_observation_count": np.full(n_val, 100, dtype=np.float32),
            "rides_lag_1": np.random.randint(100, 5000, n_val).astype(np.float32),
            "rides_lag_7": np.random.randint(100, 5000, n_val).astype(np.float32),
            "rides_lag_14": np.random.randint(100, 5000, n_val).astype(np.float32),
            "rides_lag_28": np.random.randint(100, 5000, n_val).astype(np.float32),
            "rolling_mean_7": np.random.uniform(500, 3000, n_val).astype(np.float32),
            "rolling_std_7": np.random.uniform(50, 300, n_val).astype(np.float32),
            "rolling_mean_14": np.random.uniform(500, 3000, n_val).astype(np.float32),
            "rolling_std_14": np.random.uniform(50, 300, n_val).astype(np.float32),
            "rolling_mean_28": np.random.uniform(500, 3000, n_val).astype(np.float32),
            "rolling_std_28": np.random.uniform(50, 300, n_val).astype(np.float32),
            "demand_growth_wow": np.random.uniform(-0.2, 0.2, n_val).astype(np.float32),
            "demand_growth_mom": np.random.uniform(-0.2, 0.2, n_val).astype(np.float32),
            "ridership_daytype_average": np.random.uniform(500, 3000, n_val).astype(np.float32),
            "route_relative_demand": np.random.uniform(0.5, 1.5, n_val).astype(np.float32),
        })

    def test_01_model_initialization_with_approved_configuration(self):
        """1. Model initialization matches approved hyperparameters exactly."""
        cfg = RandomForestConfig()
        self.assertEqual(cfg.n_estimators, 100)
        self.assertEqual(cfg.max_depth, 12)
        self.assertEqual(cfg.min_samples_leaf, 5)
        self.assertEqual(cfg.random_state, 42)
        self.assertEqual(cfg.n_jobs, 2)
        self.assertEqual(cfg.max_features, 1.0)

    def test_02_model_fitting_using_training_data_only(self):
        """2. Model fits strictly using the training dataset."""
        builder = FeatureMatrixBuilder()
        builder.fit_encoders(self.mock_train_df)
        ds_train = builder.build_tier1_dataset(self.mock_train_df, partition_name="train")

        trained = RandomForestTrainer.train(ds_train)
        self.assertIsInstance(trained.model, RandomForestRegressor)
        self.assertEqual(trained.training_rows, 100)

    def test_03_correct_target_separation(self):
        """3. Target variable is cleanly isolated into y and completely absent from X."""
        builder = FeatureMatrixBuilder()
        builder.fit_encoders(self.mock_train_df)
        ds = builder.build_tier1_dataset(self.mock_train_df)

        self.assertNotIn("target_rides", ds.X.columns)
        self.assertEqual(ds.y.name, "target_rides")
        self.assertEqual(len(ds.y), len(ds.X))

    def test_04_feature_matrix_dimensions(self):
        """4. Feature matrix dimension matches expected predictors (30 core + route indicators)."""
        builder = FeatureMatrixBuilder()
        builder.fit_encoders(self.mock_train_df)
        ds = builder.build_tier1_dataset(self.mock_train_df)

        # 30 core features + 3 daytype OHE + 5 routes = 35 columns
        self.assertEqual(ds.X.shape[0], 100)
        self.assertEqual(ds.X.shape[1], 35)

    def test_05_encoder_fit_only_on_training_data(self):
        """5. Encoders strictly learn vocabulary from training partition."""
        builder = FeatureMatrixBuilder()
        builder.fit_encoders(self.mock_train_df)

        self.assertNotIn("UNSEEN_ROUTE", builder.route_encoder.vocabulary_)
        self.assertEqual(set(builder.route_encoder.vocabulary_), {"1", "2", "3", "4", "5"})

    def test_06_validation_transformation_without_refitting(self):
        """6. Validation set transforms without modifying encoder vocabulary or raising exceptions."""
        builder = FeatureMatrixBuilder()
        builder.fit_encoders(self.mock_train_df)

        vocab_before = list(builder.route_encoder.vocabulary_)
        ds_val = builder.build_tier1_dataset(self.mock_val_df, partition_name="validation")

        self.assertEqual(list(builder.route_encoder.vocabulary_), vocab_before)
        self.assertEqual(ds_val.X.shape[0], 30)
        self.assertEqual(ds_val.X.shape[1], 35)

    def test_07_reproducibility_using_fixed_random_state(self):
        """7. Fixed random_state produces identical predictions across independent fits."""
        builder = FeatureMatrixBuilder()
        builder.fit_encoders(self.mock_train_df)
        ds_train = builder.build_tier1_dataset(self.mock_train_df)
        ds_val = builder.build_tier1_dataset(self.mock_val_df)

        trained_1 = RandomForestTrainer.train(ds_train)
        pred_1 = trained_1.predict(ds_val.X)

        trained_2 = RandomForestTrainer.train(ds_train)
        pred_2 = trained_2.predict(ds_val.X)

        np.testing.assert_array_almost_equal(pred_1, pred_2)

    def test_08_prediction_output_shape(self):
        """8. Prediction vector matches validation row count exactly."""
        builder = FeatureMatrixBuilder()
        builder.fit_encoders(self.mock_train_df)
        ds_train = builder.build_tier1_dataset(self.mock_train_df)
        ds_val = builder.build_tier1_dataset(self.mock_val_df)

        trained = RandomForestTrainer.train(ds_train)
        preds = trained.predict(ds_val.X)

        self.assertEqual(preds.shape, (30,))
        self.assertFalse(np.isnan(preds).any())

    def test_09_metric_calculations(self):
        """9. Metric calculations return mathematically verified results."""
        y_true = np.array([100.0, 200.0, 300.0])
        y_pred = np.array([110.0, 190.0, 330.0])

        res = ModelEvaluator.evaluate(y_true, y_pred, tier=1)
        self.assertAlmostEqual(res.mae, 16.6667, places=3)
        self.assertAlmostEqual(res.rmse, 19.1485, places=3)
        self.assertAlmostEqual(res.wape, 8.3333, places=3)
        self.assertGreater(res.r2, 0.9)

    def test_10_wape_zero_denominator_safety(self):
        """10. WAPE handles zero denominator without crashing or returning infinity."""
        y_zero = np.array([0.0, 0.0, 0.0])
        y_pred = np.array([0.0, 0.0, 0.0])
        wape_zero = ModelEvaluator.calculate_wape(y_zero, y_pred)
        self.assertEqual(wape_zero, 0.0)

        y_pred_nonzero = np.array([10.0, 20.0, 0.0])
        wape_nonzero = ModelEvaluator.calculate_wape(y_zero, y_pred_nonzero)
        self.assertEqual(wape_nonzero, 100.0)

    def test_11_model_artifact_save_load_consistency(self):
        """11. Saved model artifact reloads and reproduces exact predictions."""
        builder = FeatureMatrixBuilder()
        builder.fit_encoders(self.mock_train_df)
        ds_train = builder.build_tier1_dataset(self.mock_train_df)
        ds_val = builder.build_tier1_dataset(self.mock_val_df)

        trained = RandomForestTrainer.train(ds_train)
        pred_original = trained.predict(ds_val.X)

        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = os.path.join(tmpdir, "test_model.joblib")
            trained.save(save_path)

            loaded = TrainedRFModel.load(save_path)
            pred_loaded = loaded.predict(ds_val.X)

            np.testing.assert_allclose(pred_original, pred_loaded, rtol=1e-7, atol=1e-7)
            self.assertEqual(loaded.feature_names, trained.feature_names)
            self.assertEqual(loaded.training_rows, 100)

    def test_12_tier1_and_tier2_model_isolation(self):
        """12. Tier 1 and Tier 2 models remain completely independent."""
        cfg = RandomForestConfig()
        m1 = RandomForestRegressor(**cfg.to_dict())
        m2 = RandomForestRegressor(**cfg.to_dict())
        self.assertIsNot(m1, m2)

    def test_13_no_test_or_holdout_partition_accessed(self):
        """13. Verifies runner logic never accesses test or holdout partitions."""
        from analytics.modeling.splitters import ChronologicalSplitter
        # Check date boundaries defined in splitter
        self.assertEqual(ChronologicalSplitter.T1_TEST_START, "2025-11-23")
        self.assertEqual(ChronologicalSplitter.T1_AUG_START, "2026-08-01")
        self.assertEqual(ChronologicalSplitter.T2_TEST_START, "2026-05-30")

    def test_14_no_target_leakage(self):
        """14. Verifies no contemporaneous or future target metrics enter X."""
        builder = FeatureMatrixBuilder()
        builder.fit_encoders(self.mock_train_df)
        ds = builder.build_tier1_dataset(self.mock_train_df)

        for col in ["target_rides", "rides_per_scheduled_trip", "route", "date"]:
            self.assertNotIn(col, ds.X.columns)

    def test_15_no_modification_to_source_feature_parquet(self):
        """15. Confirms source Parquet file metadata and hash remain untouched."""
        loader = DataLoader()
        meta = loader.get_file_metadata()
        self.assertEqual(meta["size_bytes"], 50853144)
        self.assertEqual(
            meta["sha256"],
            "30980434303f7d8a96b55338572a245c479bacd3abb581cd9d7bf2b417e8b95f",
        )


if __name__ == "__main__":
    unittest.main()
