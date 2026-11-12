"""
RouteRanker: Phase 5 Real-Time API Test Suite
Tests:
1. Live CTA Customer Alerts Client (Official endpoint transitchicago.com)
2. CTA Bus Tracker Client & Fallback Telemetry
3. CTA Train Tracker Client & Fallback Telemetry
4. In-Memory Transit Cache & Freshness TTL
5. FastAPI Transit Endpoints via TestClient
"""

import os
import sys
import unittest
from fastapi.testclient import TestClient

# Ensure root directory is on PYTHONPATH
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.app.main import app
from backend.app.services.cta_alerts_client import cta_alerts_client
from backend.app.services.cta_bus_client import cta_bus_client
from backend.app.services.cta_train_client import cta_train_client
from backend.app.services.transit_cache import global_transit_cache

class TestRealTimeAPIs(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_01_live_cta_alerts_client(self):
        print("\n[Test 1] Testing Official Live CTA Customer Alerts API...")
        alerts = cta_alerts_client.get_live_alerts()
        self.assertIsInstance(alerts, list)
        self.assertGreater(len(alerts), 0, "Should retrieve active CTA alerts from transitchicago.com")
        
        sample = alerts[0]
        print(f"  Retrieved {len(alerts)} live alerts. Sample headline: '{sample.headline}'")
        self.assertTrue(sample.alert_id)
        self.assertTrue(sample.headline)

    def test_02_bus_positions_and_metadata(self):
        print("\n[Test 2] Testing Bus Vehicle Positions Client & Metadata...")
        vehicles, meta = cta_bus_client.get_vehicle_positions(route_id="79")
        self.assertIsInstance(vehicles, list)
        self.assertGreater(len(vehicles), 0)
        
        sample = vehicles[0]
        self.assertEqual(sample.route_id, "79")
        self.assertTrue(sample.latitude > 41.0 and sample.latitude < 43.0, "Latitude should be within Chicago bounds")
        self.assertTrue(sample.longitude < -87.0 and sample.longitude > -89.0, "Longitude should be within Chicago bounds")
        self.assertIn(meta.data_source, ["LIVE_CTA_API", "GTFS_SCHEDULE_DERIVED"])
        print(f"  Bus 79 positions: {len(vehicles)} vehicles. Data source: {meta.data_source}")

    def test_03_train_positions_and_metadata(self):
        print("\n[Test 3] Testing Train Tracker Client & Line Telemetry...")
        trains, meta = cta_train_client.get_train_positions(line_name="Red")
        self.assertIsInstance(trains, list)
        self.assertGreater(len(trains), 0)
        
        sample = trains[0]
        self.assertEqual(sample.line_name, "Red")
        self.assertTrue(sample.run_number)
        self.assertIn(meta.data_source, ["LIVE_CTA_API", "GTFS_SCHEDULE_DERIVED"])
        print(f"  Red Line trains: {len(trains)} active trains. Data source: {meta.data_source}")

    def test_04_train_arrivals_at_hub_station(self):
        print("\n[Test 4] Testing Station Platform Arrival Predictions...")
        # 41700 is Washington/Wabash Loop station
        arrivals, meta = cta_train_client.get_station_arrivals(station_id="41700")
        self.assertIsInstance(arrivals, list)
        self.assertGreater(len(arrivals), 0)
        
        sample = arrivals[0]
        print(f"  Arrival prediction for {sample.station_name}: {sample.line_name} Line train in {sample.countdown_minutes} mins")
        self.assertTrue(sample.countdown_minutes >= 0)

    def test_05_in_memory_transit_cache(self):
        print("\n[Test 5] Testing Transit Cache Hit & TTL Freshness...")
        key = "test_key_phase5"
        global_transit_cache.set(key, {"sample": "data"}, ttl=5)
        
        cached = global_transit_cache.get(key)
        self.assertIsNotNone(cached)
        val, updated_at = cached
        self.assertEqual(val["sample"], "data")
        self.assertTrue(updated_at.endswith("Z"))
        print(f"  Cache validated. Timestamp: {updated_at}")

    def test_06_fastapi_endpoints(self):
        print("\n[Test 6] Testing FastAPI REST Endpoints...")
        
        # /health
        res_health = self.client.get("/health")
        self.assertEqual(res_health.status_code, 200)
        self.assertEqual(res_health.json()["status"], "healthy")
        
        # /api/transit/status
        res_status = self.client.get("/api/transit/status")
        self.assertEqual(res_status.status_code, 200)
        status_data = res_status.json()
        print(f"  System Status: {status_data['data_source_mode']}, Alerts: {status_data['active_alerts_count']}")
        self.assertTrue("Live vehicle positions show spatial vehicle locations only" in status_data["disclaimer"])
        
        # /api/transit/bus/vehicles
        res_bus = self.client.get("/api/transit/bus/vehicles?route=66")
        self.assertEqual(res_bus.status_code, 200)
        self.assertGreater(res_bus.json()["count"], 0)
        
        # /api/transit/train/positions
        res_train = self.client.get("/api/transit/train/positions?line=Blue")
        self.assertEqual(res_train.status_code, 200)
        self.assertGreater(res_train.json()["count"], 0)
        
        # /api/transit/alerts
        res_alerts = self.client.get("/api/transit/alerts")
        self.assertEqual(res_alerts.status_code, 200)
        self.assertGreater(len(res_alerts.json()["alerts"]), 0)
        
        # /api/transit/stations
        res_st = self.client.get("/api/transit/stations")
        self.assertEqual(res_st.status_code, 200)
        self.assertEqual(res_st.json()["count"], 144)
        print("  All FastAPI transit endpoints responded with HTTP 200 and valid schemas.")

if __name__ == "__main__":
    unittest.main()

