"""
AI_RouteRanker - Phase 7 Stage 1 Unit Test Suite
Comprehensive testing of MCDM ranking engine, criteria transformers, WSM scoring,
TOPSIS benchmarks, explainability generation, and sensitivity analysis using
EXCLUSIVELY isolated synthetic fixtures (no canonical real-data dependencies).
Follows standard library unittest framework.
"""

import unittest
import numpy as np
import pandas as pd

from analytics.ranking.config import RankerConfig
from analytics.ranking.criteria_transformer import CriteriaTransformer
from analytics.ranking.mcdm_engine import MCDMEngine
from analytics.ranking.explainer import RouteRankerExplainer
from analytics.ranking.sensitivity import RankingSensitivityAnalyzer
from analytics.ranking.ranker_service import RouteRankerService


class TestRouteRankingEngine(unittest.TestCase):
    """
    Comprehensive unit tests for Phase 7 MCDM Route Ranking Engine.
    Covers more than 20 discrete test scenarios using synthetic test fixtures only.
    """

    def setUp(self):
        """Creates an isolated synthetic route feature DataFrame for testing."""
        np.random.seed(42)
        self.synthetic_feature_df = pd.DataFrame({
            "route_id": ["1", "2", "3", "10", "130", "Red", "Blue"],
            "route_short_name": ["1", "2", "3", "10", "130", "Red", "Blue"],
            "route_long_name": [
                "Bronzeville", "Hyde Park", "King Drive",
                "Museum of Science", "Museum Campus", "Red Line", "Blue Line"
            ],
            "route_type": [3, 3, 3, 3, 3, 1, 1],
            "is_rail": [False, False, False, False, False, True, True],
            "regional_partition": [
                "South Chicago", "South Chicago", "South Chicago",
                "South Chicago", "North Chicago", "North Chicago", "South Chicago"
            ],
            "operational_cluster_label": [
                "Trunk", "Feeder", "Trunk", "Feeder", "Feeder", "Regional", "Regional"
            ],
            # Criteria normalized features [0, 1]
            "forecasted_daily_demand_norm": [0.85, 0.40, 0.65, 0.15, 0.20, np.nan, np.nan],
            "load_intensity_factor_norm": [0.90, 0.35, 0.70, 0.10, 0.15, np.nan, np.nan],
            "scheduled_trips_norm": [0.80, 0.45, 0.60, 0.20, 0.25, 0.95, 0.92],
            "service_span_hours_norm": [0.95, 0.70, 0.85, 0.30, 0.40, 1.00, 1.00],
            # am_headway_min_norm (Cost criterion): shorter headway has lower normalized value
            "am_headway_min_norm": [0.20, 0.60, 0.35, np.nan, np.nan, 0.10, 0.15],
            "hub_stop_ratio_norm": [0.75, 0.20, 0.50, 0.10, 0.05, 0.00, 0.00],
            "corridor_duplication_index_norm": [0.70, 0.30, 0.55, 0.15, 0.25, 0.40, 0.35],
        })

    # =========================================================================
    # Test Group 1: Configuration & Weight Profile Validation
    # =========================================================================

    def test_01_weight_profile_sums(self):
        """Confirms all approved weight profiles sum to 1.000000 within floating point tolerance."""
        for profile_name, weights in RankerConfig.WEIGHT_PROFILES.items():
            total_w = sum(weights.values())
            self.assertTrue(
                np.isclose(total_w, 1.0, atol=1e-5),
                f"Profile {profile_name} weights sum to {total_w}, expected 1.0"
            )

    def test_02_profile_a_weights_alignment(self):
        """Verifies that Profile A weights exactly match the approved planning specification."""
        weights = RankerConfig.PROFILE_A_WEIGHTS
        self.assertEqual(weights["forecasted_daily_demand_norm"], 0.15)
        self.assertEqual(weights["load_intensity_factor_norm"], 0.20)
        self.assertEqual(weights["scheduled_trips_norm"], 0.10)
        self.assertEqual(weights["service_span_hours_norm"], 0.05)
        self.assertEqual(weights["am_headway_min_norm"], 0.10)
        self.assertEqual(weights["hub_stop_ratio_norm"], 0.20)
        self.assertEqual(weights["corridor_duplication_index_norm"], 0.20)

    # =========================================================================
    # Test Group 2: Criteria Transformer & Cost/Benefit Inversions
    # =========================================================================

    def test_03_criteria_transformer_cost_inversion(self):
        """Verifies cost criterion (am_headway_min_norm) is inverted: transformed = 1 - raw."""
        transformer = CriteriaTransformer()
        matrix, valid_mask, criteria, _ = transformer.transform(
            self.synthetic_feature_df, RankerConfig.PROFILE_A_WEIGHTS
        )
        hw_idx = criteria.index("am_headway_min_norm")

        # Route 1: raw 0.20 -> inverted 0.80
        self.assertTrue(np.isclose(matrix[0, hw_idx], 0.80))
        # Route 2: raw 0.60 -> inverted 0.40
        self.assertTrue(np.isclose(matrix[1, hw_idx], 0.40))
        # Route 10: raw NaN -> transformed NaN
        self.assertTrue(np.isnan(matrix[3, hw_idx]))
        self.assertFalse(valid_mask[3, hw_idx])

    def test_04_criteria_transformer_input_immutability(self):
        """Guarantees the input DataFrame is never modified in-place."""
        original_df = self.synthetic_feature_df.copy(deep=True)
        transformer = CriteriaTransformer()
        _ = transformer.transform(self.synthetic_feature_df, RankerConfig.PROFILE_A_WEIGHTS)
        pd.testing.assert_frame_equal(self.synthetic_feature_df, original_df)

    def test_05_criteria_transformer_missing_schema(self):
        """Detects missing required schema columns and raises KeyError."""
        incomplete_df = pd.DataFrame({"route_id": ["1"], "is_rail": [False]})
        transformer = CriteriaTransformer()
        with self.assertRaises(KeyError):
            transformer.transform(incomplete_df, RankerConfig.PROFILE_A_WEIGHTS)

    def test_06_criteria_transformer_empty_input(self):
        """Raises ValueError on empty or None input."""
        transformer = CriteriaTransformer()
        with self.assertRaises(ValueError):
            transformer.transform(pd.DataFrame(), RankerConfig.PROFILE_A_WEIGHTS)

    # =========================================================================
    # Test Group 3: WSM Mathematical Scoring & Dynamic Weight Redistribution
    # =========================================================================

    def test_07_wsm_hand_calculation_verification(self):
        """Tests WSM scoring on synthetic route against manually hand-calculated exact value."""
        # 3 criteria: [0.8, 0.6, 0.4], weights: [0.5, 0.3, 0.2]
        # Expected: 0.5*0.8 + 0.3*0.6 + 0.2*0.4 = 0.40 + 0.18 + 0.08 = 0.66
        matrix = np.array([[0.8, 0.6, 0.4]], dtype=np.float64)
        weights = np.array([0.5, 0.3, 0.2], dtype=np.float64)
        valid_mask = np.array([[True, True, True]], dtype=bool)
        coverage_mask = np.array([True], dtype=bool)

        scores, eff_w, contribs = MCDMEngine.compute_wsm(matrix, weights, valid_mask, coverage_mask)
        self.assertTrue(np.isclose(scores[0], 0.66))
        self.assertTrue(np.allclose(eff_w[0], weights))
        self.assertTrue(np.allclose(contribs[0], [0.40, 0.18, 0.08]))

    def test_08_wsm_dynamic_missing_weight_redistribution(self):
        """
        Tests dynamic weight redistribution when a criterion is NaN.
        Base weights: [0.5, 0.3, 0.2]. Route has [0.8, NaN, 0.4].
        Valid base weight sum = 0.5 + 0.2 = 0.7.
        Normalized weights: w1' = 0.5/0.7 = 5/7, w3' = 0.2/0.7 = 2/7.
        Expected score = (5/7)*0.8 + (2/7)*0.4 = (4.0 + 0.8) / 7 = 4.8 / 7 = 0.685714.
        """
        matrix = np.array([[0.8, np.nan, 0.4]], dtype=np.float64)
        weights = np.array([0.5, 0.3, 0.2], dtype=np.float64)
        valid_mask = np.array([[True, False, True]], dtype=bool)
        coverage_mask = np.array([True], dtype=bool)

        scores, eff_w, contribs = MCDMEngine.compute_wsm(matrix, weights, valid_mask, coverage_mask)
        expected_score = 4.8 / 7.0
        self.assertTrue(np.isclose(scores[0], expected_score, atol=1e-5))
        self.assertTrue(np.isclose(eff_w[0, 0], 5.0 / 7.0))
        self.assertEqual(eff_w[0, 1], 0.0)
        self.assertTrue(np.isclose(eff_w[0, 2], 2.0 / 7.0))
        self.assertTrue(np.isclose(np.sum(eff_w[0]), 1.0))

    def test_09_wsm_insufficient_weight_coverage_rule(self):
        """Confirms route with valid criteria weight < 50% is marked as NaN (unavailable)."""
        matrix = np.array([[0.9, np.nan, np.nan]], dtype=np.float64)
        weights = np.array([0.4, 0.3, 0.3], dtype=np.float64)
        valid_mask = np.array([[True, False, False]], dtype=bool)
        coverage_mask = np.array([False], dtype=bool)

        scores, _, _ = MCDMEngine.compute_wsm(matrix, weights, valid_mask, coverage_mask)
        self.assertTrue(np.isnan(scores[0]))

    def test_10_wsm_all_missing_criteria(self):
        """Confirms route with 100% missing criteria produces NaN score."""
        matrix = np.array([[np.nan, np.nan, np.nan]], dtype=np.float64)
        weights = np.array([0.5, 0.3, 0.2], dtype=np.float64)
        valid_mask = np.array([[False, False, False]], dtype=bool)
        coverage_mask = np.array([False], dtype=bool)

        scores, eff_w, contribs = MCDMEngine.compute_wsm(matrix, weights, valid_mask, coverage_mask)
        self.assertTrue(np.isnan(scores[0]))
        self.assertTrue(np.all(eff_w[0] == 0.0))
        self.assertTrue(np.all(contribs[0] == 0.0))

    def test_11_wsm_contribution_sum_invariant(self):
        """Mathematical Invariant: Sum of individual criterion contributions MUST equal overall score."""
        transformer = CriteriaTransformer()
        matrix, valid_mask, criteria, coverage_mask = transformer.transform(
            self.synthetic_feature_df, RankerConfig.PROFILE_A_WEIGHTS
        )
        base_w_vec = np.array([RankerConfig.PROFILE_A_WEIGHTS[c] for c in criteria], dtype=np.float64)

        scores, _, contribs = MCDMEngine.compute_wsm(matrix, base_w_vec, valid_mask, coverage_mask)

        for i in range(len(scores)):
            if not np.isnan(scores[i]):
                c_sum = np.sum(contribs[i])
                self.assertTrue(
                    np.isclose(c_sum, scores[i], atol=1e-6),
                    f"Row {i}: Contribution sum {c_sum} != Score {scores[i]}"
                )

    # =========================================================================
    # Test Group 4: TOPSIS Benchmark Algorithm
    # =========================================================================

    def test_12_topsis_bounds_and_ranking(self):
        """Verifies TOPSIS scores are bounded in [0, 1] and superior routes get higher closeness."""
        matrix = np.array([
            [0.9, 0.85, 0.95],  # Route A (strong)
            [0.2, 0.15, 0.10],  # Route B (weak)
        ], dtype=np.float64)
        weights = np.array([0.4, 0.3, 0.3], dtype=np.float64)
        valid_mask = np.ones((2, 3), dtype=bool)
        coverage_mask = np.ones(2, dtype=bool)

        topsis_scores = MCDMEngine.compute_topsis(matrix, weights, valid_mask, coverage_mask)
        self.assertEqual(len(topsis_scores), 2)
        self.assertTrue(0.0 <= topsis_scores[0] <= 1.0)
        self.assertTrue(0.0 <= topsis_scores[1] <= 1.0)
        self.assertGreater(topsis_scores[0], topsis_scores[1])

    # =========================================================================
    # Test Group 5: Deterministic Ranking & Tie Handling
    # =========================================================================

    def test_13_ranking_deterministic_and_tie_breaking(self):
        """Confirms competition ranking ('min') handles exact ties deterministically."""
        scores = np.array([0.90, 0.85, 0.85, 0.70, np.nan], dtype=np.float64)
        ranks, pct_ranks = MCDMEngine.assign_ranks(scores, ascending=False)

        self.assertEqual(ranks[0], 1.0)
        self.assertEqual(ranks[1], 2.0)
        self.assertEqual(ranks[2], 2.0)
        self.assertEqual(ranks[3], 4.0)
        self.assertTrue(np.isnan(ranks[4]))
        self.assertTrue(np.isnan(pct_ranks[4]))

    # =========================================================================
    # Test Group 6: Explainer Engine & Pillar Rollup Invariants
    # =========================================================================

    def test_14_pillar_scores_sum_invariant(self):
        """Mathematical Invariant: Sum of 4 pillar scores MUST equal overall score."""
        service = RouteRankerService()
        results = service.run_ranking(self.synthetic_feature_df, track=RankerConfig.TRACK_BUS_PRIORITY)
        ranked_df = results["rankings_df"]

        for _, row in ranked_df.iterrows():
            if pd.notna(row["overall_score"]):
                p_sum = (
                    row["pillar_demand_score"]
                    + row["pillar_service_score"]
                    + row["pillar_hub_score"]
                    + row["pillar_corridor_score"]
                )
                self.assertTrue(
                    np.isclose(p_sum, row["overall_score"], atol=1e-5),
                    f"Route {row['route_id']}: Pillar sum {p_sum} != Overall score {row['overall_score']}"
                )

    def test_15_explanation_json_schema_validity(self):
        """Verifies that generated explanation dictionaries contain all required frontend fields."""
        service = RouteRankerService()
        results = service.run_ranking(self.synthetic_feature_df, track=RankerConfig.TRACK_BUS_PRIORITY)
        explanations = results["explanations"]

        self.assertEqual(len(explanations), 5)  # 5 bus routes
        for exp in explanations:
            self.assertIn("route_id", exp)
            self.assertIn("route_short_name", exp)
            self.assertIn("overall_score", exp)
            self.assertIn("rank", exp)
            self.assertIn("pillars", exp)
            self.assertIn("top_positive_drivers", exp)
            self.assertIn("top_negative_drivers", exp)
            self.assertIn("narrative", exp)
            self.assertIn("missing_criteria", exp)

            self.assertEqual(len(exp["pillars"]), 4)
            self.assertIn("demand_pressure", exp["pillars"])
            self.assertIn("service_provision", exp["pillars"])
            self.assertIn("network_hubs", exp["pillars"])
            self.assertIn("corridor_structure", exp["pillars"])

    def test_16_explanation_narrative_objective_language(self):
        """Ensures narratives contain no pejorative language or claims of service cuts."""
        service = RouteRankerService()
        results = service.run_ranking(self.synthetic_feature_df, track=RankerConfig.TRACK_BUS_PRIORITY)
        for exp in results["explanations"]:
            text = exp["narrative"].lower()
            self.assertNotIn("cancel", text)
            self.assertNotIn("eliminate", text)
            self.assertNotIn("remove service", text)
            self.assertNotIn("safety risk", text)

    # =========================================================================
    # Test Group 7: Ranking Tracks & Population Segmentation
    # =========================================================================

    def test_17_track_bus_priority_population(self):
        """Track 1 (Bus Priority) evaluates only bus routes (is_rail == False)."""
        service = RouteRankerService()
        results = service.run_ranking(self.synthetic_feature_df, track=RankerConfig.TRACK_BUS_PRIORITY)
        ranked_df = results["rankings_df"]

        self.assertEqual(len(ranked_df), 5)
        self.assertTrue((ranked_df["is_rail"] == False).all())
        self.assertNotIn("Red", ranked_df["route_id"].values)
        self.assertNotIn("Blue", ranked_df["route_id"].values)

    def test_18_track_rail_priority_population(self):
        """Track 2 (Rail Priority) evaluates only rail routes (is_rail == True)."""
        service = RouteRankerService()
        results = service.run_ranking(self.synthetic_feature_df, track=RankerConfig.TRACK_RAIL_PRIORITY)
        ranked_df = results["rankings_df"]

        self.assertEqual(len(ranked_df), 2)
        self.assertTrue((ranked_df["is_rail"] == True).all())
        self.assertEqual(set(ranked_df["route_id"].values), {"Red", "Blue"})

    def test_19_track_unified_supply_population(self):
        """Track 3 (Unified Supply) evaluates all routes using mode-agnostic operational criteria."""
        service = RouteRankerService()
        results = service.run_ranking(self.synthetic_feature_df, track=RankerConfig.TRACK_UNIFIED_SUPPLY)
        ranked_df = results["rankings_df"]

        self.assertEqual(len(ranked_df), 7)
        self.assertEqual(set(ranked_df["route_id"].values), {"1", "2", "3", "10", "130", "Red", "Blue"})
        self.assertFalse(ranked_df["overall_score"].isna().all())

    # =========================================================================
    # Test Group 8: Sensitivity Analysis & Metrics
    # =========================================================================

    def test_20_sensitivity_weight_perturbation_sum(self):
        """Weight perturbations by ±10% and ±20% must always sum to 1.000000 exactly."""
        base_w = RankerConfig.PROFILE_A_WEIGHTS
        for delta in [-0.20, -0.10, 0.10, 0.20]:
            for crit in base_w:
                pert_w = RankingSensitivityAnalyzer.perturb_weights(base_w, crit, delta)
                self.assertTrue(
                    np.isclose(sum(pert_w.values()), 1.0, atol=1e-5),
                    f"Perturbation of {crit} by {delta} != 1.0"
                )

    def test_21_spearman_correlation_computation(self):
        """Validates Spearman rho computation on synthetic rank vectors."""
        ranks_1 = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        ranks_2 = np.array([1.0, 2.0, 3.0, 4.0, 5.0])  # Identical
        self.assertTrue(np.isclose(RankingSensitivityAnalyzer.compute_spearman_correlation(ranks_1, ranks_2), 1.0))

        ranks_3 = np.array([5.0, 4.0, 3.0, 2.0, 1.0])  # Inverse
        self.assertTrue(np.isclose(RankingSensitivityAnalyzer.compute_spearman_correlation(ranks_1, ranks_3), -1.0))

    def test_22_top_k_overlap_computation(self):
        """Validates Top-K overlap computation."""
        ranks_1 = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        ranks_2 = np.array([1.0, 3.0, 2.0, 5.0, 4.0])  # Top-3 are the same set {0, 1, 2}
        overlap_3 = RankingSensitivityAnalyzer.compute_top_k_overlap(ranks_1, ranks_2, k=3)
        self.assertTrue(np.isclose(overlap_3, 1.0))

        ranks_4 = np.array([5.0, 4.0, 3.0, 1.0, 2.0])  # Top-2 disjoint from ranks_1
        overlap_2 = RankingSensitivityAnalyzer.compute_top_k_overlap(ranks_1, ranks_4, k=2)
        self.assertTrue(np.isclose(overlap_2, 0.0))

    def test_23_end_to_end_sensitivity_pipeline(self):
        """Executes sensitivity suite and checks output structure and overall stability score."""
        service = RouteRankerService()
        results = service.run_ranking(
            self.synthetic_feature_df,
            track=RankerConfig.TRACK_BUS_PRIORITY,
            run_sensitivity=True
        )
        scenarios_df = results["sensitivity_scenarios"]
        self.assertIsNotNone(scenarios_df)
        self.assertEqual(len(scenarios_df), 7 * 4)  # 7 criteria * 4 deltas = 28 scenarios
        self.assertIn("spearman_rho", scenarios_df.columns)
        self.assertIn("top_10_overlap", scenarios_df.columns)
        self.assertTrue(0.0 <= results["overall_stability"] <= 1.0)

    def test_24_invalid_and_boundary_values(self):
        """Validates clipping and robustness on boundary values (0.0, 1.0) and values outside [0, 1]."""
        boundary_df = pd.DataFrame({
            "route_id": ["min_r", "max_r", "clip_r"],
            "route_short_name": ["min_r", "max_r", "clip_r"],
            "is_rail": [False, False, False],
            "forecasted_daily_demand_norm": [0.0, 1.0, 1.5],   # 1.5 will be clipped to 1.0
            "load_intensity_factor_norm": [0.0, 1.0, -0.5],    # -0.5 will be clipped to 0.0
            "scheduled_trips_norm": [0.0, 1.0, 0.5],
            "service_span_hours_norm": [0.0, 1.0, 0.5],
            "am_headway_min_norm": [0.0, 1.0, 0.5],
            "hub_stop_ratio_norm": [0.0, 1.0, 0.5],
            "corridor_duplication_index_norm": [0.0, 1.0, 0.5],
        })
        service = RouteRankerService()
        results = service.run_ranking(boundary_df, track=RankerConfig.TRACK_BUS_PRIORITY, run_sensitivity=False)
        ranked = results["rankings_df"]
        self.assertEqual(len(ranked), 3)
        self.assertTrue((ranked["overall_score"] >= 0.0).all())
        self.assertTrue((ranked["overall_score"] <= 1.0).all())


if __name__ == "__main__":
    unittest.main()
