"""In-app view routing that preserves Streamlit session state."""

from __future__ import annotations

from urllib.parse import urlencode

import streamlit as st

from auth.resume import portfolio_resume_token
from auth.users import sanitize_username

_APP_VIEWS = frozenset({"portfolio", "history", "news"})
_DEFAULT_VIEW = "portfolio"
_APP_VIEW_KEY = "app_view"


def portfolio_view_href(slug: str, view: str | None = None) -> str:
    clean_slug = sanitize_username(slug) or slug
    params = {
        "user": clean_slug,
        "resume": portfolio_resume_token(clean_slug),
    }
    target = (view or _DEFAULT_VIEW).lower()
    if target in _APP_VIEWS and target != _DEFAULT_VIEW:
        params["view"] = target
    return f"?{urlencode(params)}"


def resolve_active_view() -> str:
    qp_view = (st.query_params.get("view") or "").lower()
    if qp_view == "portfolio":
        st.session_state[_APP_VIEW_KEY] = _DEFAULT_VIEW
        if "view" in st.query_params:
            del st.query_params["view"]
    elif qp_view in _APP_VIEWS:
        st.session_state[_APP_VIEW_KEY] = qp_view
    if _APP_VIEW_KEY not in st.session_state:
        st.session_state[_APP_VIEW_KEY] = _DEFAULT_VIEW
    view = st.session_state[_APP_VIEW_KEY]
    return view if view in _APP_VIEWS else _DEFAULT_VIEW


def set_active_view(view: str) -> None:
    if view not in _APP_VIEWS:
        view = _DEFAULT_VIEW
    if st.session_state.get(_APP_VIEW_KEY) == view:
        return
    st.session_state[_APP_VIEW_KEY] = view
    if view == _DEFAULT_VIEW:
        if "view" in st.query_params:
            del st.query_params["view"]
    else:
        st.query_params["view"] = view
    st.rerun()


def go_to_portfolio_view() -> None:
    st.session_state[_APP_VIEW_KEY] = _DEFAULT_VIEW
    if "view" in st.query_params:
        del st.query_params["view"]
