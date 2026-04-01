"""
Tests for authentication endpoints.
"""
from fastapi.testclient import TestClient


class TestAuthEndpoints:
    """Test authentication endpoints."""

    def test_login_success(self, client: TestClient):
        """Test successful login with correct password."""
        response = client.post(
            "/api/auth/login",
            json={"password": "test-password"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "token" in data
        assert data["message"] == "Erfolgreich eingeloggt"

    def test_login_wrong_password(self, client: TestClient):
        """Test login fails with wrong password."""
        response = client.post(
            "/api/auth/login",
            json={"password": "wrong-password"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["message"] == "Falsches Passwort"

    def test_login_missing_password(self, client: TestClient):
        """Test login fails with missing password."""
        response = client.post(
            "/api/auth/login",
            json={}
        )

        assert response.status_code == 422  # Validation error

    def test_logout(self, client: TestClient, auth_token: str):
        """Test logout endpoint."""
        response = client.post("/api/auth/logout")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Ausgeloggt"

    def test_protected_endpoint_without_token(self, client: TestClient):
        """Test accessing protected endpoint without auth fails."""
        response = client.get("/api/tasks")

        assert response.status_code == 401

    def test_protected_endpoint_with_token(self, client: TestClient, auth_headers: dict):
        """Test accessing protected endpoint with valid token succeeds."""
        response = client.get("/api/tasks", headers=auth_headers)

        assert response.status_code == 200

    def test_protected_endpoint_with_invalid_token(self, client: TestClient):
        """Test accessing protected endpoint with invalid token fails."""
        response = client.get(
            "/api/tasks",
            headers={"X-Auth-Token": "invalid-token"}
        )

        assert response.status_code == 401
