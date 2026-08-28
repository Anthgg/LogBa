from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings

router = APIRouter(prefix="/api/system", tags=["System"])


class SystemInfoResponse(BaseModel):
    name: str
    environment: str
    api: str


@router.get("/info", response_model=SystemInfoResponse)
def get_system_info():
    """Returns non-sensitive public system metadata to confirm frontend-to-backend communication."""
    settings = get_settings()
    return SystemInfoResponse(
        name=settings.APP_NAME,
        environment=settings.APP_ENV,
        api="online",
    )
