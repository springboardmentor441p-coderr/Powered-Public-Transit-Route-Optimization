"""Focused unit and integration tests for Milestone 8 Stage 1 API v1 endpoints."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.api.v1.deps import get_json_repository, get_parquet_repository
from app.main import app
from app.repositories.json_repository import JSONRepository
from app.repositories.parquet_repository import ParquetRepository


class TestCanonicalAPIv1(unittest.TestCase):
    """Integration tests against the canonical Phase 6.3 and Phase 7 artifacts."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_routes_list_pagination_and_filtering(self):
        """Verify GET /api/v1/routes pagination, mode filtering, search, and deterministic sorting."""
        resp = self.client.get("/api/v1/routes?limit=10&offset=0")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["pagination"]["total"], 133)
        self.assertEqual(body["pagination"]["returned"], 10)
        self.assertTrue(body["pagination"]["has_more"])

        # Filter rail
        rail_resp = self.client.get("/api/v1/routes?mode=rail")
        self.assertEqual(rail_resp.status_code, 200)
        self.assertEqual(rail_resp.json()["pagination"]["total"], 8)

        # Filter bus
        bus_resp = self.client.get("/api/v1/routes?mode=bus&limit=150")
        self.assertEqual(bus_resp.status_code, 200)
        self.assertEqual(bus_resp.json()["pagination"]["total"], 125)
        self.assertEqual(bus_resp.json()["pagination"]["returned"], 125)

        # Search
        search_resp = self.client.get("/api/v1/routes?search=Sheridan")
        self.assertEqual(search_resp.status_code, 200)
        ids = [item["route_id"] for item in search_resp.json()["data"]]
        self.assertIn("151", ids)

    def test_route_detail_bus_rail_and_missing_headway(self):
        """Verify GET /api/v1/routes/{route_id} for bus, rail, and specialized missing-headway routes."""
        # Bus route 151
        r151 = self.client.get("/api/v1/routes/151")
        self.assertEqual(r151.status_code, 200)
        d151 = r151.json()
        self.assertEqual(d151["route_id"], "151")
        self.assertFalse(d151["is_rail"])
        self.assertTrue(d151["demand"]["demand_metrics_available"])
        self.assertIsNotNone(d151["demand"]["forecasted_daily_demand"])

        # Rail route Red (demand metrics null, availability False)
        r_red = self.client.get("/api/v1/routes/Red")
        self.assertEqual(r_red.status_code, 200)
        d_red = r_red.json()
        self.assertTrue(d_red["is_rail"])
        self.assertFalse(d_red["demand"]["demand_metrics_available"])
        self.assertIsNone(d_red["demand"]["forecasted_daily_demand"])

        # Route 10 (missing AM headway -> JSON null, valid JSON)
        r10 = self.client.get("/api/v1/routes/10")
        self.assertEqual(r10.status_code, 200)
        d10 = json.loads(r10.text)
        self.assertIsNone(d10["operational"]["am_headway_min"])

    def test_rankings_bus_track1_canonical(self):
        """Verify GET /api/v1/rankings/bus returns 125 bus routes with Route 151 #1 and missing headway flags."""
        resp = self.client.get("/api/v1/rankings/bus?limit=125")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["track"], "BUS_PRIORITY")
        self.assertEqual(body["total_routes"], 125)
        self.assertEqual(len(body["data"]), 125)

        top1 = body["data"][0]
        self.assertEqual(top1["rank"], 1)
        self.assertEqual(top1["route_id"], "151")
        self.assertAlmostEqual(top1["overall_score"], 0.636319, places=5)

        # Verify Routes 10, 130, N5 have valid_weight_coverage == 0.9 and is_headway_missing == True
        by_id = {item["route_id"]: item for item in body["data"]}
        for rid in ["10", "130", "N5"]:
            self.assertIn(rid, by_id)
            self.assertTrue(by_id[rid]["is_headway_missing"])
            self.assertIsNone(by_id[rid]["am_headway_min"])
            self.assertAlmostEqual(by_id[rid]["valid_weight_coverage"], 0.9, places=4)
            self.assertIn("am_headway_min_norm", by_id[rid]["missing_criteria"])

    def test_rankings_rail_track2_canonical(self):
        """Verify GET /api/v1/rankings/rail returns 8 rail lines with 0.0 demand pillar."""
        resp = self.client.get("/api/v1/rankings/rail")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["track"], "RAIL_PRIORITY")
        self.assertEqual(body["total_routes"], 8)
        self.assertEqual(len(body["data"]), 8)
        self.assertEqual(body["data"][0]["route_id"], "Red")
        for item in body["data"]:
            self.assertTrue(item["is_rail"])
            self.assertEqual(item["pillars"]["demand_pressure"], 0.0)

    def test_rankings_unified_track3_canonical(self):
        """Verify GET /api/v1/rankings/unified returns 133 routes with Red #1 and Route 79 #2."""
        resp = self.client.get("/api/v1/rankings/unified?limit=150")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["track"], "UNIFIED_SUPPLY")
        self.assertEqual(body["total_routes"], 133)
        self.assertEqual(len(body["data"]), 133)
        self.assertEqual(body["data"][0]["route_id"], "Red")
        self.assertEqual(body["data"][1]["route_id"], "79")

        # Mode filter on unified track
        bus_only = self.client.get("/api/v1/rankings/unified?mode=bus&limit=150")
        self.assertEqual(bus_only.status_code, 200)
        self.assertEqual(bus_only.json()["pagination"]["total"], 125)

    def test_route_explanation_endpoint(self):
        """Verify GET /api/v1/rankings/routes/{route_id}/explanation for bus, rail, and Route 10."""
        r151 = self.client.get("/api/v1/rankings/routes/151/explanation")
        self.assertEqual(r151.status_code, 200)
        d151 = r151.json()
        self.assertEqual(d151["track"], "BUS_PRIORITY")
        self.assertEqual(d151["rank"], 1)
        self.assertEqual(d151["total_routes"], 125)
        self.assertFalse(d151["is_headway_missing"])
        self.assertTrue(len(d151["top_positive_drivers"]) > 0)

        r10 = self.client.get("/api/v1/rankings/routes/10/explanation")
        self.assertEqual(r10.status_code, 200)
        d10 = r10.json()
        self.assertTrue(d10["is_headway_missing"])
        self.assertAlmostEqual(d10["valid_weight_coverage"], 0.9, places=4)
        self.assertIsNone(d10["criterion_scores"]["am_headway_min_norm"])
        self.assertEqual(d10["effective_weights"]["am_headway_min_norm"], 0.0)

        r_red_uni = self.client.get("/api/v1/rankings/routes/Red/explanation?track=UNIFIED_SUPPLY")
        self.assertEqual(r_red_uni.status_code, 200)
        self.assertEqual(r_red_uni.json()["track"], "UNIFIED_SUPPLY")
        self.assertEqual(r_red_uni.json()["total_routes"], 133)

    def test_sensitivity_endpoint(self):
        """Verify GET /api/v1/rankings/sensitivity returns 60 scenarios and filters by track."""
        all_resp = self.client.get("/api/v1/rankings/sensitivity")
        self.assertEqual(all_resp.status_code, 200)
        self.assertEqual(all_resp.json()["total_scenarios"], 60)

        bus_resp = self.client.get("/api/v1/rankings/sensitivity?track=BUS_PRIORITY")
        self.assertEqual(bus_resp.status_code, 200)
        self.assertEqual(bus_resp.json()["total_scenarios"], 28)

    def test_invalid_parameters_and_unknown_routes(self):
        """Verify 400/404/422 RFC 7807 error responses and path traversal protection."""
        # Unknown route
        r404 = self.client.get("/api/v1/routes/NONEXISTENT999")
        self.assertEqual(r404.status_code, 404)
        self.assertEqual(r404.json()["code"], "ROUTE_NOT_FOUND")

        # Unknown explanation
        e404 = self.client.get("/api/v1/rankings/routes/NONEXISTENT999/explanation")
        self.assertEqual(e404.status_code, 404)
        self.assertEqual(e404.json()["code"], "EXPLANATION_NOT_FOUND")

        # Invalid sort field
        r400_sort = self.client.get("/api/v1/routes?sort_by=invalid_col")
        self.assertEqual(r400_sort.status_code, 400)
        self.assertEqual(r400_sort.json()["code"], "INVALID_SORT_FIELD")

        # Invalid rank range
        r400_rank = self.client.get("/api/v1/rankings/bus?min_rank=20&max_rank=10")
        self.assertEqual(r400_rank.status_code, 400)
        self.assertEqual(r400_rank.json()["code"], "INVALID_RANK_RANGE")

        # Invalid limit (> 150)
        r422 = self.client.get("/api/v1/routes?limit=500")
        self.assertEqual(r422.status_code, 422)
        self.assertEqual(r422.json()["code"], "VALIDATION_ERROR")

        # Invalid track
        r400_track = self.client.get("/api/v1/rankings/sensitivity?track=BOGUS")
        self.assertEqual(r400_track.status_code, 400)

        # Path traversal attempt in route_id
        r_trav = self.client.get("/api/v1/routes/..%2Fsecret")
        self.assertIn(r_trav.status_code, {400, 404})

    def test_deterministic_sorting(self):
        """Verify repeated ranking and route queries return identical deterministic orderings."""
        r1 = self.client.get("/api/v1/rankings/bus?sort_by=pillar_hub_score&order=desc&limit=25").json()
        r2 = self.client.get("/api/v1/rankings/bus?sort_by=pillar_hub_score&order=desc&limit=25").json()
        self.assertEqual(
            [x["route_id"] for x in r1["data"]],
            [x["route_id"] for x in r2["data"]],
        )

    def test_dataframe_immutability(self):
        """Verify cached DataFrames in ParquetRepository cannot be mutated in place."""
        repo = ParquetRepository()
        df = repo.get_feature_master()
        with self.assertRaises(ValueError):
            df["scheduled_trips"].values[0] = -999


