from typing import Optional
import hashlib
import hmac
import secrets
import time

from fastapi import HTTPException, Security, Depends, Request, status
from fastapi.security import APIKeyHeader

from .config import get_settings

settings = get_settings()

api_key_header = APIKeyHeader(name="X-Auth-Token", auto_error=False)

TOKEN_TTL_S = 30 * 86400  # 30 days, for mobile app persistence


def hash_password(password: str) -> str:
    """Hash password with SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str) -> bool:
    """Verify password against configured app password (constant-time)."""
    return hmac.compare_digest(password.encode(), settings.app_password.encode())


def _sign(payload: str) -> str:
    # Keyed on the app password too, so changing it logs every session out.
    key = f"{settings.secret_key}:{settings.app_password}".encode()
    return hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()


def create_session_token() -> str:
    """Signed, stateless token `nonce.expiry.signature`. Nothing is stored, so
    sessions (and the WebSocket) survive backend restarts and deploys."""
    payload = f"{secrets.token_urlsafe(16)}.{int(time.time()) + TOKEN_TTL_S}"
    return f"{payload}.{_sign(payload)}"


def validate_token(token: str) -> bool:
    """Check signature and expiry."""
    payload, _, sig = token.rpartition(".")
    if not payload or not hmac.compare_digest(sig.encode(), _sign(payload).encode()):
        return False
    try:
        return int(payload.rsplit(".", 1)[-1]) > time.time()
    except ValueError:
        return False


async def get_current_user(
    token: Optional[str] = Security(api_key_header),
    request: Request = None
) -> bool:
    """
    Dependency to verify authentication.
    Checks X-Auth-Token header or auth_token cookie.
    """
    # Try header first
    if token and validate_token(token):
        return True
    
    # Try cookie
    if request:
        cookie_token = request.cookies.get("auth_token")
        if cookie_token and validate_token(cookie_token):
            return True
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing authentication token"
    )
