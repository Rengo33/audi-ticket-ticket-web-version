"""
Tests for task management endpoints.
"""
from fastapi.testclient import TestClient

# Valid Audi ticket URL format required by the API
VALID_PRODUCT_URL = "https://audidefuehrungen2.regiondo.de/test-event"


class TestTaskEndpoints:
    """Test task management endpoints."""

    def test_list_tasks_empty(self, client: TestClient, auth_headers: dict):
        """Test listing tasks when none exist."""
        response = client.get("/api/tasks", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "tasks" in data
        assert "total" in data
        assert data["tasks"] == []
        assert data["total"] == 0

    def test_create_task(self, client: TestClient, auth_headers: dict):
        """Test creating a new task."""
        task_data = {
            "product_url": VALID_PRODUCT_URL,
            "quantity": 2,
            "num_threads": 3
        }

        response = client.post(
            "/api/tasks",
            json=task_data,
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["product_url"] == task_data["product_url"]
        assert data["quantity"] == task_data["quantity"]
        assert data["num_threads"] == task_data["num_threads"]
        assert data["status"] == "pending"
        assert "id" in data

    def test_create_task_invalid_url(self, client: TestClient, auth_headers: dict):
        """Test creating a task with invalid URL fails."""
        task_data = {
            "product_url": "https://invalid-url.com/test",
            "quantity": 1
        }

        response = client.post(
            "/api/tasks",
            json=task_data,
            headers=auth_headers
        )

        assert response.status_code == 400

    def test_create_task_invalid_quantity(self, client: TestClient, auth_headers: dict):
        """Test creating a task with invalid quantity fails."""
        # Quantity too high
        response = client.post(
            "/api/tasks",
            json={"product_url": VALID_PRODUCT_URL, "quantity": 5},
            headers=auth_headers
        )
        assert response.status_code == 400

        # Quantity too low
        response = client.post(
            "/api/tasks",
            json={"product_url": VALID_PRODUCT_URL, "quantity": 0},
            headers=auth_headers
        )
        assert response.status_code == 400

    def test_get_task_by_id(self, client: TestClient, auth_headers: dict):
        """Test getting a specific task by ID."""
        # First create a task
        task_data = {
            "product_url": VALID_PRODUCT_URL,
            "quantity": 1
        }
        create_response = client.post(
            "/api/tasks",
            json=task_data,
            headers=auth_headers
        )
        assert create_response.status_code == 200
        task_id = create_response.json()["id"]

        # Then get it
        response = client.get(f"/api/tasks/{task_id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == task_id
        assert data["product_url"] == task_data["product_url"]

    def test_get_nonexistent_task(self, client: TestClient, auth_headers: dict):
        """Test getting a task that doesn't exist."""
        response = client.get("/api/tasks/99999", headers=auth_headers)

        assert response.status_code == 404

    def test_delete_task(self, client: TestClient, auth_headers: dict):
        """Test deleting a task."""
        # First create a task
        task_data = {
            "product_url": VALID_PRODUCT_URL,
            "quantity": 1
        }
        create_response = client.post(
            "/api/tasks",
            json=task_data,
            headers=auth_headers
        )
        assert create_response.status_code == 200
        task_id = create_response.json()["id"]

        # Delete it
        response = client.delete(f"/api/tasks/{task_id}", headers=auth_headers)

        assert response.status_code == 200

        # Verify it's gone
        get_response = client.get(f"/api/tasks/{task_id}", headers=auth_headers)
        assert get_response.status_code == 404

    def test_create_task_default_values(self, client: TestClient, auth_headers: dict):
        """Test creating a task uses correct defaults."""
        task_data = {
            "product_url": VALID_PRODUCT_URL
        }

        response = client.post(
            "/api/tasks",
            json=task_data,
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["quantity"] == 1  # default
        assert data["num_threads"] == 1  # default

    def test_list_tasks_with_data(self, client: TestClient, auth_headers: dict):
        """Test listing tasks returns created tasks."""
        # Create two tasks
        for i in range(2):
            client.post(
                "/api/tasks",
                json={"product_url": VALID_PRODUCT_URL, "quantity": i + 1},
                headers=auth_headers
            )

        response = client.get("/api/tasks", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["tasks"]) == 2
