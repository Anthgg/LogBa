from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from app.core.errors import ValidationError

# Configure Argon2id password hasher
_password_hash = PasswordHash((Argon2Hasher(),))


def hash_password(password: str) -> str:
    """Hashes a plaintext password using Argon2id."""
    return _password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plaintext password against an Argon2id hash."""
    return _password_hash.verify(plain_password, hashed_password)


def validate_password_policy(password: str) -> None:
    """Enforces minimum password length policy (>= 12 characters)."""
    if not password or len(password) < 12:
        raise ValidationError(
            message="La contrasena debe tener al menos 12 caracteres.",
            code="PASSWORD_TOO_SHORT",
            details={"min_length": 12},
        )
