"""
AI_RouteRanker - Comprehensive Unit Tests for Phase 6.2 Route Clustering
Verifies:
  1. Route geometry validation, shape selection, bounds, sequence ordering, and downsampling.
  2. 100-meter buffer corridor overlap ratio (0.0 to 1.0, symmetry, degenerate handling).
  3. Discrete Fréchet distance (0.0 for identical, symmetry, empty trajectories, O(M) memory).
  4. Stop connectivity Jaccard similarity and shared consecutive stop sequences.
  5. Route operational feature calculation, departure-based AM headway, and service spans.
  6. Operational K-Means clustering across K in [3, 7], reproducibility, and silhouette evaluation.
  7. Hierarchical agglomerative corridor clustering on precomputed buffer and Fréchet distance matrices.
"""

import unittest
import numpy as np
import pandas as pd

from analytics.clustering.spatial_projection import SpatialProjector
from analytics.clustering.route_geometry import RouteGeometryExtractor
from analytics.clustering.route_similarity import RouteSimilarityEngine
from analytics.clustering.route_connectivity import RouteConnectivityAnalyzer
from analytics.clustering.route_features import RouteFeatureExtractor
from analytics.clustering.route_evaluator import RouteEvaluator
from analytics.clustering.route_experiment import RouteExperimentConfig, RouteExperimentOrchestrator


class TestRouteGeometry(unittest.TestCase):
    """Tests for RouteGeometryExtractor."""

    def setUp(self):
        self.extractor = RouteGeometryExtractor(target_downsample_dist=50.0)

    def test_representative_shape_selection_and_coverage(self):
        """Selects shape with highest trip count and calculates coverage."""
        trips = pd.DataFrame([
            {"route_id": "1", "direction_id": 0, "trip_id": "T1", "shape_id": "S1_A"},
            {"route_id": "1", "direction_id": 0, "trip_id": "T2", "shape_id": "S1_A"},
            {"route_id": "1", "direction_id": 0, "trip_id": "T3", "shape_id": "S1_B"},
            {"route_id": "1", "direction_id": 1, "trip_id": "T4", "shape_id": "S1_RET"},
            {"route_id": "999", "direction_id": 0, "trip_id": "T5", "shape_id": np.nan},  # Missing shape
        ])

        rep_df, exclusions_df = RouteGeometryExtractor.select_representative_shapes(trips)

        # Route 1 Dir 0: S1_A should win (2 trips out of 3 = 66.7%)
        r1_d0 = rep_df[(rep_df["route_id"] == "1") & (rep_df["direction_id"] == 0)].iloc[0]
        self.assertEqual(r1_d0["representative_shape_id"], "S1_A")
        self.assertEqual(r1_d0["trip_count"], 2)
        self.assertEqual(r1_d0["total_route_dir_trips"], 3)
        self.assertEqual(r1_d0["alternative_shapes_count"], 1)

        # Route 999: excluded with reason
        self.assertEqual(len(exclusions_df), 1)
        self.assertEqual(exclusions_df.iloc[0]["route_id"], "999")
        self.assertEqual(exclusions_df.iloc[0]["reason"], "NO_VALID_SHAPES_FOR_ACTIVE_TRIPS")

    def test_shape_sequence_ordering_and_projection(self):
        """Correctly orders shape points by sequence and projects to metric coordinates."""
        raw_points = pd.DataFrame([
            {"shape_pt_lat": 41.8834, "shape_pt_lon": -87.6246, "shape_pt_sequence": 2},
            {"shape_pt_lat": 41.8700, "shape_pt_lon": -87.6246, "shape_pt_sequence": 1},
            {"shape_pt_lat": 41.9000, "shape_pt_lon": -87.6246, "shape_pt_sequence": 3},
        ])

        coords, meta = self.extractor.process_and_project_shape(raw_points)
        self.assertEqual(meta["raw_point_count"], 3)
        # Sequence 1 should be the start point
        self.assertAlmostEqual(coords[0, 1], self.extractor.projector.forward(41.8700, -87.6246)[1], places=3)
        # Sequence 3 should be the end point
        self.assertAlmostEqual(coords[-1, 1], self.extractor.projector.forward(41.9000, -87.6246)[1], places=3)

    def test_duplicate_sequence_rejection(self):
        """Raises ValueError on duplicate shape_pt_sequence."""
        dup_points = pd.DataFrame([
            {"shape_pt_lat": 41.8700, "shape_pt_lon": -87.6246, "shape_pt_sequence": 1},
            {"shape_pt_lat": 41.8834, "shape_pt_lon": -87.6246, "shape_pt_sequence": 1},  # Duplicate sequence!
        ])
        with self.assertRaises(ValueError):
            self.extractor.process_and_project_shape(dup_points)

    def test_invalid_geographic_bounds_rejection(self):
        """Raises ValueError when coordinates exceed Chicago extents."""
        bad_points = pd.DataFrame([
            {"shape_pt_lat": 41.8700, "shape_pt_lon": -87.6246, "shape_pt_sequence": 1},
            {"shape_pt_lat": 45.0000, "shape_pt_lon": -87.6246, "shape_pt_sequence": 2},  # Far north out-of-bounds!
        ])
        with self.assertRaises(ValueError):
            self.extractor.process_and_project_shape(bad_points)

    def test_missing_required_columns_and_nans(self):
        """Raises ValueError if required columns are missing or contain NaNs."""
        missing_col_df = pd.DataFrame([
            {"shape_pt_lat": 41.8700, "shape_pt_sequence": 1}
        ])
        with self.assertRaises(ValueError):
            self.extractor.process_and_project_shape(missing_col_df)

        nan_df = pd.DataFrame([
            {"shape_pt_lat": 41.8700, "shape_pt_lon": np.nan, "shape_pt_sequence": 1},
            {"shape_pt_lat": 41.8800, "shape_pt_lon": -87.6246, "shape_pt_sequence": 2},
        ])
        with self.assertRaises(ValueError):
            self.extractor.process_and_project_shape(nan_df)

    def test_fewer_than_two_points_rejection(self):
        """Raises ValueError when fewer than 2 valid points exist."""
        single_pt = pd.DataFrame([
            {"shape_pt_lat": 41.8700, "shape_pt_lon": -87.6246, "shape_pt_sequence": 1}
        ])
        with self.assertRaises(ValueError):
            self.extractor.process_and_project_shape(single_pt)

    def test_downsample_endpoint_preservation(self):
        """Downsampled polyline strictly preserves the original start and end points."""
        line = np.array([
            [0.0, 0.0],
            [10.0, 0.0],
            [30.0, 0.0],
            [120.0, 0.0],
            [250.0, 0.0]
        ])
        down = RouteGeometryExtractor._downsample_polyline(line, target_spacing=50.0)
        np.testing.assert_allclose(down[0], line[0])
        np.testing.assert_allclose(down[-1], line[-1])
        self.assertLess(len(down), len(line) + 2)


