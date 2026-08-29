import uuid
from typing import Callable, List, cast

from fastapi import FastAPI, Request, Response
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


# Correlation ID Middleware
@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next: Callable) -> Response:
    raw_correlation = request.headers.get("X-Correlation-ID")
    try:
        correlation_id = uuid.UUID(raw_correlation) if raw_correlation else uuid.uuid4()
    except (ValueError, TypeError):
        correlation_id = uuid.uuid4()

    request.state.correlation_id = correlation_id
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = str(correlation_id)
    return response


# Register machine-readable global exception handlers
register_error_handlers(app)

# Include modular API routers
app.include_router(health_router)
app.include_router(system_router)
app.include_router(logistics_router)
