"""Feature engineering tests against a compact, source-GTFS fixture."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from routeranker.features.engineering import run_feature_engineering  # noqa: E402


GTFS = {
    "routes.txt": "route_id,route_short_name,route_long_name,route_type,agency_id\nR0,0,Inactive Route,3,A\nR1,1,Route One,3,A\nR2,2,Route Two,3,A\n",
    "stops.txt": "stop_id,stop_name,stop_lat,stop_lon\nS1,Stop One,13.0,80.0\nS2,Stop Two,13.1,80.1\nS3,Stop Three,13.2,80.2\n",
    "trips.txt": "route_id,service_id,trip_id,direction_id\nR1,WK,T1,0\nR1,WK,T2,0\nR2,WK,T3,1\n",
    "stop_times.txt": (
        "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
        "T1,07:00:00,07:00:00,S1,1\nT1,07:30:00,07:30:00,S2,2\n"
        "T2,08:00:00,08:00:00,S1,1\nT2,08:30:00,08:30:00,S2,2\n"
        "T3,20:00:00,20:00:00,S2,1\nT3,20:30:00,20:30:00,S3,2\n"
    ),
    "calendar.txt": "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\nWK,1,0,0,0,0,0,0,20250101,20251231\n",
}


def write_fixture(root: Path) -> tuple[Path, Path, Path]:
    archive = root / "feed.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, value in GTFS.items():
            zf.writestr(name, value)
    gtfs_dir, eda_dir = root / "gtfs", root / "eda"
    gtfs_dir.mkdir()
    eda_dir.mkdir()

    # The Phase 1 data structures required by feature validation.
    pl.DataFrame({"route_id": ["R0", "R1", "R2"], "route_type": ["3", "3", "3"]}).write_parquet(gtfs_dir / "routes.parquet")
    pl.DataFrame({"stop_id": ["S1", "S2", "S3"], "stop_name": ["Stop One", "Stop Two", "Stop Three"], "stop_lat_value": [13.0, 13.1, 13.2], "stop_lon_value": [80.0, 80.1, 80.2]}).write_parquet(gtfs_dir / "stops.parquet")
    pl.DataFrame({"trip_id": ["T1", "T2", "T3"], "route_id": ["R1", "R1", "R2"], "service_id": ["WK"] * 3, "direction_id": ["0", "0", "1"]}).write_parquet(gtfs_dir / "trips.parquet")
    pl.DataFrame({
        "trip_id": ["T1", "T1", "T2", "T2", "T3", "T3"],
        "stop_id": ["S1", "S2", "S1", "S2", "S2", "S3"],
        "stop_sequence_value": [1, 2, 1, 2, 1, 2],
        "arrival_time_seconds": [25200, 27000, 28800, 30600, 72000, 73800],
        "departure_time_seconds": [25200, 27000, 28800, 30600, 72000, 73800],
    }).write_parquet(gtfs_dir / "stop_times.parquet")
    pl.DataFrame({"service_id": ["WK"], "monday": ["1"], "tuesday": ["0"], "wednesday": ["0"], "thursday": ["0"], "friday": ["0"], "saturday": ["0"], "sunday": ["0"], "start_date": ["20250101"], "end_date": ["20251231"]}).write_parquet(gtfs_dir / "calendar.parquet")
    phase1_files = {name: {"rows": rows} for name, rows in (("routes.txt", 3), ("stops.txt", 3), ("trips.txt", 3), ("stop_times.txt", 6), ("calendar.txt", 1))}
    for name, rows in (("routes.txt", 3), ("stops.txt", 3), ("trips.txt", 3), ("stop_times.txt", 6), ("calendar.txt", 1)):
        (gtfs_dir / name.replace(".txt", ".parquet")).touch(exist_ok=True)
    # Replace touched placeholders with readable Phase 1 Parquets.
    # The four tables above already exist; calendar is written above.
    (gtfs_dir / "data_quality_report.json").write_text(json.dumps({"status": "passed", "files": phase1_files, "metrics": {}}), encoding="utf-8")

    pl.DataFrame({
        "route_id": ["R0", "R1", "R2"], "trip_count": ["0", "2", "1"], "stop_count": ["0", "2", "2"],
        "first_service_time": [None, "07:00:00", "20:00:00"], "last_service_time": [None, "08:30:00", "20:30:00"],
    }).write_csv(eda_dir / "route_summary.csv")
    pl.DataFrame({"stop_id": ["S1", "S2", "S3"], "trip_count": ["2", "3", "1"], "route_count": ["1", "2", "1"]}).write_csv(eda_dir / "stop_summary.csv")
    pl.DataFrame({
        "route_id": ["R1", "R2"], "service_id": ["WK", "WK"], "direction_id": ["0", "1"],
        "scheduled_trip_count": ["2", "1"], "headway_observations": ["1", "0"],
        "mean_headway_seconds": ["3600.0", None],
    }).write_csv(eda_dir / "route_service_headways.csv")
    pl.DataFrame({"route_id": ["R1", "R1", "R2", "R2"], "stop_id": ["S1", "S2", "S2", "S3"]}).write_parquet(eda_dir / "route_stop_coverage.parquet")
    pl.DataFrame({
        "route_id_a": ["R1"], "route_id_b": ["R2"], "shared_stop_count": [1],
        "route_a_stop_count": [2], "route_b_stop_count": [2], "jaccard_similarity": [1 / 3],
    }).write_parquet(eda_dir / "route_pair_overlap.parquet")
    (eda_dir / "eda_report.json").write_text(json.dumps({"totals": {"route_records": 3, "stop_records": 3, "trip_records": 3, "stop_time_records": 6}}), encoding="utf-8")
    return archive, gtfs_dir, eda_dir


class FeatureEngineeringTests(unittest.TestCase):
    def test_route_stop_similarity_and_normalized_features(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive, gtfs_dir, eda_dir = write_fixture(root)
            output = root / "features"
            report = run_feature_engineering(archive, gtfs_dir, eda_dir, output)

            self.assertEqual(report["status"], "passed")
            self.assertEqual(report["route_feature_count"], 3)
            self.assertEqual(report["stop_feature_count"], 3)
            self.assertEqual(report["route_pair_feature_count"], 1)
            self.assertEqual(report["validation_checks_passed"], report["validation_check_count"])

            routes = pl.read_parquet(output / "route_features.parquet")
            r1 = routes.filter(pl.col("route_id") == "R1").row(0, named=True)
            self.assertEqual(r1["total_scheduled_trip_records"], 2)
            self.assertEqual(r1["unique_stop_count"], 2)
            self.assertEqual(r1["average_first_stop_headway_seconds"], 3600.0)
            self.assertEqual(r1["peak_scheduled_departures_per_template_week"], 2)
            self.assertEqual(r1["off_peak_scheduled_departures_per_template_week"], 0)
            self.assertEqual(r1["scheduled_service_span_seconds"], 5400)
            self.assertEqual(r1["shared_stop_ratio"], 0.5)

            inactive = routes.filter(pl.col("route_id") == "R0").row(0, named=True)
            self.assertEqual(inactive["total_scheduled_trip_records"], 0)
            self.assertIsNone(inactive["average_first_stop_headway_seconds"])
            self.assertEqual(inactive["headway_missing"], 1)

            stops = pl.read_parquet(output / "stop_features.parquet")
            s2 = stops.filter(pl.col("stop_id") == "S2").row(0, named=True)
            self.assertEqual(s2["routes_serving_stop"], 2)
            self.assertEqual(s2["scheduled_trip_records_serving_stop"], 3)
            pairs = pl.read_parquet(output / "route_pair_features.parquet")
            self.assertAlmostEqual(pairs["jaccard_similarity"][0], 1 / 3)
            normalized = pl.read_parquet(output / "route_features_normalized.parquet")
            self.assertEqual(normalized.null_count().select(pl.sum_horizontal(pl.all())).item(), 0)
            self.assertTrue((output / "feature_dictionary.md").is_file())
            self.assertTrue((output / "feature_engineering_report.md").is_file())


if __name__ == "__main__":
    unittest.main()

