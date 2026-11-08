import os
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

# Obtain admin token (uses env vars set in docker-compose)
admin_email = os.getenv("ADMIN_EMAIL", "admin@example.com")
admin_password = os.getenv("ADMIN_PASSWORD", "admin123")

@pytest.fixture(scope="module")
def admin_token():
    resp = client.post("/auth/login", data={"username": admin_email, "password": admin_password})
    assert resp.status_code == 200
    return resp.json()["access_token"]

def test_ensemble_success(admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    payload = {"route_id": "R101", "hour": 10, "day_of_week": 1}
    resp = client.post("/ensemble/ensemble", json=payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "predicted_value" in data
    assert "confidence_interval" in data
    ci = data["confidence_interval"]
    assert isinstance(ci, list) or isinstance(ci, tuple)
    assert len(ci) == 2
    assert all(isinstance(v, (int, float)) for v in ci)

def test_ensemble_invalid_hour(admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    payload = {"route_id": "R101", "hour": 30, "day_of_week": 1}
    resp = client.post("/ensemble/ensemble", json=payload, headers=headers)
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Hour must be between 0 and 23"

def test_ensemble_invalid_day(admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    payload = {"route_id": "R101", "hour": 10, "day_of_week": 9}
    resp = client.post("/ensemble/ensemble", json=payload, headers=headers)
    assert resp.status_code == 400
    assert resp.json()["detail"] == "day_of_week must be between 0 (Mon) and 6 (Sun)"

