import os
import sys
import pytest
from fastapi.testclient import TestClient

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from backend.app.main import app
from backend.scripts.seed_data import main as seed_main

client = TestClient(app)

admin_email = os.getenv("ADMIN_EMAIL", "admin@example.com")
admin_password = os.getenv("ADMIN_PASSWORD", "admin123")

@pytest.fixture(scope="module")
def auth_headers():
    seed_main()
    login_resp = client.post("/auth/login", data={"username": admin_email, "password": admin_password})
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

# ==============================================================================
# MILESTONE 1 TESTS: Architecture, Auth, GTFS Dashboard & Crowd Monitoring
# ==============================================================================

def test_health_check():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"

def test_dashboard_summary_with_gtfs(auth_headers):
    resp = client.get("/dashboard/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["routes"] > 0
    assert data["stops"] > 0
    assert data["trips"] > 0
    assert data["stop_times"] > 0

def test_crowd_monitoring_live(auth_headers):
    resp = client.get("/crowd/live?limit=10", headers=auth_headers)
    assert resp.status_code == 200
    stations = resp.json()
    assert isinstance(stations, list)
    if stations:
        st = stations[0]
        assert "stop_id" in st
        assert "passenger_density_percent" in st
        assert "crowd_level" in st
        assert "inflow_rate" in st

def test_crowd_congestion_overview(auth_headers):
    resp = client.get("/crowd/congestion", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "network_congestion_index" in data
    assert "average_passenger_density_percent" in data
    assert "bottlenecks" in data

def test_crowd_heatmap_generation(auth_headers):
    resp = client.get("/crowd/heatmap", headers=auth_headers)
    assert resp.status_code == 200
    points = resp.json()
    assert isinstance(points, list)

# ==============================================================================
# MILESTONE 2 TESTS: Scheduling, Frequency Optimization, AI Forecasting, Monitor
# ==============================================================================

def test_schedule_routes_and_trips(auth_headers):
    routes_resp = client.get("/schedule/routes?limit=5", headers=auth_headers)
    assert routes_resp.status_code == 200
    routes = routes_resp.json()
    assert len(routes) > 0
    route_id = routes[0]["route_id"]

    trips_resp = client.get(f"/schedule/trips?route_id={route_id}&limit=5", headers=auth_headers)
    assert trips_resp.status_code == 200
    trips = trips_resp.json()
    assert isinstance(trips, list)

def test_trip_timetable(auth_headers):
    # Fetch first trip
    trips_resp = client.get("/schedule/trips?limit=1", headers=auth_headers)
    assert trips_resp.status_code == 200
    trips = trips_resp.json()
    if trips:
        trip_id = trips[0]["trip_id"]
        tt_resp = client.get(f"/schedule/timetable/{trip_id}", headers=auth_headers)
        assert tt_resp.status_code == 200
        timetable = tt_resp.json()
        assert len(timetable) > 0
        assert "arrival_time" in timetable[0]
        assert "stop_name" in timetable[0]

def test_delay_management(auth_headers):
    # Fetch delays
    delays_resp = client.get("/schedule/delays", headers=auth_headers)
    assert delays_resp.status_code == 200

    # Report a new delay
    report_resp = client.post(
        "/schedule/delays",
        json={"trip_id": "TEST_TRIP_1", "delay_minutes": 12},
        headers=auth_headers
    )
    assert report_resp.status_code == 200
    assert report_resp.json()["delay_minutes"] == 12

def test_frequency_recommendations(auth_headers):
    resp = client.get("/scheduling/frequency/recommendations?limit=3", headers=auth_headers)
    assert resp.status_code == 200
    recs = resp.json()
    assert len(recs) > 0
    assert "recommended_peak_headway_minutes" in recs[0]
    assert "projected_overcrowding_reduction_percent" in recs[0]

def test_schedule_scenario_creation_and_listing(auth_headers):
    # First get a valid route_id
    routes_resp = client.get("/schedule/routes?limit=1", headers=auth_headers)
    route_id = routes_resp.json()[0]["route_id"]

    # Create scenario
    create_resp = client.post(
        "/scheduling/scenarios",
        json={
            "scenario_name": "Morning Peak Surge Relief Plan",
            "route_id": route_id,
            "target_headway_minutes": 4,
            "peak_start_time": "07:30:00",
            "peak_end_time": "09:30:00"
        },
        headers=auth_headers
    )
    assert create_resp.status_code == 200
    scenario = create_resp.json()
    assert scenario["scenario_name"] == "Morning Peak Surge Relief Plan"
    assert scenario["target_headway_minutes"] == 4

    # List scenarios
    list_resp = client.get("/scheduling/scenarios", headers=auth_headers)
    assert list_resp.status_code == 200
    scenarios = list_resp.json()
    assert len(scenarios) > 0

def test_realtime_operational_monitoring(auth_headers):
    # Live status
    status_resp = client.get("/monitor/live-status", headers=auth_headers)
    assert status_resp.status_code == 200
    data = status_resp.json()
    assert "total_active_trains" in data
    assert "on_time_performance_percent" in data

    # Train status list
    trains_resp = client.get("/monitor/trains?limit=5", headers=auth_headers)
    assert trains_resp.status_code == 200
    trains = trains_resp.json()
    assert isinstance(trains, list)

def test_ai_crowd_and_demand_prediction(auth_headers):
    # Test single prediction
    pred_resp = client.post(
        "/predict/crowd",
        json={"hour": 8, "day_of_week": 1, "stop_sequence": 10, "route_type": 1, "scheduled_frequency": 5},
        headers=auth_headers
    )
    assert pred_resp.status_code == 200
    data = pred_resp.json()
    assert "predicted_crowd_density_percent" in data
    assert "predicted_passenger_demand_footfall" in data
    assert "congestion_risk" in data
    assert data["is_peak_hour"] is True

    # Test 24-hour forecast
    forecast_resp = client.get("/predict/demand?day_of_week=2", headers=auth_headers)
    assert forecast_resp.status_code == 200
    curve = forecast_resp.json()
    assert len(curve) == 24

    # Test AI recommendations
    recs_resp = client.get("/predict/recommendations", headers=auth_headers)
    assert recs_resp.status_code == 200
    assert len(recs_resp.json()) > 0

def test_traffic_analysis_reports(auth_headers):
    # JSON report
    report_resp = client.get("/analytics/traffic-report", headers=auth_headers)
    assert report_resp.status_code == 200
    data = report_resp.json()
    assert "transit_network_metrics" in data
    assert "crowd_and_congestion_metrics" in data
    assert "operational_and_punctuality_metrics" in data

    # Markdown report
    md_resp = client.get("/analytics/traffic-report/markdown", headers=auth_headers)
    assert md_resp.status_code == 200
    assert "# MetroFlow Public Transit Traffic Analysis Report" in md_resp.text

