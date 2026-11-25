"""Comprehensive tests for Milestone 8 Stage 2B Spatial Hub & DBSCAN Cluster APIs."""

import json
import os
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.api.v1.deps import get_spatial_repository
from app.main import app
from app.repositories.spatial_repository import SpatialRepository


class TestCanonicalSpatialAPI(unittest.TestCase):
    """Integration tests against the canonical Phase 6.1 spatial artifacts."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_top_100_hubs_ranking_and_pagination(self):
        """Verify GET /api/v1/spatial/hubs/top returns top-100 hubs with valid coordinates."""
        resp = self.client.get("/api/v1/spatial/hubs/top?config=a&limit=25&offset=0")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["config"], "a")
        self.assertEqual(body["total_top_hubs"], 100)
        self.assertEqual(body["pagination"]["returned"], 25)
        self.assertTrue(body["pagination"]["has_more"])
        top1 = body["data"][0]
        self.assertEqual(top1["rank"], 1)
        self.assertEqual(top1["stop_id"], "1106")
        self.assertTrue(top1["coordinates"]["coordinates_available"])
        self.assertIn("not actual stop-level", body["methodology"]["demand_proxy_note"])

        # Config b and c
        for cfg in ["b", "c"]:
            r_cfg = self.client.get(f"/api/v1/spatial/hubs/top?config={cfg}&limit=10")
            self.assertEqual(r_cfg.status_code, 200)
            self.assertEqual(r_cfg.json()["total_top_hubs"], 100)

    def test_top_100_config_a_exact_canonical_tie_breaking_and_pagination(self):
        """Verify config=a top-100 exactly matches top100_hubs_config_a.csv including Stop 4732 vs 17046."""
        csv_path = Path(__file__).resolve().parents[2] / "artifacts" / "clustering" / "top100_hubs_config_a.csv"
        df_csv = pd.read_csv(csv_path)
        expected_ids = [str(x).strip() for x in df_csv["stop_id"].tolist()]

        r_full = self.client.get("/api/v1/spatial/hubs/top?config=a&limit=100&offset=0")
        self.assertEqual(r_full.status_code, 200)
        actual_ids = [item["stop_id"] for item in r_full.json()["data"]]

        self.assertEqual(actual_ids, expected_ids)
        self.assertEqual(actual_ids[99], "4732")
        self.assertNotIn("17046", actual_ids)

        # Pagination slice preserves canonical order
        r_page = self.client.get("/api/v1/spatial/hubs/top?config=a&limit=25&offset=75")
        self.assertEqual(r_page.status_code, 200)
        page_ids = [item["stop_id"] for item in r_page.json()["data"]]
        self.assertEqual(page_ids, expected_ids[75:100])
        self.assertEqual(page_ids[-1], "4732")

    def test_spatial_hubs_dbscan_noise_and_bbox_filtering(self):
        """Verify GET /api/v1/spatial/hubs supports noise (-1), eligibility, and bbox filtering."""
        # All 11,020 stops
        r_all = self.client.get("/api/v1/spatial/hubs?limit=25")
        self.assertEqual(r_all.status_code, 200)
        self.assertEqual(r_all.json()["pagination"]["total"], 11020)

        # Noise points only (dbscan_cluster == -1 -> 18 stops)
        r_noise = self.client.get("/api/v1/spatial/hubs?dbscan_cluster=-1&limit=50")
        self.assertEqual(r_noise.status_code, 200)
        self.assertEqual(r_noise.json()["pagination"]["total"], 18)
        for item in r_noise.json()["data"]:
            self.assertEqual(item["dbscan_cluster"], -1)
            self.assertTrue(item["is_noise_point"])

        # Bounding box around Chicago Loop
        r_bbox = self.client.get(
            "/api/v1/spatial/hubs?min_lat=41.87&max_lat=41.89&min_lon=-87.64&max_lon=-87.62&limit=50"
        )
        self.assertEqual(r_bbox.status_code, 200)
        bbox_data = r_bbox.json()["data"]
        self.assertGreater(len(bbox_data), 0)
        for item in bbox_data:
            self.assertGreaterEqual(item["coordinates"]["lat"], 41.87)
            self.assertLessEqual(item["coordinates"]["lat"], 41.89)
            self.assertGreaterEqual(item["coordinates"]["lon"], -87.64)
            self.assertLessEqual(item["coordinates"]["lon"], -87.62)

    def test_invalid_bbox_and_params(self):
        """Verify invalid bounding boxes, configs, and sort fields return HTTP 400."""
        # Partial bbox
        r1 = self.client.get("/api/v1/spatial/hubs?min_lat=41.8&max_lat=41.9")
        self.assertEqual(r1.status_code, 400)
        self.assertEqual(r1.json()["code"], "INVALID_BBOX")

        # Inverted bbox
        r2 = self.client.get("/api/v1/spatial/hubs?min_lat=42.0&max_lat=41.0&min_lon=-88.0&max_lon=-87.0")
        self.assertEqual(r2.status_code, 400)
        self.assertEqual(r2.json()["code"], "INVALID_BBOX")

        # Out of range lat
        r3 = self.client.get("/api/v1/spatial/hubs?min_lat=-95.0&max_lat=41.0&min_lon=-88.0&max_lon=-87.0")
        self.assertEqual(r3.status_code, 400)

        # Invalid config
        r4 = self.client.get("/api/v1/spatial/hubs/top?config=z")
        self.assertEqual(r4.status_code, 400)
        self.assertEqual(r4.json()["code"], "INVALID_HUB_CONFIG")

    def test_clusters_summary_canonical(self):
        """Verify GET /api/v1/spatial/clusters/summary returns exact Phase 6.1 counts."""
        resp = self.client.get("/api/v1/spatial/clusters/summary")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["boarding_stops_input_count"], 11020)
        self.assertEqual(body["dbscan_cluster_count"], 117)
        self.assertEqual(body["dbscan_noise_stop_count"], 18)
        self.assertEqual(body["kmeans_eligible_stops_count"], 10583)

    def test_spatial_dataframe_immutability(self):
        """Verify cached spatial DataFrames cannot be mutated in place."""
        repo = SpatialRepository()
        df = repo.get_hub_rankings()
        with self.assertRaises(ValueError):
            df["total_visits"].values[0] = -1

    def test_concurrent_cold_start_spatial_repository(self):
        """Verify concurrent cold-start SpatialRepository calls initialize safely."""
        repo = SpatialRepository()
        num_threads = 10
        barrier = threading.Barrier(num_threads)

        def worker():
            barrier.wait()
            df = repo.get_spatial_stops_with_clusters()
            return len(df)

        with ThreadPoolExecutor(max_workers=num_threads) as pool:
            results = list(pool.map(lambda _: worker(), range(num_threads)))

        self.assertEqual(results, [11020] * num_threads)


class TestSyntheticSpatialAndFailureModes(unittest.TestCase):
    """Tests using synthetic spatial fixtures for missing coords, zero metrics, and missing/corrupt files."""

    def setUp(self):
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_synthetic_missing_coords_and_zero_metrics(self):
        """Verify NaN coordinates serialize as null with coordinates_available=False, and 0 metrics stay 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            hubs_p = tmp / "hubs.parquet"
            dbscan_p = tmp / "dbscan.parquet"
            meta_p = tmp / "meta.json"

            pd.DataFrame(
                {
                    "stop_id": ["S_ZERO", "S_NOCOORD"],
                    "stop_name": ["Zero Hub", "No Coord Hub"],
                    "stop_lat": [41.88, np.nan],
                    "stop_lon": [-87.63, np.nan],
                    "total_visits": [0, 10],
                    "routes_served": [1, 2],
                    "attributed_demand": [0.0, 50.0],
                    "demand_intensity": [0.0, 5.0],
                    "score_config_a": [0.0, 0.2],
                    "rank_config_a": [2, 1],
                    "score_config_b": [0.0, 0.2],
                    "rank_config_b": [2, 1],
                    "score_config_c": [0.0, 0.2],
                    "rank_config_c": [2, 1],
                }
            ).to_parquet(hubs_p, index=False)

            pd.DataFrame(
                {
                    "stop_id": ["S_ZERO", "S_NOCOORD", "S_INELIGIBLE"],
                    "stop_name": ["Zero Hub", "No Coord Hub", "Noise Stop"],
                    "stop_lat": [41.88, np.nan, 41.70],
                    "stop_lon": [-87.63, np.nan, -87.60],
                    "dbscan_cluster": [0, 1, -1],
                }
            ).to_parquet(dbscan_p, index=False)

            meta_p.write_text(
                json.dumps(
                    {
                        "snapshot_id": "test",
                        "representative_service_date": "2026-06-10",
                        "demand_attribution_period": "2026",
                        "boarding_stops_input_count": 3,
                        "active_stop_visits_count": 10,
                        "dbscan_parameters": {"eps_meters": 300.0},
                        "dbscan_cluster_count": 2,
                        "dbscan_noise_stop_count": 1,
                        "dbscan_chained_cluster_count": 0,
                        "kmeans_parameters": {"k": [3]},
                        "kmeans_eligible_stops_count": 2,
                        "hub_ranking_sensitivity": {},
                        "coverage_metrics": {},
                    }
                ),
                encoding="utf-8",
            )

            syn_repo = SpatialRepository(
                hub_rankings_path=hubs_p,
                dbscan_assignments_path=dbscan_p,
                metadata_path=meta_p,
            )
            app.dependency_overrides[get_spatial_repository] = lambda: syn_repo

            resp = self.client.get("/api/v1/spatial/hubs?limit=10")
            self.assertEqual(resp.status_code, 200)
            by_id = {x["stop_id"]: x for x in resp.json()["data"]}

            # Missing coordinates
            self.assertFalse(by_id["S_NOCOORD"]["coordinates"]["coordinates_available"])
            self.assertIsNone(by_id["S_NOCOORD"]["coordinates"]["lat"])

            # Zero-valued metrics preserved
            self.assertEqual(by_id["S_ZERO"]["total_visits"], 0)
            self.assertEqual(by_id["S_ZERO"]["attributed_demand_proxy"], 0.0)
            self.assertEqual(by_id["S_ZERO"]["hub_score"], 0.0)

            # Ineligible noise stop
            self.assertFalse(by_id["S_INELIGIBLE"]["hub_ranking_eligible"])
            self.assertTrue(by_id["S_INELIGIBLE"]["is_noise_point"])
            self.assertIsNone(by_id["S_INELIGIBLE"]["rank"])

    def test_missing_and_corrupt_spatial_artifacts_return_503(self):
        """Verify missing and corrupt spatial files return HTTP 503 without path leakage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            missing_repo = SpatialRepository(
                hub_rankings_path=tmp / "missing_hubs.parquet",
                dbscan_assignments_path=tmp / "missing_dbscan.parquet",
                metadata_path=tmp / "missing_meta.json",
            )
            app.dependency_overrides[get_spatial_repository] = lambda: missing_repo

            r1 = self.client.get("/api/v1/spatial/hubs/top")
            self.assertEqual(r1.status_code, 503)
            self.assertEqual(r1.json()["code"], "ARTIFACT_MISSING")
            self.assertNotIn(tmpdir, json.dumps(r1.json()))

            bad_json = tmp / "bad.json"
            bad_json.write_text("{corrupt", encoding="utf-8")
            corrupt_repo = SpatialRepository(
                hub_rankings_path=tmp / "missing_hubs.parquet",
                dbscan_assignments_path=tmp / "missing_dbscan.parquet",
                metadata_path=bad_json,
            )
            app.dependency_overrides[get_spatial_repository] = lambda: corrupt_repo
            r2 = self.client.get("/api/v1/spatial/clusters/summary")
            self.assertEqual(r2.status_code, 503)
            self.assertEqual(r2.json()["code"], "ARTIFACT_CORRUPT")


if __name__ == "__main__":
    unittest.main()
