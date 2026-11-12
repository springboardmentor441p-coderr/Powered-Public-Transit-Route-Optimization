"""
RouteRanker: Release Gate & Acceptance Validation Test Suite
Validates:
- Dynamic forecast date generation
- Statistical interval methodology & non-negativity
- Transit route planner benchmarks & consistent stop counts (including Belmont -> Jackson)
- Mathematical integrity of Smart Scenario KPI calculations
"""

import unittest
from datetime import date, timedelta
from route_optimization.route_planner import cta_route_planner
from ml.forecasting.demand_forecast_service import demand_forecast_service
from backend.app.services.smart_recommendations import smart_recommendation_engine
from backend.app.services.cta_alerts_client import cta_alerts_client

class TestReleaseGateAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cta_route_planner._load_graph()

    def test_01_dynamic_forecast_dates(self):
        """Forecast dates must start dynamically from current date + 1, not hardcoded."""
        fc = demand_forecast_service.get_system_forecast(horizon_days=14)
        today = date.today()
        expected_start = (today + timedelta(days=1)).strftime("%Y-%m-%d")
        expected_end = (today + timedelta(days=14)).strftime("%Y-%m-%d")
        
        self.assertEqual(fc["forecast_start"], expected_start)
        self.assertEqual(fc["forecast_end"], expected_end)
        self.assertEqual(len(fc["forecast"]), 14)
        self.assertEqual(fc["latest_historical_date"], "2026-08-31")
        
        for record in fc["forecast"]:
            self.assertGreater(record["predicted_total_demand"], 0)
            self.assertGreaterEqual(record["lower_ci_95"], 100000)
            self.assertGreater(record["upper_ci_95"], record["predicted_total_demand"])
            self.assertLess(record["lower_ci_95"], record["predicted_total_demand"])

    def test_02_route_benchmarks_and_consistent_stop_counts(self):
        """
        Validate 5 transit routes.
        Verify that stop counts represent traversed stations (hops) excluding origin boarding stop:
        Belmont -> Jackson has 8 traversed stops (Fullerton, North/Clybourn, Clark/Division, Chicago, Grand, Lake, Monroe, Jackson).
        Total nodes along path = 9.
        """
        # 1. Belmont -> Jackson (Direct Red Line)
        res1 = cta_route_planner.plan_route("Belmont", "Jackson")
        p1 = res1["recommended_itinerary"]
        self.assertEqual(p1["total_stops"], 8)
        self.assertEqual(p1["transfers_count"], 0)
        self.assertAlmostEqual(p1["total_duration_minutes"], 17.1, places=1)
        self.assertEqual(len(p1["waypoints"]), 9)

        # 2. 79th -> Fullerton (Direct Red Line)
        res2 = cta_route_planner.plan_route("79th", "Fullerton")
        p2 = res2["recommended_itinerary"]
        self.assertEqual(p2["total_stops"], 16)
        self.assertEqual(p2["transfers_count"], 0)
        self.assertAlmostEqual(p2["total_duration_minutes"], 41.2, places=1)

        # 3. Ford City Mall -> Fullerton (Intermodal Bus + Transfer + Rail)
        res3 = cta_route_planner.plan_route("Ford City Mall", "Fullerton")
        p3 = res3["recommended_itinerary"]
        self.assertEqual(p3["transfers_count"], 1)
        self.assertAlmostEqual(p3["total_duration_minutes"], 80.5, places=1)

        # 4. Howard -> 95th/Dan Ryan (Entire Red Line Spine)
        res4 = cta_route_planner.plan_route("Howard", "95th/Dan Ryan")
        p4 = res4["recommended_itinerary"]
        self.assertEqual(p4["total_stops"], 32)
        self.assertEqual(p4["transfers_count"], 0)
        self.assertAlmostEqual(p4["total_duration_minutes"], 72.0, places=1)

        # 5. O'Hare -> Clark/Lake (Blue Line Airport Express)
        res5 = cta_route_planner.plan_route("O'Hare", "Clark/Lake")
        p5 = res5["recommended_itinerary"]
        self.assertEqual(p5["total_stops"], 16)
        self.assertEqual(p5["transfers_count"], 0)
        self.assertAlmostEqual(p5["total_duration_minutes"], 49.4, places=1)

    def test_03_smart_scenario_kpis_mathematical_consistency(self):
        """Validate exact mathematical consistency of Smart Scenario KPIs."""
        sim = smart_recommendation_engine.simulate_frequency_scenario("79", proposed_trips=160)
        base = sim["baseline"]
        prop = sim["simulation"]
        
        # Nominal daily capacity = trips * 60
        self.assertEqual(base["baseline_daily_capacity"], base["scheduled_daily_trips"] * 60)
        self.assertEqual(prop["total_daily_capacity"], prop["proposed_trips"] * 60)
        
        # Headway = 1080 service minutes / trips
        self.assertAlmostEqual(base["baseline_headway_minutes"], round(1080.0 / base["scheduled_daily_trips"], 1))
        self.assertAlmostEqual(prop["operating_headway_minutes"], round(1080.0 / prop["proposed_trips"], 1))
        
        # Boardings per scheduled trip
        demand = sim["metrics_comparison"]["passenger_loading_intensity"]["projected_daily_demand"]
        self.assertAlmostEqual(base["baseline_boardings_per_trip"], round(demand / base["scheduled_daily_trips"], 1))
        self.assertAlmostEqual(prop["estimated_boardings_per_trip"], round(demand / prop["proposed_trips"], 1))
        
        # Boarding ratio relative to nominal capacity
        self.assertAlmostEqual(base["baseline_boarding_ratio"], round((base["baseline_boardings_per_trip"] / 60) * 100, 1))
        self.assertAlmostEqual(prop["estimated_boarding_ratio"], round((prop["estimated_boardings_per_trip"] / 60) * 100, 1))

    def test_04_live_cta_alerts_freshness(self):
        """Verify official CTA live alerts are fetched and structured."""
        alerts = cta_alerts_client.get_live_alerts()
        self.assertIsInstance(alerts, list)
        self.assertGreater(len(alerts), 0)
        self.assertTrue(hasattr(alerts[0], "headline"))
        self.assertTrue(hasattr(alerts[0], "alert_id"))

if __name__ == "__main__":
    unittest.main()

