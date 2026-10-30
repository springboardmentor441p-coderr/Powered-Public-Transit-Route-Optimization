"""Regression checks for the mentor's historical alignment requirements."""

from pathlib import Path
import sys
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from validate_historical_alignment import activate, block_conflicts, expand_date, seconds, select_snapshot


class AlignmentTests(unittest.TestCase):
    def test_exception_removes_weekly_and_adds_only_once(self):
        date = pd.Timestamp("2026-01-05")
        calendar = pd.DataFrame({"service_id": ["remove", "keep"],
                                 "start_date": ["20260101"] * 2,
                                 "end_date": ["20261231"] * 2, "monday": ["1"] * 2})
        changes = pd.DataFrame({"service_id": ["remove", "keep", "extra"],
                                "date": ["20260105"] * 3, "exception_type": ["2", "1", "1"]})
        self.assertEqual(activate(calendar, changes, date), {"keep", "extra"})

    def test_calendar_dates_only(self):
        changes = pd.DataFrame({"service_id": ["extra"], "date": ["20260105"], "exception_type": ["1"]})
        self.assertEqual(activate(pd.DataFrame(), changes, pd.Timestamp("2026-01-05")), {"extra"})

    def test_latest_whole_snapshot_and_no_future_snapshot(self):
        feeds = [{"id": "old", "capture": pd.Timestamp("2026-01-01")},
                 {"id": "new", "capture": pd.Timestamp("2026-01-10")}]
        self.assertIsNone(select_snapshot(feeds, pd.Timestamp("2025-12-31")))
        self.assertEqual(select_snapshot(feeds, pd.Timestamp("2026-01-09"))["id"], "old")
        self.assertEqual(select_snapshot(feeds, pd.Timestamp("2026-01-10"))["id"], "new")

    def test_invalid_selected_snapshot_does_not_fall_back(self):
        feeds = [{"id": "old", "capture": pd.Timestamp("2026-01-01")},
                 {"id": "new", "capture": pd.Timestamp("2026-01-10"),
                  "start": "20260112", "end": "20260131"}]
        audit, trips = expand_date(feeds, pd.Timestamp("2026-01-11"))
        self.assertEqual(audit["source_snapshot"], "new")
        self.assertEqual(audit["status"], "selected_snapshot_outside_feed_info")
        self.assertTrue(trips.empty)

    def test_extended_time_is_not_wrapped_to_same_day(self):
        self.assertEqual(seconds(pd.Series(["25:10:00"])).iloc[0], 90600)

    def test_withdrawn_route_does_not_return_from_old_snapshot(self):
        calendar = pd.DataFrame({"service_id": ["s"], "start_date": ["20260101"],
                                 "end_date": ["20260131"], "monday": ["1"]})
        exceptions = pd.DataFrame(columns=["service_id", "date", "exception_type"])
        common = {"start": None, "end": None, "calendar": calendar, "exceptions": exceptions}
        feeds = [dict(common, id="old", capture=pd.Timestamp("2026-01-01"),
                      trips=pd.DataFrame({"service_id": ["s"], "route_id": ["M1"]})),
                 dict(common, id="new", capture=pd.Timestamp("2026-01-10"),
                      trips=pd.DataFrame({"service_id": ["s"], "route_id": ["M2"]}))]
        audit, trips = expand_date(feeds, pd.Timestamp("2026-01-12"))
        self.assertEqual(audit["source_snapshot"], "new")
        self.assertEqual(set(trips.route_id), {"M2"})

    def test_block_overlap_flags_both_routes_but_not_touching_endpoints(self):
        trips = pd.DataFrame({"block_id": ["b"] * 3,
                              "route_short_name": ["M1", "M2", "M3"],
                              "first_departure_seconds": [100, 150, 250],
                              "final_arrival_seconds": [200, 250, 300]})
        self.assertEqual(block_conflicts(trips), {"M1", "M2"})
        nested = pd.DataFrame({"block_id": ["b", "b", "b", "other"],
                               "route_short_name": ["M1", "M2", "M3", "M4"],
                               "first_departure_seconds": [0, 10, 40, 5],
                               "final_arrival_seconds": [1000, 30, 50, 15]})
        self.assertEqual(block_conflicts(nested), {"M1", "M2", "M3"})


if __name__ == "__main__":
    unittest.main()
