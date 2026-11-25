import os
import sys
import unittest

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from app.main import app


class TestHealthEndpoint(unittest.TestCase):
    """Test suite for AI_RouteRanker API endpoints."""

    def setUp(self):
        self.client = TestClient(app)

    def test_health_check_endpoint(self):
        """Verify that GET /api/health returns 200 and expected status."""
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("AI_RouteRanker", data["project"])
        self.assertIn("timestamp", data)
        self.assertEqual(data["version"], "0.1.0")

    def test_root_endpoint(self):
        """Verify that GET / returns 200 and includes link to health check."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "online")
        self.assertEqual(data["health_check"], "/api/health")


if __name__ == "__main__":
    unittest.main()
