"""
tests/test_api_endpoints.py
Integration tests for FastAPI REST backend endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from backend.main import app

@pytest.fixture(scope="module")
def client():
    return TestClient(app)

def test_api_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["version"] == "2.0.0"

def test_api_coverage(client):
    res = client.get("/api/data/coverage")
    assert res.status_code == 200
    data = res.json()
    assert data["total_historical_records"] >= 1_120_000
    assert data["gtfs_bus_routes_count"] == 124
    assert data["temporal_gap_days"] == 42

def test_api_routes_list(client):
    res = client.get("/api/routes")
    assert res.status_code == 200
    data = res.json()
    assert data["count"] == 124
    assert len(data["routes"]) == 124

def test_api_route_history(client):
    res = client.get("/api/routes/79/history?limit=10")
    assert res.status_code == 200
    data = res.json()
    assert data["route"] == "79"
    assert len(data["history"]) == 10

def test_api_rankings_filter(client):
    res = client.get("/api/rankings?tier=Tier%201")
    assert res.status_code == 200
    data = res.json()
    assert data["count"] == 31
    for item in data["rankings"]:
        assert "Tier 1" in item["review_priority"]

def test_api_forecasts(client):
    res = client.get("/api/forecasts?route=79&limit=15")
    assert res.status_code == 200
    data = res.json()
    assert len(data["predictions"]) == 15
    assert "XGBoost" in data["metrics_summary"]

def test_api_scenario_post(client):
    payload = {
        "route_id": "8",
        "percent_trip_change": 25.0,
        "elasticity": 0.42,
        "cost_per_trip": 85.0
    }
    res = client.post("/api/scenarios", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["route_id"] == "8"
    assert data["simulated_weekday_rides"] > data["base_weekday_rides"]
    assert data["delta_trips"] > 0

def test_api_overlap(client):
    res = client.get("/api/overlap?route=49&min_jaccard=0.1")
    assert res.status_code == 200
    data = res.json()
    assert data["count"] > 0
