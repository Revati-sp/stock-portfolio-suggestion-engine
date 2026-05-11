"""
auth/tokens.py — JWT token generation and validation.

Creates and verifies JWT tokens for FastAPI authentication.
Extracted from api_auth.py.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import jwt

from auth.users import sanitize_username

# Use tomllib (Python 3.11+) or fall back to tomli package
if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib  # type: ignore
    except ImportError:
        tomllib = None  # type: ignore


def _get_secrets_path() -> Path:
    """Return path to .streamlit/secrets.toml relative to project root."""
    return Path(__file__).parent.parent / ".streamlit" / "secrets.toml"


def get_secret_key() -> str:
    """JWT signing key from env or a fallback."""
    key = os.environ.get("JWT_SECRET_KEY")
    if key:
        return key
    # Fallback: read from secrets.toml [jwt] section
    path = _get_secrets_path()
    if path.exists() and tomllib is not None:
        try:
            with open(path, "rb") as f:
                data = tomllib.load(f)
            key = data.get("jwt", {}).get("secret_key")
            if key:
                return str(key)
        except Exception:
            pass
    # Last resort: insecure default (for dev only)
    return "dev-insecure-key-change-in-production"


def create_access_token(username: str, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token. Default expiry: 1 hour."""
    user = sanitize_username(username)
    if user is None:
        raise ValueError(f"Invalid username: {username}")

    if expires_delta is None:
        expires_delta = timedelta(hours=1)

    expire = datetime.now(timezone.utc) + expires_delta
    payload = {"sub": user, "exp": expire}
    token = jwt.encode(payload, get_secret_key(), algorithm="HS256")
    return token


def decode_token(token: str) -> str:
    """
    Decode JWT and return username (sub claim).
    Raises ValueError if invalid or expired.
    """
    try:
        payload = jwt.decode(token, get_secret_key(), algorithms=["HS256"])
        username: str = payload.get("sub")
        if username is None:
            raise ValueError("Missing 'sub' claim in token")
        return sanitize_username(username) or username
    except jwt.ExpiredSignatureError:
        raise ValueError("Token has expired")
    except jwt.InvalidTokenError as e:
        raise ValueError(f"Invalid token: {e}")
