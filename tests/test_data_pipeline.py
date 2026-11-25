#!/usr/bin/env python3
"""
Unit tests for AI_RouteRanker Data Ingestion & Validation Utilities.
Tests ZIP security, SHA-256 calculation, CSV streaming validation, and disk checks
using isolated temporary files.
"""

import csv
import hashlib
import io
import os
import shutil
import tempfile
import unittest
import zipfile

from scripts.download_sources import (
    calculate_sha256,
    check_disk_space,
    probe_remote_resource,
)
from scripts.validate_downloads import (
    safe_extract_zip,
    validate_ridership_csv,
    REQUIRED_GTFS_FILES,
    REQUIRED_RIDERSHIP_COLUMNS,
)


class TestDataIngestionPipeline(unittest.TestCase):
    """Test suite for data download and validation modules."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="ai_routeranker_test_")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_calculate_sha256(self):
        """Verify streaming SHA-256 calculation matches hashlib on known payload."""
        test_file = os.path.join(self.test_dir, "sample.txt")
        test_content = b"AI_RouteRanker Public Transit Optimization Test Payload"
        with open(test_file, "wb") as f:
            f.write(test_content)

        expected_hash = hashlib.sha256(test_content).hexdigest()
        actual_hash = calculate_sha256(test_file)
        self.assertEqual(actual_hash, expected_hash)

    def test_check_disk_space(self):
        """Verify disk space checking utility operates without errors."""
        has_space, free_bytes = check_disk_space(self.test_dir, required_bytes=1024)
        self.assertTrue(has_space)
        self.assertGreater(free_bytes, 0)

    def test_safe_extract_zip_valid(self):
        """Verify safe extraction of valid ZIP archive containing required GTFS files."""
        zip_path = os.path.join(self.test_dir, "test_gtfs.zip")
        extracted_dir = os.path.join(self.test_dir, "extracted")

        with zipfile.ZipFile(zip_path, "w") as zf:
            for req_file in REQUIRED_GTFS_FILES:
                zf.writestr(req_file, f"Dummy GTFS content for {req_file}\n")
            zf.writestr("shapes.txt", "shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence\n")

        success, files, error = safe_extract_zip(zip_path, extracted_dir)
        self.assertTrue(success)
        self.assertIsNone(error)
        self.assertEqual(len(files), len(REQUIRED_GTFS_FILES) + 1)
        for req_file in REQUIRED_GTFS_FILES:
            self.assertTrue(os.path.exists(os.path.join(extracted_dir, req_file)))

    def test_safe_extract_zip_path_traversal_protection(self):
        """Verify protection against Zip Slip path traversal attacks."""
        zip_path = os.path.join(self.test_dir, "malicious.zip")
        extracted_dir = os.path.join(self.test_dir, "safe_target")

        # Create ZIP entry with path traversal ../../attack.txt
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("../../attack.txt", "Malicious content")

        success, files, error = safe_extract_zip(zip_path, extracted_dir)
        self.assertFalse(success)
        self.assertIn("path traversal", error.lower())

    def test_safe_extract_zip_corrupt_detection(self):
        """Verify that a corrupted ZIP triggers failure."""
        zip_path = os.path.join(self.test_dir, "corrupt.zip")
        with open(zip_path, "wb") as f:
            f.write(b"PK\x03\x04This is not a real zip payload truncated")

        extracted_dir = os.path.join(self.test_dir, "extracted")
        success, files, error = safe_extract_zip(zip_path, extracted_dir)
        self.assertFalse(success)
        self.assertIsNotNone(error)

    def test_validate_ridership_csv_valid(self):
        """Verify CSV validation logic on well-formed test ridership file."""
        csv_path = os.path.join(self.test_dir, "sample_ridership.csv")
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["route", "date", "daytype", "rides"])
            writer.writerow(["1", "2024-01-01", "U", "520"])
            writer.writerow(["2", "2024-01-02", "W", "1430"])
            writer.writerow(["3", "2024-01-03", "A", "890"])

        result = validate_ridership_csv(csv_path)
        self.assertTrue(result["exists"])
        self.assertTrue(result["columns_present"])
        self.assertEqual(result["total_records"], 3)
        self.assertEqual(result["min_date"], "2024-01-01")
        self.assertEqual(result["max_date"], "2024-01-03")
        self.assertEqual(result["distinct_routes_count"], 3)
        self.assertEqual(result["status"], "VALID")

    def test_validate_ridership_csv_missing_column(self):
        """Verify CSV validation fails when required columns are absent."""
        csv_path = os.path.join(self.test_dir, "bad_ridership.csv")
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["route", "date", "rides"])  # missing 'daytype'
            writer.writerow(["1", "2024-01-01", "520"])

        result = validate_ridership_csv(csv_path)
        self.assertFalse(result["columns_present"])
        self.assertEqual(result["status"], "INVALID")
        self.assertIn("daytype", result["notes"])


if __name__ == "__main__":
    unittest.main()
