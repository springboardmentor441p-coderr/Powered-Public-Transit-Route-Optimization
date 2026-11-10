"""Tests for GTFS Validator and Sanitizer Module."""

import unittest
import pandas as pd
from data_processing.gtfs_validator import (
    GTFSValidator,
    parse_gtfs_time_seconds,
    sanitize_text,
)


class TestGTFSValidator(unittest.TestCase):
    """Test suite for sanitization, XSS defense, and time normalization."""

    def test_sanitize_xss_injection(self):
        malicious_input = "'/><script>alert(1)</script>"
        sanitized, was_modified = sanitize_text(malicious_input)
        self.assertTrue(was_modified)
        self.assertNotIn("<script>", sanitized)
        self.assertNotIn("alert(1)", sanitized)

    def test_sanitize_whitespace_trimming(self):
        input_with_spaces = "test "
        sanitized, was_modified = sanitize_text(input_with_spaces)
        self.assertTrue(was_modified)
        self.assertEqual(sanitized, "test")

    def test_time_parsing_under_24h(self):
        secs, norm_str, day_off, gt24 = parse_gtfs_time_seconds("08:30:15")
        self.assertEqual(secs, 8 * 3600 + 30 * 60 + 15)
        self.assertEqual(norm_str, "08:30:15")
        self.assertEqual(day_off, 0)
        self.assertFalse(gt24)

    def test_time_parsing_over_24h(self):
        # GTFS allows trips extending past midnight
        secs, norm_str, day_off, gt24 = parse_gtfs_time_seconds("25:10:00")
        self.assertEqual(secs, 25 * 3600 + 10 * 60)
        self.assertEqual(norm_str, "01:10:00")
        self.assertEqual(day_off, 1)
        self.assertTrue(gt24)

    def test_calendar_sanitization(self):
        cal_data = {
            "service_id": ["Regular", "test ", "'/><script>alert(1)</script>"],
            "monday": [1, 1, 1],
            "tuesday": [1, 1, 0],
            "wednesday": [1, 1, 0],
            "thursday": [1, 0, 0],
            "friday": [1, 0, 0],
            "saturday": [1, 0, 0],
            "sunday": [1, 0, 0],
            "start_date": ["20240501", "20240501", "20240501"],
            "end_date": ["20300501", "20300501", "20300501"],
        }
        cal_df = pd.DataFrame(cal_data)
        validator = GTFSValidator()
        clean_cal = validator.sanitize_calendar(cal_df)

        service_ids = list(clean_cal["service_id"])
        self.assertIn("Regular", service_ids)
        self.assertIn("test", service_ids)
        self.assertNotIn("test ", service_ids)
        for s in service_ids:
            self.assertNotIn("<script>", s)

    def test_coordinate_validation(self):
        stops_data = {
            "stop_id": ["1", "2", "3"],
            "stop_name": ["Stop A", "Stop B", "Stop C"],
            "stop_lat": [13.0827, 95.0, 12.9800],  # 95 is invalid
            "stop_lon": [80.2707, 80.2000, 200.0],  # 200 is invalid
        }
        validator = GTFSValidator()
        stops_df = validator.sanitize_stops(pd.DataFrame(stops_data))
        self.assertEqual(validator.report.invalid_coordinates_count, 2)


if __name__ == "__main__":
    unittest.main()

