"""Tests for GTFS Preprocessing Pipeline."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from data_processing.preprocessing import GTFSPreprocessor


class TestGTFSPreprocessing(unittest.TestCase):
    """Test suite for preprocessing, DuckDB parquet creation, and analytical aggregations."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = TemporaryDirectory(prefix="routeranker-preprocessing-")
        cls.processed_dir = Path(cls.temp_dir.name) / "processed"
        preprocessor = GTFSPreprocessor(processed_dir=cls.processed_dir)
        cls.result = preprocessor.run_pipeline()

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    def test_pipeline_success(self):
        self.assertEqual(self.result["status"], "success")
        self.assertGreaterEqual(self.result["quality_score"], 90.0)

    def test_parquet_files_created(self):
        expected_files = [
            "agency.parquet",
            "routes.parquet",
            "stops.parquet",
            "trips.parquet",
            "stop_times.parquet",
            "calendar.parquet",
            "route_stops.parquet",
            "route_service_summary.parquet",
            "stop_coverage.parquet",
            "route_stop_overlap.parquet",
        ]
        for f in expected_files:
            p_file = self.processed_dir / f
            self.assertTrue(p_file.exists(), f"Parquet file {f} was not created.")
            self.assertGreater(p_file.stat().st_size, 0, f"Parquet file {f} is empty.")

    def test_stop_times_normalized(self):
        df = pd.read_parquet(self.processed_dir / "stop_times.parquet")
        self.assertGreater(len(df), 1000000)
        self.assertIn("arrival_seconds", df.columns)
        self.assertIn("normalized_arrival_time", df.columns)
        self.assertIn("day_offset", df.columns)
        # Check that normalized times all have hour < 24
        sample_hours = df["normalized_arrival_time"].head(100).apply(lambda x: int(x.split(":")[0]))
        self.assertTrue((sample_hours < 24).all())


if __name__ == "__main__":
    unittest.main()