class TestRouteSimilarity(unittest.TestCase):
    """Tests for RouteSimilarityEngine (Buffer overlap & Fréchet distance)."""

    def test_buffer_overlap_identical_geometries(self):
        """Identical geometries yield buffer overlap ratio exactly 1.0."""
        line = np.array([[0.0, 0.0], [500.0, 0.0], [1000.0, 0.0]])
        ov = RouteSimilarityEngine.compute_buffer_overlap(line, line, buffer_radius=100.0)
        self.assertAlmostEqual(ov, 1.0, places=5)

    def test_buffer_overlap_non_overlapping_geometries(self):
        """Parallel lines separated by 10,000 meters yield overlap ratio 0.0."""
        line_a = np.array([[0.0, 0.0], [1000.0, 0.0]])
        line_b = np.array([[0.0, 10000.0], [1000.0, 10000.0]])
        ov = RouteSimilarityEngine.compute_buffer_overlap(line_a, line_b, buffer_radius=100.0)
        self.assertEqual(ov, 0.0)

    def test_buffer_overlap_symmetry(self):
        """Buffer overlap is symmetric: Overlap(A, B) == Overlap(B, A)."""
        line_a = np.array([[0.0, 0.0], [1000.0, 0.0]])
        line_b = np.array([[0.0, 50.0], [1000.0, 50.0]])
        ov_ab = RouteSimilarityEngine.compute_buffer_overlap(line_a, line_b, buffer_radius=100.0)
        ov_ba = RouteSimilarityEngine.compute_buffer_overlap(line_b, line_a, buffer_radius=100.0)
        self.assertAlmostEqual(ov_ab, ov_ba, places=5)
        self.assertGreater(ov_ab, 0.0)
        self.assertLess(ov_ab, 1.0)

    def test_buffer_overlap_degenerate_and_bounds(self):
        """Geometries with fewer than 2 points return 0.0; overlap is strictly in [0.0, 1.0]."""
        single_pt = np.array([[0.0, 0.0]])
        valid_line = np.array([[0.0, 0.0], [500.0, 0.0]])
        self.assertEqual(RouteSimilarityEngine.compute_buffer_overlap(single_pt, valid_line), 0.0)
        self.assertEqual(RouteSimilarityEngine.compute_buffer_overlap(valid_line, single_pt), 0.0)

        # Bounds check
        ov = RouteSimilarityEngine.compute_buffer_overlap(valid_line, valid_line)
        self.assertGreaterEqual(ov, 0.0)
        self.assertLessEqual(ov, 1.0)

    def test_discrete_frechet_identical_geometries(self):
        """Identical polylines yield discrete Fréchet distance exactly 0.0."""
        line = np.array([[0.0, 0.0], [100.0, 50.0], [300.0, 100.0]])
        df = RouteSimilarityEngine.compute_discrete_frechet(line, line)
        self.assertAlmostEqual(df, 0.0, places=5)

    def test_discrete_frechet_known_parallel_distance(self):
        """Two parallel horizontal lines separated by 80 meters yield Fréchet distance 80.0 meters."""
        line_a = np.array([[0.0, 0.0], [500.0, 0.0], [1000.0, 0.0]])
        line_b = np.array([[0.0, 80.0], [500.0, 80.0], [1000.0, 80.0]])
        df = RouteSimilarityEngine.compute_discrete_frechet(line_a, line_b)
        self.assertAlmostEqual(df, 80.0, places=4)

    def test_discrete_frechet_symmetry(self):
        """Discrete Fréchet distance is strictly symmetric: d_F(A, B) == d_F(B, A)."""
        line_a = np.array([[0.0, 0.0], [200.0, 100.0]])
        line_b = np.array([[50.0, 30.0], [150.0, 80.0], [250.0, 120.0]])
        df_ab = RouteSimilarityEngine.compute_discrete_frechet(line_a, line_b)
        df_ba = RouteSimilarityEngine.compute_discrete_frechet(line_b, line_a)
        self.assertAlmostEqual(df_ab, df_ba, places=4)

    def test_discrete_frechet_empty_trajectories(self):
        """Empty trajectory returns infinity."""
        empty_line = np.empty((0, 2))
        valid_line = np.array([[0.0, 0.0], [100.0, 100.0]])
        self.assertEqual(RouteSimilarityEngine.compute_discrete_frechet(empty_line, valid_line), float("inf"))
        self.assertEqual(RouteSimilarityEngine.compute_discrete_frechet(valid_line, empty_line), float("inf"))

    def test_pairwise_similarity_matrices_properties(self):
        """Validates diagonal, symmetry, and dimensions of computed similarity matrices."""
        geoms = {
            "R1__dir_0": np.array([[0.0, 0.0], [1000.0, 0.0]]),
            "R2__dir_0": np.array([[0.0, 50.0], [1000.0, 50.0]]),
            "R3__dir_0": np.array([[0.0, 5000.0], [1000.0, 5000.0]]),
        }
        res = RouteSimilarityEngine.compute_pairwise_similarity_matrices(geoms)
        ov_mat = res["buffer_overlap_matrix"]
        b_dist_mat = res["buffer_distance_matrix"]
        f_dist_mat = res["frechet_distance_matrix"]

        # Check dimensions
        self.assertEqual(ov_mat.shape, (3, 3))
        self.assertEqual(f_dist_mat.shape, (3, 3))

        # Check diagonal
        np.testing.assert_allclose(np.diag(ov_mat), [1.0, 1.0, 1.0])
        np.testing.assert_allclose(np.diag(b_dist_mat), [0.0, 0.0, 0.0])
        np.testing.assert_allclose(np.diag(f_dist_mat), [0.0, 0.0, 0.0])

        # Check symmetry
        np.testing.assert_allclose(ov_mat, ov_mat.T)
        np.testing.assert_allclose(f_dist_mat, f_dist_mat.T)


