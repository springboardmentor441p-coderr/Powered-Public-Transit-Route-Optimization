"""Comprehensive tests for Milestone 8 Stage 2A Historical Ridership API."""

import json
import os
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import duckdb
from fastapi.testclient import TestClient

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.api.v1.deps import get_duckdb_repository
from app.main import app
from app.repositories.duckdb_repository import DuckDBRepository


class TestCanonicalRidershipAPI(unittest.TestCase):
    """Integration tests against the canonical DuckDB analytical.daily_ridership table."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_valid_bus_route_monthly_and_daily(self):
        """Verify GET /api/v1/ridership/routes/151/timeseries for monthly and daily granularities."""
        resp_m = self.client.get(
            "/api/v1/ridership/routes/151/timeseries?start_date=2026-01-01&end_date=2026-08-31&granularity=monthly"
        )
        self.assertEqual(resp_m.status_code, 200)
        body_m = resp_m.json()
        self.assertEqual(body_m["route_id"], "151")
        self.assertFalse(body_m["is_rail"])
        self.assertTrue(body_m["ridership_available"])
        self.assertEqual(body_m["observation_count"], 8)
        self.assertEqual([d["period"] for d in body_m["data"]], sorted(d["period"] for d in body_m["data"]))
        self.assertIn("not onboard vehicle occupancy", body_m["methodology"]["metric_definition"])

        resp_d = self.client.get(
            "/api/v1/ridership/routes/151/timeseries?start_date=2026-08-01&end_date=2026-08-10&granularity=daily"
        )
        self.assertEqual(resp_d.status_code, 200)
        body_d = resp_d.json()
        self.assertEqual(body_d["observation_count"], 10)
        self.assertEqual(body_d["data"][0]["period"], "2026-08-01")
        self.assertEqual(body_d["data"][-1]["period"], "2026-08-10")

    def test_rail_route_unavailable_behavior(self):
        """Verify rail routes return ridership_available=False and empty data rather than 0."""
        resp = self.client.get("/api/v1/ridership/routes/Red/timeseries")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["route_id"], "Red")
        self.assertTrue(body["is_rail"])
        self.assertFalse(body["ridership_available"])
        self.assertIsNotNone(body["unavailable_reason"])
        self.assertEqual(body["observation_count"], 0)
        self.assertEqual(body["data"], [])

    def test_unknown_route_and_invalid_parameters(self):
        """Verify 404 for unknown route and 400 for invalid date ranges, bounds, or route IDs."""
        r404 = self.client.get("/api/v1/ridership/routes/NONEXISTENT999/timeseries")
        self.assertEqual(r404.status_code, 404)
        self.assertEqual(r404.json()["code"], "ROUTE_NOT_FOUND")

        r_bad_id = self.client.get("/api/v1/ridership/routes/bad.route/timeseries")
        self.assertEqual(r_bad_id.status_code, 400)
        self.assertEqual(r_bad_id.json()["code"], "INVALID_ROUTE_ID")

        r_bad_dates = self.client.get(
            "/api/v1/ridership/routes/151/timeseries?start_date=2026-08-10&end_date=2026-08-01"
        )
        self.assertEqual(r_bad_dates.status_code, 400)
        self.assertEqual(r_bad_dates.json()["code"], "INVALID_DATE_RANGE")

        r_too_large = self.client.get(
            "/api/v1/ridership/routes/151/timeseries?start_date=2024-01-01&end_date=2026-01-01&granularity=daily"
        )
        self.assertEqual(r_too_large.status_code, 400)
        self.assertEqual(r_too_large.json()["code"], "DATE_RANGE_TOO_LARGE")

        r_bad_gran = self.client.get("/api/v1/ridership/routes/151/timeseries?granularity=hourly")
        self.assertEqual(r_bad_gran.status_code, 400)
        self.assertEqual(r_bad_gran.json()["code"], "INVALID_GRANULARITY")

        r_bad_dt = self.client.get("/api/v1/ridership/routes/151/timeseries?daytype=X")
        self.assertEqual(r_bad_dt.status_code, 400)
        self.assertEqual(r_bad_dt.json()["code"], "INVALID_DAYTYPE")

    def test_empty_date_range_and_daytype_filtering(self):
        """Verify empty date range returns 0 observations and daytype filter works."""
        r_empty = self.client.get(
            "/api/v1/ridership/routes/151/timeseries?start_date=2027-01-01&end_date=2027-02-01"
        )
        self.assertEqual(r_empty.status_code, 200)
        self.assertTrue(r_empty.json()["ridership_available"])
        self.assertEqual(r_empty.json()["observation_count"], 0)
        self.assertIsNone(r_empty.json()["actual_date_range"])

        r_daytype = self.client.get(
            "/api/v1/ridership/routes/151/timeseries?start_date=2026-08-01&end_date=2026-08-31&daytype=W"
        )
        self.assertEqual(r_daytype.status_code, 200)
        obs = r_daytype.json()["data"][0]
        self.assertIsNotNone(obs["weekday_avg_rides"])
        self.assertIsNone(obs["saturday_avg_rides"])
        self.assertIsNone(obs["sunday_avg_rides"])

    def test_concurrent_ridership_requests(self):
        """Verify concurrent requests execute safely against read-only DuckDB."""
        num_threads = 8
        barrier = threading.Barrier(num_threads)

        def call_worker(idx: int):
            barrier.wait()
            route = "151" if idx % 2 == 0 else "79"
            r = self.client.get(
                f"/api/v1/ridership/routes/{route}/timeseries?start_date=2026-06-01&end_date=2026-08-31"
            )
            return (r.status_code, r.json()["route_id"], r.json()["observation_count"])

        with ThreadPoolExecutor(max_workers=num_threads) as pool:
            results = list(pool.map(call_worker, range(num_threads)))

        for idx, res in enumerate(results):
            expected_route = "151" if idx % 2 == 0 else "79"
            self.assertEqual(res, (200, expected_route, 3))


class TestSyntheticDuckDBAndFailureModes(unittest.TestCase):
    """Tests using synthetic DuckDB fixtures for zero-ridership, missing dates, and failure modes."""

    def setUp(self):
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_synthetic_zero_ridership_and_missing_dates(self):
        """Verify zero-ridership days are preserved as 0 and missing dates are not fabricated."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_file = Path(tmpdir) / "synthetic.duckdb"
            con = duckdb.connect(str(db_file))
            con.execute("CREATE SCHEMA analytical")
            con.execute(
                """
                CREATE TABLE analytical.daily_ridership (
                    route VARCHAR,
                    date DATE,
                    daytype VARCHAR,
                    rides BIGINT,
                    day_of_week VARCHAR,
                    day_of_week_int BIGINT,
                    is_weekend BOOLEAN
                )
                """
            )
            # Route 151 has a zero-ridership day on 2026-08-01, missing 2026-08-02, and 100 on 2026-08-03
            con.execute(
                """
                INSERT INTO analytical.daily_ridership VALUES
                ('151', '2026-08-01', 'A', 0, 'Saturday', 5, TRUE),
                ('151', '2026-08-03', 'W', 100, 'Monday', 0, FALSE)
                """
            )
            con.close()

            syn_repo = DuckDBRepository(duckdb_path=db_file)
            app.dependency_overrides[get_duckdb_repository] = lambda: syn_repo

            # Daily check: 2 observations (2026-08-02 omitted, not fabricated; 0 preserved)
            resp_d = self.client.get(
                "/api/v1/ridership/routes/151/timeseries?start_date=2026-08-01&end_date=2026-08-03&granularity=daily"
            )
            self.assertEqual(resp_d.status_code, 200)
            data_d = resp_d.json()["data"]
            self.assertEqual(len(data_d), 2)
            self.assertEqual(data_d[0]["period"], "2026-08-01")
            self.assertEqual(data_d[0]["rides"], 0)
            self.assertEqual(data_d[1]["period"], "2026-08-03")
            self.assertEqual(data_d[1]["rides"], 100)

            # Monthly check: saturday_avg_rides == 0.0 (preserved), sunday_avg_rides == None (null)
            resp_m = self.client.get(
                "/api/v1/ridership/routes/151/timeseries?start_date=2026-08-01&end_date=2026-08-31&granularity=monthly"
            )
            self.assertEqual(resp_m.status_code, 200)
            row_m = resp_m.json()["data"][0]
            self.assertEqual(row_m["saturday_avg_rides"], 0.0)
            self.assertIsNone(row_m["sunday_avg_rides"])
            self.assertEqual(row_m["total_rides"], 100)

            # Parameterized SQL safety check directly on repo
            rows_sqli = syn_repo.get_daily_ridership(
                route_id="151' OR '1'='1",
                start_date=date(2026, 8, 1),
                end_date=date(2026, 8, 31),
            )
            self.assertEqual(rows_sqli, [])

    def test_missing_duckdb_returns_503_safely(self):
        """Verify missing DuckDB file returns HTTP 503 without leaking local paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_repo = DuckDBRepository(duckdb_path=Path(tmpdir) / "missing.duckdb")
            app.dependency_overrides[get_duckdb_repository] = lambda: missing_repo

            resp = self.client.get("/api/v1/ridership/routes/151/timeseries")
            self.assertEqual(resp.status_code, 503)
            body = resp.json()
            self.assertEqual(body["code"], "DATABASE_UNAVAILABLE")
            self.assertNotIn(tmpdir, json.dumps(body))


if __name__ == "__main__":
    unittest.main()
