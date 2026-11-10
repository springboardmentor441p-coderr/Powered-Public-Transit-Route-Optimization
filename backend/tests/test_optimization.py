"""Tests for Schedule Optimization and Simulation."""

import unittest
from app.core.database import db
from ml.optimization import ScheduleSimulator, SimulationScenarioRequest


class TestOptimizationSimulator(unittest.TestCase):
    """Test suite for deterministic transit schedule simulation."""

    @classmethod
    def setUpClass(cls):
        df = db.get_table("route_features")
        cls.simulator = ScheduleSimulator(df)
        cls.sample_route_id = str(df.iloc[0]["route_id"])

    def test_frequency_increase_simulation(self):
        req = SimulationScenarioRequest(
            route_id=self.sample_route_id,
            scenario_name="25% Frequency Boost",
            frequency_multiplier=1.25,
        )
        res = self.simulator.simulate(req)

        self.assertEqual(res.route_id, self.sample_route_id)
        self.assertGreater(res.simulated_trips, res.baseline_trips)
        self.assertLess(res.simulated_headway_min, res.baseline_headway_min)
        # Compare fleet requirements
        self.assertGreaterEqual(res.simulated_vehicles_required, res.baseline_vehicles_required)
        self.assertGreater(len(res.comparisons), 5)
        self.assertGreater(len(res.schedule_derived_notes), 0)

    def test_stop_consolidation_simulation(self):
        req = SimulationScenarioRequest(
            route_id=self.sample_route_id,
            scenario_name="Stop Consolidation 20%",
            stop_consolidation_pct=20.0,
        )
        res = self.simulator.simulate(req)

        # One-way duration should decrease due to reduced dwell times
        self.assertLess(res.simulated_trip_duration_min, res.baseline_trip_duration_min)
        # Speed should increase
        self.assertGreater(res.simulated_speed_kmh, res.baseline_speed_kmh)

    def test_target_headway_simulation(self):
        req = SimulationScenarioRequest(
            route_id=self.sample_route_id,
            scenario_name="Set 15 Min Headway",
            target_headway_min=15.0,
        )
        res = self.simulator.simulate(req)
        self.assertEqual(res.simulated_headway_min, 15.0)


if __name__ == "__main__":
    unittest.main()

