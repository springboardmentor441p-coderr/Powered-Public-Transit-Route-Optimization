"""Tests for GTFS Loader Module."""

import unittest
from pathlib import Path
from data_processing.gtfs_loader import GTFSLoader, REQUIRED_GTFS_FILES


class TestGTFSLoader(unittest.TestCase):
    """Test suite for GTFS loading and feed inspection."""

    @classmethod
    def setUpClass(cls):
        cls.loader = GTFSLoader()

    def test_inspect_feed(self):
        manifest = self.loader.inspect_feed()
        self.assertTrue(manifest.is_valid, f"Missing required files: {manifest.missing_required_files}")
        for req in REQUIRED_GTFS_FILES:
            self.assertIn(req, manifest.present_files)

    def test_load_agency(self):
        df = self.loader.load_table("agency.txt")
        self.assertFalse(df.empty)
        self.assertIn("agency_id", df.columns)
        self.assertIn("agency_name", df.columns)
        self.assertEqual(df["agency_name"].iloc[0].strip(), "MTC")

    def test_load_routes(self):
        df = self.loader.load_table("routes.txt")
        self.assertGreater(len(df), 4000)
        self.assertIn("route_id", df.columns)
        self.assertIn("route_short_name", df.columns)

    def test_load_stops(self):
        df = self.loader.load_table("stops.txt")
        self.assertGreater(len(df), 5000)
        self.assertIn("stop_id", df.columns)
        self.assertIn("stop_lat", df.columns)
        self.assertIn("stop_lon", df.columns)


if __name__ == "__main__":
    unittest.main()

