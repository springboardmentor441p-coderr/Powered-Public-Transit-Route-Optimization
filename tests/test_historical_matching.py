#!/usr/bin/env python3
"""
Unit tests for AI_RouteRanker Historical Schedule Matching & Service Calendar.
Tests GTFSServiceCalendar logic, schedule matching completeness,
service span calculations, and quality categorization.
Complies with Milestone 3.1 specifications.
"""

import datetime
import os
import sys
import unittest
import duckdb

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from analytics.preprocessing.calendar_service import GTFSServiceCalendar


class TestCalendarService(unittest.TestCase):
    """Test unit suite for GTFSServiceCalendar exception and day rules."""

    def test_calendar_rules_and_exceptions(self):
        cal = GTFSServiceCalendar()
        service_id = "SVC_TEST"
        # Runs Mondays and Tuesdays between 2026-01-01 and 2026-01-31
        cal.add_calendar_rule(
            service_id=service_id,
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 1, 31),
            monday=1,
            tuesday=1,
            wednesday=0,
            thursday=0,
            friday=0,
            saturday=0,
            sunday=0,
        )

        # 2026-01-05 is a Monday -> should be active
        self.assertTrue(cal.is_service_active(service_id, datetime.date(2026, 1, 5)))
        # 2026-01-07 is a Wednesday -> should be inactive
        self.assertFalse(cal.is_service_active(service_id, datetime.date(2026, 1, 7)))

        # Add exception: Service added on Wednesday 2026-01-07 (type 1)
        cal.add_exception(service_id, datetime.date(2026, 1, 7), exception_type=1)
        self.assertTrue(cal.is_service_active(service_id, datetime.date(2026, 1, 7)))

        # Add exception: Service removed on Monday 2026-01-05 (type 2)
        cal.add_exception(service_id, datetime.date(2026, 1, 5), exception_type=2)
        self.assertFalse(cal.is_service_active(service_id, datetime.date(2026, 1, 5)))


class TestHistoricalScheduleMatching(unittest.TestCase):
    """Test suite for integrated historical schedule matching table in DuckDB."""

    @classmethod
    def setUpClass(cls):
        cls.db_path = os.path.join("data", "processed", "ai_routeranker.duckdb")
        cls.con = duckdb.connect(cls.db_path, read_only=True)
        cls.df = cls.con.execute("SELECT * FROM analytical.historical_schedule_match").df()

    @classmethod
    def tearDownClass(cls):
        if cls.con:
            cls.con.close()

    def test_row_count_matches_gtfs_coverage_ridership(self):
        """Verify record count is exactly 28,798 within GTFS coverage period."""
        self.assertEqual(len(self.df), 28798)

    def test_match_rate_above_95_percent(self):
        """Verify matched records exceed 95% threshold (expected ~98.5%)."""
        matched_count = len(self.df[self.df["match_quality"] == "matched"])
        rate = matched_count / len(self.df)
        self.assertGreaterEqual(rate, 0.95, f"Schedule match rate {rate:.4f} is below 95%!")

    def test_service_span_and_departure_times_consistency(self):
        """Verify service span is positive and departure times are properly formatted for matched routes."""
        matched = self.df[self.df["match_quality"] == "matched"]
        self.assertTrue(all(matched["scheduled_trips_count"] > 0))
        self.assertTrue(all(matched["service_span_seconds"] >= 0))
        # Verify departure time strings are HH:MM:SS
        sample_time = matched["first_departure_time"].dropna().iloc[0]
        self.assertEqual(len(sample_time.split(":")), 3)


if __name__ == "__main__":
    unittest.main()
