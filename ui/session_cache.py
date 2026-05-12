"""Session cache helpers shared across Streamlit pages."""

from __future__ import annotations

import streamlit as st


def clear_session_portfolio_cache() -> None:
    for key in list(st.session_state.keys()):
        if key.startswith("portfolio_snapshot_"):
            del st.session_state[key]
    st.session_state.allocation_df_by_user = {}
