"""
Simple Fernet encryption for card details.
"""
import base64
import hashlib
from cryptography.fernet import Fernet

from .config import get_settings


def _get_fernet() -> Fernet:
    """Derive a Fernet key from SECRET_KEY."""
    key = get_settings().secret_key.encode()
    # Fernet requires a 32-byte url-safe base64 key
    derived = hashlib.sha256(key).digest()
    return Fernet(base64.urlsafe_b64encode(derived))


def encrypt(value: str) -> str:
    if not value:
        return ""
    return _get_fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    if not value:
        return ""
    return _get_fernet().decrypt(value.encode()).decode()
