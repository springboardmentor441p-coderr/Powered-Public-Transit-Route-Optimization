"""Unit tests for GTFS parsing, validation, and output generation."""

from __future__ import annotations

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from routeranker.ingestion import parse_gtfs_time, run_pipeline  # noqa: E402


FILES = {
    "agency.txt": "agency_id,agency_name,agency_url,agency_timezone\nA1,Transit,https://example.test,Asia/Kolkata\n",
    "stops.txt": "stop_id,stop_name,stop_lat,stop_lon\nS1,Stop One,13.0,80.0\nS2,Stop Two,13.1,80.1\n",
    "routes.txt": "route_id,route_short_name,route_type,agency_id\nR1,1,3,A1\n",
    "trips.txt": "route_id,service_id,trip_id\nR1,WK,T1\n",
    "stop_times.txt": "trip_id,arrival_time,departure_time,stop_id,stop_sequence\nT1,25:10:00,25:10:00,S1,1\nT1,25:20:00,25:20:00,S2,2\n",
    "calendar.txt": "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\nWK,1,1,1,1,1,0,0,20250101,20251231\n",
}


def make_zip(path: Path, files: dict[str, str] | None = None) -> Path:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, text in (files or FILES).items():
            archive.writestr(name, text)
    return path


class TimeParsingTests(unittest.TestCase):
    def test_after_midnight_time_is_seconds_after_service_day_start(self) -> None:
        self.assertEqual(parse_gtfs_time("25:10:00"), 90_600)

    def test_invalid_time_rejected(self) -> None:
        for value in ("", "25:60:00", "8:1:00", "abc"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_gtfs_time(value)


class PipelineTests(unittest.TestCase):
    def test_pipeline_writes_typed_parquet_and_empty_calendar_exceptions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = make_zip(root / "feed.zip")
            report = run_pipeline(archive, root / "out")
            self.assertEqual(report["status"], "passed")
            self.assertEqual(report["files"]["stop_times.txt"]["rows"], 2)
            self.assertEqual(report["files"]["calendar_dates.txt"]["presence"], "absent_optional_empty_output")
            stop_times = pl.read_parquet(root / "out" / "stop_times.parquet")
            self.assertEqual(stop_times["arrival_time_seconds"].to_list(), [90_600, 91_200])
            self.assertEqual(pl.read_parquet(root / "out" / "calendar_dates.parquet").height, 0)
            self.assertTrue((root / "out" / "data_quality_report.md").exists())

    def test_calendar_date_exceptions_are_preserved(self) -> None:
        files = dict(FILES)
        files["calendar_dates.txt"] = "service_id,date,exception_type\nWK,20250704,2\n"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = run_pipeline(make_zip(root / "feed.zip", files), root / "out")
            self.assertEqual(report["files"]["calendar_dates.txt"]["rows"], 1)
            exceptions = pl.read_parquet(root / "out" / "calendar_dates.parquet")
            self.assertEqual(exceptions["date"].to_list(), ["20250704"])
            self.assertEqual(exceptions["exception_type_value"].to_list(), [2])

    def test_relationship_errors_and_duplicates_are_reported(self) -> None:
        files = dict(FILES)
        files["trips.txt"] = "route_id,service_id,trip_id\nMISSING,WK,T1\nMISSING,WK,T1\n"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = run_pipeline(make_zip(root / "feed.zip", files), root / "out")
            codes = {issue["code"] for issue in report["issues"]}
            self.assertEqual(report["status"], "failed")
            self.assertIn("duplicate_primary_key", codes)
            self.assertIn("unresolved_reference", codes)

    def test_non_monotonic_stop_times_are_rejected(self) -> None:
        files = dict(FILES)
        files["stop_times.txt"] = (
            "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
            "T1,25:20:00,25:20:00,S1,1\n"
            "T1,25:10:00,25:10:00,S2,2\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = run_pipeline(make_zip(root / "feed.zip", files), root / "out")
            codes = {issue["code"] for issue in report["issues"]}
            self.assertEqual(report["status"], "failed")
            self.assertIn("arrival_time_regression", codes)

    def test_routes_require_at_least_one_route_name_column(self) -> None:
        files = dict(FILES)
        files["routes.txt"] = "route_id,route_type,agency_id\nR1,3,A1\n"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = run_pipeline(make_zip(root / "feed.zip", files), root / "out")
            self.assertIn("missing_alternative_required_columns", {issue["code"] for issue in report["issues"]})


if __name__ == "__main__":
    unittest.main()

