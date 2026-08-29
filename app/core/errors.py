from typing import Any, Dict, Optional


class DomainError(Exception):
    """Base exception for all domain and business rule violations."""

    def __init__(
        self,
        message: str,
        code: str = "DOMAIN_ERROR",
        details: Optional[Dict[str, Any]] = None,
        status_code: int = 400,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}
        self.status_code = status_code


class NotFoundError(DomainError):
    """Raised when an entity or resource is not found."""

    def __init__(
        self,
        message: str,
        code: str = "NOT_FOUND",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message=message, code=code, details=details, status_code=404)


class ConflictError(DomainError):
    """Raised when a state conflict or business collision occurs."""

    def __init__(
        self,
        message: str,
        code: str = "CONFLICT",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message=message, code=code, details=details, status_code=409)


class ValidationError(DomainError):
    """Raised when payload or business invariant validation fails."""

    def __init__(
        self,
        message: str,
        code: str = "VALIDATION_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message=message, code=code, details=details, status_code=422)


class DependencyRequiredError(DomainError):
    """Raised when a required operational pre-requisite or parent entity is missing."""

    def __init__(
        self,
        message: str,
        code: str = "DEPENDENCY_REQUIRED",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message=message, code=code, details=details, status_code=409)


class UnauthorizedError(DomainError):
    """Raised when authentication credentials are missing or invalid."""

    def __init__(
        self,
        message: str = "Authentication required",
        code: str = "UNAUTHORIZED",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message=message, code=code, details=details, status_code=401)


class ForbiddenError(DomainError):
    """Raised when user lacks permission to access the requested resource."""

    def __init__(
        self,
        message: str = "Permission denied",
        code: str = "FORBIDDEN",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message=message, code=code, details=details, status_code=403)


class PreconditionRequiredError(DomainError):
    """Raised when an operation requires step-up authentication or MFA enrollment (HTTP 428)."""

    def __init__(
        self,
        message: str = "Precondition required for sensitive operation",
        code: str = "STEP_UP_REQUIRED",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message=message, code=code, details=details, status_code=428)
