import logging
from typing import Any, Dict

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.errors import DomainError

logger = logging.getLogger("app.errors")


def register_error_handlers(app: FastAPI) -> None:
    """Registers standard machine-readable JSON error handlers on the FastAPI application."""

    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
        logger.warning(
            "Domain error [%s] on %s: %s",
            exc.code,
            request.url.path,
            exc.message,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        formatted_errors: Dict[str, Any] = {}
        for err in exc.errors():
            loc = ".".join(str(x) for x in err.get("loc", []))
            formatted_errors[loc] = err.get("msg")

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "code": "REQUEST_VALIDATION_ERROR",
                "message": "The submitted payload contains validation errors.",
                "details": formatted_errors,
            },
        )
