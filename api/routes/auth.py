"""
api/routes/auth.py — Authentication endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from api.schemas import LoginRequest, LoginResponse
from auth.users import verify_password
from auth.tokens import create_access_token

router = APIRouter()


@router.post("/api/auth/login", response_model=LoginResponse)
def login(req: LoginRequest) -> LoginResponse:
    """Authenticate user and return JWT access token."""
    if not verify_password(req.username, req.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    token = create_access_token(req.username)
    return LoginResponse(access_token=token, token_type="bearer")
