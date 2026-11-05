"""Authentication tests."""
import pytest
from httpx import AsyncClient


class TestAuth:
    """Authentication tests."""

    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient):
        """Test successful login."""
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": "admin@metroflow.com", "password": "admin123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self, client: AsyncClient):
        """Test login with invalid credentials."""
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": "invalid@metroflow.com", "password": "wrongpassword"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_me_with_valid_token(self, client: AsyncClient):
        """Test getting current user with valid token."""
        # First login
        login_response = await client.post(
            "/api/v1/auth/login",
            data={"username": "admin@metroflow.com", "password": "admin123"},
        )
        token = login_response.json()["access_token"]

        # Get current user
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "admin@metroflow.com"
        assert data["role"] == "admin"

    @pytest.mark.asyncio
    async def test_get_me_without_token(self, client: AsyncClient):
        """Test getting current user without token."""
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_token(self, client: AsyncClient):
        """Test refreshing access token."""
        # First login
        login_response = await client.post(
            "/api/v1/auth/login",
            data={"username": "admin@metroflow.com", "password": "admin123"},
        )
        refresh_token = login_response.json()["refresh_token"]

        # Refresh token
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    @pytest.mark.asyncio
    async def test_logout(self, client: AsyncClient):
        """Test logout."""
        # First login
        login_response = await client.post(
            "/api/v1/auth/login",
            data={"username": "admin@metroflow.com", "password": "admin123"},
        )
        refresh_token = login_response.json()["refresh_token"]

        # Logout
        response = await client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 200


class TestStations:
    """Station tests."""

    @pytest.mark.asyncio
    async def test_list_stations(self, client: AsyncClient):
        """Test listing stations."""
        # Login first
        login_response = await client.post(
            "/api/v1/auth/login",
            data={"username": "admin@metroflow.com", "password": "admin123"},
        )
        token = login_response.json()["access_token"]

        response = await client.get(
            "/api/v1/stations",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_list_lines(self, client: AsyncClient):
        """Test listing lines."""
        login_response = await client.post(
            "/api/v1/auth/login",
            data={"username": "admin@metroflow.com", "password": "admin123"},
        )
        token = login_response.json()["access_token"]

        response = await client.get(
            "/api/v1/stations/lines",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestTrains:
    """Train tests."""

    @pytest.mark.asyncio
    async def test_list_trains(self, client: AsyncClient):
        """Test listing trains."""
        login_response = await client.post(
            "/api/v1/auth/login",
            data={"username": "admin@metroflow.com", "password": "admin123"},
        )
        token = login_response.json()["access_token"]

        response = await client.get(
            "/api/v1/trains",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestHealth:
    """Health check tests."""

    @pytest.mark.asyncio
    async def test_health_check(self, client: AsyncClient):
        """Test health check endpoint."""
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "app" in data
        assert "version" in data