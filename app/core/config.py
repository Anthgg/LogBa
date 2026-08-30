import json
from functools import lru_cache
from typing import Any, List, Optional, Union

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Sistema Logistico Integral"
    APP_ENV: str = "development"
    APP_DEBUG: bool = True

    DATABASE_URL: str = ""
    SUPABASE_URL: Optional[str] = None
    SUPABASE_ANON_KEY: Optional[str] = None
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = None

    BACKEND_CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "https://fronlog-web-303244958634.southamerica-west1.run.app",
    ]

    # Session & Cookie Security (F008)
    SESSION_COOKIE_NAME: str = "logistics_session"
    SESSION_COOKIE_SECURE: bool = False
    SESSION_COOKIE_SAMESITE: str = "none"
    SESSION_ABSOLUTE_TTL_MINUTES: int = 480
    SESSION_IDLE_TIMEOUT_MINUTES: int = 30

    # CSRF & Bootstrap Secrets (Backend only, never in Git/Frontend)
    CSRF_SIGNING_SECRET: str = "dev-csrf-secret-key-32-chars-minimum-entropy!!"
    DEMO_USER_PASSWORD: str = "DemoSecurePass2026_9x!Lp"

    # MFA & Step-Up Security (F009)
    MFA_ENCRYPTION_KEY: str = "K7gNU3sdo+OL0w1g5xV7l4k9a2j5h6P8Q1w2e3r4t5Y="
    MFA_TOTP_ISSUER: str = "Sistema Logistico Integral"
    STEP_UP_CHALLENGE_TTL_SECONDS: int = 300
    STEP_UP_HIGH_GRANT_TTL_SECONDS: int = 300
    STEP_UP_CRITICAL_GRANT_TTL_SECONDS: int = 120
    STEP_UP_MAX_ATTEMPTS: int = 5

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    @field_validator("BACKEND_CORS_ORIGINS", mode="after")
    @classmethod
    def assemble_cors_origins(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                try:
                    parsed = json.loads(v)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return [str(item).strip() for item in v if str(item).strip()]
        return ["http://localhost:5173"]

    @field_validator("DATABASE_URL", mode="after")
    @classmethod
    def validate_and_normalize_database_url(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("DATABASE_URL must not be empty.")

        url = v.strip()
        # Normalize protocol for SQLAlchemy 2.x + psycopg v3
        if url.startswith("postgres://"):
            url = "postgresql+psycopg://" + url[len("postgres://") :]
        elif url.startswith("postgresql://") and not url.startswith("postgresql+"):
            url = "postgresql+psycopg://" + url[len("postgresql://") :]

        return url

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() == "production"

    def enforce_production_security(self) -> None:
        """Enforces critical security policies in production environments."""
        if self.is_production:
            if not self.SESSION_COOKIE_SECURE:
                raise RuntimeError(
                    "PRODUCTION_SECURE_COOKIE_ENFORCED_VIOLATION: "
                    "SESSION_COOKIE_SECURE must be True in production."
                )

    def sanitized_database_url(self) -> str:
        """Returns a sanitized representation of the database URL hiding credentials."""
        try:
            from sqlalchemy.engine import make_url

            url = make_url(self.DATABASE_URL)
            return str(url.render_as_string(hide_password=True))
        except Exception:
            return "[REDACTED_DATABASE_URL]"


@lru_cache
def get_settings() -> Settings:
    return Settings()
