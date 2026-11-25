"""Focused unit and concurrency tests for Pre-Stage 2A repository hardening (L-01 & L-02)."""

import os
import sys
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pandas as pd
from fastapi.testclient import TestClient

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.repositories.json_repository import JSONRepository
from app.repositories.parquet_repository import ParquetRepository


class TestRepositoryHardening(unittest.TestCase):
    """Tests verifying L-01 lightweight weight metadata and L-02 thread-safe lazy caching."""

    def test_weight_metadata_equivalence_with_full_explanation(self):
        """Verify get_weight_metadata matches full explanation weights, coverage, and missing_criteria."""
        repo = JSONRepository()
        for track, route_ids in [
            ("BUS_PRIORITY", ["151", "10", "130", "N5"]),
            ("RAIL_PRIORITY", ["Red", "Blue", "Y"]),
            ("UNIFIED_SUPPLY", ["Red", "79", "10"]),
        ]:
            for rid in route_ids:
                full = repo.get_explanation(rid, track)
                meta = repo.get_weight_metadata(rid, track)
                self.assertIsNotNone(full)
                self.assertIsNotNone(meta)
                self.assertEqual(meta["original_weights"], full["original_weights"])
                self.assertEqual(meta["effective_weights"], full["effective_weights"])
                self.assertEqual(meta["missing_criteria"], full["missing_criteria"])
                expected_cov = round(
                    sum(
                        v
                        for k, v in full["original_weights"].items()
                        if k not in full["missing_criteria"]
                    ),
                    6,
                )
                self.assertEqual(meta["valid_weight_coverage"], expected_cov)

        self.assertIsNone(repo.get_weight_metadata("NONEXISTENT_999", "BUS_PRIORITY"))

    def test_returned_weight_metadata_and_explanation_immutability(self):
        """Verify mutating returned weight metadata or explanation does not corrupt cached data."""
        repo = JSONRepository()
        meta1 = repo.get_weight_metadata("10", "BUS_PRIORITY")
        meta1["original_weights"]["tampered"] = 999.0
        meta1["effective_weights"]["am_headway_min_norm"] = 0.99
        meta1["missing_criteria"].append("tampered_criterion")

        meta2 = repo.get_weight_metadata("10", "BUS_PRIORITY")
        self.assertNotIn("tampered", meta2["original_weights"])
        self.assertEqual(meta2["effective_weights"]["am_headway_min_norm"], 0.0)
        self.assertEqual(meta2["missing_criteria"], ["am_headway_min_norm"])

        expl1 = repo.get_explanation("151", "BUS_PRIORITY")
        expl1["top_positive_drivers"].clear()
        expl2 = repo.get_explanation("151", "BUS_PRIORITY")
        self.assertGreater(len(expl2["top_positive_drivers"]), 0)

    def test_parquet_concurrent_cold_start_initializes_once(self):
        """Verify concurrent cold-start ParquetRepository calls initialize each dataset exactly once."""
        repo = ParquetRepository()
        num_threads = 12
        barrier = threading.Barrier(num_threads)

        with patch("app.repositories.parquet_repository.pd.read_parquet", wraps=pd.read_parquet) as mock_read:
            def worker():
                barrier.wait()
                df = repo.get_rankings_master()
                return len(df)

            with ThreadPoolExecutor(max_workers=num_threads) as pool:
                results = list(pool.map(lambda _: worker(), range(num_threads)))

            self.assertEqual(results, [266] * num_threads)
            self.assertEqual(mock_read.call_count, 1)

    def test_json_concurrent_cold_start_initializes_once(self):
        """Verify concurrent cold-start JSONRepository calls parse JSON exactly once."""
        import json as std_json

        repo = JSONRepository()
        num_threads = 12
        barrier = threading.Barrier(num_threads)

        with patch("app.repositories.json_repository.json.load", wraps=std_json.load) as mock_load:
            def worker():
                barrier.wait()
                meta = repo.get_weight_metadata("151", "BUS_PRIORITY")
                return meta["valid_weight_coverage"]

            with ThreadPoolExecutor(max_workers=num_threads) as pool:
                results = list(pool.map(lambda _: worker(), range(num_threads)))

            self.assertEqual(results, [1.0] * num_threads)
            self.assertEqual(mock_load.call_count, 1)

    def test_concurrent_api_requests_consistency(self):
        """Verify multiple simultaneous API requests return identical consistent responses."""
        client = TestClient(app)
        num_threads = 10
        barrier = threading.Barrier(num_threads)

        def call_api(idx: int):
            barrier.wait()
            if idx % 2 == 0:
                r = client.get("/api/v1/rankings/bus?limit=25")
                return (r.status_code, len(r.json()["data"]), r.json()["data"][0]["route_id"])
            r = client.get("/api/v1/rankings/unified?limit=25")
            return (r.status_code, len(r.json()["data"]), r.json()["data"][0]["route_id"])

        with ThreadPoolExecutor(max_workers=num_threads) as pool:
            results = list(pool.map(call_api, range(num_threads)))

        for idx, res in enumerate(results):
            if idx % 2 == 0:
                self.assertEqual(res, (200, 25, "151"))
            else:
                self.assertEqual(res, (200, 25, "Red"))


if __name__ == "__main__":
    unittest.main()
