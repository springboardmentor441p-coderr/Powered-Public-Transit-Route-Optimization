"""Dependency-free integration checks against an explicitly running API server.

Set ROUTERANKER_TEST_API_BASE_URL (for example, http://127.0.0.1:8001) to run.
These checks use the real processed MTC feed exposed by the configured server.
"""

from __future__ import annotations

import json
import os
import unittest
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_URL = os.getenv("ROUTERANKER_TEST_API_BASE_URL", "").rstrip("/")


@unittest.skipUnless(BASE_URL, "Set ROUTERANKER_TEST_API_BASE_URL to run live API integration tests")
class LiveApiIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            cls.get_json("/health")
        except (OSError, URLError) as exc:
            raise unittest.SkipTest(f"Configured API is not reachable: {exc}") from exc

    @classmethod
    def get_json(cls, path: str):
        with urlopen(f"{BASE_URL}{path}", timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    @classmethod
    def get_status(cls, path: str) -> tuple[int, dict]:
        try:
            with urlopen(f"{BASE_URL}{path}", timeout=30) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def test_openapi_and_actual_dataset_summary(self) -> None:
        spec = self.get_json("/openapi.json")
        required = {
            "/api/v1/routes", "/api/v1/routes/compare", "/api/v1/stops",
            "/api/v1/stops/{stop_id}/routes", "/api/v1/analytics/statistics",
            "/api/v1/analytics/scheduled-trips/by-hour", "/api/v1/ml/metrics",
        }
        self.assertTrue(required.issubset(spec["paths"]))
        statistics = self.get_json("/api/v1/analytics/statistics")
        totals = statistics["dataset_totals"]
        self.assertGreater(totals["route_records"], 0)
        self.assertGreater(totals["trip_records"], 0)
        self.assertGreater(totals["stop_time_records"], 0)
        self.assertIn("not passenger demand", statistics["interpretation"])
        self.assertFalse(statistics["limitations"]["shapes_available"])
        health = self.get_json("/health")
        self.assertEqual(health["status"], "ok")
        self.assertNotIn("data_directory", health)

    def test_route_search_filter_pagination_detail_features_and_assignments(self) -> None:
        page = self.get_json("/api/v1/routes?limit=3&offset=0")
        self.assertEqual(len(page["items"]), 3)
        self.assertGreater(page["total"], 3)
        route = page["items"][0]
        route_id = route["route_id"]
        self.assertIsInstance(route_id, str)
        q = urlencode({"q": route_id, "limit": 10, "offset": 0})
        found = self.get_json(f"/api/v1/routes?{q}")
        self.assertIn(route_id, {row["route_id"] for row in found["items"]})
        trip_count = route["trip_count"]
        filtered = self.get_json(f"/api/v1/routes?min_trips={trip_count}&limit=20")
        self.assertTrue(all(row["trip_count"] >= trip_count for row in filtered["items"]))
        detail = self.get_json(f"/api/v1/routes/{route_id}")
        features = self.get_json(f"/api/v1/routes/{route_id}/features")
        clusters = self.get_json(f"/api/v1/routes/{route_id}/clusters")
        self.assertEqual(detail["route_id"], features["route_id"])
        self.assertEqual(clusters["route_id"], route_id)
        self.assertIn("kmeans_cluster_id", clusters)
        self.assertIn("dbscan_cluster_id", clusters)

    def test_route_comparison_and_stop_route_relationship(self) -> None:
        routes = self.get_json("/api/v1/routes?limit=2")['items']
        ids = [row["route_id"] for row in routes]
        query = "&".join(f"route_ids={urlencode({'id': route_id})[3:]}" for route_id in ids)
        comparison = self.get_json(f"/api/v1/routes/compare?{query}")
        self.assertEqual(set(comparison["compared_route_ids"]), set(ids))
        self.assertEqual({row["route_id"] for row in comparison["routes"]}, set(ids))

        stops = self.get_json("/api/v1/stops?limit=5")
        self.assertEqual(len(stops["items"]), 5)
        stop = stops["items"][0]
        self.assertIsInstance(stop["stop_lat_value"], (int, float))
        serving = self.get_json(f"/api/v1/stops/{stop['stop_id']}/routes")
        self.assertEqual(len(serving), stop["route_count"])

    def test_analytics_and_saved_machine_learning_results(self) -> None:
        hourly = self.get_json("/api/v1/analytics/scheduled-trips/by-hour")
        self.assertTrue(hourly)
        self.assertTrue(all(isinstance(row["scheduled_trip_records"], int) for row in hourly))
        headway = self.get_json("/api/v1/analytics/headways")
        self.assertGreater(headway["groups_with_estimates"], 0)
        self.assertIn("scheduled first-stop", headway["note"])
        clusters = self.get_json("/api/v1/ml/clusters")
        metrics = self.get_json("/api/v1/ml/metrics")
        models = self.get_json("/api/v1/ml/models")
        self.assertTrue(any(row["algorithm"] == "KMeans" for row in clusters))
        self.assertTrue(any(row["algorithm"] == "DBSCAN" for row in clusters))
        self.assertTrue(any(row["algorithm"] == "KMeans" for row in metrics))
        self.assertTrue(any("refit" in row["new_route_behavior"].lower() for row in models if row["model"] == "dbscan"))

    def test_invalid_ids_filters_and_cors(self) -> None:
        status, body = self.get_status("/api/v1/routes/definitely-unknown-routeranker-id")
        self.assertEqual(status, 404)
        self.assertEqual(body["code"], "not_found")
        status, body = self.get_status("/api/v1/stops/definitely-unknown-routeranker-id")
        self.assertEqual(status, 404)
        status, _ = self.get_status("/api/v1/routes?limit=0")
        self.assertEqual(status, 422)
        request = Request(
            f"{BASE_URL}/health", method="OPTIONS",
            headers={"Origin": "http://127.0.0.1:5173", "Access-Control-Request-Method": "GET"},
        )
        with urlopen(request, timeout=10) as response:
            self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "http://127.0.0.1:5173")


if __name__ == "__main__":
    unittest.main()
