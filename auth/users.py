"""
auth/users.py — User management with password hashing.

Handles user creation, login verification, and existence checks.
Combines functionality from db_auth.py and auth.py.
"""

from __future__ import annotations

import re
from typing import Optional

from database.connection import get_db, get_user_id
from auth.hashing import hash_password, verify_hash

_MAX_USER_LEN = 48
_USER_RE = re.compile(r"^[a-zA-Z0-9][-a-zA-Z0-9_]{0,47}$")


def sanitize_username(raw: str) -> Optional[str]:
    """Return a safe filesystem / session key, or None if invalid."""
    if not raw or not isinstance(raw, str):
        return None
    s = raw.strip()
    if not _USER_RE.match(s) or len(s) > _MAX_USER_LEN:
        return None
    return s.lower()


def create_user(username: str, plain_password: str) -> None:
    """Create a new user with a bcrypt-hashed password."""
    hashed = hash_password(plain_password)
    conn = get_db()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO users (username, password_hash) VALUES (?, ?)",
            (username, hashed),
        )
        conn.commit()
    finally:
        conn.close()


def verify_password(username: str, plain: str) -> bool:
    """Verify a plain-text password against the bcrypt hash in the DB."""
    user_id = get_user_id(username)
    if user_id is None:
        return False

    conn = get_db()
    try:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if row is None:
            return False
        stored_hash = row[0]
        return verify_hash(plain, stored_hash)
    finally:
        conn.close()


def any_users_exist() -> bool:
    """Check if any users are configured in the database."""
    conn = get_db()
    try:
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        return count > 0
    finally:
        conn.close()


def users_from_secrets() -> dict:
    """Return truthy value if any users exist in DB, empty dict otherwise.

    Kept for Streamlit backward compatibility. Delegates to any_users_exist().
    """
    return {"_db": True} if any_users_exist() else {}
