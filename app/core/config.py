from functools import lru_cache
from typing import Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Sistema Logistico Integral"
    APP_ENV: str = "development"
    APP_DEBUG: bool = True

    DATABASE_URL: str
    SUPABASE_URL: Optional[str] = None
    SUPABASE_ANON_KEY: Optional[str] = None
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    @field_validator("DATABASE_URL", mode="after")
    @classmethod
    def validate_and_normalize_database_url(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("DATABASE_URL must not be empty.")
        
        url = v.strip()
        # Normalize protocol for SQLAlchemy 2.x + psycopg v3
        if url.startswith("postgres://"):
            url = "postgresql+psycopg://" + url[len("postgres://"):]
        elif url.startswith("postgresql://") and not url.startswith("postgresql+"):
            url = "postgresql+psycopg://" + url[len("postgresql://"):]
            
        return url

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() == "production"

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
