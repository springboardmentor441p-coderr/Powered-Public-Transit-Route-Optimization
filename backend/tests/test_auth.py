import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.scripts.seed_data import main as seed_main

# Ensure the DB is seeded before tests run
@pytest.fixture(scope="module", autouse=True)
def seed_db():
    # Run the seed script (creates roles and admin user)
    seed_main()
    yield

client = TestClient(app)

admin_email = os.getenv("ADMIN_EMAIL", "admin@example.com")
admin_password = os.getenv("ADMIN_PASSWORD", "admin123")

def test_login_success():
    response = client.post("/auth/login", data={"username": admin_email, "password": admin_password})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    # Store token for later tests
    global admin_token
    admin_token = data["access_token"]

def test_me_endpoint():
    # Ensure login test ran first
    if "admin_token" not in globals():
        pytest.fail("admin_token not set – login test failed")
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = client.get("/auth/me", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == admin_email
    assert data["role"] == "admin"

def test_create_operator_user():
    # Admin creates a new operator user
    headers = {"Authorization": f"Bearer {admin_token}"}
    payload = {
        "email": "operator@example.com",
        "password": "operator123",
        "full_name": "Operator User",
        "role": "operator",
    }
    response = client.post("/auth/admin/users", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "operator@example.com"
    assert data["role"] == "operator"

def test_non_admin_cannot_create_user():
    # Login as the newly created operator
    login_resp = client.post("/auth/login", data={"username": "operator@example.com", "password": "operator123"})
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    # Attempt to create another user
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "email": "test2@example.com",
        "password": "test123",
        "full_name": "Test User",
        "role": "operator",
    }
    resp = client.post("/auth/admin/users", json=payload, headers=headers)
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Admin privileges required"