class TestSyntheticAndFailureModes(unittest.TestCase):
    """Tests using synthetic fixtures for missing/corrupt artifacts and controlled data."""

    def setUp(self):
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_missing_artifact_returns_503_safely(self):
        """Verify missing Parquet or JSON artifacts return HTTP 503 without leaking filesystem paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_parquet = ParquetRepository(
                feature_master_path=Path(tmpdir) / "missing_features.parquet",
                rankings_master_path=Path(tmpdir) / "missing_rankings.parquet",
                sensitivity_path=Path(tmpdir) / "missing_sens.parquet",
            )
            missing_json = JSONRepository(
                explanations_path=Path(tmpdir) / "missing_expl.json",
            )
            app.dependency_overrides[get_parquet_repository] = lambda: missing_parquet
            app.dependency_overrides[get_json_repository] = lambda: missing_json

            resp = self.client.get("/api/v1/routes")
            self.assertEqual(resp.status_code, 503)
            body = resp.json()
            self.assertEqual(body["code"], "ARTIFACT_MISSING")
            self.assertNotIn(tmpdir, json.dumps(body))

            resp_expl = self.client.get("/api/v1/rankings/routes/1/explanation")
            self.assertEqual(resp_expl.status_code, 503)
            self.assertEqual(resp_expl.json()["code"], "ARTIFACT_MISSING")
            self.assertNotIn(tmpdir, json.dumps(resp_expl.json()))

    def test_corrupt_artifact_returns_503_safely(self):
        """Verify corrupt Parquet or JSON artifacts return HTTP 503 without leaking tracebacks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bad_parquet = Path(tmpdir) / "bad.parquet"
            bad_parquet.write_text("not a valid parquet file", encoding="utf-8")
            bad_json = Path(tmpdir) / "bad.json"
            bad_json.write_text("{invalid json", encoding="utf-8")

            corrupt_parquet_repo = ParquetRepository(
                feature_master_path=bad_parquet,
                rankings_master_path=bad_parquet,
                sensitivity_path=bad_parquet,
            )
            corrupt_json_repo = JSONRepository(explanations_path=bad_json)

            app.dependency_overrides[get_parquet_repository] = lambda: corrupt_parquet_repo
            app.dependency_overrides[get_json_repository] = lambda: corrupt_json_repo

            resp = self.client.get("/api/v1/routes")
            self.assertEqual(resp.status_code, 503)
            self.assertEqual(resp.json()["code"], "ARTIFACT_CORRUPT")

            resp_expl = self.client.get("/api/v1/rankings/routes/1/explanation")
            self.assertEqual(resp_expl.status_code, 503)
            self.assertEqual(resp_expl.json()["code"], "ARTIFACT_CORRUPT")

    def test_synthetic_fixture_nan_to_null_and_ranking(self):
        """Verify synthetic Parquet and JSON fixtures serve cleanly with NaN serialized as JSON null."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            feat_path = tmp / "features.parquet"
            rank_path = tmp / "rankings.parquet"
            sens_path = tmp / "sens.parquet"
            expl_path = tmp / "expl.json"

            df_feat = pd.DataFrame(
                {
                    "route_id": ["SYN1", "SYN_RAIL"],
                    "route_short_name": ["S1", "SR"],
                    "route_long_name": ["Synthetic Bus 1", "Synthetic Rail"],
                    "route_type": [3, 1],
                    "is_rail": [False, True],
                    "scheduled_trips": [100, 200],
                    "service_span_hours": [18.0, 24.0],
                    "am_headway_min": [np.nan, 5.0],
                    "route_length_km": [12.5, 20.0],
                    "unique_stops_count": [30, 15],
                    "operational_cluster_k3": [1.0, np.nan],
                    "operational_cluster_label": ["Trunk", np.nan],
                    "historical_mean_daily_rides": [5000.0, np.nan],
                    "forecasted_daily_demand": [5200.0, np.nan],
                    "rides_per_trip": [52.0, np.nan],
                    "hub_stop_count": [5, 10],
                    "hub_stop_ratio": [0.16, 0.66],
                    "hub_weighted_importance": [0.4, 0.8],
                    "max_corridor_overlap": [0.5, 0.3],
                    "mean_corridor_overlap": [0.2, 0.1],
                    "shared_consecutive_stop_count": [6, 4],
                    "corridor_duplication_ratio": [0.2, 0.25],
                    "regional_partition": ["North Chicago", "South Chicago"],
                    "load_intensity_factor": [1.1, np.nan],
                    "hub_connectivity_index": [0.3, 0.7],
                    "corridor_duplication_index": [0.4, 0.2],
                }
            )
            df_feat.to_parquet(feat_path, index=False)

            df_rank = pd.DataFrame(
                {
                    "route_id": ["SYN1"],
                    "route_short_name": ["S1"],
                    "route_long_name": ["Synthetic Bus 1"],
                    "route_type": [3],
                    "is_rail": [False],
                    "scheduled_trips": [100],
                    "service_span_hours": [18.0],
                    "am_headway_min": [np.nan],
                    "operational_cluster_label": ["Trunk"],
                    "regional_partition": ["North Chicago"],
                    "corridor_duplication_index": [0.4],
                    "track": ["BUS_PRIORITY"],
                    "profile": ["BALANCED_DEFAULT"],
                    "overall_score": [0.55],
                    "rank": [1],
                    "percentile_rank": [100.0],
                    "topsis_score": [0.60],
                    "topsis_rank": [1],
                    "pillar_demand_score": [0.20],
                    "pillar_service_score": [0.10],
                    "pillar_hub_score": [0.15],
                    "pillar_corridor_score": [0.10],
                    "contrib_forecasted_daily_demand": [0.10],
                    "contrib_load_intensity_factor": [0.10],
                    "contrib_scheduled_trips": [0.05],
                    "contrib_service_span_hours": [0.05],
                    "contrib_am_headway_min": [0.0],
                    "contrib_hub_stop_ratio": [0.15],
                    "contrib_corridor_duplication_index": [0.10],
                }
            )
            df_rank.to_parquet(rank_path, index=False)

            df_sens = pd.DataFrame(
                {
                    "scenario_id": ["test_scen"],
                    "target_criterion": ["forecasted_daily_demand_norm"],
                    "delta": [0.10],
                    "spearman_rho": [1.0],
                    "mean_absolute_rank_shift": [0.0],
                    "max_rank_shift": [0],
                    "top_10_overlap": [1.0],
                    "top_20_overlap": [1.0],
                    "track": ["BUS_PRIORITY"],
                }
            )
            df_sens.to_parquet(sens_path, index=False)

            expl_payload = {
                "track_bus_priority": [
                    {
                        "route_id": "SYN1",
                        "route_short_name": "S1",
                        "route_long_name": "Synthetic Bus 1",
                        "is_rail": False,
                        "operational_cluster_label": "Trunk",
                        "regional_partition": "North Chicago",
                        "track": "BUS_PRIORITY",
                        "profile": "BALANCED_DEFAULT",
                        "overall_score": 0.55,
                        "rank": 1,
                        "percentile_rank": 100.0,
                        "topsis_score": 0.60,
                        "topsis_rank": 1,
                        "pillars": {
                            "demand_pressure": 0.20,
                            "service_provision": 0.10,
                            "network_hubs": 0.15,
                            "corridor_structure": 0.10,
                        },
                        "criterion_scores": {"am_headway_min_norm": None},
                        "original_weights": {"am_headway_min_norm": 0.10, "hub_stop_ratio_norm": 0.90},
                        "effective_weights": {"am_headway_min_norm": 0.0, "hub_stop_ratio_norm": 1.0},
                        "contributions": {"am_headway_min_norm": 0.0, "hub_stop_ratio_norm": 0.15},
                        "missing_criteria": ["am_headway_min_norm"],
                        "top_positive_drivers": [],
                        "top_negative_drivers": [],
                        "narrative": "Synthetic test narrative.",
                    }
                ],
                "track_rail_priority": [],
                "track_unified_supply": [],
            }
            expl_path.write_text(json.dumps(expl_payload), encoding="utf-8")

            syn_parquet = ParquetRepository(
                feature_master_path=feat_path,
                rankings_master_path=rank_path,
                sensitivity_path=sens_path,
            )
            syn_json = JSONRepository(explanations_path=expl_path)
            app.dependency_overrides[get_parquet_repository] = lambda: syn_parquet
            app.dependency_overrides[get_json_repository] = lambda: syn_json

            r_list = self.client.get("/api/v1/routes")
            self.assertEqual(r_list.status_code, 200)
            self.assertEqual(r_list.json()["pagination"]["total"], 2)

            r_rail = self.client.get("/api/v1/routes/SYN_RAIL")
            self.assertEqual(r_rail.status_code, 200)
            self.assertIsNone(r_rail.json()["operational"]["operational_cluster_label"])
            self.assertFalse(r_rail.json()["demand"]["demand_metrics_available"])

            r_bus_rank = self.client.get("/api/v1/rankings/bus")
            self.assertEqual(r_bus_rank.status_code, 200)
            self.assertTrue(r_bus_rank.json()["data"][0]["is_headway_missing"])
            self.assertIsNone(r_bus_rank.json()["data"][0]["am_headway_min"])


if __name__ == "__main__":
    unittest.main()
