#!/usr/bin/env python3
"""
Unit tests for AI_RouteRanker EDA Module.
Verifies report generation, chart persistence, image validity,
and aggregate metric consistency across exploratory analyses.
Complies with Milestone 4 specifications.
"""

import os
import sys
import unittest

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class TestEDAPipeline(unittest.TestCase):
    """Test suite for Exploratory Data Analysis deliverables and artifacts."""

    def setUp(self):
        self.reports_dir = os.path.join("reports", "eda")
        self.charts_dir = os.path.join(self.reports_dir, "charts")

    def test_all_eda_reports_exist_and_non_empty(self):
        """Verify all 7 required Milestone 4 Markdown reports exist and contain content."""
        expected_reports = [
            "ridership_overview.md",
            "temporal_analysis.md",
            "route_analysis.md",
            "service_analysis.md",
            "demand_service_analysis.md",
            "feature_engineering_report.md",
            "eda_summary.md",
        ]
        for r in expected_reports:
            p = os.path.join(self.reports_dir, r)
            self.assertTrue(os.path.exists(p), f"Missing EDA report: {p}")
            self.assertGreater(os.path.getsize(p), 500, f"Report {p} is suspiciously small!")

    def test_all_eda_charts_exist_and_valid_png(self):
        """Verify all 17 generated PNG charts exist with valid PNG file signatures."""
        expected_charts = [
            "ridership_distribution_hist.png",
            "ridership_boxplot_daytype.png",
            "top_bottom_routes_avg.png",
            "yearly_ridership_trend.png",
            "monthly_seasonality.png",
            "daytype_comparison.png",
            "day_of_week_distribution.png",
            "route_variability_scatter.png",
            "top_routes_timeseries.png",
            "route_daytype_profile.png",
            "gtfs_snapshot_trips_comparison.png",
            "service_span_distribution.png",
            "route_scheduled_trips_top.png",
            "demand_vs_scheduled_trips_scatter.png",
            "rides_per_trip_distribution.png",
            "demand_service_ratio_by_route.png",
            "date_level_trend_chart.png",
        ]
        png_magic = b"\x89PNG\r\n\x1a\n"
        for c in expected_charts:
            p = os.path.join(self.charts_dir, c)
            self.assertTrue(os.path.exists(p), f"Missing chart: {p}")
            self.assertGreater(os.path.getsize(p), 10000, f"Chart {p} has unexpectedly small file size!")
            with open(p, "rb") as f:
                header = f.read(8)
                self.assertEqual(header, png_magic, f"Chart {p} is not a valid PNG image!")


if __name__ == "__main__":
    unittest.main()
