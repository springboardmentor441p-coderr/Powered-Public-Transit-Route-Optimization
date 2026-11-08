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
def admin_headers():
    seed_main()
    login_resp = client.post("/auth/login", data={"username": admin_email, "password": admin_password})
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture(scope="module")
def operator_headers(admin_headers):
    # Ensure operator user exists
    client.post(
        "/auth/admin/users",
        json={"email": "op_test@example.com", "password": "op_password", "role": "operator"},
        headers=admin_headers
    )
    login_resp = client.post("/auth/login", data={"username": "op_test@example.com", "password": "op_password"})
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

# ==============================================================================
# MILESTONE 3 TESTS: Alerts, Notifications, Emergency Announcements, Updates
# ==============================================================================

def test_alerts_lifecycle(admin_headers):
    # Create alert
    create_resp = client.post(
        "/alerts",
        json={
            "title": "Platform Congestion Alert",
            "category": "CONGESTION_INDICATOR",
            "severity": "WARNING",
            "message": "Platform crowd exceeds 75% at Central Interchange."
        },
        headers=admin_headers
    )
    assert create_resp.status_code == 200
    alert_id = create_resp.json()["id"]

    # List alerts
    list_resp = client.get("/alerts?status=ACTIVE", headers=admin_headers)
    assert list_resp.status_code == 200
    assert any(a["id"] == alert_id for a in list_resp.json())

    # Acknowledge
    ack_resp = client.post(f"/alerts/{alert_id}/acknowledge", headers=admin_headers)
    assert ack_resp.status_code == 200
    assert ack_resp.json()["status"] == "ACKNOWLEDGED"

    # Resolve
    res_resp = client.post(f"/alerts/{alert_id}/resolve", headers=admin_headers)
    assert res_resp.status_code == 200
    assert res_resp.json()["status"] == "RESOLVED"

def test_notifications_workflow(admin_headers):
    # Create notification
    create_resp = client.post(
        "/notifications",
        json={
            "title": "Shift Handover Notice",
            "message": "Evening rush hour dispatch protocol activated.",
            "category": "OPERATIONAL",
            "severity": "INFO"
        },
        headers=admin_headers
    )
    assert create_resp.status_code == 200
    notif_id = create_resp.json()["id"]

    # Unread count
    count_resp = client.get("/notifications/unread-count", headers=admin_headers)
    assert count_resp.status_code == 200
    assert count_resp.json()["unread_count"] >= 1

    # Mark read
    read_resp = client.post(f"/notifications/{notif_id}/read", headers=admin_headers)
    assert read_resp.status_code == 200
    assert read_resp.json()["is_read"] is True

def test_emergency_announcements(admin_headers, operator_headers):
    # Admin creates emergency announcement
    create_resp = client.post(
        "/announcements",
        json={
            "title": "Severe Weather Precautionary Slowdown",
            "message": "Maximum track speed reduced to 40 km/h due to torrential rain.",
            "severity": "SEVERE"
        },
        headers=admin_headers
    )
    assert create_resp.status_code == 200
    ann_id = create_resp.json()["id"]

    # Active announcements
    active_resp = client.get("/announcements/active", headers=operator_headers)
    assert active_resp.status_code == 200
    assert any(a["id"] == ann_id for a in active_resp.json())

    # Non-admin cannot create announcement
    forbidden_resp = client.post(
        "/announcements",
        json={"title": "Unauthorized", "message": "Test"},
        headers=operator_headers
    )
    assert forbidden_resp.status_code == 403

    # Admin deactivates
    deact_resp = client.post(f"/announcements/{ann_id}/deactivate", headers=admin_headers)
    assert deact_resp.status_code == 200
    assert deact_resp.json()["is_active"] is False

def test_operational_schedule_updates(operator_headers):
    # Create operational schedule update
    resp = client.post(
        "/schedule-updates",
        json={
            "route_id": "100",
            "update_type": "DELAY",
            "description": "Signal malfunction causing 10m delay near junction.",
            "delay_minutes": 10
        },
        headers=operator_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["route_id"] == "100"
    assert data["delay_minutes"] == 10

    # List updates
    list_resp = client.get("/schedule-updates?route_id=100", headers=operator_headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) > 0

def test_service_intensity_heatmap_and_insights(admin_headers):
    # Service intensity heatmap
    hm_resp = client.get("/analytics/heatmap/service-intensity?limit=10", headers=admin_headers)
    assert hm_resp.status_code == 200
    points = hm_resp.json()
    assert len(points) > 0
    assert "scheduled_departures_per_day" in points[0]
    assert "service_intensity_ratio" in points[0]

    # Operational insights
    insights_resp = client.get("/analytics/insights", headers=admin_headers)
    assert insights_resp.status_code == 200
    insights = insights_resp.json()["insights"]
    assert len(insights) >= 3
    assert "data_basis" in insights[0]

