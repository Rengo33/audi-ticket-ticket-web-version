"""
Pytest configuration and fixtures.
"""
import os
import sys
import pytest
from typing import Generator
from unittest.mock import patch, MagicMock, AsyncMock

# Set test environment BEFORE any app imports
os.environ["APP_PASSWORD"] = "test-password"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

# Clear any cached settings
from app.config import get_settings
get_settings.cache_clear()

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base


# Test database setup - use in-memory SQLite with StaticPool
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    """Override database dependency for tests."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def test_db():
    """Create a fresh test database for each test."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def db_session(test_db) -> Generator:
    """Get a database session for tests."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def client(test_db) -> Generator[TestClient, None, None]:
    """Create a test client with mocked dependencies."""
    from app.main import app
    from app.database import get_db

    # Override database dependency
    app.dependency_overrides[get_db] = override_get_db

    # Mock the scheduler and task_manager at module level before TestClient starts
    with patch("app.main.scheduler") as mock_scheduler, \
         patch("app.main.task_manager") as mock_task_manager:

        mock_scheduler.start = AsyncMock()
        mock_scheduler.stop = AsyncMock()
        mock_task_manager.active_tasks = {}
        mock_task_manager.set_ws_broadcast = MagicMock()

        with TestClient(app) as test_client:
            yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def auth_token(client: TestClient) -> str:
    """Get a valid authentication token."""
    response = client.post(
        "/api/auth/login",
        json={"password": "test-password"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    return data["token"]


@pytest.fixture
def auth_headers(auth_token: str) -> dict:
    """Get headers with authentication token."""
    return {"X-Auth-Token": auth_token}


@pytest.fixture
def mock_audi_api():
    """Mock the Audi ticket API responses."""
    with patch("app.bot.core.AudiTicketBot") as mock_bot:
        mock_instance = MagicMock()
        mock_bot.return_value = mock_instance

        # Default mock responses
        mock_instance.get_product_info.return_value = {
            "event_id": "test-event-123",
            "ticket_id": "test-ticket-456",
            "title": "Test Event"
        }
        mock_instance.check_availability.return_value = {
            "available": False,
            "quantity": 0
        }
        mock_instance.add_to_cart.return_value = {
            "success": False,
            "message": "No tickets available"
        }

        yield mock_instance