class TestRouteConnectivity(unittest.TestCase):
    """Tests for RouteConnectivityAnalyzer."""

    def test_jaccard_similarity_identical_and_disjoint(self):
        """Identical stop sets yield Jaccard 1.0; disjoint sets yield Jaccard 0.0."""
        set_a = {"S1", "S2", "S3"}
        set_b = {"S1", "S2", "S3"}
        set_c = {"S4", "S5"}

        self.assertAlmostEqual(RouteConnectivityAnalyzer.compute_jaccard_similarity(set_a, set_b), 1.0)
        self.assertEqual(RouteConnectivityAnalyzer.compute_jaccard_similarity(set_a, set_c), 0.0)
        self.assertEqual(RouteConnectivityAnalyzer.compute_jaccard_similarity(set(), set_a), 0.0)

    def test_jaccard_similarity_empty_sets(self):
        """Empty stop sets return 0.0 without division by zero."""
        self.assertEqual(RouteConnectivityAnalyzer.compute_jaccard_similarity(set(), set()), 0.0)

    def test_pairwise_connectivity_matrix(self):
        """Validates Jaccard and shared-stop matrices."""
        stop_sets = {
            "R1": {"S1", "S2", "S3", "S4"},
            "R2": {"S3", "S4", "S5", "S6"},
        }
        res = RouteConnectivityAnalyzer.compute_pairwise_connectivity_matrix(stop_sets)
        jac = res["jaccard_similarity_matrix"]
        shared = res["shared_stops_matrix"]

        # Intersection is {S3, S4} (size 2), Union is {S1..S6} (size 6) -> 2/6 = 0.3333
        self.assertAlmostEqual(jac[0, 1], 2.0 / 6.0)
        self.assertAlmostEqual(jac[1, 0], 2.0 / 6.0)
        self.assertEqual(shared[0, 1], 2)
        self.assertEqual(shared[0, 0], 4)

    def test_extract_route_direction_stop_sequences(self):
        """Extracts ordered sequences selecting representative trips with most stops."""
        stop_times_df = pd.DataFrame([
            {"route_id": "1", "direction_id": 0, "trip_id": "T1", "stop_id": "S1", "stop_sequence": 1},
            {"route_id": "1", "direction_id": 0, "trip_id": "T1", "stop_id": "S2", "stop_sequence": 2},
            {"route_id": "1", "direction_id": 0, "trip_id": "T2", "stop_id": "S1", "stop_sequence": 1},
            {"route_id": "1", "direction_id": 0, "trip_id": "T2", "stop_id": "S2", "stop_sequence": 2},
            {"route_id": "1", "direction_id": 0, "trip_id": "T2", "stop_id": "S3", "stop_sequence": 3},
            {"route_id": "2", "direction_id": 1, "trip_id": "T3", "stop_id": "S10", "stop_sequence": 1},
        ])
        seqs = RouteConnectivityAnalyzer.extract_route_direction_stop_sequences(stop_times_df)
        self.assertEqual(seqs["1__dir_0"], ["S1", "S2", "S3"])
        self.assertEqual(seqs["2__dir_1"], ["S10"])

    def test_consecutive_stop_sequences_identical_and_partial(self):
        """Finds identical and partial contiguous shared stop sequences."""
        seqs = {
            "R1__dir_0": ["S1", "S2", "S3", "S4", "S5"],
            "R2__dir_0": ["S1", "S2", "S3", "S4", "S5"],
            "R3__dir_0": ["S0", "S2", "S3", "S4", "S9"],
        }
        res = RouteConnectivityAnalyzer.find_shared_consecutive_stop_sequences(seqs, min_sequence_length=2)

        # R1 and R2: full sequence of 5 stops
        r1_r2 = [r for r in res if r["pattern_a"] == "R1__dir_0" and r["pattern_b"] == "R2__dir_0"]
        self.assertEqual(len(r1_r2), 1)
        self.assertEqual(r1_r2[0]["shared_sequence"], ["S1", "S2", "S3", "S4", "S5"])
        self.assertEqual(r1_r2[0]["sequence_length"], 5)

        # R1 and R3: partial contiguous sequence S2 -> S3 -> S4
        r1_r3 = [r for r in res if r["pattern_a"] == "R1__dir_0" and r["pattern_b"] == "R3__dir_0"]
        self.assertEqual(len(r1_r3), 1)
        self.assertEqual(r1_r3[0]["shared_sequence"], ["S2", "S3", "S4"])
        self.assertEqual(r1_r3[0]["sequence_length"], 3)

    def test_consecutive_stop_sequences_different_order_and_gaps(self):
        """Gaps break contiguity; reverse sequences yield no forward matches."""
        seqs = {
            "R1__dir_0": ["S1", "S2", "S3", "S4"],
            "R2__dir_0": ["S1", "S3", "S4"],  # Gap: S2 missing, so S1 is separate, contiguous match is only S3->S4
            "R3__dir_0": ["S4", "S3", "S2", "S1"],  # Reverse order
        }
        res = RouteConnectivityAnalyzer.find_shared_consecutive_stop_sequences(seqs, min_sequence_length=2)

        r1_r2 = [r for r in res if r["pattern_a"] == "R1__dir_0" and r["pattern_b"] == "R2__dir_0"]
        self.assertEqual(len(r1_r2), 1)
        self.assertEqual(r1_r2[0]["shared_sequence"], ["S3", "S4"])

        r1_r3 = [r for r in res if r["pattern_a"] == "R1__dir_0" and r["pattern_b"] == "R3__dir_0"]
        self.assertEqual(len(r1_r3), 0)

    def test_consecutive_stop_sequences_empty_and_repeated_stops(self):
        """Handles repeated stop IDs (loops) and sequences below min_sequence_length gracefully."""
        seqs = {
            "R1__dir_0": ["S1", "S2", "S3", "S1", "S2"],
            "R2__dir_0": ["S1", "S2"],
            "R3__dir_0": ["S9"],  # Length 1 < 2
            "R4__dir_0": [],
        }
        res = RouteConnectivityAnalyzer.find_shared_consecutive_stop_sequences(seqs, min_sequence_length=2)

        # R1 and R2 match S1->S2
        r1_r2 = [r for r in res if r["pattern_a"] == "R1__dir_0" and r["pattern_b"] == "R2__dir_0"]
        self.assertEqual(len(r1_r2), 1)
        self.assertEqual(r1_r2[0]["shared_sequence"], ["S1", "S2"])

        # R3 and R4 have no pairs
        r3_matches = [r for r in res if "R3__dir_0" in (r["pattern_a"], r["pattern_b"])]
        self.assertEqual(len(r3_matches), 0)


