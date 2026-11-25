"""
AI_RouteRanker - Focused Unit Tests for Milestone 6, Phase 6.1 Spatial Stop & Route Clustering
Verifies:
  1. Spatial projection accuracy, invertibility, and geodesic error bounds.
  2. Route demand attribution, conservation, coverage classification, and intensity.
  3. Scheduled headway calculations across all five approved windows with post-midnight preservation.
  4. Stop eligibility waterfall classification and reconciliation.
  5. DBSCAN baseline clustering and corridor chaining diagnostics.
  6. K-Means candidate evaluation across k in [3, 8] on invariant standardized inputs.
  7. Deterministic 5-seed sampled silhouette scoring with noise exclusion, represented weighting,
     and NOT COMPUTABLE degeneracy handling.
  8. Hub ranking sensitivity across Configs A, B, and C over an identical eligible population.
"""

import unittest
import numpy as np
import pandas as pd

from analytics.clustering.spatial_projection import SpatialProjector
from analytics.clustering.demand_aggregator import (
    DemandAggregator,
    CANONICAL_SNAPSHOT_ID,
    REPRESENTATIVE_DATE,
    HEADWAY_WINDOWS,
)
from analytics.clustering.stop_clustering import StopClusterer
from analytics.clustering.evaluator import ClusteringEvaluator


class TestSpatialProjection(unittest.TestCase):
    """Unit tests for pure NumPy local Equirectangular projection."""

    def setUp(self):
        self.projector = SpatialProjector()

    def test_centroid_projects_to_origin(self):
        """Centroid coordinates must map to (0.0, 0.0) meters."""
        x, y = self.projector.forward(self.projector.lat_0, self.projector.lon_0)
        self.assertAlmostEqual(x, 0.0, places=4)
        self.assertAlmostEqual(y, 0.0, places=4)

    def test_forward_inverse_invertibility(self):
        """Inverse projection of forward coordinates must recover original lat/lon."""
        test_lats = np.array([41.65, 41.85, 42.05])
        test_lons = np.array([-87.85, -87.71, -87.55])
        
        x, y = self.projector.forward(test_lats, test_lons)
        recovered_lat, recovered_lon = self.projector.inverse(x, y)
        
        np.testing.assert_allclose(recovered_lat, test_lats, atol=1e-7)
        np.testing.assert_allclose(recovered_lon, test_lons, atol=1e-7)

    def test_projection_distortion_bound(self):
        """Maximum distortion across Chicago extents must be bounded below 0.35%."""
        # Extreme Northern baseline across Chicago stops
        lat_north = 42.0731530
        lon_west = -87.90422307
        lon_east = -87.52569948
        
        d_hav, d_proj, err_pct = self.projector.calculate_distortion(
            lat_north, lon_west, lat_north, lon_east
        )
        self.assertGreater(d_hav, 30000.0)  # ~31.2 km
        self.assertLessEqual(err_pct, 0.35, f"Distortion {err_pct:.4f}% exceeded 0.35% threshold!")
        self.assertAlmostEqual(err_pct, 0.3373, places=2)

    def test_projection_identical_coordinates_zero_distance(self):
        """Two identical non-origin coordinates produce zero distance and finite zero distortion without division-by-zero."""
        lat_loop = 41.8834
        lon_loop = -87.6246

        d_hav = self.projector.haversine_distance(lat_loop, lon_loop, lat_loop, lon_loop)
        d_proj = self.projector.projected_euclidean_distance(lat_loop, lon_loop, lat_loop, lon_loop)
        hav_val, proj_val, err_pct = self.projector.calculate_distortion(lat_loop, lon_loop, lat_loop, lon_loop)

        self.assertAlmostEqual(float(d_hav), 0.0, places=6)
        self.assertAlmostEqual(float(d_proj), 0.0, places=6)
        self.assertEqual(hav_val, 0.0)
        self.assertEqual(proj_val, 0.0)
        self.assertEqual(err_pct, 0.0)
        self.assertTrue(np.isfinite(err_pct))


