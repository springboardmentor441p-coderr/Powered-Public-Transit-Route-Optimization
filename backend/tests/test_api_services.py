"""Fast unit tests for the API data and domain service without ASGI dependencies."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import polars as pl

from routeranker.api.data_access import DataRepository, DatasetUnavailable
from routeranker.api.services import InvalidFilter, RecordNotFound, RouteRankerService


class ApiServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.processed = Path(self.tmp.name)
        for phase in ("gtfs", "eda", "features", "clustering"):
            (self.processed / phase).mkdir()
        pl.DataFrame([{"route_id": "001", "route_short_name": "1", "route_long_name": "Test", "route_type": "3"}]).write_parquet(
            self.processed / "gtfs" / "routes.parquet"
        )
        pl.DataFrame([{"route_id": "001", "trip_count": 12, "stop_count": 5, "template_week_trip_count": 60,
                       "first_service_time": "05:00:00", "last_service_time": "23:00:00"}]).write_csv(
            self.processed / "eda" / "route_summary.csv"
        )
        pl.DataFrame([{"route_id": "001", "average_first_stop_headway_seconds": 1800.0}]).write_parquet(
            self.processed / "features" / "route_features.parquet"
        )
        pl.DataFrame([{"route_id": "001", "total_scheduled_trip_records": 12, "kmeans_cluster_id": 2,
                       "dbscan_cluster_id": -1, "fit_status": "dbscan_noise"}]).write_parquet(
            self.processed / "clustering" / "cluster_predictions.parquet"
        )
        self.service = RouteRankerService(DataRepository(self.processed))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_csv_identifier_is_preserved_and_joined_to_actual_features(self) -> None:
        page = self.service.list_routes(10, 0)
        self.assertEqual(page["total"], 1)
        self.assertEqual(page["items"][0]["route_id"], "001")
        self.assertEqual(self.service.route_features("001")["average_first_stop_headway_seconds"], 1800.0)
        self.assertEqual(self.service.route_cluster("001")["dbscan_cluster_id"], -1)

    def test_characteristic_filter_and_invalid_route_errors(self) -> None:
        self.assertEqual(self.service.list_routes(10, 0, min_trips=10, max_headway_seconds=1800)["total"], 1)
        with self.assertRaises(InvalidFilter):
            self.service.list_routes(10, 0, min_trips=20, max_trips=10)
        with self.assertRaises(RecordNotFound):
            self.service.route("absent")

    def test_missing_artifacts_fail_explicitly(self) -> None:
        service = RouteRankerService(DataRepository(Path(self.tmp.name) / "missing"))
        with self.assertRaises(DatasetUnavailable):
            service.routes()


if __name__ == "__main__":
    unittest.main()
