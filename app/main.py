import logging
import time
import uuid
from typing import Callable, List, cast

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.logistics.router import router as logistics_router
from app.api.routes.health import router as health_router
from app.api.routes.system import router as system_router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.modules.auth.mfa_router import mfa_router
from app.modules.auth.router import auth_router
from app.shared.errors.handlers import register_error_handlers

settings = get_settings()
setup_logging()
logger = logging.getLogger("app.http")

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
for prod_origin in [
    "https://fronlog-web-303244958634.southamerica-west1.run.app",
    "http://localhost:5173",
    "http://localhost:3000",
]:
    if prod_origin not in cors_origins:
        cors_origins.append(prod_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=r"https://.*\.run\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "X-Snapshot-Hash",
        "X-Pdf-Hash",
        "X-Template-Key",
        "X-Document-Type",
        "X-Renderer-Name",
        "X-Correlation-ID",
        "Content-Disposition",
    ],
)


# Correlation ID & Request Logging Middleware
@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next: Callable) -> Response:
    raw_correlation = request.headers.get("X-Correlation-ID")
    try:
        correlation_id = uuid.UUID(raw_correlation) if raw_correlation else uuid.uuid4()
    except (ValueError, TypeError):
        correlation_id = uuid.uuid4()

    request.state.correlation_id = correlation_id
    start_time = time.time()

    response = await call_next(request)
    duration_ms = round((time.time() - start_time) * 1000, 2)

    response.headers["X-Correlation-ID"] = str(correlation_id)

    # Structured request logging
    logger.info(
        f"{request.method} {request.url.path} -> {response.status_code} ({duration_ms}ms)",
        extra={
            "correlation_id": str(correlation_id),
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    return response


# Register machine-readable global exception handlers
register_error_handlers(app)

# Include modular API routers
app.include_router(health_router)
app.include_router(system_router)
app.include_router(auth_router)
app.include_router(mfa_router)
app.include_router(logistics_router)