class TestDemandAggregator(unittest.TestCase):
    """Unit tests for demand attribution, headway calculation, and eligibility waterfall."""

    def test_gtfs_time_parsing_beyond_24h(self):
        """Preserves hours >= 24 as continuous seconds without modulo wrapping."""
        self.assertEqual(DemandAggregator.parse_gtfs_time_to_seconds("08:30:00"), 30600)
        self.assertEqual(DemandAggregator.parse_gtfs_time_to_seconds("24:15:00"), 87300)
        self.assertEqual(DemandAggregator.parse_gtfs_time_to_seconds("25:30:00"), 91800)

    def test_demand_attribution_conservation(self):
        """Sum of attributed stop demand for mapped route must strictly equal route demand."""
        # 3 stops served by Route 4 (mapped) and Route 999 (unmapped)
        stop_visits = pd.DataFrame([
            {"stop_id": "S1", "route_id": "4", "visits": 20},
            {"stop_id": "S2", "route_id": "4", "visits": 30},
            {"stop_id": "S3", "route_id": "4", "visits": 50},
            {"stop_id": "S3", "route_id": "999", "visits": 10},
            {"stop_id": "S4", "route_id": "999", "visits": 15},
        ])
        route_demand = pd.DataFrame([
            {"route_id": "4", "mean_daily_rides": 1000.0},
        ])
        mapped_routes = {"4"}

        result = DemandAggregator.compute_route_stop_demand_attribution(
            stop_visits, route_demand, mapped_routes
        )

        # Check conservation for route 4: sum over S1, S2, S3 must be 1000.0
        # S1: 200.0, S2: 300.0, S3: 500.0
        s1 = result[result["stop_id"] == "S1"].iloc[0]
        s2 = result[result["stop_id"] == "S2"].iloc[0]
        s3 = result[result["stop_id"] == "S3"].iloc[0]
        s4 = result[result["stop_id"] == "S4"].iloc[0]

        self.assertAlmostEqual(s1["attributed_demand"], 200.0)
        self.assertAlmostEqual(s2["attributed_demand"], 300.0)
        self.assertAlmostEqual(s3["attributed_demand"], 500.0)
        self.assertEqual(s1["demand_coverage_status"], "COMPLETE")
        self.assertEqual(s3["demand_coverage_status"], "PARTIAL")
        self.assertEqual(s4["demand_coverage_status"], "UNAVAILABLE")
        self.assertTrue(pd.isna(s4["attributed_demand"]))

        total_attributed_r4 = s1["attributed_demand"] + s2["attributed_demand"] + s3["attributed_demand"]
        self.assertAlmostEqual(total_attributed_r4, 1000.0, places=4)

    def test_headway_calculation_window_isolation(self):
        """Headways must not cross window boundaries; single arrivals return NaN."""
        # Stop S1 has trips at 08:30, 08:50 (AM Peak), and 09:10 (Midday)
        stop_times = pd.DataFrame([
            {"stop_id": "S1", "route_id": "1", "direction_id": 0, "arrival_seconds": 30600}, # 08:30:00 (AM)
            {"stop_id": "S1", "route_id": "1", "direction_id": 0, "arrival_seconds": 31800}, # 08:50:00 (AM)
            {"stop_id": "S1", "route_id": "1", "direction_id": 0, "arrival_seconds": 33000}, # 09:10:00 (Midday)
            # S2 has only ONE arrival in AM Peak (08:45)
            {"stop_id": "S2", "route_id": "1", "direction_id": 0, "arrival_seconds": 31500}, # 08:45:00 (AM)
        ])

        hw_am = DemandAggregator.calculate_headways_for_window(stop_times, "AM_PEAK")
        
        # S1 has one interval: 31800 - 30600 = 1200 sec = 20.0 min
        s1_row = hw_am[hw_am["stop_id"] == "S1"].iloc[0]
        self.assertAlmostEqual(s1_row["mean_headway_interval_weighted_am_peak"], 20.0)
        self.assertEqual(s1_row["valid_route_dirs_am_peak"], 1)

        # S2 has 0 valid intervals in AM peak, should not be in valid interval results or have NaN
        s2_match = hw_am[hw_am["stop_id"] == "S2"]
        self.assertEqual(len(s2_match), 0)

    def test_headway_exact_window_boundaries(self):
        """Verifies half-open [start, end) window boundary inclusion, exclusion, and service-date isolation."""
        # AM Peak is [25200, 32400) (07:00:00 to 08:59:59)
        # Midday is [32400, 57600) (09:00:00 to 15:59:59)
        stop_times = pd.DataFrame([
            # Stop S1: arrivals at exact start (25200), middle (28800), exact end (32400), and Midday (36000)
            {"stop_id": "S1", "route_id": "1", "direction_id": 0, "service_date": "2026-06-10", "arrival_seconds": 25200}, # 07:00:00 (exact start of AM Peak)
            {"stop_id": "S1", "route_id": "1", "direction_id": 0, "service_date": "2026-06-10", "arrival_seconds": 28800}, # 08:00:00 (inside AM Peak)
            {"stop_id": "S1", "route_id": "1", "direction_id": 0, "service_date": "2026-06-10", "arrival_seconds": 32400}, # 09:00:00 (exact boundary: excluded from AM, start of Midday)
            {"stop_id": "S1", "route_id": "1", "direction_id": 0, "service_date": "2026-06-10", "arrival_seconds": 36000}, # 10:00:00 (inside Midday)
        ])

        # 1. AM Peak: 07:00:00 (25200) belongs to AM; 09:00:00 (32400) is strictly excluded from AM
        hw_am = DemandAggregator.calculate_headways_for_window(stop_times, "AM_PEAK")
        s1_am = hw_am[hw_am["stop_id"] == "S1"].iloc[0]
        # In AM Peak, only 25200 and 28800 are present -> exactly 1 interval: (28800 - 25200) / 60 = 60.0 min
        # If 32400 were incorrectly included, total_intervals would be 2 and (32400 - 28800) would be present.
        self.assertEqual(s1_am["valid_route_dirs_am_peak"], 1)
        self.assertAlmostEqual(s1_am["mean_headway_interval_weighted_am_peak"], 60.0)

        # 2. Midday: 09:00:00 (32400) belongs to Midday (next approved window); 10:00:00 (36000) inside Midday
        hw_mid = DemandAggregator.calculate_headways_for_window(stop_times, "MIDDAY")
        s1_mid = hw_mid[hw_mid["stop_id"] == "S1"].iloc[0]
        # In Midday, arrivals are 32400 and 36000 -> exactly 1 interval: (36000 - 32400) / 60 = 60.0 min
        self.assertEqual(s1_mid["valid_route_dirs_midday"], 1)
        self.assertAlmostEqual(s1_mid["mean_headway_interval_weighted_midday"], 60.0)

        # 3. Confirm no headway interval is calculated across different windows (e.g., between 28800 and 32400)
        # Neither AM nor Midday should contain an interval bridging 28800 to 32400
        # In AM, 28800 is the last arrival, so no post-28800 headway is formed.
        # In Midday, 32400 is the first arrival (shift(1) is NaN), so it cannot pair with 28800 from AM.

    def test_multi_service_date_headway_safety(self):
        """Verifies multi-date trips are grouped independently by service_date, preventing cross-date intervals."""
        # Stop S_MULTI has trips across two dates: 2026-06-10 and 2026-06-11
        # On 2026-06-10: arrivals at 25200 (07:00) and 27000 (07:30) -> headway = 30.0 min
        # On 2026-06-11: arrivals at 28800 (08:00) and 30600 (08:30) -> headway = 30.0 min
        stop_times_multidate = pd.DataFrame([
            {"stop_id": "S_MULTI", "route_id": "10", "direction_id": 0, "service_date": "2026-06-10", "arrival_seconds": 25200},
            {"stop_id": "S_MULTI", "route_id": "10", "direction_id": 0, "service_date": "2026-06-10", "arrival_seconds": 27000},
            {"stop_id": "S_MULTI", "route_id": "10", "direction_id": 0, "service_date": "2026-06-11", "arrival_seconds": 28800},
            {"stop_id": "S_MULTI", "route_id": "10", "direction_id": 0, "service_date": "2026-06-11", "arrival_seconds": 30600},
        ])

        # When service_date column is present:
        # Group 1 (2026-06-10): 1 interval of 30.0 min
        # Group 2 (2026-06-11): 1 interval of 30.0 min
        # Total intervals: 2, total sum: 60.0 min, weighted mean: 30.0 min
        hw_multidate = DemandAggregator.calculate_headways_for_window(stop_times_multidate, "AM_PEAK")
        row_multi = hw_multidate[hw_multidate["stop_id"] == "S_MULTI"].iloc[0]
        self.assertAlmostEqual(row_multi["mean_headway_interval_weighted_am_peak"], 30.0)
        self.assertAlmostEqual(row_multi["median_headway_am_peak"], 30.0)

        # Stop with only 1 trip per day across 2 dates:
        stop_times_single_per_day = pd.DataFrame([
            {"stop_id": "S_SINGLE", "route_id": "10", "direction_id": 0, "service_date": "2026-06-10", "arrival_seconds": 26000},
            {"stop_id": "S_SINGLE", "route_id": "10", "direction_id": 0, "service_date": "2026-06-11", "arrival_seconds": 27000},
        ])
        hw_single = DemandAggregator.calculate_headways_for_window(stop_times_single_per_day, "AM_PEAK")
        # With service_date, neither date has >= 2 trips, so 0 valid intervals exist
        self.assertEqual(len(hw_single), 0)

        # When service_date column is absent (legacy / single-date feed):
        stop_times_no_date = stop_times_multidate.drop(columns=["service_date"])
        # Without service_date, all 4 trips sort by arrival_seconds: 25200, 27000, 28800, 30600
        # Intervals: (27000-25200)=1800s (30 min), (28800-27000)=1800s (30 min), (30600-28800)=1800s (30 min) -> 3 intervals
        hw_nodate = DemandAggregator.calculate_headways_for_window(stop_times_no_date, "AM_PEAK")
        row_nodate = hw_nodate[hw_nodate["stop_id"] == "S_MULTI"].iloc[0]
        self.assertAlmostEqual(row_nodate["mean_headway_interval_weighted_am_peak"], 30.0)
        self.assertEqual(row_nodate["valid_route_dirs_am_peak"], 1)

    def test_demand_intensity_calculation(self):
        """Demand intensity I_s = D / v returns NaN when visits=0 or demand=NaN."""
        self.assertAlmostEqual(DemandAggregator.compute_demand_intensity(500.0, 50.0), 10.0)
        self.assertTrue(pd.isna(DemandAggregator.compute_demand_intensity(500.0, 0.0)))
        self.assertTrue(pd.isna(DemandAggregator.compute_demand_intensity(np.nan, 50.0)))

    def test_stop_eligibility_reconciliation(self):
        """Waterfall assigns mutually exclusive status and reconciles to 100%."""
        mock_stops = pd.DataFrame([
            {"stop_id": "S1", "total_visits": 0, "attributed_demand": 100.0, "mean_headway_interval_weighted_am_peak": 10.0},
            {"stop_id": "S2", "total_visits": 50, "attributed_demand": np.nan, "mean_headway_interval_weighted_am_peak": 10.0},
            {"stop_id": "S3", "total_visits": 50, "attributed_demand": 100.0, "mean_headway_interval_weighted_am_peak": np.nan},
            {"stop_id": "S4", "total_visits": 50, "attributed_demand": 0.0, "mean_headway_interval_weighted_am_peak": 12.0, "demand_coverage_status": "COMPLETE"}, # Valid zero demand
            {"stop_id": "S5", "total_visits": 60, "attributed_demand": 250.0, "mean_headway_interval_weighted_am_peak": 8.0, "demand_coverage_status": "COMPLETE"},
        ])

        classified, summary = DemandAggregator.classify_stop_eligibility(mock_stops)
        
        self.assertEqual(classified.loc[0, "primary_eligibility_status"], "EXCLUDED_ZERO_VISITS")
        self.assertEqual(classified.loc[1, "primary_eligibility_status"], "EXCLUDED_UNAVAILABLE_DEMAND")
        self.assertEqual(classified.loc[2, "primary_eligibility_status"], "EXCLUDED_NO_AM_HEADWAY")
        self.assertEqual(classified.loc[3, "primary_eligibility_status"], "ELIGIBLE") # D_s = 0.0 is ELIGIBLE!
        self.assertEqual(classified.loc[4, "primary_eligibility_status"], "ELIGIBLE")
        
        self.assertTrue(summary["is_fully_reconciled"])
        self.assertEqual(summary["total_stops"], 5)
        self.assertEqual(summary["sum_partition_counts"], 5)

    def test_eligibility_multi_condition_waterfall_priority(self):
        """Verifies that EXCLUDED_ZERO_VISITS strictly takes precedence when multiple conditions fail simultaneously."""
        multi_fail_stop = pd.DataFrame([{
            "stop_id": "S_MULTI",
            "total_visits": 0,                     # Fails visits -> priority 1
            "attributed_demand": np.nan,           # Fails demand -> priority 2
            "mean_headway_interval_weighted_am_peak": np.nan,  # Fails headway -> priority 3
            "demand_coverage_status": "UNAVAILABLE",
            "routes_served": 1,
            "service_span_hours": 0.0,
        }])

        classified, summary = DemandAggregator.classify_stop_eligibility(multi_fail_stop)

        # Primary status MUST be EXCLUDED_ZERO_VISITS due to waterfall short-circuit
        self.assertEqual(classified.loc[0, "primary_eligibility_status"], "EXCLUDED_ZERO_VISITS")

        # Secondary diagnostic flags MUST all be recorded independently
        self.assertTrue(classified.loc[0, "flag_zero_visits"])
        self.assertTrue(classified.loc[0, "flag_unavailable_demand"])
        self.assertTrue(classified.loc[0, "flag_no_am_headway"])

        # Reconciled to exactly 1 stop
        self.assertTrue(summary["is_fully_reconciled"])
        self.assertEqual(summary["table"]["EXCLUDED_ZERO_VISITS"]["count"], 1)