class TestRouteFeatures(unittest.TestCase):
    """Tests for RouteFeatureExtractor."""

    def test_route_features_calculation_and_beyond_24h(self):
        """Computes trips, service span across midnight, AM headway, and preserves missing ridership as NaN."""
        routes_df = pd.DataFrame([
            {"route_id": "1", "route_short_name": "1", "route_type": 3},
            {"route_id": "Red", "route_short_name": "Red", "route_type": 1},  # Rail
        ])
        trips_df = pd.DataFrame([
            {"trip_id": "T1", "route_id": "1", "direction_id": 0},
            {"trip_id": "T2", "route_id": "1", "direction_id": 0},
            {"trip_id": "T3", "route_id": "Red", "direction_id": 0},
        ])
        stop_times_df = pd.DataFrame([
            # Route 1: Trip 1 at 07:00:00 (25200) and Trip 2 at 07:30:00 (27000) -> Headway = 30.0 min
            {"trip_id": "T1", "stop_id": "S1", "arrival_seconds": 25200, "departure_seconds": 25220},
            {"trip_id": "T2", "stop_id": "S1", "arrival_seconds": 27000, "departure_seconds": 27020},
            # Route Red: Overnight trip ending at 25:30:00 (91800s)
            {"trip_id": "T3", "stop_id": "S_RAIL", "arrival_seconds": 21600, "departure_seconds": 91800},
        ])
        route_lengths = {"1": 15.5, "Red": 35.2}

        # Ridership with only Route 1 mapped
        ridership_df = pd.DataFrame([
            {"route_id": "1", "mean_daily_rides": 5000.0}
        ])

        feat_df = RouteFeatureExtractor.compute_route_features(
            routes_df=routes_df,
            trips_df=trips_df,
            stop_times_df=stop_times_df,
            route_lengths_km=route_lengths,
            ridership_df=ridership_df,
        )

        # Route 1 checks
        r1 = feat_df[feat_df["route_id"] == "1"].iloc[0]
        self.assertEqual(r1["total_scheduled_trips"], 2)
        self.assertAlmostEqual(r1["am_peak_mean_headway_min"], 30.0)
        self.assertEqual(r1["is_rail"], False)
        self.assertEqual(r1["mean_daily_rides"], 5000.0)

        # Route Red checks: span = (91800 - 21600) / 3600 = 70200 / 3600 = 19.5 hours
        r_red = feat_df[feat_df["route_id"] == "Red"].iloc[0]
        self.assertEqual(r_red["is_rail"], True)
        self.assertAlmostEqual(r_red["service_span_hours"], 19.5)
        # Unmapped ridership must remain NaN, NOT converted to 0.0!
        self.assertTrue(pd.isna(r_red["mean_daily_rides"]))

    def test_am_headway_departures_vs_arrivals(self):
        """Verifies that headway strictly uses scheduled departure times, not arrival times."""
        routes_df = pd.DataFrame([{"route_id": "R1", "route_short_name": "R1", "route_type": 3}])
        trips_df = pd.DataFrame([
            {"trip_id": "T1", "route_id": "R1", "direction_id": 0},
            {"trip_id": "T2", "route_id": "R1", "direction_id": 0},
        ])
        # Arrivals are outside AM peak (24000s = 06:40, 24600s = 06:50), but departures are inside (25500s = 07:05, 26400s = 07:20)
        # Headway between departures is 26400 - 25500 = 900s = 15.0 min
        stop_times_df = pd.DataFrame([
            {"trip_id": "T1", "stop_id": "S1", "arrival_seconds": 24000, "departure_seconds": 25500},
            {"trip_id": "T2", "stop_id": "S1", "arrival_seconds": 24600, "departure_seconds": 26400},
        ])
        feat = RouteFeatureExtractor.compute_route_features(
            routes_df=routes_df, trips_df=trips_df, stop_times_df=stop_times_df,
            route_lengths_km={"R1": 10.0}
        )
        self.assertAlmostEqual(feat.iloc[0]["am_peak_mean_headway_min"], 15.0)

    def test_am_headway_exact_boundaries(self):
        """Tests exact boundary conditions: 25200 is included, 32400 is excluded [25200, 32400)."""
        routes_df = pd.DataFrame([{"route_id": "R1", "route_short_name": "R1", "route_type": 3}])
        trips_df = pd.DataFrame([
            {"trip_id": "T_PRE", "route_id": "R1", "direction_id": 0},
            {"trip_id": "T_START", "route_id": "R1", "direction_id": 0},
            {"trip_id": "T_END", "route_id": "R1", "direction_id": 0},
            {"trip_id": "T_POST", "route_id": "R1", "direction_id": 0},
        ])
        stop_times_df = pd.DataFrame([
            {"trip_id": "T_PRE", "stop_id": "S1", "arrival_seconds": 25199, "departure_seconds": 25199},   # 06:59:59 (Excluded)
            {"trip_id": "T_START", "stop_id": "S1", "arrival_seconds": 25200, "departure_seconds": 25200}, # 07:00:00 (Included)
            {"trip_id": "T_END", "stop_id": "S1", "arrival_seconds": 32399, "departure_seconds": 32399},   # 08:59:59 (Included)
            {"trip_id": "T_POST", "stop_id": "S1", "arrival_seconds": 32400, "departure_seconds": 32400},  # 09:00:00 (Excluded)
        ])
        feat = RouteFeatureExtractor.compute_route_features(
            routes_df=routes_df, trips_df=trips_df, stop_times_df=stop_times_df,
            route_lengths_km={"R1": 10.0}
        )
        # Included departures are 25200 and 32399 -> diff is 7199 seconds = 119.9833 minutes
        self.assertAlmostEqual(feat.iloc[0]["am_peak_mean_headway_min"], 7199.0 / 60.0, places=4)

    def test_am_headway_multi_service_date_isolation(self):
        """Cross-date 24-hour gaps must NOT be calculated as artificial multi-day headways."""
        routes_df = pd.DataFrame([{"route_id": "R1", "route_short_name": "R1", "route_type": 3}])
        trips_df = pd.DataFrame([
            {"trip_id": "T_DAY1", "route_id": "R1", "direction_id": 0, "service_date": "2026-05-01"},
            {"trip_id": "T_DAY2", "route_id": "R1", "direction_id": 0, "service_date": "2026-05-02"},
        ])
        # Each day has only 1 departure in the AM window. Cross-date interval would be 86400s = 1440 min!
        stop_times_df = pd.DataFrame([
            {"trip_id": "T_DAY1", "stop_id": "S1", "arrival_seconds": 26000, "departure_seconds": 26000},
            {"trip_id": "T_DAY2", "stop_id": "S1", "arrival_seconds": 26000, "departure_seconds": 26000},
        ])
        feat = RouteFeatureExtractor.compute_route_features(
            routes_df=routes_df, trips_df=trips_df, stop_times_df=stop_times_df,
            route_lengths_km={"R1": 10.0}
        )
        # Because each service_date has only 1 observation, headway cannot be formed -> NaN
        self.assertTrue(pd.isna(feat.iloc[0]["am_peak_mean_headway_min"]))

    def test_am_headway_different_directions_and_stops_isolation(self):
        """Stops and directions are strictly isolated when computing consecutive intervals."""
        routes_df = pd.DataFrame([{"route_id": "R1", "route_short_name": "R1", "route_type": 3}])
        trips_df = pd.DataFrame([
            {"trip_id": "T1", "route_id": "R1", "direction_id": 0},
            {"trip_id": "T2", "route_id": "R1", "direction_id": 1},
        ])
        # Same stop S1, but opposite directions: should not compute interval between them
        stop_times_df = pd.DataFrame([
            {"trip_id": "T1", "stop_id": "S1", "arrival_seconds": 26000, "departure_seconds": 26000},
            {"trip_id": "T2", "stop_id": "S1", "arrival_seconds": 26300, "departure_seconds": 26300},
        ])
        feat = RouteFeatureExtractor.compute_route_features(
            routes_df=routes_df, trips_df=trips_df, stop_times_df=stop_times_df,
            route_lengths_km={"R1": 10.0}
        )
        self.assertTrue(pd.isna(feat.iloc[0]["am_peak_mean_headway_min"]))

    def test_unmapped_ridership_remains_nan(self):
        """Unmapped ridership remains NaN and is excluded from KMeans predictors."""
        routes_df = pd.DataFrame([
            {"route_id": "R1", "route_short_name": "R1", "route_type": 3},
            {"route_id": "R2", "route_short_name": "R2", "route_type": 3},
        ])
        trips_df = pd.DataFrame([
            {"trip_id": "T1", "route_id": "R1", "direction_id": 0},
            {"trip_id": "T2", "route_id": "R2", "direction_id": 0},
        ])
        stop_times_df = pd.DataFrame([
            {"trip_id": "T1", "stop_id": "S1", "arrival_seconds": 26000, "departure_seconds": 26000},
            {"trip_id": "T2", "stop_id": "S2", "arrival_seconds": 26000, "departure_seconds": 26000},
        ])
        # Only R1 has ridership
        ridership_df = pd.DataFrame([{"route_id": "R1", "mean_daily_rides": 12000.0}])

        feat = RouteFeatureExtractor.compute_route_features(
            routes_df=routes_df, trips_df=trips_df, stop_times_df=stop_times_df,
            route_lengths_km={"R1": 10.0, "R2": 12.0},
            ridership_df=ridership_df,
        )
        self.assertEqual(feat[feat["route_id"] == "R1"]["mean_daily_rides"].iloc[0], 12000.0)
        self.assertTrue(pd.isna(feat[feat["route_id"] == "R2"]["mean_daily_rides"].iloc[0]))


