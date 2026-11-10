"""Service and HTTP contract tests for the Phase 5 API."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import polars as pl

HAS_API_DEPS = all(importlib.util.find_spec(name) for name in ("fastapi", "pydantic", "httpx"))


@unittest.skipUnless(HAS_API_DEPS, "Install backend API dependencies and httpx test extra")
class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from fastapi.testclient import TestClient
        from routeranker.api.app import create_app
        from routeranker.api.config import Settings

        cls.TestClient = TestClient
        cls.create_app = staticmethod(create_app)
        cls.Settings = Settings

    def build_data(self, root: Path, empty: bool = False) -> Path:
        processed = root / "processed"
        for phase in ("gtfs", "eda", "features", "clustering"):
            (processed / phase).mkdir(parents=True)
        route_rows = [] if empty else [
            {"route_id": "R1", "route_short_name": "1", "route_long_name": "Central", "route_type": "3", "agency_id": "A"},
            {"route_id": "R2", "route_short_name": "2", "route_long_name": "Coast", "route_type": "3", "agency_id": "A"},
        ]
        pl.DataFrame(route_rows, schema={"route_id": pl.String, "route_short_name": pl.String,
                                         "route_long_name": pl.String, "route_type": pl.String,
                                         "agency_id": pl.String}, orient="row").write_parquet(processed / "gtfs" / "routes.parquet")
        summary = [] if empty else [
            {"route_id": "R1", "trip_count": 12, "stop_count": 5, "template_week_trip_count": 60,
             "first_service_time": "05:00:00", "last_service_time": "23:00:00"},
            {"route_id": "R2", "trip_count": 6, "stop_count": 3, "template_week_trip_count": 30,
             "first_service_time": "06:00:00", "last_service_time": "22:00:00"},
        ]
        pl.DataFrame(summary, schema={"route_id": pl.String, "trip_count": pl.Int64, "stop_count": pl.Int64,
                                      "template_week_trip_count": pl.Int64, "first_service_time": pl.String,
                                      "last_service_time": pl.String}, orient="row").write_csv(processed / "eda" / "route_summary.csv")
        stop_rows = [] if empty else [
            {"stop_id": "S1", "stop_name": "Alpha", "stop_lat_value": 13.0, "stop_lon_value": 80.0, "trip_count": 8, "route_count": 2},
            {"stop_id": "S2", "stop_name": "Beta", "stop_lat_value": 13.1, "stop_lon_value": 80.1, "trip_count": 4, "route_count": 1},
        ]
        pl.DataFrame(stop_rows, schema={"stop_id": pl.String, "stop_name": pl.String, "stop_lat_value": pl.Float64,
                                        "stop_lon_value": pl.Float64, "trip_count": pl.Int64, "route_count": pl.Int64}, orient="row").write_csv(processed / "eda" / "stop_summary.csv")
        pl.DataFrame([] if empty else [{"route_id": "R1", "stop_id": "S1"}, {"route_id": "R2", "stop_id": "S1"},
                                       {"route_id": "R1", "stop_id": "S2"}],
                     schema={"route_id": pl.String, "stop_id": pl.String}, orient="row").write_parquet(processed / "eda" / "route_stop_coverage.parquet")
        pl.DataFrame([] if empty else [{"route_id": "R1", "service_id": "svc", "direction_id": 0,
                                        "mean_headway_seconds": 1800.0, "median_headway_seconds": 1600.0},
                                       {"route_id": "R2", "service_id": "svc", "direction_id": 0,
                                        "mean_headway_seconds": None, "median_headway_seconds": None}],
                     schema={"route_id": pl.String, "service_id": pl.String, "direction_id": pl.Int64,
                             "mean_headway_seconds": pl.Float64, "median_headway_seconds": pl.Float64}, orient="row").write_csv(processed / "eda" / "route_service_headways.csv")
        pl.DataFrame([] if empty else [{"service_hour": 5, "scheduled_trip_records": 2},
                                       {"service_hour": 6, "scheduled_trip_records": 3}],
                     schema={"service_hour": pl.Int64, "scheduled_trip_records": pl.Int64}, orient="row").write_csv(processed / "eda" / "scheduled_trips_by_service_hour.csv")
        pl.DataFrame([] if empty else [{"route_id_a": "R1", "route_id_b": "R2", "shared_stop_count": 1,
                                        "route_a_stop_count": 2, "route_b_stop_count": 1, "jaccard_similarity": 0.5}],
                     schema={"route_id_a": pl.String, "route_id_b": pl.String, "shared_stop_count": pl.Int64,
                             "route_a_stop_count": pl.Int64, "route_b_stop_count": pl.Int64,
                             "jaccard_similarity": pl.Float64}, orient="row").write_parquet(processed / "eda" / "route_pair_overlap.parquet")
        (processed / "gtfs" / "data_quality_report.json").write_text(json.dumps({"status": "passed"}), encoding="utf-8")
        (processed / "eda" / "eda_report.json").write_text(json.dumps({"totals": {"route_records": len(route_rows), "trip_records": 18},
            "service_level": {}, "headways": {}, "time_of_day": {}, "data_quality": {}, "limitations": {"shapes_available": False}}), encoding="utf-8")
        features = [] if empty else [{"route_id": "R1", "total_scheduled_trip_records": 12, "unique_stop_count": 2,
                                      "average_first_stop_headway_seconds": 1800.0, "scheduled_service_span_seconds": 64800,
                                      "shared_stop_ratio": 0.5}]
        pl.DataFrame(features, schema={"route_id": pl.String, "total_scheduled_trip_records": pl.Int64,
                                       "unique_stop_count": pl.Int64, "average_first_stop_headway_seconds": pl.Float64,
                                       "scheduled_service_span_seconds": pl.Int64, "shared_stop_ratio": pl.Float64}, orient="row").write_parquet(processed / "features" / "route_features.parquet")
        pl.DataFrame([] if empty else [
            {"route_id": "R1", "total_scheduled_trip_records": 12, "kmeans_cluster_id": 0, "dbscan_cluster_id": 1, "fit_status": "clustered"},
            {"route_id": "R2", "total_scheduled_trip_records": 6, "kmeans_cluster_id": 1, "dbscan_cluster_id": -1, "fit_status": "dbscan_noise"},
        ], schema={"route_id": pl.String, "total_scheduled_trip_records": pl.Int64, "kmeans_cluster_id": pl.Int64,
                  "dbscan_cluster_id": pl.Int64, "fit_status": pl.String}, orient="row").write_parquet(processed / "clustering" / "cluster_predictions.parquet")
        pl.DataFrame([] if empty else [{"algorithm": "KMeans", "cluster_id": 0, "route_count": 1, "is_noise": False}],
                     schema={"algorithm": pl.String, "cluster_id": pl.Int64, "route_count": pl.Int64, "is_noise": pl.Boolean}, orient="row").write_csv(processed / "clustering" / "cluster_sizes.csv")
        pl.DataFrame([] if empty else [{"algorithm": "KMeans", "cluster_id": 0, "cluster_name": "KMeans cluster 0",
                                        "route_count": 1, "interpretation": "Scheduled service profile.",
                                        "median_total_scheduled_trip_records": 12.0}],
                     schema={"algorithm": pl.String, "cluster_id": pl.Int64, "cluster_name": pl.String,
                             "route_count": pl.Int64, "interpretation": pl.String,
                             "median_total_scheduled_trip_records": pl.Float64}, orient="row").write_parquet(processed / "clustering" / "cluster_profiles.parquet")
        pl.DataFrame([] if empty else [{"algorithm": "KMeans", "n_clusters": 2, "silhouette_score": 0.4,
                                        "silhouette_sample_size": 2, "davies_bouldin_index": 0.5,
                                        "noise_count": 0, "inlier_count": 2, "k": 2, "eps": None, "min_samples": None}],
                     schema={"algorithm": pl.String, "n_clusters": pl.Int64, "silhouette_score": pl.Float64,
                             "silhouette_sample_size": pl.Int64, "davies_bouldin_index": pl.Float64,
                             "noise_count": pl.Int64, "inlier_count": pl.Int64, "k": pl.Int64,
                             "eps": pl.Float64, "min_samples": pl.Int64}, orient="row").write_csv(processed / "clustering" / "model_comparison.csv")
        import joblib
        for name, metadata in (("kmeans_model.joblib", {"feature_columns": ["x"], "training_route_count": 2, "selected_k": 2}),
                               ("dbscan_model.joblib", {"feature_columns": ["x"], "training_route_count": 2, "eps": 1.1, "min_samples": 8})):
            joblib.dump(metadata, processed / "clustering" / name)
        return processed

    def test_catalog_pagination_filtering_comparison_and_schemas(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            processed = self.build_data(Path(tmp))
            app = self.create_app(self.Settings(processed, ("http://localhost:5173",)))
            with self.TestClient(app) as client:
                page = client.get("/api/v1/routes?limit=1&offset=1")
                self.assertEqual(page.status_code, 200)
                self.assertEqual(page.json()["total"], 2)
                self.assertEqual(page.json()["items"][0]["route_id"], "R2")
                filtered = client.get("/api/v1/routes?min_trips=10")
                self.assertEqual([row["route_id"] for row in filtered.json()["items"]], ["R1"])
                compared = client.get("/api/v1/routes/compare?route_ids=R1&route_ids=R2")
                self.assertEqual(compared.status_code, 200)
                self.assertEqual(len(compared.json()["routes"]), 2)
                self.assertEqual(client.get("/api/v1/routes/R1/features").json()["total_scheduled_trip_records"], 12)
                self.assertEqual(client.get("/api/v1/routes/R1/clusters").json()["kmeans_cluster_id"], 0)

    def test_stop_analytics_similarity_and_saved_model_endpoints(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = self.create_app(self.Settings(self.build_data(Path(tmp)), ()))
            with self.TestClient(app) as client:
                self.assertEqual(client.get("/api/v1/stops?limit=1").json()["total"], 2)
                self.assertEqual(len(client.get("/api/v1/stops/S1/routes").json()), 2)
                self.assertEqual(client.get("/api/v1/analytics/scheduled-trips/by-hour").json()[0]["service_hour"], 5)
                self.assertEqual(client.get("/api/v1/analytics/route-similarity").json()[0]["jaccard_similarity"], 0.5)
                self.assertIn("refit", client.get("/api/v1/ml/models").json()[1]["new_route_behavior"])
                self.assertEqual(client.get("/api/v1/ml/metrics").json()[0]["n_clusters"], 2)

    def test_invalid_ids_filters_pagination_and_missing_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = self.create_app(self.Settings(self.build_data(Path(tmp)), ()))
            with self.TestClient(app) as client:
                self.assertEqual(client.get("/api/v1/routes/invalid").status_code, 404)
                self.assertEqual(client.get("/api/v1/stops/invalid").status_code, 404)
                self.assertEqual(client.get("/api/v1/routes?limit=999").status_code, 422)
                self.assertEqual(client.get("/api/v1/routes?min_trips=9&max_trips=2").status_code, 422)
            missing_app = self.create_app(self.Settings(Path(tmp) / "absent", ()))
            with self.TestClient(missing_app) as client:
                response = client.get("/api/v1/routes")
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json()["code"], "dataset_unavailable")

    def test_empty_processed_tables_return_empty_page(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = self.create_app(self.Settings(self.build_data(Path(tmp), empty=True), ()))
            with self.TestClient(app) as client:
                response = client.get("/api/v1/routes")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["items"], [])
                self.assertEqual(response.json()["total"], 0)


if __name__ == "__main__":
    unittest.main()