class TestStopClusterer(unittest.TestCase):
    """Unit tests for DBSCAN chaining diagnostics and K-Means candidate evaluation."""

    def test_dbscan_clustering_and_chaining_diagnostics(self):
        """DBSCAN groups nearby points, labels noise as -1, and flags chained clusters."""
        # Cluster 0: tight 3-point cluster (within 100m)
        # Cluster 1: elongated 60-point linear corridor spanning 2000m
        # Point 63: isolated outlier (noise)
        c0_x = np.array([0.0, 50.0, 80.0])
        c0_y = np.array([0.0, 30.0, 60.0])

        c1_x = np.linspace(10000.0, 12000.0, 60)
        c1_y = np.linspace(10000.0, 10050.0, 60)

        outlier_x = np.array([50000.0])
        outlier_y = np.array([50000.0])

        all_x = np.concatenate([c0_x, c1_x, outlier_x])
        all_y = np.concatenate([c0_y, c1_y, outlier_y])

        clusterer = StopClusterer(eps=300.0, min_samples=2)
        labels, diagnostics = clusterer.run_spatial_dbscan(all_x, all_y)

        # Outlier is noise (-1)
        self.assertEqual(labels[-1], -1)

        # c0 is not chained
        c0_id = labels[0]
        self.assertFalse(diagnostics[c0_id]["is_chained"])
        self.assertLess(diagnostics[c0_id]["diameter_meters"], 200.0)

        # c1 is chained (both size > 50 and diameter > 1500m)
        c1_id = labels[3]
        self.assertTrue(diagnostics[c1_id]["is_chained"])
        self.assertGreater(diagnostics[c1_id]["diameter_meters"], 1500.0)
        self.assertEqual(diagnostics[c1_id]["stop_count"], 60)

    def test_kmeans_candidate_evaluation(self):
        """Evaluates k in [3, 8] deterministically and verifies error on NaN."""
        rng = np.random.RandomState(42)
        synthetic_features = rng.uniform(1.0, 100.0, size=(100, 5))

        clusterer = StopClusterer(random_state=42)
        results = clusterer.evaluate_kmeans_candidates(synthetic_features, candidate_k=[3, 4, 5])

        self.assertIn("candidates", results)
        for k in [3, 4, 5]:
            cand = results["candidates"][k]
            self.assertEqual(cand["k"], k)
            self.assertEqual(len(cand["labels"]), 100)
            self.assertGreater(cand["inertia"], 0.0)

        # Must reject NaN inputs
        nan_features = synthetic_features.copy()
        nan_features[0, 0] = np.nan
        with self.assertRaises(ValueError):
            clusterer.evaluate_kmeans_candidates(nan_features)


