"""Tests for reproducible, missingness-aware GTFS route clustering."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import polars as pl

from routeranker.clustering.route_clusters import run_route_clustering


class RouteClusteringTests(unittest.TestCase):
    def _write_fixture(self, root: Path) -> Path:
        features = root / "features"
        features.mkdir()
        rows = []
        for index in range(80):
            group = index // 40
            trips = (4 if group == 0 else 35) + (index % 5)
            headway = None if index % 11 == 0 else (7800.0 if group == 0 else 1500.0) + (index % 7) * 10
            rows.append({
                "route_id": f"route-{index:03d}",
                "total_scheduled_trip_records": trips,
                "unique_stop_count": (12 if group == 0 else 38) + index % 4,
                "average_first_stop_headway_seconds": headway,
                "headway_interval_count": 0 if headway is None else 5,
                "peak_scheduled_departures_per_template_week": 2 + group * 30 + index % 3,
                "off_peak_scheduled_departures_per_template_week": 20 + (1 - group) * 15 + index % 4,
                "scheduled_service_span_seconds": (18000 if group == 0 else 54000) + index * 10,
                "shared_stop_ratio": 0.2 + group * 0.5,
                "headway_missing": int(headway is None),
                "service_span_missing": 0,
                "shared_stop_ratio_missing": 0,
            })
        rows.extend([
            {**rows[0], "route_id": f"inactive-{index}", "total_scheduled_trip_records": 0,
             "average_first_stop_headway_seconds": None, "headway_interval_count": 0, "headway_missing": 1}
            for index in range(3)
        ])
        raw = pl.DataFrame(rows)
        raw.write_parquet(features / "route_features.parquet")
        pl.DataFrame({"route_id": raw["route_id"], "feature_z": np.arange(raw.height, dtype=float)}).write_parquet(
            features / "route_features_normalized.parquet"
        )
        (features / "feature_engineering_report.json").write_text(json.dumps({"status": "passed"}), encoding="utf-8")
        (features / "feature_validation_report.json").write_text(json.dumps({"status": "passed", "check_count": 20}), encoding="utf-8")
        (features / "normalization_parameters.json").write_text("{}", encoding="utf-8")
        return features

    def test_pipeline_preserves_inactive_routes_missingness_and_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            features = self._write_fixture(root)
            result = run_route_clustering(features, root / "output", random_seed=17)
            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["feature_quality"]["routes_with_trip_records"], 80)
            predictions = pl.read_parquet(root / "output" / "cluster_predictions.parquet")
            self.assertEqual(predictions.height, 83)
            self.assertEqual(predictions.filter(pl.col("fit_status") == "excluded_no_scheduled_trip_records").height, 3)
            self.assertTrue(result["feature_selection"]["headway_missing_indicator_included"])
            matrix = pl.read_parquet(root / "output" / "standardized_model_matrix.parquet")
            self.assertEqual(matrix.null_count().select(pl.sum_horizontal(pl.all())).item(), 0)
            self.assertTrue((root / "output" / "kmeans_model.joblib").is_file())
            self.assertTrue((root / "output" / "dbscan_model.joblib").is_file())
            self.assertTrue((root / "output" / "charts" / "route_cluster_pca_comparison.png").is_file())
            self.assertEqual(sum(row["route_count"] for row in result["selected_models"][0]["cluster_sizes"]), 80)

    def test_same_seed_produces_same_labels(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            features = self._write_fixture(root)
            first = run_route_clustering(features, root / "first", random_seed=29)
            second = run_route_clustering(features, root / "second", random_seed=29)
            for name in ("kmeans_cluster_id", "dbscan_cluster_id"):
                left = pl.read_parquet(root / "first" / "cluster_predictions.parquet")[name]
                right = pl.read_parquet(root / "second" / "cluster_predictions.parquet")[name]
                self.assertEqual(left.to_list(), right.to_list())
            self.assertEqual(first["selected_models"], second["selected_models"])


if __name__ == "__main__":
    unittest.main()
