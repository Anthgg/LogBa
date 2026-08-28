import importlib

from app.db.connection import engine

EXPECTED_MODULES = [
    "organization",
    "warehouse",
    "catalog",
    "business_partners",
    "purchasing",
    "receiving",
    "quality",
    "inventory",
    "outbound",
    "transport",
    "routing",
    "delivery",
    "reverse_logistics",
    "documents",
    "analytics",
]

EXPECTED_SHARED = [
    "audit",
    "documents",
    "files",
    "routing",
    "integrations",
    "errors",
]


def test_expected_domain_modules_count():
    assert len(EXPECTED_MODULES) == 15


def test_domain_modules_importability():
    for mod_name in EXPECTED_MODULES:
        mod = importlib.import_module(f"app.modules.{mod_name}")
        assert mod is not None


def test_shared_services_importability():
    for shared_name in EXPECTED_SHARED:
        mod = importlib.import_module(f"app.shared.{shared_name}")
        assert mod is not None


def test_single_database_engine():
    from app.db import connection

    assert hasattr(connection, "engine")
    assert connection.engine is engine
    assert connection.engine.pool is not None
