"""
api/dependencies.py — FastAPI dependency injection functions.

Extracts authentication requirements from request headers.
"""

from __future__ import annotations

from typing import Optional

from fastapi import Header, HTTPException, status

from auth.users import sanitize_username
from auth.tokens import decode_token


def get_current_user(authorization: Optional[str] = Header(None)) -> str:
    """Extract and validate JWT token from Authorization header. Returns user_slug."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization[7:]  # Remove "Bearer " prefix
    try:
        username = decode_token(token)
        user_slug = sanitize_username(username)
        if user_slug is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username format",
            )
        return user_slug
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )
