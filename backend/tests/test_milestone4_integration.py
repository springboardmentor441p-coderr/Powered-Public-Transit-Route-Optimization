"""Milestone 4 Comprehensive Integration & Verification Test Suite.
Validates full end-to-end system interoperability across all modules:
Authentication, Ingestion, Monitoring, Scheduling, AI Prediction,
Alerts, Notifications, Analytics, and API documentation.
"""

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
def admin_token():
    seed_main()
    resp = client.post("/auth/login", data={"username": admin_email, "password": admin_password})
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    return resp.json()["access_token"]

@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}

# ==============================================================================
# MILESTONE 4 TESTS: Comprehensive Verification & End-to-End Interoperability
# ==============================================================================

def test_openapi_schema_completeness():
    """Verify OpenAPI spec is generated with all required paths and tags."""
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    assert "paths" in schema
    assert "/health" in schema["paths"]
    assert "/dashboard/summary" in schema["paths"]
    assert "/crowd/live" in schema["paths"]
    assert "/schedule/routes" in schema["paths"]
    assert "/scheduling/frequency/recommendations" in schema["paths"]
    assert "/predict/crowd" in schema["paths"]
    assert "/alerts" in schema["paths"]
    assert "/notifications" in schema["paths"]
    assert "/announcements/active" in schema["paths"]
    assert "/schedule-updates" in schema["paths"]
    assert "/analytics/traffic-report" in schema["paths"]

def test_frontend_mount_or_fallback():
    """Verify that root URL returns HTTP 200 with HTML content."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert len(resp.text) > 100

def test_e2e_operator_delegation(auth_headers):
    """Admin creates operator -> operator logs in -> operator accesses protected APIs."""
    unique_email = "e2e_operator@example.com"
    client.post(
        "/auth/admin/users",
        json={"email": unique_email, "password": "secure_password_123", "full_name": "E2E Operator", "role": "operator"},
        headers=auth_headers
    )
    
    # Login as new operator
    login_resp = client.post("/auth/login", data={"username": unique_email, "password": "secure_password_123"})
    assert login_resp.status_code == 200
    op_token = login_resp.json()["access_token"]
    op_headers = {"Authorization": f"Bearer {op_token}"}

    # Verify operator profile
    me_resp = client.get("/auth/me", headers=op_headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["role"] == "operator"

    # Operator performs schedule update on a genuine GTFS route
    update_resp = client.post(
        "/schedule-updates",
        json={
            "route_id": "100",
            "update_type": "EXTRA_SERVICE",
            "description": "Supplemental morning peak shuttle dispatched.",
            "delay_minutes": 0
        },
        headers=op_headers
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["created_by"] == unique_email

def test_gtfs_relational_data_integrity(auth_headers):
    """Verify GTFS relationships: routes -> trips -> timetables."""
    # Fetch active routes
    routes_resp = client.get("/schedule/routes?limit=5", headers=auth_headers)
    assert routes_resp.status_code == 200
    routes = routes_resp.json()
    assert len(routes) > 0
    route_id = routes[0]["route_id"]

    # Fetch trips for that route
    trips_resp = client.get(f"/schedule/trips?route_id={route_id}&limit=5", headers=auth_headers)
    assert trips_resp.status_code == 200
    trips = trips_resp.json()
    if len(trips) > 0:
        trip_id = trips[0]["trip_id"]
        # Fetch timetable for that trip
        tt_resp = client.get(f"/schedule/timetable/{trip_id}", headers=auth_headers)
        assert tt_resp.status_code == 200
        timetable = tt_resp.json()
        assert isinstance(timetable, list)
        if len(timetable) > 0:
            assert "stop_sequence" in timetable[0]
            assert "arrival_time" in timetable[0]

def test_ai_prediction_boundary_conditions(auth_headers):
    """Test AI demand predictor with valid and edge hour/day combinations."""
    # Morning rush peak
    rush_resp = client.post("/predict/crowd", json={"hour": 8, "day_of_week": 1}, headers=auth_headers)
    assert rush_resp.status_code == 200
    rush_data = rush_resp.json()
    assert rush_data["predicted_crowd_density_percent"] > 0

    # Late night lull
    night_resp = client.post("/predict/crowd", json={"hour": 23, "day_of_week": 6}, headers=auth_headers)
    assert night_resp.status_code == 200
    night_data = night_resp.json()
    assert night_data["predicted_crowd_density_percent"] < rush_data["predicted_crowd_density_percent"]

def test_unauthenticated_access_is_rejected():
    """Verify that protected operational endpoints reject unauthenticated access with 401."""
    assert client.get("/crowd/live").status_code == 401
    assert client.get("/alerts").status_code == 401
    assert client.get("/notifications").status_code == 401
    assert client.get("/announcements/active").status_code == 401
    assert client.get("/schedule-updates").status_code == 401
    assert client.get("/analytics/traffic-report").status_code == 401

def test_admin_list_users(auth_headers):
    """Verify admin can list registered users and roles."""
    resp = client.get("/auth/admin/users", headers=auth_headers)
    assert resp.status_code == 200
    users = resp.json()
    assert isinstance(users, list)
    assert len(users) > 0
    assert any(u["role"] == "admin" for u in users)

def test_system_performance_metrics(auth_headers):
    """Verify system performance metrics endpoint matching PDF specification Section 8 & 9."""
    resp = client.get("/monitor/metrics", headers=auth_headers)
    assert resp.status_code == 200
    metrics = resp.json()
    assert "crowd_monitoring_performance" in metrics
    assert "scheduling_performance" in metrics
    assert "ai_prediction_performance" in metrics
    assert "system_performance" in metrics
    assert metrics["crowd_monitoring_performance"]["passenger_density_estimation_accuracy_percent"] > 90
    assert metrics["scheduling_performance"]["fleet_on_time_performance_percent"] > 0
    assert metrics["ai_prediction_performance"]["model_r2_score"] > 0.85

def test_ai_smart_recommendations(auth_headers):
    """Verify AI smart operational recommendations endpoint."""
    resp = client.get("/predict/recommendations", headers=auth_headers)
    assert resp.status_code == 200
    recs = resp.json()
    assert isinstance(recs, list)
    assert len(recs) >= 3
    assert "recommended_action" in recs[0]
    assert "projected_benefit" in recs[0]

