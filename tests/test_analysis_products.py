"""Integration checks on saved notebook products; skip without the local collection."""

import hashlib
import json
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/processed/new_york"


class ProductContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (OUT / "feature_manifest.json").exists():
            raise unittest.SkipTest("Run notebooks 02-03 for local product integration checks")
        cls.manifest = json.loads((OUT / "feature_manifest.json").read_text())
        cls.daily = pd.read_csv(OUT / "matched_daily_features.csv", low_memory=False,
                               dtype={"bus_route": "string"}, parse_dates=["payment_date"])

    def test_source_and_product_fingerprints(self):
        clean = json.loads((OUT / "cleaning_manifest.json").read_text())
        for source in clean["source_files"]:
            with (ROOT / source["file"]).open("rb") as handle:
                self.assertEqual(hashlib.file_digest(handle, "sha256").hexdigest(), source["sha256"])
        self.assertEqual(hashlib.sha256((OUT / "cleaning_manifest.json").read_bytes()).hexdigest(),
                         self.manifest["inputs"]["cleaning_manifest_sha256"])
        for name, record in self.manifest["products"].items():
            with (OUT / f"{name}.csv").open("rb") as handle:
                self.assertEqual(hashlib.file_digest(handle, "sha256").hexdigest(), record["sha256"])

    def test_declared_grains_are_unique(self):
        grains = {
            "daily_demand_features": ["bus_route", "payment_date"],
            "trip_template_features": ["snapshot_id", "trip_id"],
            "shape_features": ["snapshot_id", "shape_id"],
            "pattern_service_date_features": ["service_date", "bus_route", "direction_id", "origin_stop_id", "pattern_id"],
            "schedule_clock_daily": ["bus_route", "payment_date"],
            "schedule_clock_hourly": ["bus_route", "local_hour"],
            "matched_daily_features": ["bus_route", "payment_date"],
            "matched_hourly_features": ["bus_route", "local_hour"],
            "route_day_type_profiles": ["bus_route", "day_type"],
            "route_overlap": ["snapshot_id", "route_a", "route_b"],
        }
        for name, keys in grains.items():
            frame = pd.read_csv(OUT / f"{name}.csv", usecols=keys, dtype="string")
            self.assertFalse(frame.isna().any().any(), name)
            self.assertFalse(frame.duplicated(keys).any(), name)

    def test_ineligible_rows_cannot_have_comparison_ratios(self):
        frame = self.daily
        eligible = frame.comparison_eligible.eq(True)
        self.assertTrue(frame.loc[~eligible, ["boardings_per_scheduled_departure",
                                             "boardings_per_scheduled_service_hour"]].isna().all().all())
        self.assertFalse(frame.loc[eligible, ["dst_context_review", "block_overlap_review",
                                              "partial_calendar_review", "demand_review_required"]].any().any())
        self.assertTrue(frame.loc[eligible, "analysis_boardings"].notna().all())
        absent_schedule = ~frame.schedule_comparison_eligible.eq(True)
        self.assertTrue(frame.loc[absent_schedule, "scheduled_departures"].isna().all())
        # Sparse calendars also invalidate the following clock date's overnight context.
        calendar = pd.read_csv(OUT / "calendar_expansion.csv", parse_dates=["date"])
        partial = calendar.loc[calendar.partial_calendar_review, "date"]
        affected = set(partial) | set(partial + pd.Timedelta(days=1))
        self.assertFalse(frame.loc[frame.payment_date.isin(affected), "comparison_eligible"].any())

    def test_profile_ratios_reconcile_with_their_member_observations(self):
        frame = self.daily.loc[self.daily.comparison_eligible & self.daily.scheduled_departures.gt(0)
                               & self.daily.scheduled_service_hours.gt(0)]
        grouped = frame.groupby(["bus_route", "day_type"])
        expected_boardings = grouped.analysis_boardings.sum()
        profiles = pd.read_csv(OUT / "route_day_type_profiles.csv", dtype={"bus_route": "string"}).set_index(["bus_route", "day_type"])
        pd.testing.assert_series_equal(profiles.total_boardings.sort_index(), expected_boardings.sort_index(),
                                       check_names=False, check_dtype=False)
        expected_ratio = expected_boardings / grouped.scheduled_service_hours.sum()
        np.testing.assert_allclose(profiles.boardings_per_scheduled_service_hour.sort_index(), expected_ratio.sort_index())
        np.testing.assert_array_equal(profiles.observed_dates.sort_index(), grouped.payment_date.nunique().sort_index())

    def test_clock_hour_supply_sums_to_daily_supply_and_archive_is_not_future(self):
        hours = pd.read_csv(OUT / "schedule_clock_hourly.csv", parse_dates=["local_hour", "payment_date"])
        days = pd.read_csv(OUT / "schedule_clock_daily.csv", parse_dates=["payment_date"])
        aggregate = hours.groupby(["bus_route", "payment_date"])[
            ["scheduled_departures", "scheduled_service_hours"]].sum(min_count=1).sort_index()
        saved = days.set_index(["bus_route", "payment_date"])[aggregate.columns].sort_index()
        np.testing.assert_allclose(aggregate, saved, equal_nan=True)
        for column, offset in [("source_snapshot", 0), ("prior_source_snapshot", 1)]:
            captured = pd.to_datetime(days[column].str.rsplit("_", n=1).str[-1], format="%Y%m%d")
            self.assertTrue(captured.le(days.payment_date - pd.Timedelta(days=offset)).all())


if __name__ == "__main__":
    unittest.main()
