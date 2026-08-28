from typing import List, cast

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.health import router as health_router
from app.api.routes.system import router as system_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.APP_DEBUG,
    docs_url="/docs" if settings.APP_DEBUG else None,
    redoc_url="/redoc" if settings.APP_DEBUG else None,
)

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

# Include modular routers
app.include_router(health_router)
app.include_router(system_router)
