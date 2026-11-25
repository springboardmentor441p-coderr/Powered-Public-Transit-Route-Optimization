#!/usr/bin/env python3
"""
Unit tests for AI_RouteRanker Ridership Preprocessing Pipeline.
Tests date parsing, route ID preservation, daytype normalization,
duplicate detection, and invalid row quarantine using isolated temporary datasets.
"""

import csv
import os
import shutil
import sys
import tempfile
import unittest

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from analytics.preprocessing.ridership_pipeline import preprocess_ridership


class TestRidershipPreprocessing(unittest.TestCase):
    """Test suite for ridership preprocessing and data cleansing."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="ai_routeranker_ridership_test_")
        self.raw_csv = os.path.join(self.test_dir, "test_raw_ridership.csv")
        self.clean_parquet = os.path.join(self.test_dir, "cta_ridership_clean.parquet")
        self.clean_csv = os.path.join(self.test_dir, "cta_ridership_clean.csv")
        self.quarantine_csv = os.path.join(self.test_dir, "cta_ridership_quarantine.csv")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_clean_pipeline_with_various_routes_and_zeros(self):
        """Verify normal parsing, route preservation (prefixes/zeros), and zero rides."""
        rows = [
            ["route", "date", "daytype", "rides"],
            ["1", "05/14/2024", "W", "6,217"],
            ["X4", "05/15/2024", "W", "1,200"],
            ["N5", "05/18/2024", "A", "450"],
            ["008", "05/19/2024", "U", "0"],  # Zero rides kept
            ["X99", "05/20/2024", "W", " 150 "],  # Whitespace trimmed
        ]
        with open(self.raw_csv, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(rows)

        metrics = preprocess_ridership(
            self.raw_csv,
            self.clean_parquet,
            self.clean_csv,
            self.quarantine_csv,
        )

        self.assertEqual(metrics["total_raw_records"], 5)
        self.assertEqual(metrics["clean_records"], 5)
        self.assertEqual(metrics["quarantined_records"], 0)
        self.assertEqual(metrics["zero_rides_records"], 1)
        self.assertEqual(metrics["distinct_routes"], 5)

        # Verify parsed CSV contents
        with open(self.clean_csv, "r", encoding="utf-8") as f:
            reader = list(csv.DictReader(f))
            self.assertEqual(len(reader), 5)
            # Check route X4
            r_x4 = next(r for r in reader if r["route"] == "X4")
            self.assertEqual(r_x4["daytype"], "W")
            self.assertEqual(r_x4["daytype_label"], "Weekday")
            self.assertEqual(r_x4["rides"], "1200")
            self.assertEqual(r_x4["date"], "2024-05-15")

            # Check route 008 (leading zeros preserved)
            r_008 = next(r for r in reader if r["route"] == "008")
            self.assertEqual(r_008["rides"], "0")
            self.assertEqual(r_008["daytype_label"], "Sunday/Holiday")

    def test_quarantine_invalid_rows(self):
        """Verify that invalid rows (bad dates, negative rides, invalid daytypes) are quarantined."""
        rows = [
            ["route", "date", "daytype", "rides"],
            ["1", "01/01/2024", "W", "500"],  # VALID
            ["", "01/02/2024", "W", "200"],  # MISSING_ROUTE
            ["2", "99/99/2024", "W", "300"],  # INVALID_DATE_FORMAT
            ["3", "01/03/2024", "X", "400"],  # INVALID_DAYTYPE
            ["4", "01/04/2024", "W", "-50"],  # NEGATIVE_RIDES
            ["5", "01/05/2024", "W", "NOT_A_NUM"],  # NON_NUMERIC_RIDES
        ]
        with open(self.raw_csv, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(rows)

        metrics = preprocess_ridership(
            self.raw_csv,
            self.clean_parquet,
            self.clean_csv,
            self.quarantine_csv,
        )

        self.assertEqual(metrics["total_raw_records"], 6)
        self.assertEqual(metrics["clean_records"], 1)
        self.assertEqual(metrics["quarantined_records"], 5)

        # Inspect quarantine CSV
        with open(self.quarantine_csv, "r", encoding="utf-8") as f:
            quarantined = list(csv.DictReader(f))
            self.assertEqual(len(quarantined), 5)
            reasons = {q["quarantine_reason"] for q in quarantined}
            self.assertIn("MISSING_ROUTE", reasons)
            self.assertIn("INVALID_DATE_FORMAT", reasons)
            self.assertIn("INVALID_DAYTYPE", reasons)
            self.assertIn("NEGATIVE_RIDES", reasons)
            self.assertIn("INVALID_OR_NON_NUMERIC_RIDES", reasons)

    def test_duplicate_business_key_detection(self):
        """Verify duplicate detection on (route, date, daytype) without silent loss."""
        rows = [
            ["route", "date", "daytype", "rides"],
            ["1", "01/01/2024", "W", "500"],
            ["1", "01/01/2024", "W", "550"],  # Duplicate key!
            ["2", "01/01/2024", "W", "300"],
        ]
        with open(self.raw_csv, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(rows)

        metrics = preprocess_ridership(
            self.raw_csv,
            self.clean_parquet,
            self.clean_csv,
            self.quarantine_csv,
        )

        self.assertEqual(metrics["total_raw_records"], 3)
        self.assertEqual(metrics["clean_records"], 2)
        self.assertEqual(metrics["duplicate_keys"], 1)
        self.assertEqual(metrics["duplicate_rows"], 1)
        self.assertEqual(metrics["quarantined_records"], 1)

        with open(self.quarantine_csv, "r", encoding="utf-8") as f:
            quarantined = list(csv.DictReader(f))
            self.assertEqual(len(quarantined), 1)
            self.assertEqual(quarantined[0]["quarantine_reason"], "DUPLICATE_BUSINESS_KEY")


if __name__ == "__main__":
    unittest.main()
