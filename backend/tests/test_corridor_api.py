"""Comprehensive tests for Milestone 8 Stage 2C Corridor Topology & Co-Routing APIs."""

import json
import os
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.api.v1.deps import get_corridor_repository, get_parquet_repository
from app.main import app
from app.repositories.corridor_repository import CorridorRepository
from app.repositories.parquet_repository import ParquetRepository


class TestCanonicalCorridorAPI(unittest.TestCase):
    """Integration tests against the canonical Phase 6.2 & 6.3 corridor artifacts."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_corridor_clusters_retrieval_and_filtering(self):
        """Verify GET /api/v1/corridors/clusters pagination, k, cluster_type, mode, and deterministic order."""
        r_default = self.client.get("/api/v1/corridors/clusters?limit=25&offset=0")
        self.assertEqual(r_default.status_code, 200)
        body = r_default.json()
        self.assertEqual(body["k"], 3)
        self.assertEqual(body["cluster_type"], "geographic_buffer_overlap")
        self.assertEqual(body["pagination"]["total"], 261)
        self.assertEqual(body["pagination"]["returned"], 25)
        self.assertIn("never merged", body["methodology"]["metric_distinctions"])

        # Frechet cluster type with k=5 and route_id filter
        r_fre = self.client.get("/api/v1/corridors/clusters?k=5&cluster_type=frechet&route_id=151")
        self.assertEqual(r_fre.status_code, 200)
        b_fre = r_fre.json()
        self.assertEqual(b_fre["cluster_type"], "geometric_frechet_shape")
        self.assertEqual(b_fre["pagination"]["total"], 2)
        self.assertEqual([x["pattern_id"] for x in b_fre["data"]], ["151__dir_0", "151__dir_1"])

        # Rail mode filter
        r_rail = self.client.get("/api/v1/corridors/clusters?mode=rail")
        self.assertEqual(r_rail.status_code, 200)
        self.assertGreater(r_rail.json()["pagination"]["total"], 0)
        for item in r_rail.json()["data"]:
            self.assertTrue(item["is_rail"])

    def test_route_co_routing_distinct_metrics_and_sequences(self):
        """Verify GET /api/v1/corridors/routes/151/co-routing returns distinct overlap, jaccard, and sequences."""
        resp = self.client.get("/api/v1/corridors/routes/151/co-routing?min_similarity=0.1&top_n=5")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["route_id"], "151")
        self.assertEqual(len(body["patterns"]), 2)
        p0 = body["patterns"][0]
        self.assertEqual(p0["direction_id"], 0)
        self.assertGreater(len(p0["geographic_overlap_peers"]), 0)
        self.assertGreater(len(p0["stop_jaccard_peers"]), 0)
        self.assertGreater(len(p0["shared_consecutive_sequences"]), 0)
        self.assertEqual(p0["geographic_overlap_peers"][0]["metric_type"], "geographic_buffer_overlap")
        self.assertEqual(p0["stop_jaccard_peers"][0]["metric_type"], "stop_set_jaccard_similarity")

        # Direction filter
        r_dir1 = self.client.get("/api/v1/corridors/routes/151/co-routing?direction_id=1")
        self.assertEqual(r_dir1.status_code, 200)
        self.assertEqual(len(r_dir1.json()["patterns"]), 1)
        self.assertEqual(r_dir1.json()["patterns"][0]["direction_id"], 1)

    def test_invalid_params_and_unknown_route(self):
        """Verify 404 for unknown route and 400 for invalid filters/route IDs."""
        r404 = self.client.get("/api/v1/corridors/routes/NONEXISTENT999/co-routing")
        self.assertEqual(r404.status_code, 404)
        self.assertEqual(r404.json()["code"], "ROUTE_NOT_FOUND")

        self.assertEqual(self.client.get("/api/v1/corridors/routes/bad.id/co-routing").status_code, 400)
        self.assertEqual(self.client.get("/api/v1/corridors/clusters?k=99").status_code, 422)
        self.assertEqual(self.client.get("/api/v1/corridors/clusters?cluster_type=bogus").status_code, 400)
        self.assertEqual(self.client.get("/api/v1/corridors/clusters?direction_id=5").status_code, 400)
        self.assertEqual(self.client.get("/api/v1/corridors/clusters?sort_by=invalid").status_code, 400)

    def test_corridor_immutability_and_concurrent_cold_start(self):
        """Verify cached corridor DataFrames are immutable and thread-safe under concurrent cold start."""
        repo = CorridorRepository()
        df = repo.get_corridor_clusters()
        with self.assertRaises(ValueError):
            df["direction_id"].values[0] = 99

        cold_repo = CorridorRepository()
        barrier = threading.Barrier(10)

        def worker():
            barrier.wait()
            return cold_repo.get_buffer_similarity_matrix().shape

        with ThreadPoolExecutor(max_workers=10) as pool:
            shapes = list(pool.map(lambda _: worker(), range(10)))
        self.assertEqual(shapes, [(261, 261)] * 10)


class TestSyntheticCorridorAndFailureModes(unittest.TestCase):
    """Tests using synthetic fixtures for NaN/zero similarity values and missing/corrupt artifacts."""

    def setUp(self):
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_synthetic_missing_and_zero_similarity_values(self):
        """Verify NaN similarity entries are counted as missing (never fabricated) and 0.0 is preserved."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            clusters_p = tmp / "clusters.parquet"
            buf_p = tmp / "buf.parquet"
            jac_p = tmp / "jac.parquet"
            seq_p = tmp / "seq.parquet"
            geo_p = tmp / "geo.parquet"
            conn_p = tmp / "conn.parquet"

            cols_k = {f"cluster_buffer_k{k}": [0, 1, 1] for k in range(2, 13)}
            cols_k.update({f"cluster_frechet_k{k}": [0, 0, 1] for k in range(2, 13)})
            pd.DataFrame(
                {
                    "pattern_id": ["151__dir_0", "79__dir_0", "66__dir_0"],
                    "route_id": ["151", "79", "66"],
                    "direction_id": [0, 0, 0],
                    **cols_k,
                }
            ).to_parquet(clusters_p, index=False)

            pids = ["151__dir_0", "79__dir_0", "66__dir_0"]
            # 151__dir_0 has 0.0 overlap with 79__dir_0, and NaN (missing) with 66__dir_0
            pd.DataFrame(
                [[1.0, 0.0, np.nan], [0.0, 1.0, 0.5], [np.nan, 0.5, 1.0]],
                index=pids,
                columns=pids,
            ).to_parquet(buf_p)

            pd.DataFrame(
                [[1.0, 0.25, 0.0], [0.25, 1.0, 0.1], [0.0, 0.1, 1.0]],
                index=pids,
                columns=pids,
            ).to_parquet(jac_p)

            pd.DataFrame(
                {
                    "pattern_a": ["151__dir_0"],
                    "pattern_b": ["79__dir_0"],
                    "sequence_length": [3],
                    "start_stop_id": ["S1"],
                    "end_stop_id": ["S3"],
                    "shared_stops_json": ['["S1", "S2", "S3"]'],
                }
            ).to_parquet(seq_p, index=False)

            pd.DataFrame(
                {
                    "pattern_id": pids,
                    "route_id": ["151", "79", "66"],
                    "direction_id": [0, 0, 0],
                    "scheduled_trip_count": [100, 200, 150],
                    "length_km": [10.0, 15.0, 12.0],
                }
            ).to_parquet(geo_p, index=False)

            pd.DataFrame(
                {
                    "pattern_id": pids,
                    "route_id": ["151", "79", "66"],
                    "direction_id": [0, 0, 0],
                    "hub_stop_count": [5, 8, 6],
                    "hub_stop_ratio": [0.2, 0.3, 0.25],
                }
            ).to_parquet(conn_p, index=False)

            syn_repo = CorridorRepository(
                clusters_path=clusters_p,
                buffer_matrix_path=buf_p,
                jaccard_matrix_path=jac_p,
                sequences_path=seq_p,
                geometries_path=geo_p,
                connectivity_path=conn_p,
            )
            app.dependency_overrides[get_corridor_repository] = lambda: syn_repo

            resp = self.client.get("/api/v1/corridors/routes/151/co-routing?min_similarity=0.0&top_n=10")
            self.assertEqual(resp.status_code, 200)
            p0 = resp.json()["patterns"][0]
            self.assertEqual(p0["missing_buffer_entries_count"], 1)
            self.assertEqual(len(p0["geographic_overlap_peers"]), 1)
            self.assertEqual(p0["geographic_overlap_peers"][0]["peer_pattern_id"], "79__dir_0")
            self.assertEqual(p0["geographic_overlap_peers"][0]["similarity_score"], 0.0)

    def test_missing_and_corrupt_corridor_artifacts_return_503(self):
        """Verify missing and corrupt corridor artifacts return HTTP 503 without path leakage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            missing_repo = CorridorRepository(
                clusters_path=tmp / "missing_c.parquet",
                buffer_matrix_path=tmp / "missing_b.parquet",
                jaccard_matrix_path=tmp / "missing_j.parquet",
                sequences_path=tmp / "missing_s.parquet",
                geometries_path=tmp / "missing_g.parquet",
                connectivity_path=tmp / "missing_conn.parquet",
            )
            app.dependency_overrides[get_corridor_repository] = lambda: missing_repo
            r1 = self.client.get("/api/v1/corridors/clusters")
            self.assertEqual(r1.status_code, 503)
            self.assertEqual(r1.json()["code"], "ARTIFACT_MISSING")
            self.assertNotIn(tmpdir, json.dumps(r1.json()))

            bad_p = tmp / "bad.parquet"
            bad_p.write_text("not parquet", encoding="utf-8")
            corrupt_repo = CorridorRepository(clusters_path=bad_p)
            app.dependency_overrides[get_corridor_repository] = lambda: corrupt_repo
            r2 = self.client.get("/api/v1/corridors/clusters")
            self.assertEqual(r2.status_code, 503)
            self.assertEqual(r2.json()["code"], "ARTIFACT_CORRUPT")


if __name__ == "__main__":
    unittest.main()
