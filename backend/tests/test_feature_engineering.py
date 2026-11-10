"""Tests for Route Feature Engineering."""

import unittest
from data_processing.feature_engineering import RouteFeatureEngineer
from app.core.database import db


class TestFeatureEngineering(unittest.TestCase):
    """Test suite for schedule-derived operational feature engineering."""

    @classmethod
    def setUpClass(cls):
        engineer = RouteFeatureEngineer()
        cls.features_df = engineer.build_features()

    def test_features_shape_and_columns(self):
        self.assertFalse(self.features_df.empty)
        self.assertGreater(len(self.features_df), 4000)

        required_cols = [
            "route_id",
            "route_short_name",
            "total_trips",
            "service_span_hours",
            "avg_trip_duration_min",
            "stop_count",
            "estimated_distance_km",
            "avg_speed_kmh",
            "avg_headway_min",
            "headway_cv",
            "direction_balance_ratio",
            "high_frequency_flag",
            "data_source",
        ]
        for col in required_cols:
            self.assertIn(col, self.features_df.columns)

    def test_no_fabricated_ridership_data(self):
        # Confirm critical rule: Never fabricate passenger counts, congestion, or ridership data
        forbidden_substrings = ["passenger_count", "ridership", "ticket_sales", "congestion_index"]
        for col in self.features_df.columns:
            for forbidden in forbidden_substrings:
                self.assertNotIn(forbidden, col.lower())

    def test_provenance_marking(self):
        self.assertTrue((self.features_df["data_source"] == "GTFS_Timetable_Schedule_Derived").all())

    def test_metric_sanity_ranges(self):
        # Service span must be between 0 and 24 hours
        self.assertTrue((self.features_df["service_span_hours"] >= 0.0).all())
        self.assertTrue((self.features_df["service_span_hours"] <= 24.0).all())
        # Speed should be positive
        self.assertTrue((self.features_df["avg_speed_kmh"] > 0.0).all())


if __name__ == "__main__":
    unittest.main()

