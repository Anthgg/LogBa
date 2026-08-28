from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from app.core.config import get_settings
from app.db.connection import check_database_connection

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.APP_DEBUG,
    docs_url="/docs" if settings.APP_DEBUG else None,
    redoc_url="/redoc" if settings.APP_DEBUG else None,
)


@app.get("/live", status_code=status.HTTP_200_OK, tags=["Health"])
def health_live():
    """Liveness probe: verifies that FastAPI is up and responding without querying DB."""
    return {"status": "ok"}


@app.get("/ready", tags=["Health"])
def health_ready():
    """Readiness probe: validates real database connectivity against PostgreSQL/Supabase."""
    is_connected, db_status = check_database_connection()
    if is_connected:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "ready",
                "database": "ok",
            },
        )
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "not_ready",
            "database": db_status,
        },
    )
