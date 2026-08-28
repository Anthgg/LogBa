import logging
from typing import Generator, Tuple

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

logger = logging.getLogger("app.db")

settings = get_settings()

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=5,
    max_overflow=10,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database_connection() -> Tuple[bool, str]:
    """
    Executes a real SELECT 1 query against Supabase PostgreSQL.
    Returns (True, "ok") on success or (False, sanitized_error_message) on failure.
    Never exposes passwords, raw tokens, or sensitive connection strings.
    """
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1")).scalar()
            if result == 1:
                return True, "ok"
            return False, "Unexpected query result"
    except Exception as exc:
        logger.error("Database connection verification failed: %s", type(exc).__name__)
        return False, "error"
