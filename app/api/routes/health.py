from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.db.connection import check_database_connection

router = APIRouter(tags=["Health"])


@router.get("/live", status_code=status.HTTP_200_OK)
def health_live():
    """Liveness probe: verifies that FastAPI is up and responding without querying DB."""
    return {"status": "ok"}


@router.get("/ready")
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
