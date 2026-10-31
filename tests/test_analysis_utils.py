"""Boundary cases that affect scientific meaning, independent of the real feeds."""

from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from analysis_utils import exact_date_lags, gtfs_anchor_utc, ratio_of_sums, separate_duplicates, trip_clock_hours


class AnalysisTests(unittest.TestCase):
    def test_conflicting_keys_are_quarantined_not_summed(self):
        data = pd.DataFrame({"route": ["a", "a", "b", "b"], "count": [5, 5, 3, 4]})
        clean, conflicts, duplicates = separate_duplicates(data, ["route"])
        self.assertEqual(duplicates, 1)
        self.assertEqual(clean.to_dict("records"), [{"route": "a", "count": 5}])
        self.assertEqual(len(conflicts), 2)

    def test_lags_use_dates_and_preserve_missing_and_zero(self):
        data = pd.DataFrame({"bus_route": ["a"]*4, "payment_date": pd.to_datetime(
            ["2026-01-01", "2026-01-03", "2026-01-08", "2026-01-09"]),
                            "analysis_boardings": [0, 50, np.nan, 20]})
        result = exact_date_lags(data)
        self.assertTrue(pd.isna(result.lag_1d.iloc[1]))
        self.assertEqual(result.lag_7d.iloc[2], 0)
        self.assertTrue(pd.isna(result.lag_1d.iloc[3]))

    def test_clock_midnight_and_duration_conservation(self):
        trips = pd.DataFrame({"bus_route": ["a", "a"], "first_departure_seconds": [84600, 90600],
                              "final_arrival_seconds": [88200, 91800]})
        result = trip_clock_hours(trips, "2026-07-01").set_index("local_hour")
        self.assertEqual(result.loc[pd.Timestamp("2026-07-01 23:00"), "scheduled_departures"], 1)
        self.assertEqual(result.loc[pd.Timestamp("2026-07-02 01:00"), "scheduled_departures"], 1)
        self.assertAlmostEqual(result.scheduled_service_hours.sum(), 4/3)

    def test_daylight_saving_uses_gtfs_noon_anchor(self):
        self.assertEqual(str(gtfs_anchor_utc("2026-03-08")), "2026-03-08 04:00:00+00:00")
        self.assertEqual(str(gtfs_anchor_utc("2026-11-01")), "2026-11-01 05:00:00+00:00")
        trips = pd.DataFrame({"bus_route": ["a"], "first_departure_seconds": [7200],
                              "final_arrival_seconds": [14400]})
        result = trip_clock_hours(trips, "2026-03-08")
        self.assertEqual(result.local_hour.dt.hour.tolist(), [1, 3])
        self.assertEqual(result.scheduled_service_hours.sum(), 2)

    def test_invalid_duration_fails_instead_of_zero_imputation(self):
        with self.assertRaises(ValueError):
            trip_clock_hours(pd.DataFrame({"bus_route": ["a"], "first_departure_seconds": [0],
                                           "final_arrival_seconds": [0]}), "2026-07-01")

    def test_ratios_weight_by_service_and_keep_zero_boardings(self):
        data = pd.DataFrame({"boardings": [100, 100, 0, 1000], "trips": [1, 9, 2, np.nan]})
        self.assertAlmostEqual(ratio_of_sums(data, "boardings", "trips"), 200/12)
        self.assertTrue(np.isnan(ratio_of_sums(data.iloc[3:], "boardings", "trips")))


if __name__ == "__main__":
    unittest.main()
