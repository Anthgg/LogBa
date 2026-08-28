import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.errors import (
    ConflictError,
    DependencyRequiredError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from app.shared.errors.handlers import register_error_handlers


@pytest.fixture
def error_app():
    test_app = FastAPI()
    register_error_handlers(test_app)

    @test_app.get("/trigger-not-found")
    def trigger_not_found():
        raise NotFoundError("Resource not found", code="ITEM_NOT_FOUND", details={"id": "123"})

    @test_app.get("/trigger-conflict")
    def trigger_conflict():
        raise ConflictError("State conflict", code="STATUS_CONFLICT", details={"status": "CLOSED"})

    @test_app.get("/trigger-validation")
    def trigger_validation():
        raise ValidationError("Invalid input", code="BAD_PAYLOAD", details={"field": "qty"})

    @test_app.get("/trigger-dependency")
    def trigger_dependency():
        raise DependencyRequiredError(
            "Warehouse required", code="WAREHOUSE_REQUIRED", details={"branch": "B1"}
        )

    @test_app.get("/trigger-unauthorized")
    def trigger_unauthorized():
        raise UnauthorizedError("Auth required")

    @test_app.get("/trigger-forbidden")
    def trigger_forbidden():
        raise ForbiddenError("Permission denied")

    return test_app


def test_not_found_error_handler(error_app):
    client = TestClient(error_app)
    res = client.get("/trigger-not-found")
    assert res.status_code == 404
    assert res.json() == {
        "code": "ITEM_NOT_FOUND",
        "message": "Resource not found",
        "details": {"id": "123"},
    }


def test_conflict_error_handler(error_app):
    client = TestClient(error_app)
    res = client.get("/trigger-conflict")
    assert res.status_code == 409
    assert res.json() == {
        "code": "STATUS_CONFLICT",
        "message": "State conflict",
        "details": {"status": "CLOSED"},
    }


def test_validation_error_handler(error_app):
    client = TestClient(error_app)
    res = client.get("/trigger-validation")
    assert res.status_code == 422
    assert res.json() == {
        "code": "BAD_PAYLOAD",
        "message": "Invalid input",
        "details": {"field": "qty"},
    }


def test_dependency_required_error_handler(error_app):
    client = TestClient(error_app)
    res = client.get("/trigger-dependency")
    assert res.status_code == 409
    assert res.json() == {
        "code": "WAREHOUSE_REQUIRED",
        "message": "Warehouse required",
        "details": {"branch": "B1"},
    }


def test_unauthorized_and_forbidden_error_handlers(error_app):
    client = TestClient(error_app)
    res_unauth = client.get("/trigger-unauthorized")
    assert res_unauth.status_code == 401
    assert res_unauth.json()["code"] == "UNAUTHORIZED"

    res_forbid = client.get("/trigger-forbidden")
    assert res_forbid.status_code == 403
    assert res_forbid.json()["code"] == "FORBIDDEN"
