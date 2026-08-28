from typing import List, cast

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.logistics.router import router as logistics_router
from app.api.routes.health import router as health_router
from app.api.routes.system import router as system_router
from app.core.config import get_settings
from app.shared.errors.handlers import register_error_handlers

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.APP_DEBUG,
    docs_url="/docs" if settings.APP_DEBUG else None,
    redoc_url="/redoc" if settings.APP_DEBUG else None,
)

# CORS configuration
cors_origins: List[str] = (
    cast(List[str], settings.BACKEND_CORS_ORIGINS)
    if isinstance(settings.BACKEND_CORS_ORIGINS, list)
    else [str(settings.BACKEND_CORS_ORIGINS)]
)

if cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Register machine-readable global exception handlers
register_error_handlers(app)

# Include modular API routers
app.include_router(health_router)
app.include_router(system_router)
app.include_router(logistics_router)
