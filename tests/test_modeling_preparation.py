#!/usr/bin/env python3
"""
AI_RouteRanker - Unit Tests for Milestone 5.1 Phase 1
Tests modeling data preparation, chronological partitioning, feature transformations,
leakage prevention, missing-value treatment, and Parquet immutability.
Does NOT train any machine-learning models.
"""

import os
import sys
import unittest
import numpy as np
import pandas as pd

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from analytics.modeling.data_loader import DataLoader
from analytics.modeling.splitters import ChronologicalSplitter, Tier1Partitions, Tier2Partitions
from analytics.modeling.encoders import RouteEncoder, DaytypeEncoder
from analytics.modeling.feature_builder import FeatureMatrixBuilder, ModelingDataset
from analytics.modeling.validation import ModelingDataValidator


class TestModelingPreparation(unittest.TestCase):
    """Test suite for Milestone 5.1 Phase 1 Data Preparation & Transformations."""

    @classmethod
    def setUpClass(cls):
        cls.data_loader = DataLoader()
        # Record file metadata before any operations
        cls.initial_metadata = cls.data_loader.get_file_metadata()

        # Load raw slices for testing
        cls.tier1_raw = cls.data_loader.load_tier1_dataset()
        cls.tier2_raw = cls.data_loader.load_tier2_dataset()

        # Split into partitions
        cls.t1_partitions = ChronologicalSplitter.split_tier1(cls.tier1_raw)
        cls.t2_partitions = ChronologicalSplitter.split_tier2(cls.tier2_raw)

        # Fit builders strictly on training partitions
        cls.t1_builder = FeatureMatrixBuilder()
        cls.t1_builder.fit_encoders(cls.t1_partitions.train)

        cls.t2_builder = FeatureMatrixBuilder()
        cls.t2_builder.fit_encoders(cls.t2_partitions.train)

    def test_01_parquet_inputs_load_correctly(self):
        """1. Verify parquet input loads correctly with expected total rows."""
        row_count, col_count = self.data_loader.get_row_and_column_counts()
        self.assertEqual(row_count, DataLoader.EXPECTED_TOTAL_ROWS)
        self.assertEqual(col_count, DataLoader.EXPECTED_COLUMN_COUNT)

    def test_02_expected_feature_columns_exist(self):
        """2. Verify expected feature columns exist in the feature store."""
        schema = self.data_loader.inspect_schema()
        col_names = [col["column_name"] for col in schema]
        self.assertIn("target_rides", col_names)
        self.assertIn("rides_lag_1", col_names)
        self.assertIn("rides_lag_7", col_names)
        self.assertIn("rolling_mean_7", col_names)
        self.assertIn("scheduled_trips_count", col_names)
        self.assertIn("schedule_coverage_status", col_names)
        self.assertEqual(len(col_names), 43)

    def test_03_tier1_date_boundaries(self):
        """3. Verify Tier 1 chronological date boundaries."""
        t1 = self.t1_partitions
        self.assertEqual(str(t1.train["date"].min().date()), ChronologicalSplitter.T1_TRAIN_START)
        self.assertEqual(str(t1.train["date"].max().date()), ChronologicalSplitter.T1_TRAIN_END)
        self.assertEqual(str(t1.validation["date"].min().date()), ChronologicalSplitter.T1_VAL_START)
        self.assertEqual(str(t1.validation["date"].max().date()), ChronologicalSplitter.T1_VAL_END)
        self.assertEqual(str(t1.test["date"].min().date()), ChronologicalSplitter.T1_TEST_START)
        self.assertEqual(str(t1.test["date"].max().date()), ChronologicalSplitter.T1_TEST_END)
        self.assertEqual(str(t1.august_holdout["date"].min().date()), ChronologicalSplitter.T1_AUG_START)
        self.assertEqual(str(t1.august_holdout["date"].max().date()), ChronologicalSplitter.T1_AUG_END)

    def test_04_tier2_date_boundaries(self):
        """4. Verify Tier 2 chronological date boundaries."""
        t2 = self.t2_partitions
        self.assertEqual(str(t2.train["date"].min().date()), ChronologicalSplitter.T2_TRAIN_START)
        self.assertEqual(str(t2.train["date"].max().date()), ChronologicalSplitter.T2_TRAIN_END)
        self.assertEqual(str(t2.validation["date"].min().date()), ChronologicalSplitter.T2_VAL_START)
        self.assertEqual(str(t2.validation["date"].max().date()), ChronologicalSplitter.T2_VAL_END)
        self.assertEqual(str(t2.test["date"].min().date()), ChronologicalSplitter.T2_TEST_START)
        self.assertEqual(str(t2.test["date"].max().date()), ChronologicalSplitter.T2_TEST_END)

    def test_05_partition_row_counts_match_audited_reference(self):
        """5. Verify partition row counts match audited reference values."""
        t1 = self.t1_partitions
        self.assertEqual(len(t1.train), 125447)
        self.assertEqual(len(t1.validation), 37786)
        self.assertEqual(len(t1.test), 28798)
        self.assertEqual(len(t1.august_holdout), 3566)
        self.assertEqual(len(t1.train) + len(t1.validation) + len(t1.test) + len(t1.august_holdout), 195597)

        t2 = self.t2_partitions
        self.assertEqual(len(t2.train), 17388)
        self.assertEqual(len(t2.validation), 4117)
        self.assertEqual(len(t2.test), 7293)
        self.assertEqual(len(t2.train) + len(t2.validation) + len(t2.test), 28798)

    def test_06_no_overlapping_partitions(self):
        """6. Verify partitions are strictly mutually exclusive with no date overlap."""
        t1 = self.t1_partitions
        self.assertTrue(t1.train["date"].max() < t1.validation["date"].min())
        self.assertTrue(t1.validation["date"].max() < t1.test["date"].min())
        self.assertTrue(t1.test["date"].max() < t1.august_holdout["date"].min())

        t2 = self.t2_partitions
        self.assertTrue(t2.train["date"].max() < t2.validation["date"].min())
        self.assertTrue(t2.validation["date"].max() < t2.test["date"].min())

    def test_07_route_vocabulary_fitted_on_train_only(self):
        """7. Verify route vocabulary is derived strictly from training partitions."""
        # Tier 1 training vocabulary: 130 routes
        self.assertEqual(len(self.t1_builder.route_encoder.vocabulary_), 130)
        self.assertEqual(self.t1_partitions.train["route"].nunique(), 130)

        # Tier 2 training vocabulary: 127 routes
        self.assertEqual(len(self.t2_builder.route_encoder.vocabulary_), 127)
        self.assertEqual(self.t2_partitions.train["route"].nunique(), 127)

    def test_08_unseen_route_handling(self):
        """8. Verify unseen routes produce all-zero indicator vectors without error."""
        encoder = self.t1_builder.route_encoder
        unseen_series = pd.Series(["UNSEEN_ROUTE_999", "N5"])
        transformed = encoder.transform(unseen_series)
        self.assertEqual(transformed.shape, (2, 130))
        # Route UNSEEN_ROUTE_999 is unknown -> all zeros
        self.assertEqual(transformed.iloc[0].sum(), 0.0)

    def test_09_daytype_is_one_hot_encoded(self):
        """9. Verify daytype is learned from training data only via categories='auto' and non-ordinal."""
        # 1. Categories learned strictly from training partitions (A, U, W in alphabetical order)
        t1_encoder = self.t1_builder.daytype_encoder
        t2_encoder = self.t2_builder.daytype_encoder

        self.assertEqual(t1_encoder.categories_, ["A", "U", "W"])
        self.assertEqual(t2_encoder.categories_, ["A", "U", "W"])

        # 2. Output column names contain daytype_W, daytype_A, daytype_U
        expected_names = {"daytype_A", "daytype_U", "daytype_W"}
        self.assertEqual(set(t1_encoder.feature_names_), expected_names)
        self.assertEqual(set(t2_encoder.feature_names_), expected_names)

        # 3. Transform test: non-ordinal indicator verification
        sample = pd.Series(["W", "A", "U"])
        transformed = t1_encoder.transform(sample)
        self.assertEqual(transformed.loc[0, "daytype_W"], 1.0)
        self.assertEqual(transformed.loc[0, "daytype_A"], 0.0)
        self.assertEqual(transformed.loc[0, "daytype_U"], 0.0)

        self.assertEqual(transformed.loc[1, "daytype_W"], 0.0)
        self.assertEqual(transformed.loc[1, "daytype_A"], 1.0)
        self.assertEqual(transformed.loc[1, "daytype_U"], 0.0)

        self.assertEqual(transformed.loc[2, "daytype_W"], 0.0)
        self.assertEqual(transformed.loc[2, "daytype_A"], 0.0)
        self.assertEqual(transformed.loc[2, "daytype_U"], 1.0)

        # 4. Unseen category handling (handle_unknown='ignore')
        unseen_sample = pd.Series(["X", "SPECIAL"])
        unseen_trans = t1_encoder.transform(unseen_sample)
        self.assertEqual(unseen_trans.shape, (2, 3))
        self.assertTrue((unseen_trans == 0.0).all().all())

        # 5. Validation/Test categories isolation check
        isolated_encoder = DaytypeEncoder().fit(self.t1_partitions.train["daytype"])
        self.assertEqual(isolated_encoder.categories_, ["A", "U", "W"])

    def test_10_target_leakage_columns_excluded(self):
        """10. Verify target_rides and rides_per_scheduled_trip are strictly excluded from X."""
        t1_ds = self.t1_builder.build_tier1_dataset(self.t1_partitions.train)
        t2_ds = self.t2_builder.build_tier2_dataset(self.t2_partitions.train)

        for ds in [t1_ds, t2_ds]:
            self.assertNotIn("target_rides", ds.X.columns)
            self.assertNotIn("rides_per_scheduled_trip", ds.X.columns)
            self.assertNotIn("route", ds.X.columns)
            self.assertNotIn("date", ds.X.columns)
            self.assertEqual(ds.y.name, "target_rides")

    def test_11_gtfs_genuine_zeros_preserved(self):
        """11. Verify GTFS genuine zeros are preserved for zero-service records."""
        # Find records where schedule_coverage_status == 'zero_scheduled_trips'
        zero_records = self.tier2_raw[self.tier2_raw["schedule_coverage_status"] == "zero_scheduled_trips"]
        self.assertEqual(len(zero_records), 19)

        # In raw parquet, scheduled_trips_count is genuinely 0
        self.assertTrue((zero_records["scheduled_trips_count"] == 0).all())
        self.assertTrue((zero_records["scheduled_stop_visits"] == 0.0).all())
        self.assertTrue((zero_records["service_active"] == False).all())

        # In built Tier 2 matrix, scheduled_trips_count remains 0.0 (not placeholder -1.0)
        t2_ds = self.t2_builder.build_tier2_dataset(self.tier2_raw)
        zero_indices = zero_records.index
        zero_matrix_trips = t2_ds.X.loc[zero_indices, "scheduled_trips_count"]
        self.assertTrue((zero_matrix_trips == 0.0).all())

    def test_12_gtfs_nulls_preserved_in_source_data(self):
        """12. Verify GTFS departure and span NULLs remain NULL in source parquet data."""
        zero_records = self.tier2_raw[self.tier2_raw["schedule_coverage_status"] == "zero_scheduled_trips"]
        self.assertEqual(zero_records["service_span_seconds"].isna().sum(), 19)
        self.assertEqual(zero_records["first_departure_seconds"].isna().sum(), 19)
        self.assertEqual(zero_records["last_departure_seconds"].isna().sum(), 19)

    def test_13_zero_service_and_unmatched_flags_distinct(self):
        """13. Verify zero-service and unmatched flags remain strictly distinct in matrix."""
        t2_ds = self.t2_builder.build_tier2_dataset(self.tier2_raw)
        meta = t2_ds.metadata

        # Zero scheduled trips
        zero_mask = (meta["schedule_coverage_status"] == "zero_scheduled_trips")
        self.assertTrue((t2_ds.X.loc[zero_mask, "gtfs_is_zero_service"] == 1.0).all())
        self.assertTrue((t2_ds.X.loc[zero_mask, "gtfs_is_unmatched"] == 0.0).all())
        self.assertTrue((t2_ds.X.loc[zero_mask, "gtfs_is_matched"] == 1.0).all())

        # Unmatched routes
        unmatched_mask = (meta["schedule_coverage_status"] == "unmatched_route")
        self.assertTrue((t2_ds.X.loc[unmatched_mask, "gtfs_is_zero_service"] == 0.0).all())
        self.assertTrue((t2_ds.X.loc[unmatched_mask, "gtfs_is_unmatched"] == 1.0).all())
        self.assertTrue((t2_ds.X.loc[unmatched_mask, "gtfs_is_matched"] == 0.0).all())

    def test_14_undefined_ratios_receive_documented_placeholder(self):
        """14. Verify undefined ratios receive -1.0 placeholder and do not overlap valid positive ratios."""
        t2_ds = self.t2_builder.build_tier2_dataset(self.tier2_raw)
        meta = t2_ds.metadata

        # Zero service records receive -1.0
        zero_mask = (meta["schedule_coverage_status"] == "zero_scheduled_trips")
        self.assertTrue((t2_ds.X.loc[zero_mask, "ridership_per_trip_lag7"] == -1.0).all())

        # Unmatched records receive -1.0
        unmatched_mask = (meta["schedule_coverage_status"] == "unmatched_route")
        self.assertTrue((t2_ds.X.loc[unmatched_mask, "ridership_per_trip_lag7"] == -1.0).all())

        # Positive matched records receive genuine ratios >= 0.0 (strictly non-negative)
        matched_mask = (meta["schedule_coverage_status"] == "matched")
        matched_ratios = t2_ds.X.loc[matched_mask, "ridership_per_trip_lag7"]
        self.assertTrue((matched_ratios >= 0.0).all())
        # Confirm placeholder -1.0 is strictly distinct from the entire positive distribution
        self.assertTrue((matched_ratios > -1.0).all())

    def test_15_lagged_interaction_uses_approved_definition_b(self):
        """15. Verify ridership_per_trip_lag7 uses Definition B (rides_lag_7 / scheduled_trips_count)."""
        t2_ds = self.t2_builder.build_tier2_dataset(self.tier2_raw)
        # Sample 10 positive matched rows
        matched_sample = self.tier2_raw[self.tier2_raw["schedule_coverage_status"] == "matched"].head(10)
        for idx, row in matched_sample.iterrows():
            expected_ratio = float(row["rides_lag_7"]) / float(row["scheduled_trips_count"])
            actual_ratio = t2_ds.X.loc[idx, "ridership_per_trip_lag7"]
            self.assertAlmostEqual(actual_ratio, expected_ratio, places=4)

    def test_16_no_target_date_ridership_in_interaction(self):
        """16. Verify no target-date ridership is used in ridership_per_trip_lag7."""
        # Check by modifying target_rides artificially: the interaction MUST NOT CHANGE
        df_copy = self.tier2_raw.head(5).copy()
        df_copy_altered = df_copy.copy()
        df_copy_altered["target_rides"] = df_copy_altered["target_rides"] * 1000

        ds1 = self.t2_builder.build_tier2_dataset(df_copy)
        ds2 = self.t2_builder.build_tier2_dataset(df_copy_altered)

        np.testing.assert_array_equal(
            ds1.X["ridership_per_trip_lag7"].values,
            ds2.X["ridership_per_trip_lag7"].values,
        )

    def test_17_original_input_parquet_remains_unchanged(self):
        """17. Verify original input Parquet file remains unmodified (size, SHA-256 match)."""
        current_metadata = self.data_loader.get_file_metadata()
        self.assertEqual(current_metadata["size_bytes"], self.initial_metadata["size_bytes"])
        self.assertEqual(current_metadata["sha256"], self.initial_metadata["sha256"])


if __name__ == "__main__":
    unittest.main()
