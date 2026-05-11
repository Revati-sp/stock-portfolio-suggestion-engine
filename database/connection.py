"""
db.py — SQLite connection factory and schema initialization.

Single point of database access for both Streamlit app and FastAPI.
Creates and manages the portfolio.db file with four tables:
  - users: authentication with bcrypt hashes
  - portfolio_history: per-user transaction log (replaces CSV)
  - portfolio_daily_trend: per-user daily values (replaces CSV)
  - current_holdings: per-user saved basket (replaces JSON)
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "portfolio.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    UNIQUE NOT NULL,
    password_hash TEXT    NOT NULL,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS portfolio_history (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id               INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    date                  TEXT    NOT NULL,
    strategies            TEXT    NOT NULL,
    investment_amount     REAL    NOT NULL,
    total_portfolio_value REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS portfolio_daily_trend (
    user_id               INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    date                  TEXT    NOT NULL,
    total_portfolio_value REAL    NOT NULL,
    PRIMARY KEY (user_id, date)
);

CREATE TABLE IF NOT EXISTS current_holdings (
    user_id           INTEGER NOT NULL PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    saved_at          TEXT    NOT NULL,
    strategies        TEXT    NOT NULL,
    investment_amount REAL    NOT NULL,
    dollar_per_ticker REAL    NOT NULL,
    holdings          TEXT    NOT NULL
);
"""


def get_db() -> sqlite3.Connection:
    """Get a database connection with proper configuration."""
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging for concurrency
    conn.execute("PRAGMA foreign_keys=ON")   # Enable foreign key constraints
    conn.row_factory = sqlite3.Row  # Return rows as dict-like objects
    return conn


def init_db() -> None:
    """Initialize database schema if not already present."""
    conn = get_db()
    try:
        for statement in _SCHEMA.split(";"):
            stmt = statement.strip()
            if stmt:
                conn.execute(stmt)
        conn.commit()
    finally:
        conn.close()


def get_user_id(username: str) -> int | None:
    """Lookup user ID by username. Returns None if not found."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


# Initialize schema on import so both app.py and api.py are ready
init_db()
