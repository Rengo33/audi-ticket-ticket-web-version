from datetime import datetime, timedelta
from typing import Optional
import secrets
import hashlib

from fastapi import HTTPException, Security, Depends, Request, status
from fastapi.security import APIKeyHeader

from .config import get_settings

settings = get_settings()

# Simple token storage (in production, use Redis or DB)
active_tokens: dict[str, datetime] = {}

api_key_header = APIKeyHeader(name="X-Auth-Token", auto_error=False)


def generate_token() -> str:
    """Generate a secure random token."""
    return secrets.token_urlsafe(32)


def hash_password(password: str) -> str:
    """Hash password with SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str) -> bool:
    """Verify password against configured app password."""
    return password == settings.app_password


def create_session_token() -> str:
    """Create a new session token valid for 30 days (for mobile app persistence)."""
    token = generate_token()
    active_tokens[token] = datetime.utcnow() + timedelta(days=30)
    return token


def validate_token(token: str) -> bool:
    """Check if token is valid and not expired."""
    if token not in active_tokens:
        return False
    
    if datetime.utcnow() > active_tokens[token]:
        # Token expired, remove it
        del active_tokens[token]
        return False
    
    return True


def invalidate_token(token: str) -> None:
    """Remove a token (logout)."""
    if token in active_tokens:
        del active_tokens[token]


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


def cleanup_expired_tokens() -> int:
    """Remove expired tokens. Returns count of removed tokens."""
    now = datetime.utcnow()
    expired = [t for t, exp in active_tokens.items() if now > exp]
    for token in expired:
        del active_tokens[token]
    return len(expired)
