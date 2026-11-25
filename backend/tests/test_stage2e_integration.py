"""Milestone 8 Stage 2E Cross-Stage Backend Integration Tests."""

import json
import os
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app


def _strict_json_loads(raw: str):
    def _reject_non_finite(val: str):
        raise ValueError(f"Non-finite JSON constant encountered: {val}")

    return json.loads(raw, parse_constant=_reject_non_finite)


class TestStage2ECrossStageIntegration(unittest.TestCase):
    """Cross-stage integration and invariant tests across Core, Stage 1, 2A, 2B, 2C, and 2D."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_openapi_schema_and_docs_availability(self):
        """Verify OpenAPI schema, Swagger UI, ReDoc, and exact 17 registered paths."""
        r_spec = self.client.get("/openapi.json")
        self.assertEqual(r_spec.status_code, 200)
        spec = _strict_json_loads(r_spec.text)
        expected_paths = {
            "/",
            "/api/health",
            "/api/v1/routes",
            "/api/v1/routes/{route_id}",
            "/api/v1/rankings/bus",
            "/api/v1/rankings/rail",
            "/api/v1/rankings/unified",
            "/api/v1/rankings/routes/{route_id}/explanation",
            "/api/v1/rankings/sensitivity",
            "/api/v1/ridership/routes/{route_id}/timeseries",
            "/api/v1/spatial/hubs/top",
            "/api/v1/spatial/hubs",
            "/api/v1/spatial/clusters/summary",
            "/api/v1/corridors/clusters",
            "/api/v1/corridors/routes/{route_id}/co-routing",
            "/api/v1/forecasting/historical",
            "/api/v1/forecasting/historical/summary",
        }
        self.assertEqual(set(spec["paths"].keys()), expected_paths)
        self.assertEqual(self.client.get("/docs").status_code, 200)
        self.assertEqual(self.client.get("/redoc").status_code, 200)

    def test_cross_stage_route_151_identity_and_reconciliation(self):
        """Verify Route 151 maintains consistent string identity across Stages 1, 2A, 2C, and 2D."""
        r_route = self.client.get("/api/v1/routes/151")
        self.assertEqual(r_route.status_code, 200)
        self.assertEqual(r_route.json()["route_id"], "151")
        self.assertFalse(r_route.json()["is_rail"])

        r_rank = self.client.get("/api/v1/rankings/bus?limit=1")
        self.assertEqual(r_rank.status_code, 200)
        self.assertEqual(r_rank.json()["data"][0]["route_id"], "151")

        r_exp = self.client.get("/api/v1/rankings/routes/151/explanation")
        self.assertEqual(r_exp.status_code, 200)
        self.assertEqual(r_exp.json()["route_id"], "151")

        r_ride = self.client.get("/api/v1/ridership/routes/151/timeseries?granularity=monthly")
        self.assertEqual(r_ride.status_code, 200)
        self.assertEqual(r_ride.json()["route_id"], "151")
        self.assertTrue(r_ride.json()["ridership_available"])

        r_corr = self.client.get("/api/v1/corridors/routes/151/co-routing")
        self.assertEqual(r_corr.status_code, 200)
        self.assertEqual(r_corr.json()["route_id"], "151")

        r_fc = self.client.get("/api/v1/forecasting/historical?tier=tier1&period=august_holdout&route_id=151&limit=5")
        self.assertEqual(r_fc.status_code, 200)
        self.assertGreater(r_fc.json()["total_records"], 0)
        self.assertTrue(all(x["route_id"] == "151" for x in r_fc.json()["data"]))

    def test_cross_stage_rail_red_identity_and_ridership_unavailable(self):
        """Verify Rail 'Red' identity and unavailable bus-only ridership handling."""
        r_route = self.client.get("/api/v1/routes/Red")
        self.assertEqual(r_route.status_code, 200)
        self.assertEqual(r_route.json()["route_id"], "Red")
        self.assertTrue(r_route.json()["is_rail"])

        r_ride = self.client.get("/api/v1/ridership/routes/Red/timeseries")
        self.assertEqual(r_ride.status_code, 200)
        self.assertFalse(r_ride.json()["ridership_available"])
        self.assertEqual(r_ride.json()["data"], [])

    def test_cross_stage_pagination_and_canonical_invariants(self):
        """Verify pagination bounds, non-overlapping adjacent pages, and Stage 2B/2C invariants."""
        p1 = self.client.get("/api/v1/routes?limit=10&offset=0").json()["data"]
        p2 = self.client.get("/api/v1/routes?limit=10&offset=10").json()["data"]
        ids1 = {x["route_id"] for x in p1}
        ids2 = {x["route_id"] for x in p2}
        self.assertTrue(ids1.isdisjoint(ids2))

        r_top = self.client.get("/api/v1/spatial/hubs/top?config=a&limit=100&offset=0")
        self.assertEqual(r_top.status_code, 200)
        self.assertEqual(r_top.json()["data"][-1]["stop_id"], "4732")

        r_fc = self.client.get("/api/v1/forecasting/historical?tier=tier1&period=august_holdout&limit=5")
        self.assertEqual(r_fc.status_code, 200)
        self.assertEqual(r_fc.json()["forecast_scope"], "historical_evaluation_only")
        self.assertFalse(r_fc.json()["future_forecasting_supported"])

        r_sum = self.client.get("/api/v1/forecasting/historical/summary")
        self.assertEqual(r_sum.status_code, 200)
        self.assertEqual(r_sum.json()["forecast_scope"], "historical_evaluation_only")
        self.assertFalse(r_sum.json()["future_forecasting_supported"])

    def test_cross_stage_security_and_strict_json_serialization(self):
        """Verify traversal/injection rejection and strict RFC-compliant JSON across all endpoints."""
        self.assertIn(self.client.get("/api/v1/routes/..%2F..%2Fetc%2Fpasswd").status_code, (400, 404))
        self.assertEqual(self.client.get("/api/v1/ridership/routes/151;DROP/timeseries").status_code, 400)
        self.assertEqual(self.client.get("/api/v1/routes?limit=151").status_code, 422)
        self.assertEqual(self.client.get("/api/v1/forecasting/historical?tier=tier2&period=august_holdout").status_code, 400)

        urls = [
            "/",
            "/api/health",
            "/api/v1/routes?limit=5",
            "/api/v1/rankings/unified?limit=5",
            "/api/v1/rankings/routes/151/explanation",
            "/api/v1/rankings/sensitivity",
            "/api/v1/ridership/routes/151/timeseries?granularity=monthly",
            "/api/v1/spatial/hubs/top?config=a&limit=5",
            "/api/v1/spatial/clusters/summary",
            "/api/v1/corridors/clusters?limit=5",
            "/api/v1/corridors/routes/151/co-routing",
            "/api/v1/forecasting/historical?tier=tier1&period=august_holdout&limit=5",
            "/api/v1/forecasting/historical/summary",
        ]
        for url in urls:
            with self.subTest(url=url):
                r = self.client.get(url)
                self.assertEqual(r.status_code, 200)
                _strict_json_loads(r.text)

    def test_cross_stage_concurrent_mixed_requests(self):
        """Verify 10 concurrent mixed cross-stage requests succeed with HTTP 200."""
        urls = [
            "/api/health",
            "/api/v1/routes?limit=10",
            "/api/v1/rankings/bus?limit=10",
            "/api/v1/rankings/rail?limit=8",
            "/api/v1/ridership/routes/151/timeseries?granularity=monthly",
            "/api/v1/spatial/hubs/top?config=a&limit=10",
            "/api/v1/spatial/clusters/summary",
            "/api/v1/corridors/clusters?limit=10",
            "/api/v1/corridors/routes/151/co-routing",
            "/api/v1/forecasting/historical/summary",
        ]
        with ThreadPoolExecutor(max_workers=10) as pool:
            statuses = list(pool.map(lambda u: self.client.get(u).status_code, urls))
        self.assertEqual(statuses, [200] * len(urls))


if __name__ == "__main__":
    unittest.main()
