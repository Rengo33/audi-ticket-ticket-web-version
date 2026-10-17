"""
Tests for health check and status endpoints.
"""
from fastapi.testclient import TestClient


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_health_check(self, client: TestClient):
        """Test the /api/health endpoint returns OK status."""
        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["version"] == "2.0.0"
        assert "app" in data

    def test_status_endpoint(self, client: TestClient):
        """Test the /api/status endpoint returns task info."""
        response = client.get("/api/status")

        assert response.status_code == 200
        data = response.json()
        assert "active_tasks" in data
        assert "task_ids" in data
        assert data["active_tasks"] == 0
        assert data["task_ids"] == []
