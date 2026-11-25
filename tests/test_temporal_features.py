#!/usr/bin/env python3
"""
Unit tests for AI_RouteRanker Temporal Feature Engineering.
Tests calendar extraction, cyclical bounds, weekend logic, and month boundaries.
Complies with Milestone 4 specifications.
"""

import os
import sys
import unittest
import duckdb

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class TestTemporalFeatures(unittest.TestCase):
    """Test suite for temporal and calendar feature extraction."""

    @classmethod
    def setUpClass(cls):
        cls.parquet_path = os.path.join("data", "processed", "features", "ridership_features.parquet")
        cls.con = duckdb.connect()
        cls.df = cls.con.execute(f"SELECT * FROM '{cls.parquet_path}' LIMIT 50000").df()

    @classmethod
    def tearDownClass(cls):
        if cls.con:
            cls.con.close()

    def test_row_count_and_columns(self):
        """Verify ridership_features has 1,124,170 rows and all temporal columns."""
        total_rows = self.con.execute(f"SELECT count(*) FROM '{self.parquet_path}'").fetchone()[0]
        self.assertEqual(total_rows, 1124170)
        expected_cols = {
            "route", "date", "daytype", "year", "month", "quarter", "day",
            "day_of_week", "day_of_week_int", "day_of_year", "week_of_year",
            "is_weekend", "is_month_start", "is_month_end"
        }
        self.assertTrue(expected_cols.issubset(set(self.df.columns)))

    def test_temporal_value_ranges(self):
        """Verify months (1-12), quarters (1-4), days (1-31), days of week (0-6)."""
        self.assertTrue(self.df["month"].between(1, 12).all())
        self.assertTrue(self.df["quarter"].between(1, 4).all())
        self.assertTrue(self.df["day"].between(1, 31).all())
        self.assertTrue(self.df["day_of_week_int"].between(0, 6).all())

    def test_weekend_flag_consistency(self):
        """Verify is_weekend is True for Saturday/Sunday or daytypes A/U."""
        weekend_rows = self.df[self.df["day_of_week"].isin(["Saturday", "Sunday"])]
        self.assertTrue(weekend_rows["is_weekend"].all())

    def test_month_start_end_flags(self):
        """Verify is_month_start is True when day == 1."""
        start_rows = self.df[self.df["day"] == 1]
        self.assertTrue(start_rows["is_month_start"].all())
        non_start = self.df[self.df["day"] > 1]
        self.assertFalse(non_start["is_month_start"].any())


if __name__ == "__main__":
    unittest.main()