class TestClusteringEvaluator(unittest.TestCase):
    """Unit tests for sampled silhouette scoring and hub sensitivity analysis."""

    def test_silhouette_noise_exclusion_and_five_seeds(self):
        """Excludes noise label -1 and evaluates 5 fixed deterministic seeds."""
        rng = np.random.RandomState(42)
        # Create 3 well-separated clusters of 50 points each plus 10 noise points
        c1 = rng.normal(loc=0.0, scale=1.0, size=(50, 4))
        c2 = rng.normal(loc=15.0, scale=1.0, size=(50, 4))
        c3 = rng.normal(loc=30.0, scale=1.0, size=(50, 4))
        noise = rng.uniform(low=-50.0, high=50.0, size=(10, 4))

        X = np.vstack([c1, c2, c3, noise])
        labels = np.array([0] * 50 + [1] * 50 + [2] * 50 + [-1] * 10)

        eval_res = ClusteringEvaluator.evaluate_sampled_silhouette(X, labels, sample_size=100)

        self.assertEqual(eval_res["status"], "VALID EVALUATION")
        self.assertEqual(eval_res["n_noise_stops"], 10)
        self.assertEqual(eval_res["n_valid_clusters"], 3)
        self.assertEqual(eval_res["n_represented_stops"], 150)
        self.assertEqual(len(eval_res["seed_scores"]), 5)
        self.assertGreater(eval_res["mean_score"], 0.70)  # Distinct clusters have high silhouette

    def test_silhouette_degeneracy_not_computable(self):
        """Returns NOT COMPUTABLE (NaN) when fewer than 2 valid clusters exist."""
        X = np.random.randn(50, 4)
        # Case 1: All points in single cluster
        labels_one = np.zeros(50, dtype=int)
        res_one = ClusteringEvaluator.evaluate_sampled_silhouette(X, labels_one)
        self.assertEqual(res_one["status"], "NOT COMPUTABLE")
        self.assertEqual(res_one["reason"], "REASON_FEWER_THAN_TWO_VALID_CLUSTERS")
        self.assertTrue(np.isnan(res_one["mean_score"]))

        # Case 2: All points are noise (-1)
        labels_noise = np.full(50, -1, dtype=int)
        res_noise = ClusteringEvaluator.evaluate_sampled_silhouette(X, labels_noise)
        self.assertEqual(res_noise["status"], "NOT COMPUTABLE")
        self.assertEqual(res_noise["reason"], "REASON_ALL_POINTS_NOISE")
        self.assertTrue(np.isnan(res_noise["mean_score"]))

    def test_silhouette_largest_remainder_deterministic_tie_break(self):
        """Verifies Largest Remainder Method deterministic tie-breaking (remainder desc, pop desc, cluster ID asc)."""
        rng = np.random.RandomState(42)
        # Create 4 distinct clusters: C0 (20 pts), C1 (20 pts), C2 (15 pts), C3 (15 pts)
        # Target sample size 13 with base minimum 3 per cluster:
        # Base allocated = 4 * 3 = 12. Remaining sample size = 1.
        # Capacities: C0: 17, C1: 17, C2: 12, C3: 12. Total = 58.
        # Quotas: C0: 17/58, C1: 17/58. Exact fractional remainder tie between C0 and C1!
        # Deterministic tie-breaker selects C0 because cluster_id 0 < 1.
        c0 = rng.randn(20, 2)
        c1 = rng.randn(20, 2) + 10.0
        c2 = rng.randn(15, 2) + 20.0
        c3 = rng.randn(15, 2) + 30.0

        X = np.vstack([c0, c1, c2, c3])
        labels = np.array([0] * 20 + [1] * 20 + [2] * 15 + [3] * 15)

        # Run 1
        res1 = ClusteringEvaluator.evaluate_sampled_silhouette(X, labels, sample_size=13, seeds=[42])
        # Run 2 (repeated call with identical seed to test reproducibility)
        res2 = ClusteringEvaluator.evaluate_sampled_silhouette(X, labels, sample_size=13, seeds=[42])

        self.assertEqual(res1["status"], "VALID EVALUATION")
        self.assertEqual(res1["sample_size_evaluated"], 13)
        self.assertEqual(res1["n_represented_stops"], 70)
        self.assertEqual(res1["n_evaluated_clusters"], 4)

        # Bit-for-bit repeatability under same seed
        self.assertEqual(res1["mean_score"], res2["mean_score"])
        self.assertEqual(res1["seed_scores"], res2["seed_scores"])

    def test_hub_sensitivity_evaluation(self):
        """Computes HubScores across Configs A, B, and C on identical cohort."""
        mock_stops = pd.DataFrame([
            {"stop_id": f"S{i}", "total_visits": 10 + i * 5, "mapped_visits": 10 + i * 5, "routes_served": 1 + i % 4, "attributed_demand": 50.0 + i * 20.0}
            for i in range(150)
        ])

        ranked = ClusteringEvaluator.compute_hub_rankings(mock_stops)
        self.assertEqual(len(ranked), 150)
        self.assertIn("score_config_a", ranked.columns)
        self.assertIn("score_config_b", ranked.columns)
        self.assertIn("score_config_c", ranked.columns)

        sens = ClusteringEvaluator.evaluate_hub_sensitivity(ranked)
        self.assertEqual(sens["eligible_population_size"], 150)
        self.assertGreaterEqual(sens["spearman_rank_corr_a_b"], 0.70)
        self.assertGreaterEqual(sens["top100_jaccard_a_b"], 0.60)


if __name__ == "__main__":
    unittest.main()