class TestRouteEvaluator(unittest.TestCase):
    """Tests for RouteEvaluator (Operational KMeans & Hierarchical Corridor Clustering)."""

    def test_operational_kmeans_evaluation(self):
        """Fits KMeans across full candidate range K in [3, 4, 5, 6, 7] and verifies all assignments."""
        np.random.seed(42)
        mock_routes = pd.DataFrame({
            "route_id": [str(i) for i in range(25)],
            "route_type": [3] * 20 + [1] * 5,
            "log_scheduled_trips": np.random.uniform(2.0, 6.0, 25),
            "service_span_hours": np.random.uniform(14.0, 24.0, 25),
            "am_peak_mean_headway_min": np.random.uniform(6.0, 20.0, 25),
            "route_length_km": np.random.uniform(5.0, 40.0, 25),
            "unique_stops_count": np.random.uniform(20.0, 120.0, 25),
        })
        feature_cols = [
            "log_scheduled_trips", "service_span_hours", "am_peak_mean_headway_min",
            "route_length_km", "unique_stops_count"
        ]

        res = RouteEvaluator.evaluate_operational_kmeans(
            feature_df=mock_routes,
            feature_cols=feature_cols,
            k_values=[3, 4, 5, 6, 7],
            random_state=42,
            n_init=5
        )

        eval_summary = res["evaluation_summary"]
        self.assertEqual(len(eval_summary), 5)
        self.assertTrue((eval_summary["status"] == "VALID").all())
        self.assertTrue((eval_summary["silhouette"] > -1.0).all())

        # Verify all candidate results contain cluster summaries and route counts
        for k in [3, 4, 5, 6, 7]:
            cand = res["candidate_results"][k]
            self.assertEqual(len(cand["labels"]), 25)
            self.assertEqual(len(cand["cluster_summaries"]), k)
            total_assigned = sum(s["stop_count"] for s in cand["cluster_summaries"])
            self.assertEqual(total_assigned, 25)

    def test_operational_kmeans_degenerate_conditions(self):
        """Raises ValueError when N < max(K), and handles degenerate clusters."""
        few_routes = pd.DataFrame({
            "route_id": ["1", "2"],
            "log_scheduled_trips": [3.0, 4.0],
            "service_span_hours": [15.0, 16.0],
            "am_peak_mean_headway_min": [10.0, 12.0],
            "route_length_km": [10.0, 12.0],
            "unique_stops_count": [30.0, 35.0],
        })
        feature_cols = [
            "log_scheduled_trips", "service_span_hours", "am_peak_mean_headway_min",
            "route_length_km", "unique_stops_count"
        ]

        # N = 2 < max(K)=5 -> must raise ValueError
        with self.assertRaises(ValueError):
            RouteEvaluator.evaluate_operational_kmeans(
                feature_df=few_routes,
                feature_cols=feature_cols,
                k_values=[3, 4, 5]
            )

    def test_hierarchical_corridor_evaluation(self):
        """Evaluates Agglomerative Clustering on precomputed distance matrix."""
        dist_mat = np.array([
            [0.0, 0.1, 0.9, 0.9],
            [0.1, 0.0, 0.9, 0.9],
            [0.9, 0.9, 0.0, 0.1],
            [0.9, 0.9, 0.1, 0.0],
        ])
        pattern_ids = ["R1__0", "R2__0", "R3__0", "R4__0"]

        res = RouteEvaluator.evaluate_hierarchical_corridors(
            distance_matrix=dist_mat,
            pattern_ids=pattern_ids,
            k_values=[2]
        )

        cand_2 = res["candidate_results"][2]
        labels = cand_2["labels"]
        self.assertEqual(labels[0], labels[1])
        self.assertEqual(labels[2], labels[3])
        self.assertNotEqual(labels[0], labels[2])
        self.assertGreater(cand_2["silhouette"], 0.80)

    def test_hierarchical_clustering_k_boundaries_and_independent_matrices(self):
        """Tests hierarchical clustering separately on buffer distance and Fréchet distance."""
        # 6 patterns: 3 clusters of 2
        buf_dist = np.array([
            [0.0, 0.05, 0.8, 0.8, 0.9, 0.9],
            [0.05, 0.0, 0.8, 0.8, 0.9, 0.9],
            [0.8, 0.8, 0.0, 0.05, 0.9, 0.9],
            [0.8, 0.8, 0.05, 0.0, 0.9, 0.9],
            [0.9, 0.9, 0.9, 0.9, 0.0, 0.05],
            [0.9, 0.9, 0.9, 0.9, 0.05, 0.0],
        ])
        frechet_dist = buf_dist * 1000.0  # Scaled to meters
        pattern_ids = [f"P_{i}" for i in range(6)]

        # Evaluate buffer distance matrix
        res_buf = RouteEvaluator.evaluate_hierarchical_corridors(
            distance_matrix=buf_dist,
            pattern_ids=pattern_ids,
            k_values=[2, 3, 4]
        )
        self.assertEqual(len(res_buf["evaluation_summary"]), 3)
        self.assertTrue((res_buf["evaluation_summary"]["status"] == "VALID").all())
        # K=3 should achieve highest silhouette
        sil_k3_buf = res_buf["candidate_results"][3]["silhouette"]
        self.assertGreater(sil_k3_buf, 0.70)

        # Evaluate Fréchet distance matrix
        res_fre = RouteEvaluator.evaluate_hierarchical_corridors(
            distance_matrix=frechet_dist,
            pattern_ids=pattern_ids,
            k_values=[2, 3, 4]
        )
        self.assertEqual(len(res_fre["evaluation_summary"]), 3)
        self.assertTrue((res_fre["evaluation_summary"]["status"] == "VALID").all())


class TestRouteExperimentOrchestration(unittest.TestCase):
    """Tests for RouteExperimentOrchestrator configuration and memory guard."""

    def test_orchestration_config_manifest(self):
        """Generates valid experiment manifest without executing complete clustering."""
        orch = RouteExperimentOrchestrator()
        manifest = orch.generate_experiment_manifest()

        self.assertEqual(manifest["snapshot_id"], "mdb-389-202605300003")
        self.assertEqual(manifest["buffer_radius_meters"], 100.0)
        self.assertEqual(manifest["execution_status"], "STAGE_1_CONFIGURED_NOT_EXECUTED")
        self.assertIn("initial_memory_check", manifest)
        self.assertGreater(manifest["initial_memory_check"]["avail_phys_mb"], 0.0)


if __name__ == "__main__":
    unittest.main()
