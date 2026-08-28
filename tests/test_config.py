from app.core.config import Settings, get_settings


def test_settings_singleton():
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2


def test_cors_origins_parsing():
    # String with comma separation
    settings_comma = Settings(
        DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/db",
        BACKEND_CORS_ORIGINS="http://localhost:5173, http://localhost:3000",
    )
    assert settings_comma.BACKEND_CORS_ORIGINS == [
        "http://localhost:5173",
        "http://localhost:3000",
    ]

    # JSON array string
    settings_json = Settings(
        DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/db",
        BACKEND_CORS_ORIGINS='["http://localhost:5173", "http://localhost:8000"]',
    )
    assert settings_json.BACKEND_CORS_ORIGINS == [
        "http://localhost:5173",
        "http://localhost:8000",
    ]


def test_database_url_normalization():
    # postgres:// to postgresql+psycopg://
    s = Settings(DATABASE_URL="postgres://user:pass@localhost:5432/db")
    assert s.DATABASE_URL.startswith("postgresql+psycopg://")


def test_database_url_sanitization():
    s = Settings(DATABASE_URL="postgresql+psycopg://user:secretpass@localhost:5432/testdb")
    sanitized = s.sanitized_database_url()
    assert "secretpass" not in sanitized
    assert "***" in sanitized or ":" in sanitized
