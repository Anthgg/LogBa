import base64
import hashlib
import os
import secrets
from typing import List, Tuple

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings

settings = get_settings()


def _get_encryption_key() -> bytes:
    """Decodes or derives a 32-byte AES key from settings.MFA_ENCRYPTION_KEY."""
    raw_key = settings.MFA_ENCRYPTION_KEY.strip()
    try:
        key_bytes = base64.b64decode(raw_key)
        if len(key_bytes) == 32:
            return key_bytes
    except Exception:
        pass
    # Fallback to SHA-256 digest of key string to guarantee exactly 32 bytes
    return hashlib.sha256(raw_key.encode("utf-8")).digest()


def encrypt_totp_secret(secret_plaintext: str) -> Tuple[str, str]:
    """Encrypts a plaintext TOTP secret using AES-256-GCM.

    Returns:
        (ciphertext_b64, nonce_b64)
    """
    key = _get_encryption_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, secret_plaintext.encode("utf-8"), None)

    ciphertext_b64 = base64.b64encode(ciphertext).decode("utf-8")
    nonce_b64 = base64.b64encode(nonce).decode("utf-8")
    return ciphertext_b64, nonce_b64


def decrypt_totp_secret(ciphertext_b64: str, nonce_b64: str) -> str:
    """Decrypts an AES-256-GCM encrypted TOTP secret."""
    key = _get_encryption_key()
    aesgcm = AESGCM(key)
    nonce = base64.b64decode(nonce_b64.encode("utf-8"))
    ciphertext = base64.b64decode(ciphertext_b64.encode("utf-8"))

    decrypted_bytes = aesgcm.decrypt(nonce, ciphertext, None)
    return decrypted_bytes.decode("utf-8")


def normalize_recovery_code(code: str) -> str:
    """Normalizes a recovery code by stripping spaces, dashes, and converting to uppercase."""
    return code.strip().replace("-", "").replace(" ", "").upper()


def hash_recovery_code(code: str) -> str:
    """Computes the SHA-256 hash of a normalized recovery code."""
    normalized = normalize_recovery_code(code)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def generate_recovery_codes(count: int = 8) -> Tuple[List[str], List[str]]:
    """Generates random high-entropy recovery codes.

    Returns:
        (plaintext_codes, hashed_codes)
    """
    plaintext_codes: List[str] = []
    hashed_codes: List[str] = []

    for _ in range(count):
        # 10 character code formatted as XXXXX-XXXXX
        part1 = secrets.token_hex(3).upper()[:5]
        part2 = secrets.token_hex(3).upper()[:5]
        code = f"{part1}-{part2}"
        plaintext_codes.append(code)
        hashed_codes.append(hash_recovery_code(code))

    return plaintext_codes, hashed_codes
