#!/usr/bin/env python3
"""
Unit tests for AI_RouteRanker Service Feature Engineering.
Tests GTFS supply features, null preservation for pre-GTFS dates,
and schedule coverage status flags.
Complies with Milestone 4 specifications.
"""

import os
import sys
import unittest
import duckdb

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class TestServiceFeatures(unittest.TestCase):
    """Test suite for GTFS service features and missing value preservation."""

    @classmethod
    def setUpClass(cls):
        cls.parquet_path = os.path.join("data", "processed", "features", "service_features.parquet")
        cls.con = duckdb.connect()

    @classmethod
    def tearDownClass(cls):
        if cls.con:
            cls.con.close()

    def test_total_row_count(self):
        """Verify service_features contains 1,124,170 rows."""
        count = self.con.execute(f"SELECT count(*) FROM '{self.parquet_path}'").fetchone()[0]
        self.assertEqual(count, 1124170)

    def test_pre_gtfs_dates_remain_null(self):
        """Verify dates prior to 2025-11-23 have strictly NULL supply features (never false 0)."""
        pre_gtfs_non_nulls = self.con.execute(f"""
            SELECT count(*) 
            FROM '{self.parquet_path}'
            WHERE date < '2025-11-23' 
              AND (scheduled_trips_count IS NOT NULL OR snapshot_id IS NOT NULL);
        """).fetchone()[0]
        self.assertEqual(pre_gtfs_non_nulls, 0, "Pre-GTFS records were falsely imputed with supply data!")

    def test_gtfs_coverage_records_are_populated(self):
        """Verify exactly 28,798 records within GTFS coverage period have snapshot_id."""
        coverage_count = self.con.execute(f"""
            SELECT count(*) 
            FROM '{self.parquet_path}' 
            WHERE snapshot_id IS NOT NULL;
        """).fetchone()[0]
        self.assertEqual(coverage_count, 28798)

    def test_service_span_hours_non_negative(self):
        """Verify non-null service span hours are strictly positive."""
        invalid_spans = self.con.execute(f"""
            SELECT count(*) 
            FROM '{self.parquet_path}' 
            WHERE service_span_hours IS NOT NULL AND service_span_hours <= 0;
        """).fetchone()[0]
        self.assertEqual(invalid_spans, 0, "Found zero or negative service span hours!")


if __name__ == "__main__":
    unittest.main()
