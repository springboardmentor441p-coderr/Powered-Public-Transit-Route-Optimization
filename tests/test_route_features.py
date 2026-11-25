#!/usr/bin/env python3
"""
Unit tests for AI_RouteRanker Route Feature Engineering.
Tests expanding historical calculations and verifies strict leakage prevention.
Complies with Milestone 4 specifications.
"""

import os
import sys
import unittest
import duckdb

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class TestRouteFeatures(unittest.TestCase):
    """Test suite for route historical expanding features and leakage prevention."""

    @classmethod
    def setUpClass(cls):
        cls.parquet_path = os.path.join("data", "processed", "features", "route_features.parquet")
        cls.con = duckdb.connect()

    @classmethod
    def tearDownClass(cls):
        if cls.con:
            cls.con.close()

    def test_total_row_count(self):
        """Verify route_features contains exactly 1,124,170 rows."""
        count = self.con.execute(f"SELECT count(*) FROM '{self.parquet_path}'").fetchone()[0]
        self.assertEqual(count, 1124170)

    def test_first_observation_is_null_for_expanding_stats(self):
        """Verify expanding mean/std are NULL on initial route observation (leakage prevention)."""
        first_obs = self.con.execute(f"""
            WITH ranked AS (
                SELECT 
                    route,
                    row_number() OVER (PARTITION BY route ORDER BY date ASC) AS rn,
                    historical_mean_rides,
                    route_observation_count
                FROM '{self.parquet_path}'
            )
            SELECT count(*) 
            FROM ranked 
            WHERE rn = 1 AND (historical_mean_rides IS NOT NULL OR route_observation_count != 0);
        """).fetchone()[0]
        self.assertEqual(first_obs, 0, "Initial route observation has non-null expanding mean (leakage)!")

    def test_route_observation_count_strictly_increasing(self):
        """Verify route_observation_count increments monotonically with each service day."""
        violations = self.con.execute(f"""
            WITH deltas AS (
                SELECT 
                    route,
                    route_observation_count,
                    lag(route_observation_count, 1) OVER (PARTITION BY route ORDER BY date ASC) AS prev_cnt
                FROM '{self.parquet_path}'
            )
            SELECT count(*) 
            FROM deltas 
            WHERE prev_cnt IS NOT NULL AND route_observation_count != prev_cnt + 1;
        """).fetchone()[0]
        self.assertEqual(violations, 0, "Route observation count did not increment monotonically by 1!")


if __name__ == "__main__":
    unittest.main()
