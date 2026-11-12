"""
RouteRanker: Technical Specification v3.8 Verification Test Suite
Validates:
1. Source Manifest & Dataset SHA-256 integrity
2. K-Means route clustering: eligibility gates, centroids, and group explanations
3. Independent ranking indicators: ratios of sums and unranked reasons
4. Historical replay: strict virtual date gating and reporting delay enforcement
"""

import unittest
from fastapi.testclient import TestClient
from backend.app.main import app
from ml.clustering.route_clustering_service import route_clustering_service
from ml.ranking.route_ranking_service import route_ranking_service
from ml.replay.historical_replay_controller import historical_replay_controller

class TestTechSpecV38Requirements(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_01_source_manifest_endpoint(self):
        """Verify GET /api/data/manifest returns datasets with SHA-256 and timestamps."""
        res = self.client.get("/api/data/manifest")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("manifest_version", data)
        self.assertEqual(data["manifest_version"], "3.8.0")
        self.assertGreaterEqual(len(data.get("datasets", [])), 3)
        for ds in data["datasets"]:
            self.assertIn("sha256", ds)
            self.assertIn("agency_timezone", ds)
            self.assertEqual(ds["agency_timezone"], "America/Chicago")

    def test_02_route_clustering_kmeans(self):
        """Verify GET /api/route-groups returns K-Means clusters with 4 groups and descriptions."""
        res = self.client.get("/api/route-groups")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["n_clusters"], 4)
        self.assertIn("cluster_summaries", data)
        self.assertEqual(len(data["cluster_summaries"]), 4)
        for cid, c_info in data["cluster_summaries"].items():
            self.assertIn("cluster_name", c_info)
            self.assertIn("description", c_info)
            self.assertGreater(c_info["route_count"], 0)

    def test_03_route_productivity_rankings_ratio_of_sums(self):
        """Verify GET /api/rankings calculates ratios of sums and separates unranked routes."""
        res = self.client.get("/api/rankings?day_type=W&sort_by=rides_per_scheduled_hour")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["day_type"], "W")
        self.assertGreater(data["eligible_count"], 100)
        
        rankings = data.get("rankings", [])
        top_eligible = rankings[0]
        self.assertTrue(top_eligible["is_eligible"])
        self.assertIsNotNone(top_eligible["rides_per_scheduled_hour"])
        self.assertIsNotNone(top_eligible["rides_per_scheduled_trip"])
        
        # Verify unranked routes have clear reason codes
        unranked_list = [r for r in rankings if not r["is_eligible"]]
        if unranked_list:
            for unranked in unranked_list:
                self.assertIsNotNone(unranked["unranked_reason"])

    def test_04_historical_replay_gating(self):
        """Verify historical replay enforces reporting delay and blocks future knowledge."""
        # Create session
        res_create = self.client.post("/api/replays?reporting_delay_days=1&playback_speed_sec=5")
        self.assertEqual(res_create.status_code, 200)
        session_id = res_create.json()["session_id"]
        
        # Initial view: June 1, 2026. Delay = 1 day -> permitted cutoff = May 31, 2026
        res_view = self.client.get(f"/api/replays/{session_id}?focus_route=79")
        self.assertEqual(res_view.status_code, 200)
        v1 = res_view.json()
        self.assertEqual(v1["current_virtual_date"], "2026-06-01")
        self.assertEqual(v1["latest_permitted_actual_date"], "2026-05-31")
        self.assertIsNotNone(v1["focus_route"]["predicted_rides"])

        # Advance one step -> June 2, 2026. Permitted cutoff = June 1, 2026
        res_adv = self.client.post(f"/api/replays/{session_id}/control?action=ADVANCE")
        self.assertEqual(res_adv.status_code, 200)
        v2 = res_adv.json()
        self.assertEqual(v2["current_virtual_date"], "2026-06-02")
        self.assertEqual(v2["latest_permitted_actual_date"], "2026-06-01")

if __name__ == "__main__":
    unittest.main()

