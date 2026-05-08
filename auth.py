"""
Simple login helpers — credentials are read from Streamlit secrets, not hard-coded.

Create `.streamlit/secrets.toml` (see `.streamlit/secrets.toml.example`) with a [users] table.
Passwords are compared in plain text here for classroom demos only; use a real auth backend for production.
"""

from __future__ import annotations

import re
from typing import Optional

import streamlit as st

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


def users_from_secrets() -> dict[str, str]:
    """username -> password (demo-style; from st.secrets['users'])."""
    try:
        block = st.secrets.get("users", {})
    except (FileNotFoundError, KeyError, TypeError):
        return {}
    if block is None:
        return {}
    out: dict[str, str] = {}
    for k, v in dict(block).items():
        key = sanitize_username(str(k))
        if key is None:
            continue
        out[key] = str(v) if v is not None else ""
    return out


def verify_password(username: str, password: str) -> bool:
    """True if username/password match a secrets.toml entry."""
    u = sanitize_username(username)
    if u is None:
        return False
    users = users_from_secrets()
    if u not in users:
        return False
    return users[u] == password
