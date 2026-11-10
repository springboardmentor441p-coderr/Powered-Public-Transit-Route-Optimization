"""Tests for schedule-based EDA metrics and output generation."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from routeranker.analysis.eda import run_eda  # noqa: E402


def write_fixture(directory: Path) -> None:
    tables = {
        "routes": pl.DataFrame({"route_id": ["R0", "R1", "R2"], "route_type": ["3", "3", "3"]}),
        "stops": pl.DataFrame({
            "stop_id": ["S1", "S2", "S3"],
            "stop_name": ["Stop 1", "Stop 2", "Stop 3"],
            "stop_lat_value": [13.0, 13.1, 13.2],
            "stop_lon_value": [80.0, 80.1, 80.2],
        }),
        "trips": pl.DataFrame({
            "trip_id": ["T1", "T2", "T3"],
            "route_id": ["R1", "R1", "R2"],
            "service_id": ["WK", "WK", "WK"],
            "direction_id": ["0", "0", "1"],
        }),
        "stop_times": pl.DataFrame({
            "trip_id": ["T1", "T1", "T2", "T2", "T3", "T3"],
            "stop_id": ["S1", "S2", "S1", "S2", "S2", "S3"],
            "stop_sequence_value": [1, 2, 1, 2, 1, 2],
            "arrival_time_seconds": [85800, 86400, 87000, 87600, 90000, 90600],
            "departure_time_seconds": [85800, 86400, 87000, 87600, 90000, 90600],
        }),
        "calendar": pl.DataFrame({
            "service_id": ["WK"],
            "monday": ["1"], "tuesday": ["1"], "wednesday": ["1"],
            "thursday": ["1"], "friday": ["1"], "saturday": ["0"], "sunday": ["0"],
            "start_date": ["20250101"], "end_date": ["20251231"],
        }),
    }
    for name, frame in tables.items():
        frame.write_parquet(directory / f"{name}.parquet")


class EdaTests(unittest.TestCase):
    def test_route_stop_headway_and_after_midnight_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, output = root / "source", root / "eda"
            source.mkdir()
            write_fixture(source)
            result = run_eda(source, output)

            self.assertEqual(result["totals"]["route_records"], 3)
            self.assertEqual(result["totals"]["routes_with_trips"], 2)
            self.assertEqual(result["totals"]["route_stop_pairs"], 4)
            self.assertEqual(result["totals"]["shared_stops"], 1)
            self.assertEqual(result["totals"]["route_pairs_with_shared_stops"], 1)
            self.assertEqual(result["totals"]["after_midnight_trip_starts"], 2)
            self.assertEqual(result["totals"]["after_midnight_stop_time_records"], 5)

            routes = pl.read_csv(output / "route_summary.csv")
            route1 = routes.filter(pl.col("route_id") == "R1").row(0, named=True)
            self.assertEqual(route1["trip_count"], 2)
            self.assertEqual(route1["stop_count"], 2)
            self.assertAlmostEqual(route1["used_network_stop_coverage_pct"], 200.0 / 3.0)
            self.assertEqual(route1["first_service_time"], "23:50:00")
            self.assertEqual(route1["last_service_time"], "24:20:00")

            headways = pl.read_csv(output / "route_service_headways.csv")
            route1_headway = headways.filter(pl.col("route_id") == "R1").row(0, named=True)
            self.assertEqual(route1_headway["median_headway_seconds"], 1200)
            overlap = pl.read_parquet(output / "route_pair_overlap.parquet")
            self.assertAlmostEqual(overlap["jaccard_similarity"][0], 1 / 3)
            self.assertTrue((output / "charts" / "scheduled_trip_starts_by_service_hour.png").is_file())


if __name__ == "__main__":
    unittest.main()

