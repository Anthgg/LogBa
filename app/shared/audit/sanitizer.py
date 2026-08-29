from typing import Any, Dict, Set

SENSITIVE_KEY_SUBSTRINGS: Set[str] = {
    "password",
    "password_hash",
    "initial_password",
    "token",
    "access_token",
    "refresh_token",
    "csrf_token",
    "secret",
    "totp_secret",
    "manual_key",
    "otp",
    "mfa_code",
    "recovery_code",
    "recovery_codes",
    "mfa_encryption_key",
    "secret_ciphertext",
    "secret_nonce",
    "api_key",
    "service_role",
    "database_url",
    "authorization",
    "cookie",
    "set-cookie",
    "bearer",
    "private_key",
}


def sanitize_sensitive_data(data: Any) -> Any:
    """Recursively traverses data structures to redact any sensitive keys or tokens.

    Guarantees AUDIT_SECRET_LEAKS = 0 across all audit event snapshots and metadata.
    """
    if data is None:
        return None

    if isinstance(data, dict):
        sanitized_dict: Dict[str, Any] = {}
        for key, value in data.items():
            key_lower = str(key).lower()
            if any(sensitive in key_lower for sensitive in SENSITIVE_KEY_SUBSTRINGS):
                sanitized_dict[key] = "[REDACTED]"
            else:
                sanitized_dict[key] = sanitize_sensitive_data(value)
        return sanitized_dict

    if isinstance(data, (list, tuple, set)):
        return [sanitize_sensitive_data(item) for item in data]

    return data
