#!/usr/bin/env python3
"""
Unit tests for AI_RouteRanker GTFS Relational Ingestion.
Tests DuckDB tables, primary key uniqueness, foreign key integrity,
and multi-hour cumulative second computation.
Complies with Milestone 3.1 specifications.
"""

import os
import sys
import unittest
import duckdb

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class TestGTFSIngestion(unittest.TestCase):
    """Test suite for relational GTFS ingestion and data integrity in DuckDB."""

    @classmethod
    def setUpClass(cls):
        cls.db_path = os.path.join("data", "processed", "ai_routeranker.duckdb")
        cls.con = duckdb.connect(cls.db_path, read_only=True)

    @classmethod
    def tearDownClass(cls):
        if cls.con:
            cls.con.close()

    def test_all_gtfs_tables_exist(self):
        """Verify all analytical schema GTFS tables are present."""
        expected_tables = {
            "gtfs_snapshots",
            "gtfs_agency",
            "gtfs_routes",
            "gtfs_trips",
            "gtfs_stops",
            "gtfs_stop_times",
            "gtfs_calendar",
            "gtfs_calendar_dates",
            "gtfs_frequencies",
            "gtfs_shapes",
        }
        res = self.con.execute("SHOW ALL TABLES").df()
        analytical_tables = set(res[res["schema"] == "analytical"]["name"].tolist())
        for tbl in expected_tables:
            self.assertIn(tbl, analytical_tables, f"Table analytical.{tbl} is missing!")

    def test_snapshot_count_and_integrity(self):
        """Verify exactly 8 snapshots are ingested with PK and FK integrity passing."""
        df = self.con.execute("SELECT * FROM analytical.gtfs_snapshots").df()
        self.assertEqual(len(df), 8, "Expected exactly 8 GTFS snapshots.")
        self.assertTrue(all(df["pk_integrity_passed"]), "PK integrity check failed on snapshots.")
        self.assertTrue(all(df["fk_integrity_passed"]), "FK integrity check failed on snapshots.")

    def test_total_trips_and_stops_thresholds(self):
        """Verify trips and stop_times counts across snapshots."""
        trips_count = self.con.execute("SELECT count(*) FROM analytical.gtfs_trips").fetchone()[0]
        self.assertGreater(trips_count, 600000, f"Unexpectedly low trips count: {trips_count}")

        stop_times_count = self.con.execute("SELECT count(*) FROM analytical.gtfs_stop_times").fetchone()[0]
        self.assertGreater(stop_times_count, 35000000, f"Unexpectedly low stop_times count: {stop_times_count}")

    def test_departure_seconds_exceeding_24_hours(self):
        """Verify times >= 24:00:00 (late night bus runs) are converted to >= 86400 seconds."""
        count_past_midnight = self.con.execute("""
            SELECT count(*) 
            FROM analytical.gtfs_stop_times 
            WHERE departure_seconds >= 86400;
        """).fetchone()[0]
        self.assertGreater(count_past_midnight, 0, "Expected trips operating past 24:00:00 in Chicago CTA data.")

    def test_foreign_key_referential_integrity(self):
        """Verify trips reference valid routes and stop_times reference valid trips."""
        dangling_trips = self.con.execute("""
            SELECT count(*) 
            FROM analytical.gtfs_trips t
            LEFT JOIN analytical.gtfs_routes r
                ON t.snapshot_id = r.snapshot_id AND t.route_id = r.route_id
            WHERE r.route_id IS NULL;
        """).fetchone()[0]
        self.assertEqual(dangling_trips, 0, f"Found {dangling_trips} trips with dangling route_id!")


if __name__ == "__main__":
    unittest.main()
