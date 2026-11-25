#!/usr/bin/env python3
"""
Unit tests for AI_RouteRanker Route Identifier Mapper.
Tests mapping accuracy, route string preservation, match status categorization,
and ambiguity handling across snapshots.
Complies with Milestone 3.1 specifications.
"""

import os
import sys
import unittest
import duckdb

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from analytics.preprocessing.route_mapper import RouteIdentifierMapper


class TestRouteMapping(unittest.TestCase):
    """Test suite for RouteIdentifierMapper cross-matching ridership and GTFS."""

    @classmethod
    def setUpClass(cls):
        cls.db_path = os.path.join("data", "processed", "ai_routeranker.duckdb")
        cls.con = duckdb.connect(cls.db_path, read_only=True)
        cls.mapper = RouteIdentifierMapper(cls.con)
        cls.mapping_df = cls.con.execute("SELECT * FROM analytical.route_mapping").df()

    @classmethod
    def tearDownClass(cls):
        if cls.con:
            cls.con.close()

    def test_total_route_snapshot_grid_size(self):
        """Verify 188 ridership routes across 8 snapshots yield 1,504 rows."""
        self.assertEqual(len(self.mapping_df), 1504)

    def test_zero_ambiguous_matches(self):
        """Verify no routes matched ambiguously to multiple candidates."""
        ambiguous = self.mapping_df[self.mapping_df["match_status"] == "ambiguous"]
        self.assertEqual(len(ambiguous), 0, f"Found unexpected ambiguous matches: {ambiguous}")

    def test_major_routes_are_exact_matches(self):
        """Verify core Chicago routes like 79, 9, 4, X4, 1 are exact matches."""
        core_routes = ["1", "4", "9", "79", "X4"]
        for r in core_routes:
            sub = self.mapping_df[self.mapping_df["ridership_route"] == r]
            if len(sub) > 0:
                # In at least one snapshot it should be exact match if active
                exact_count = len(sub[sub["match_status"] == "exact_match"])
                self.assertGreater(exact_count, 0, f"Route {r} should have exact matches!")

    def test_route_string_format_preserved(self):
        """Verify route codes are string objects and not converted to integer."""
        sample_routes = self.mapping_df["ridership_route"].tolist()
        self.assertTrue(all(isinstance(r, str) for r in sample_routes))


if __name__ == "__main__":
    unittest.main()
