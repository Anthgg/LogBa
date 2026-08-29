import hashlib
import hmac
import secrets
import time

from app.core.config import get_settings
from app.core.errors import UnauthorizedError

settings = get_settings()


def _get_csrf_secret() -> str:
    secret = settings.CSRF_SIGNING_SECRET
    if not secret:
        secret = "default-development-csrf-secret-key-32-chars-long"
    return secret


def generate_csrf_token() -> str:
    """Generates an HMAC-signed CSRF token with timestamp."""
    entropy = secrets.token_hex(16)
    timestamp = str(int(time.time()))
    payload = f"{entropy}:{timestamp}"
    signature = hmac.new(
        _get_csrf_secret().encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload}:{signature}"


def validate_csrf_token(token: str, max_age_seconds: int = 86400) -> bool:
    """Validates an HMAC-signed CSRF token."""
    if not token or ":" not in token:
        return False

    parts = token.split(":")
    if len(parts) != 3:
        return False

    entropy, timestamp_str, signature = parts
    try:
        token_time = int(timestamp_str)
    except ValueError:
        return False

    # Check expiration
    now = int(time.time())
    if now - token_time > max_age_seconds or token_time > now + 300:
        return False

    payload = f"{entropy}:{timestamp_str}"
    expected_signature = hmac.new(
        _get_csrf_secret().encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(signature, expected_signature)


def require_csrf(token: str) -> None:
    """Validates CSRF token or raises UnauthorizedError."""
    if not token or not validate_csrf_token(token):
        raise UnauthorizedError(
            message="CSRF token invalido o faltante.",
            code="CSRF_TOKEN_INVALID",
        )
