"""
Authentication endpoints.
"""
from fastapi import APIRouter, Response

from ..schemas import LoginRequest, LoginResponse
from ..auth import verify_password, create_session_token, invalidate_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, response: Response):
    """
    Login with shared password.
    Returns a session token and sets it as cookie.
    """
    if not verify_password(request.password):
        return LoginResponse(
            success=False,
            message="Falsches Passwort"
        )
    
    token = create_session_token()
    
    # Set cookie for browser clients
    response.set_cookie(
        key="auth_token",
        value=token,
        httponly=True,
        max_age=86400,  # 24 hours
        samesite="lax"
    )
    
    return LoginResponse(
        success=True,
        token=token,
        message="Erfolgreich eingeloggt"
    )


@router.post("/logout")
async def logout(response: Response):
    """Logout and invalidate token."""
    response.delete_cookie("auth_token")
    return {"success": True, "message": "Ausgeloggt"}
