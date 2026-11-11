"""Application boundaries and interactions, using the validated local study data."""
from datetime import date
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

import numpy as np
import pandas as pd
from streamlit.testing.v1 import AppTest

from dashboard import data

ROOT = Path(__file__).resolve().parents[1]


class DashboardDataTests(unittest.TestCase):
    def test_hash_mismatch_blocks_input(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "modified.csv"
            path.write_text("value\n1\n")
            digest = data.digest(path)
            path.write_text("value\n2\n")
            with self.assertRaisesRegex(data.DataUnavailable, "Fingerprint mismatch"):
                data.checked_bytes(path, digest)

    def test_all_pinned_inputs_are_present_and_verified(self):
        audit = data.inventory()
        self.assertEqual(len(audit), 27)
        self.assertTrue(audit.status.eq("verified").all())

    def test_paired_ratio_does_not_use_unmatched_demand(self):
        frame = pd.DataFrame({"analysis_boardings": [100., 900., 0., np.nan],
                              "scheduled_service_hours": [10., np.nan, 5., 2.],
                              "comparison_eligible": [True, False, True, False]})
        result = data.history_summary(frame)
        self.assertEqual(result["observed_days"], 3)
        self.assertEqual(result["paired_days"], 2)
        self.assertAlmostEqual(result["boardings_per_bus_hour"], 100 / 15)
        self.assertTrue(np.isnan(data.history_summary(frame.iloc[1:2])["boardings_per_bus_hour"]))

    def test_empty_filters_remain_empty(self):
        frame = data.table("daily")
        result = data.filtered_history(frame, "M34+", "2026-07-06", "2026-09-27", [])
        self.assertTrue(result.empty)
        with self.assertRaises(ValueError):
            data.filtered_history(frame, "M34+", "2026-09-27", "2026-07-06", ["Weekday"])

    def test_route_geometry_and_peer_orientation(self):
        paths = data.route_paths("M34+")
        self.assertGreater(len(paths), 0)
        for entry in paths:
            self.assertEqual(entry["route"], "M34+")
            for lon, lat in entry["path"]:
                self.assertTrue(-75 < lon < -72 and 39 < lat < 42)
        a = data.peer_overlaps("M34+").set_index("peer").loc["M34A+"]
        b = data.peer_overlaps("M34A+").set_index("peer").loc["M34+"]
        self.assertEqual(a.selected_route_only_stops, b.peer_only_stops)
        self.assertEqual(a.shared_stop_ids, 22)

    def test_saved_forecasts_validate_and_challenger_ranges_stay_withheld(self):
        previews, rejected = data.preview_list()
        self.assertFalse(rejected)
        for mode in ["reference", "challenger"]:
            choice = next(x for x in previews if x["preview_mode"] == mode)
            metadata, points, ranges = data.load_preview(choice["id"])
            self.assertEqual(len(points), 287)
            self.assertFalse(metadata["operationally_accepted"])
            if mode == "challenger":
                self.assertTrue(ranges.empty)
                self.assertEqual(metadata["range_levels_available"], [])
            self.assertIn("Archived", data.preview_age(metadata, "2030-01-01"))

    def test_preview_path_and_invalid_target_cannot_start_process(self):
        with self.assertRaises(data.DataUnavailable):
            data.load_preview("../outside")
        with patch("dashboard.data.subprocess.run") as run:
            with self.assertRaises(ValueError):
                data.generate_preview("reference", date(2001, 1, 1))
            run.assert_not_called()

    def test_scenario_download_contains_inputs_and_assumptions(self):
        frame = data.table("baselines").head(1)
        bundle = data.scenario_export(frame, {"frequency_factor": 1.2, "max_added_bus_hours": None})
        with ZipFile(BytesIO(bundle)) as archive:
            meta = json.loads(archive.read("assumptions.json"))
            self.assertEqual(meta["frequency_factor"], 1.2)
            self.assertIsNone(meta["max_added_bus_hours"])
            self.assertFalse(meta["automatic_service_change"])
            self.assertEqual(meta["timetable_feasibility"], "not_assessed")
            self.assertIn("observation_dates_sha256", archive.read("scenario.csv").decode("utf-8-sig"))

    def test_csv_escape_keeps_numeric_negatives(self):
        output = pd.read_csv(BytesIO(data.csv_bytes(pd.DataFrame({"text": ["=1+1", "M34+"], "number": [-2, 3]}))))
        self.assertEqual(output.text.iloc[0], "'=1+1")
        self.assertEqual(output.text.iloc[1], "M34+")
        self.assertEqual(output.number.iloc[0], -2)


class DashboardInteractionTests(unittest.TestCase):
    def make_app(self):
        app = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=90).run()
        self.assertFalse(app.exception, [e.message for e in app.exception])
        return app

    def test_all_six_pages_render(self):
        app = self.make_app()
        for page in ["Route explorer", "Demand forecasts", "Planning review", "Service scenarios", "Data coverage"]:
            with self.subTest(page=page):
                app.radio(key="workspace").set_value(page).run()
                self.assertFalse(app.exception, [e.message for e in app.exception])
                self.assertFalse(app.error, [e.value for e in app.error])

    def test_empty_filter_and_period_without_schedule(self):
        app = self.make_app()
        app.radio(key="workspace").set_value("Route explorer").run()
        app.multiselect(key="explore_day_types").set_value([]).run()
        self.assertFalse(app.exception)
        self.assertTrue(any("No observations" in e.value for e in app.info))
        app.multiselect(key="explore_day_types").set_value(["Weekday"])
        app.date_input(key="explore_dates").set_value((date(2025, 1, 1), date(2025, 1, 31))).run()
        self.assertFalse(app.exception)
        metrics = {m.label: m.value for m in app.metric}
        self.assertEqual(metrics["Comparable service days"], "0")
        self.assertEqual(metrics["Boardings / bus-hour"], "Unavailable")

    def test_scenario_limits_recalculate_and_source_gate_persists(self):
        app = self.make_app()
        app.radio(key="workspace").set_value("Service scenarios").run()
        app.slider(key="frequency_change").set_value(20).run()
        self.assertFalse(app.exception)
        self.assertTrue(any("Exceeds" in e.value for e in app.warning))
        app.checkbox(key="has_budget").set_value(False).run()
        self.assertTrue(any("budget unspecified" in e.value for e in app.info))
        app.slider(key="frequency_change").set_value(-50).run()
        self.assertTrue(any("Below the minimum" in e.value for e in app.warning))
        app.selectbox(key="selected_route").set_value("M98").run()
        self.assertFalse(app.exception)
        self.assertTrue(any("Projection withheld" in e.value for e in app.warning))
        self.assertTrue(any("Transfers are unavailable" in e.value for e in app.warning))

    def test_challenger_and_review_source_state(self):
        app = self.make_app()
        app.radio(key="workspace").set_value("Demand forecasts").run()
        app.selectbox(key="forecast_mode").set_value("challenger").run()
        self.assertFalse(app.exception)
        self.assertTrue(any("Ranges are withheld" in e.value for e in app.info))
        app.radio(key="workspace").set_value("Planning review")
        app.selectbox(key="selected_route").set_value("M98").run()
        self.assertFalse(app.exception)
        self.assertTrue(any("Source clarification required" in e.value for e in app.warning))

    def test_missing_local_artifact_displays_setup_message(self):
        with patch("dashboard.data.table", side_effect=data.DataUnavailable("Missing required local file")):
            app = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=90).run()
            self.assertFalse(app.exception)
            self.assertTrue(any("Missing required" in e.value for e in app.error))

    def test_generated_preview_is_selected_after_rerun(self):
        app = self.make_app()
        app.radio(key="workspace").set_value("Demand forecasts").run()
        existing = [x["id"] for x in data.preview_list()[0] if x["preview_mode"] == "reference"][-1]
        with patch("dashboard.views.generate_preview", return_value=existing) as generate:
            next(b for b in app.button if b.label == "Generate seven-day preview").click().run()
        generate.assert_called_once()
        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox(key="preview_reference").value, existing)
        self.assertTrue(any("saved and selected" in e.value for e in app.success))


if __name__ == "__main__":
    unittest.main()
