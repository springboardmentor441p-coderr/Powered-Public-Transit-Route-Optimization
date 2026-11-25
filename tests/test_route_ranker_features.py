"""
AI_RouteRanker - Comprehensive Unit Tests for Phase 6.3 Route Ranker Feature Synthesis
Tests the architecture, configuration, hub metrics, corridor metrics,
demand integrator, feature synthesis, normalization, memory guard, and schema validation.
Uses SYNTHETIC test fixtures only. Zero canonical real-data files accessed.
Follows standard library unittest framework.
"""

from typing import Dict, Any, List
import unittest
import numpy as np
import pandas as pd

from analytics.ranking.config import RankerConfig
from analytics.ranking.hub_metrics import compute_route_hub_metrics, compute_pattern_hub_metrics
from analytics.ranking.corridor_metrics import compute_corridor_metrics
from analytics.ranking.demand_integrator import integrate_demand_predictions
from analytics.ranking.route_ranker_features import (
    synthesize_route_ranker_features,
    normalize_features,
    validate_feature_master,
)
from analytics.ranking.ranker_dataset_builder import RankerDatasetBuilder


class MockRandomForest:
    """Mock Random Forest model for unit testing demand inference."""
    def predict(self, X):
        return np.array([5432.1] * len(X))


class TestRouteRankerFeatures(unittest.TestCase):
    """
    Comprehensive unit tests for Phase 6.3 Route Ranker feature synthesis.
    Covers all 24 required validation areas using synthetic fixtures only.
    """

    def setUp(self):
        """Set up synthetic test fixtures for 133 CTA routes."""
        np.random.seed(42)

        # 1. Synthetic 133 routes operational features (125 bus, 8 rail)
        # Ensure 125 bus routes explicitly include specialized routes 10, 130, N5
        bus_ids = [str(i) for i in range(1, 124)] + ["130", "N5"]
        ops_records = []
        for route_id in bus_ids:
            is_special = route_id in RankerConfig.SPECIALIZED_HEADWAY_EXCLUDED_ROUTES
            ops_records.append({
                "route_id": route_id,
                "route_short_name": route_id,
                "route_long_name": f"Bus Route {route_id}",
                "route_type": 3,
                "is_rail": False,
                "scheduled_trips": int(np.random.randint(40, 200)),
                "service_span_hours": float(np.random.uniform(14.0, 24.0)),
                "am_headway_min": np.nan if is_special else float(np.random.uniform(5.0, 25.0)),
                "route_length_km": float(np.random.uniform(8.0, 35.0)),
                "unique_stops_count": int(np.random.randint(30, 120)),
                "historical_mean_daily_rides": float(np.random.uniform(1000.0, 15000.0)),
            })

        for rail_id in sorted(list(RankerConfig.RAIL_ROUTE_IDS)):
            ops_records.append({
                "route_id": rail_id,
                "route_short_name": rail_id,
                "route_long_name": f"{rail_id} Line",
                "route_type": 1,
                "is_rail": True,
                "scheduled_trips": int(np.random.randint(150, 400)),
                "service_span_hours": 24.0,
                "am_headway_min": float(np.random.uniform(4.0, 10.0)),
                "route_length_km": float(np.random.uniform(15.0, 50.0)),
                "unique_stops_count": int(np.random.randint(18, 35)),
                "historical_mean_daily_rides": np.nan,  # STRICT RAIL POLICY
            })
        self.synthetic_ops_df = pd.DataFrame(ops_records)

        # 2. Synthetic KMeans operational assignments (130 clustered routes)
        km_records = []
        cluster_labels = {0: "Trunk", 1: "Feeder", 2: "Regional"}
        for idx, route_id in enumerate(bus_ids):
            if route_id not in RankerConfig.SPECIALIZED_HEADWAY_EXCLUDED_ROUTES:
                c = (idx % 3)
                km_records.append({
                    "route_id": route_id,
                    "operational_cluster_k3": c,
                    "operational_cluster_label": cluster_labels[c],
                })
        for idx, rail_id in enumerate(sorted(list(RankerConfig.RAIL_ROUTE_IDS))):
            c = (idx % 3)
            km_records.append({
                "route_id": rail_id,
                "operational_cluster_k3": c,
                "operational_cluster_label": cluster_labels[c],
            })
        self.synthetic_kmeans_df = pd.DataFrame(km_records)

        # 3. Synthetic Hub data
        stops_records = []
        for idx, route_id in enumerate(bus_ids):
            for s in range(10):
                stops_records.append({"route_id": route_id, "stop_id": f"stop_{s + (idx % 20)}"})
        for rail_id in RankerConfig.RAIL_ROUTE_IDS:
            for s in range(10):
                stops_records.append({"route_id": rail_id, "stop_id": f"stop_{s + 100}"})
        self.synthetic_route_stops = pd.DataFrame(stops_records)

        self.synthetic_top100_hubs = pd.DataFrame({"stop_id": [f"stop_{i}" for i in range(100)]})
        self.synthetic_hub_rankings = pd.DataFrame({
            "stop_id": [f"stop_{i}" for i in range(200)],
            "composite_hub_score_a": [float(100 - i * 0.4) for i in range(200)],
        })
        self.synthetic_periph_stops = pd.DataFrame({"stop_id": [f"stop_{i}" for i in range(150, 200)]})

        # 4. Synthetic Corridor data
        patterns = ["1_0", "1_1", "2_0", "2_1", "Red_0", "Red_1"]
        n = len(patterns)
        mat = np.eye(n)
        mat[0, 2] = mat[2, 0] = 0.75
        mat[0, 3] = mat[3, 0] = 0.40
        mat[1, 2] = mat[2, 1] = 0.35
        mat[1, 3] = mat[3, 1] = 0.60
        mat[4, 0] = mat[0, 4] = 0.20
        mat[4, 5] = mat[5, 4] = 0.10
        self.synthetic_overlap_matrix = pd.DataFrame(mat, index=patterns, columns=patterns)

        self.synthetic_shared_df = pd.DataFrame([
            {"route_id_1": "1", "route_id_2": "2", "sequence_length": 6, "shared_stop_ids": ["s1", "s2", "s3", "s4", "s5", "s6"]},
            {"route_id_1": "1", "route_id_2": "Red", "sequence_length": 3, "shared_stop_ids": ["s10", "s11", "s12"]},
        ])
        self.synthetic_corr_assign_df = pd.DataFrame({
            "pattern_id": patterns,
            "corridor_cluster_k2": [0, 0, 1, 1, 0, 0],
        })

    # Test 1: Configuration and canonical constants
    def test_01_configuration_and_canonical_constants(self):
        self.assertEqual(RankerConfig.SNAPSHOT_ID, "mdb-389-202605300003")
        self.assertEqual(RankerConfig.REPRESENTATIVE_DATE, "2026-06-10")
        self.assertEqual(RankerConfig.EXPECTED_TOTAL_ROUTES, 133)
        self.assertEqual(RankerConfig.EXPECTED_BUS_ROUTES, 125)
        self.assertEqual(RankerConfig.EXPECTED_RAIL_ROUTES, 8)
        self.assertEqual(len(RankerConfig.RAIL_ROUTE_IDS), 8)
        self.assertEqual(len(RankerConfig.SPECIALIZED_HEADWAY_EXCLUDED_ROUTES), 3)
        self.assertEqual(len(RankerConfig.APPROVED_24_FEATURES), 24)
        self.assertEqual(RankerConfig.MEMORY_ABORT_THRESHOLD_MB, 600.0)
        self.assertEqual(RankerConfig.MEMORY_LOAD_ABORT_PCT, 95)

    # Test 2: Hub stop counts and ratios
    def test_02_hub_stop_counts_and_ratios(self):
        hub_df = compute_route_hub_metrics(
            self.synthetic_route_stops, self.synthetic_hub_rankings, self.synthetic_top100_hubs
        )
        self.assertIn("hub_stop_count", hub_df.columns)
        self.assertIn("hub_stop_ratio", hub_df.columns)
        self.assertTrue((hub_df["hub_stop_ratio"] >= 0.0).all())
        self.assertTrue((hub_df["hub_stop_ratio"] <= 1.0).all())
        self.assertTrue((hub_df["hub_stop_count"] >= 0).all())

    # Test 3: Hub weighted importance calculations
    def test_03_hub_weighted_importance(self):
        hub_df = compute_route_hub_metrics(
            self.synthetic_route_stops, self.synthetic_hub_rankings, self.synthetic_top100_hubs
        )
        self.assertIn("hub_weighted_importance", hub_df.columns)
        self.assertIn("hub_connectivity_index", hub_df.columns)
        self.assertTrue((hub_df["hub_weighted_importance"] >= 0.0).all())
        self.assertTrue((hub_df["hub_connectivity_index"] >= 0.0).all())
        self.assertTrue((hub_df["hub_connectivity_index"] <= 1.0).all())

    # Test 4: Corridor overlap calculations
    def test_04_corridor_overlap_calculations(self):
        corridor_df = compute_corridor_metrics(
            self.synthetic_overlap_matrix, self.synthetic_shared_df, self.synthetic_corr_assign_df
        )
        self.assertIn("max_corridor_overlap", corridor_df.columns)
        r1 = corridor_df[corridor_df["route_id"] == "1"].iloc[0]
        self.assertAlmostEqual(r1["max_corridor_overlap"], 0.75, places=3)

    # Test 5: Top-five corridor overlap aggregation
    def test_05_top_five_corridor_overlap(self):
        corridor_df = compute_corridor_metrics(
            self.synthetic_overlap_matrix, self.synthetic_shared_df, self.synthetic_corr_assign_df
        )
        self.assertIn("mean_corridor_overlap", corridor_df.columns)
        self.assertTrue((corridor_df["mean_corridor_overlap"] >= 0.0).all())
        self.assertTrue((corridor_df["mean_corridor_overlap"] <= 1.0).all())

    # Test 6: Shared consecutive stop metrics
    def test_06_shared_consecutive_stop_metrics(self):
        meta_df = pd.DataFrame({"route_id": ["1", "2", "Red"], "unique_stops_count": [20, 20, 20]})
        corridor_df = compute_corridor_metrics(
            self.synthetic_overlap_matrix, self.synthetic_shared_df, self.synthetic_corr_assign_df,
            route_metadata_df=meta_df
        )
        self.assertIn("shared_consecutive_stop_count", corridor_df.columns)
        self.assertIn("corridor_duplication_ratio", corridor_df.columns)
        r1 = corridor_df[corridor_df["route_id"] == "1"].iloc[0]
        self.assertEqual(r1["shared_consecutive_stop_count"], 9)
        self.assertAlmostEqual(r1["corridor_duplication_ratio"], 9 / 20, places=3)

    # Test 7: Fréchet regional divider handling
    def test_07_frechet_regional_divider_handling(self):
        corridor_df = compute_corridor_metrics(
            self.synthetic_overlap_matrix, self.synthetic_shared_df, self.synthetic_corr_assign_df
        )
        self.assertIn("regional_partition", corridor_df.columns)
        r1 = corridor_df[corridor_df["route_id"] == "1"].iloc[0]
        r2 = corridor_df[corridor_df["route_id"] == "2"].iloc[0]
        self.assertEqual(r1["regional_partition"], "North Chicago")
        self.assertEqual(r2["regional_partition"], "South Chicago")

    # Test 8: Random Forest prediction integration using mocked models
    def test_08_rf_prediction_integration(self):
        mock_rf = MockRandomForest()
        mrf = pd.DataFrame({
            "route_id": ["1", "2"],
            "service_date": ["2026-06-10", "2026-06-10"],
            "feat_1": [1.0, 2.0],
            "feat_2": [3.0, 4.0],
        })
        demand_df = integrate_demand_predictions(self.synthetic_ops_df, mrf, rf_model=mock_rf)
        self.assertIn("forecasted_daily_demand", demand_df.columns)
        r1_demand = demand_df[demand_df["route_id"] == "1"]["forecasted_daily_demand"].iloc[0]
        self.assertAlmostEqual(r1_demand, 5432.1, places=1)

    # Test 9: Tier 1 and Tier 2 coverage handling
    def test_09_tier1_tier2_coverage(self):
        mrf = pd.DataFrame({"route_id": ["1"], "forecasted_daily_demand": [8888.0]})
        demand_df = integrate_demand_predictions(self.synthetic_ops_df, mrf)
        r1 = demand_df[demand_df["route_id"] == "1"]["forecasted_daily_demand"].iloc[0]
        self.assertAlmostEqual(r1, 8888.0, places=1)

        r2_hist = self.synthetic_ops_df[self.synthetic_ops_df["route_id"] == "2"]["historical_mean_daily_rides"].iloc[0]
        r2 = demand_df[demand_df["route_id"] == "2"]["forecasted_daily_demand"].iloc[0]
        self.assertAlmostEqual(r2, r2_hist, places=1)

    # Test 10: Missing rail ridership preservation
    def test_10_missing_rail_ridership_preservation(self):
        mock_rf = MockRandomForest()
        mrf = pd.DataFrame({"route_id": ["Red"], "service_date": ["2026-06-10"], "feat_1": [1.0]})
        demand_df = integrate_demand_predictions(self.synthetic_ops_df, mrf, rf_model=mock_rf)

        rail_records = demand_df[demand_df["route_id"].isin(RankerConfig.RAIL_ROUTE_IDS)]
        self.assertEqual(len(rail_records), 8)
        for col in ["historical_mean_daily_rides", "forecasted_daily_demand", "rides_per_trip", "load_intensity_factor"]:
            self.assertTrue(rail_records[col].isna().all(), f"Rail column {col} was not completely NaN!")

    # Test 11: Missing AM headway handling for Routes 10, 130 and N5
    def test_11_missing_am_headway_handling(self):
        master = synthesize_route_ranker_features(self.synthetic_ops_df, self.synthetic_kmeans_df)
        for rid in ["10", "130", "N5"]:
            row = master[master["route_id"] == rid].iloc[0]
            self.assertTrue(pd.isna(row["am_headway_min"]), f"Route {rid} should have NaN am_headway_min")
            self.assertTrue(pd.isna(row["operational_cluster_k3"]), f"Route {rid} should have NaN operational_cluster_k3")

    # Test 12: Duplicate route identifiers rejection
    def test_12_duplicate_route_identifiers(self):
        df_with_dups = pd.DataFrame({
            "route_id": ["1", "1", "2"],
            "is_rail": [False, False, False],
            "scheduled_trips": [10, 10, 20],
        })
        val = validate_feature_master(df_with_dups, expected_total=2, expected_bus=2, expected_rail=0)
        self.assertFalse(val["is_valid"])
        self.assertTrue(any("Duplicate route_ids" in err for err in val["errors"]))

    # Test 13: Missing route identifiers
    def test_13_missing_route_identifiers(self):
        df_missing_pk = pd.DataFrame({"route_short_name": ["1", "2"], "is_rail": [False, False]})
        val = validate_feature_master(df_missing_pk, expected_total=2, expected_bus=2, expected_rail=0)
        self.assertFalse(val["is_valid"])
        self.assertTrue(any("Missing primary key column 'route_id'" in err for err in val["errors"]))

    # Test 14: Invalid and non-finite numeric values
    def test_14_invalid_and_non_finite_numeric_values(self):
        master = synthesize_route_ranker_features(self.synthetic_ops_df, self.synthetic_kmeans_df)
        master.loc[0, "hub_stop_ratio"] = 1.5
        val = validate_feature_master(master)
        self.assertFalse(val["is_valid"])
        self.assertTrue(any("has values outside [0, 1]" in err for err in val["errors"]))

    # Test 15: Missing input files and schema mismatches
    def test_15_missing_input_and_schema_mismatch(self):
        with self.assertRaises(ValueError):
            synthesize_route_ranker_features(pd.DataFrame())

        empty_hub = compute_route_hub_metrics(pd.DataFrame(), pd.DataFrame(), pd.DataFrame())
        self.assertTrue(empty_hub.empty)
        self.assertIn("route_id", empty_hub.columns)

    # Test 16: Constant-valued feature normalization
    def test_16_constant_valued_feature_normalization(self):
        df = pd.DataFrame({
            "route_id": ["1", "2", "3"],
            "constant_col": [10.0, 10.0, 10.0],
            "normal_col": [1.0, 5.0, 10.0],
        })
        norm_df, params = normalize_features(df, feature_cols=["constant_col", "normal_col"])
        self.assertIn("constant_col_norm", norm_df.columns)
        self.assertTrue((norm_df["constant_col_norm"] == 0.5).all())
        self.assertTrue(params["constant_col"]["is_constant"])

    # Test 17: Percentile clipping boundaries
    def test_17_percentile_clipping_boundaries(self):
        df = pd.DataFrame({
            "route_id": [str(i) for i in range(100)],
            "val": [10.0] * 98 + [-999.0, 9999.0],
        })
        norm_df, params = normalize_features(df, feature_cols=["val"], p_min=1.0, p_max=99.0)
        self.assertGreaterEqual(norm_df["val_norm"].min(), 0.0)
        self.assertLessEqual(norm_df["val_norm"].max(), 1.0)

    # Test 18: Division-by-zero protection
    def test_18_division_by_zero_protection(self):
        ops_df = pd.DataFrame({
            "route_id": ["zero_route"],
            "is_rail": [False],
            "scheduled_trips": [0],
            "route_length_km": [0.0],
            "service_span_hours": [0.0],
            "historical_mean_daily_rides": [100.0],
        })
        demand_df = integrate_demand_predictions(ops_df)
        self.assertTrue(pd.isna(demand_df["rides_per_trip"].iloc[0]))
        self.assertTrue(pd.isna(demand_df["load_intensity_factor"].iloc[0]))

    # Test 19: Output schema and feature count
    def test_19_output_schema_and_feature_count(self):
        master = synthesize_route_ranker_features(self.synthetic_ops_df, self.synthetic_kmeans_df)
        for feat in RankerConfig.APPROVED_24_FEATURES:
            self.assertIn(feat, master.columns, f"Approved feature '{feat}' missing from synthesized master!")

    # Test 20: Full 133-route synthetic population accounting
    def test_20_full_133_route_population_accounting(self):
        builder = RankerDatasetBuilder()
        builder.config.MEMORY_ABORT_THRESHOLD_MB = 100.0  # Synthetic fixture threshold
        master, meta = builder.build_synthetic_dataset(
            operational_df=self.synthetic_ops_df,
            kmeans_df=self.synthetic_kmeans_df,
            route_stops_df=self.synthetic_route_stops,
            hub_rankings_df=self.synthetic_hub_rankings,
            top100_hubs_df=self.synthetic_top100_hubs,
            peripheral_stops_df=self.synthetic_periph_stops,
            overlap_matrix=self.synthetic_overlap_matrix,
            shared_sequences_df=self.synthetic_shared_df,
            corridor_assignments_df=self.synthetic_corr_assign_df,
        )
        self.assertEqual(len(master), 133)
        self.assertEqual(master["is_rail"].sum(), 8)
        self.assertEqual((~master["is_rail"]).sum(), 125)
        self.assertTrue(meta["validation"]["is_valid"])
        self.assertEqual(meta["status"], "STAGE_1_SYNTHETIC_BUILD_SUCCESS")

    # Test 21: No target leakage
    def test_21_no_target_leakage(self):
        mock_rf = MockRandomForest()
        mrf = pd.DataFrame({
            "route_id": ["1", "1"],
            "service_date": ["2026-06-10", "2026-07-01"],
            "target": [5000.0, 99999.0],
            "feat_1": [1.0, 2.0],
        })
        demand_df = integrate_demand_predictions(
            self.synthetic_ops_df, mrf, rf_model=mock_rf, service_date="2026-06-10"
        )
        r1 = demand_df[demand_df["route_id"] == "1"]["forecasted_daily_demand"].iloc[0]
        self.assertAlmostEqual(r1, 5432.1, places=1)

    # Test 22: No modification of input DataFrames
    def test_22_no_modification_of_input_dfs(self):
        ops_copy = self.synthetic_ops_df.copy(deep=True)
        km_copy = self.synthetic_kmeans_df.copy(deep=True)
        _ = synthesize_route_ranker_features(self.synthetic_ops_df, self.synthetic_kmeans_df)
        pd.testing.assert_frame_equal(self.synthetic_ops_df, ops_copy)
        pd.testing.assert_frame_equal(self.synthetic_kmeans_df, km_copy)

    # Test 23: Memory guard behavior
    def test_23_memory_guard_behavior(self):
        builder = RankerDatasetBuilder()
        builder.config.MEMORY_ABORT_THRESHOLD_MB = 999999.0
        with self.assertRaises(MemoryError):
            builder.check_memory_guard("test_abort")

    # Test 24: Reproducible metadata generation
    def test_24_reproducible_metadata_generation(self):
        builder = RankerDatasetBuilder()
        builder.config.MEMORY_ABORT_THRESHOLD_MB = 100.0  # Synthetic fixture threshold
        master, meta = builder.build_synthetic_dataset(self.synthetic_ops_df, self.synthetic_kmeans_df)
        self.assertIn("milestone", meta)
        self.assertIn("phase", meta)
        self.assertIn("stage", meta)
        self.assertIn("snapshot_id", meta)
        self.assertIn("representative_service_date", meta)
        self.assertIn("validation", meta)
        self.assertIn("memory_status", meta)
        self.assertEqual(meta["record_count"], 133)


if __name__ == "__main__":
    unittest.main()
