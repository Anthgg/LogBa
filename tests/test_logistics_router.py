import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_logistics_status_endpoint(client: TestClient):
    response = client.get("/api/logistics/status")
    assert response.status_code == 200
    data = response.json()
    assert data["domain"] == "logistics"
    assert data["status"] == "available"
    assert data["version"] == "1.0.0"
