#!/usr/bin/env python3
"""
Unit tests for AI_RouteRanker Demand & Interaction Features.
Tests lag shifts, rolling window exclusion, rides_per_scheduled_trip calculations,
and verifies model_ready_features.parquet consolidation.
Complies with Milestone 4 specifications.
"""

import os
import sys
import unittest
import duckdb

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class TestDemandFeatures(unittest.TestCase):
    """Test suite for demand lags, rolling windows, and model-ready feature consolidation."""

    @classmethod
    def setUpClass(cls):
        cls.demand_parquet = os.path.join("data", "processed", "features", "demand_service_features.parquet")
        cls.model_ready_parquet = os.path.join("data", "processed", "features", "model_ready_features.parquet")
        cls.con = duckdb.connect()

    @classmethod
    def tearDownClass(cls):
        if cls.con:
            cls.con.close()

    def test_row_counts_and_column_breadth(self):
        """Verify model_ready_features has 1,124,170 rows and 43 columns."""
        count = self.con.execute(f"SELECT count(*) FROM '{self.model_ready_parquet}'").fetchone()[0]
        self.assertEqual(count, 1124170)
        cols = self.con.execute(f"DESCRIBE SELECT * FROM '{self.model_ready_parquet}'").fetchall()
        self.assertEqual(len(cols), 43)

    def test_key_uniqueness(self):
        """Verify zero duplicate (route, date) keys in model_ready_features."""
        dups = self.con.execute(f"""
            SELECT count(*) FROM (
                SELECT route, date 
                FROM '{self.model_ready_parquet}' 
                GROUP BY route, date 
                HAVING count(*) > 1
            )
        """).fetchone()[0]
        self.assertEqual(dups, 0, "Found duplicate (route, date) keys in model_ready_features!")

    def test_lag_1_exact_match_to_previous_target(self):
        """Verify rides_lag_1 strictly matches prior chronological day's target_rides."""
        mismatches = self.con.execute(f"""
            WITH audit AS (
                SELECT 
                    route, date, target_rides, rides_lag_1,
                    lag(target_rides, 1) OVER (PARTITION BY route ORDER BY date ASC) AS prev_target
                FROM '{self.model_ready_parquet}'
            )
            SELECT count(*) 
            FROM audit 
            WHERE prev_target IS NOT NULL AND rides_lag_1 != prev_target;
        """).fetchone()[0]
        self.assertEqual(mismatches, 0, f"Found {mismatches} mismatched lag-1 values!")

    def test_rolling_mean_7_excludes_current_target(self):
        """Verify rolling_mean_7 on initial row is strictly NULL."""
        initial_non_nulls = self.con.execute(f"""
            WITH ranked AS (
                SELECT 
                    route, rolling_mean_7,
                    row_number() OVER (PARTITION BY route ORDER BY date ASC) AS rn
                FROM '{self.model_ready_parquet}'
            )
            SELECT count(*) 
            FROM ranked 
            WHERE rn = 1 AND rolling_mean_7 IS NOT NULL;
        """).fetchone()[0]
        self.assertEqual(initial_non_nulls, 0, "Rolling mean includes current observation (leakage)!")

    def test_rides_per_scheduled_trip_safety(self):
        """Verify rides_per_scheduled_trip is non-negative and finite."""
        invalid_ratios = self.con.execute(f"""
            SELECT count(*) 
            FROM '{self.model_ready_parquet}' 
            WHERE rides_per_scheduled_trip IS NOT NULL 
              AND (isinf(rides_per_scheduled_trip) OR isnan(rides_per_scheduled_trip) OR rides_per_scheduled_trip < 0);
        """).fetchone()[0]
        self.assertEqual(invalid_ratios, 0, "Found invalid / negative rides_per_scheduled_trip values!")


if __name__ == "__main__":
    unittest.main()
