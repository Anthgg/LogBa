import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_system_info_endpoint(client: TestClient):
    response = client.get("/api/system/info")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "environment" in data
    assert data["api"] == "online"


def test_system_info_no_secrets(client: TestClient):
    response = client.get("/api/system/info")
    assert response.status_code == 200
    content_str = response.text.lower()
    assert "password" not in content_str
    assert "postgres" not in content_str
    assert "service_role" not in content_str
    assert "anon" not in content_str
    assert "secret" not in content_str

    settings = get_settings()
    assert settings.DATABASE_URL not in response.text
