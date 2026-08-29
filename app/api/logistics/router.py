from fastapi import APIRouter
from pydantic import BaseModel

from app.modules.auth.router import users_router
from app.modules.organization.router import router as organization_router
from app.shared.audit.router import router as audit_router

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


# Include domain modules
router.include_router(organization_router)
router.include_router(audit_router)
router.include_router(users_router)
