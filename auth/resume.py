"""Signed return links for cross-app navigation back to Streamlit."""

from __future__ import annotations

import hashlib
import hmac
import os

import streamlit as st


def _resume_secret() -> bytes:
    try:
        return str(st.secrets["auth"]["resume_secret"]).encode("utf-8")
    except Exception:
        return os.environ.get("PORTFOLIO_RESUME_SECRET", "dev-resume-secret").encode("utf-8")


def portfolio_resume_token(slug: str) -> str:
    return hmac.new(_resume_secret(), slug.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_portfolio_resume(slug: str, token: str) -> bool:
    if not slug or not token:
        return False
    expected = portfolio_resume_token(slug)
    return hmac.compare_digest(expected, token)
