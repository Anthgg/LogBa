from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/logistics", tags=["Logistics Core"])


class LogisticsDomainStatusResponse(BaseModel):
    domain: str = "logistics"
    status: str = "available"
    version: str = "1.0.0"


@router.get("/status", response_model=LogisticsDomainStatusResponse)
def get_logistics_status():
    """Technical probe verifying that the logistics root domain is active and responding."""
    return LogisticsDomainStatusResponse(
        domain="logistics",
        status="available",
        version="1.0.0",
    )
