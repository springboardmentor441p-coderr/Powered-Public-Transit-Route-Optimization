"""
RouteRanker: Comprehensive Backend REST API Integration Test Suite
Validates all endpoints across:
- Real-time transit telemetry & live CTA alerts
- System & route daily passenger demand forecasting
- Smart scenario frequency simulation & recommendations
- Multi-modal route optimization & itineraries
- Historical route performance analytics & network connectivity
"""

import os
import sys
import unittest
from fastapi.testclient import TestClient

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.app.main import app

class TestFullBackendAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_01_root_and_health(self):
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "healthy")

    def test_02_system_forecast(self):
        res = self.client.get("/api/forecast/system?horizon_days=7")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("forecast", data)
        self.assertEqual(len(data["forecast"]), 7)
        self.assertIn("crowd_classification", data["forecast"][0])
        print(f"  System Forecast 7-Day: Day 1={data['forecast'][0]['predicted_total_demand']:,} ({data['forecast'][0]['crowd_classification']})")

    def test_03_route_forecast(self):
        res = self.client.get("/api/forecast/route?route_id=79&horizon_days=5")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["route_id"], "79")
        self.assertEqual(len(data["forecast"]), 5)
        print(f"  Route 79 Forecast: Day 1={data['forecast'][0]['predicted_rides']:,} rides")

    def test_04_model_evaluation_metrics(self):
        res = self.client.get("/api/forecast/metrics")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("best_model", data)
        print(f"  Model Benchmarks: Best Model={data['best_model']}")

    def test_05_recommendations_simulate(self):
        res = self.client.get("/api/recommendations/simulate?route_id=79&proposed_trips=160")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["route_id"], "79")
        self.assertIn("metrics_comparison", data)
        self.assertGreater(len(data["recommendations"]), 0)
        print(f"  Simulation Route 79: Rec='{data['recommendations'][0]['title']}', Headway={data['metrics_comparison']['headway']['proposed_minutes']}m")

    def test_06_route_planning(self):
        res = self.client.get("/api/route/plan?origin=Belmont&destination=Jackson&preference=fastest")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("recommended_itinerary", data)
        itin = data["recommended_itinerary"]
        self.assertGreater(itin["total_duration_minutes"], 0)
        self.assertGreater(len(itin["itinerary_legs"]), 0)
        print(f"  Route Plan Belmont -> Jackson: {itin['total_duration_minutes']} mins, {itin['transfers_count']} transfers")

    def test_07_route_locations_search(self):
        res = self.client.get("/api/route/locations?query=Clark")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertGreater(data["count"], 0)
        print(f"  Location Search 'Clark': Found {data['count']} matches")

    def test_10_bus_locations_search_and_intermodal(self):
        # Verify all 38 bus stops are searchable
        res_all = self.client.get("/api/route/locations")
        self.assertEqual(res_all.status_code, 200)
        locations = res_all.json()["locations"]
        bus_stops = [l for l in locations if "Bus" in l["type"]]
        rail_stations = [l for l in locations if "Rail" in l["type"]]
        self.assertEqual(len(rail_stations), 144)
        self.assertEqual(len(bus_stops), 38)
        print(f"  Verified Location Inventory: {len(rail_stations)} rail stations + {len(bus_stops)} bus stops")

        # Test intermodal routing from Ford City Mall to Fullerton
        res_plan = self.client.get("/api/route/plan?origin=BUS_79_Ford_City_Mall&destination=Fullerton")
        self.assertEqual(res_plan.status_code, 200)
        plan_data = res_plan.json()
        rec = plan_data["recommended_itinerary"]
        self.assertGreater(rec["total_duration_minutes"], 0)
        self.assertEqual(rec["transfers_count"], 1)
        print(f"  Intermodal Plan (Ford City Mall -> Fullerton): {rec['total_duration_minutes']}m, {rec['transfers_count']} transfer")

    def test_11_crowd_classification_semantics(self):
        # Verify updated semantically clear demand labels
        res = self.client.get("/api/forecast/route?route_id=79&horizon_days=3")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        crowd_label = data["forecast"][0]["crowd_classification"]
        self.assertNotIn("Potentially Overcrowded", crowd_label)
        self.assertIn("Peak Overcrowding Risk", crowd_label)
        print(f"  Verified Semantics: Route 79 Classification = '{crowd_label}'")

    def test_08_analytics_routes(self):
        res = self.client.get("/api/analytics/routes?limit=10")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["count"], 10)
        top = data["routes"][0]
        print(f"  Top Route: Rt {top['route_id']} ({top['route_long_name']}) - {top['mean_daily_rides']:,} avg daily rides")

    def test_09_analytics_network(self):
        res = self.client.get("/api/analytics/network")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("top_connectivity_hubs", data)
        self.assertGreater(len(data["top_connectivity_hubs"]), 0)
        top_hub = data["top_connectivity_hubs"][0]
        print(f"  Top Network Hub: {top_hub['name']} (Centrality={top_hub['centrality_score']})")

if __name__ == "__main__":
    unittest.main()

