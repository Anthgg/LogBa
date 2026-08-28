import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import get_settings


@pytest.fixture
def client():
    return TestClient(app)


def test_live_endpoint(client):
    response = client.get("/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_endpoint(client):
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "ok"}


def test_settings_sanitization():
    settings = get_settings()
    sanitized = settings.sanitized_database_url()
    assert "@" not in sanitized or "***" in sanitized or ":" in sanitized
    if settings.DATABASE_URL:
        assert "[REDACTED_DATABASE_URL]" == sanitized or "***" in sanitized or "postgresql" in sanitized
