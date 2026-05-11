#!/usr/bin/env python3
"""
migrate.py — One-time migration from secrets.toml + CSV/JSON to SQLite.

Run once to:
1. Initialize database schema
2. Create users from .streamlit/secrets.toml with bcrypt hashing
3. Import existing portfolio data from user_data/<slug>/ CSV/JSON files

Safe to re-run: INSERT OR IGNORE and ON CONFLICT clauses prevent duplicates.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# Use tomllib (Python 3.11+) or fall back to tomli package
if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib  # type: ignore
    except ImportError:
        print("ERROR: Python <3.11 requires 'tomli' package. Run: pip install tomli")
        sys.exit(1)

from database.connection import init_db, get_db, get_user_id
from auth.users import create_user
SECRETS_TOML = REPO_ROOT / ".streamlit" / "secrets.toml"
USER_DATA_DIR = REPO_ROOT / "user_data"


def migrate_users() -> None:
    """Create users from [users] section in secrets.toml with bcrypt hashing."""
    if not SECRETS_TOML.exists():
        print("⚠️  secrets.toml not found, skipping user migration")
        return

    try:
        with open(SECRETS_TOML, "rb") as f:
            config = tomllib.load(f)
    except Exception as e:
        print(f"⚠️  Could not read secrets.toml: {e}")
        return

    users_block = config.get("users", {})
    if not users_block:
        print("⚠️  No [users] section in secrets.toml, skipping")
        return

    count = 0
    for username, password in users_block.items():
        username_str = str(username).lower()
        password_str = str(password) if password else ""
        try:
            create_user(username_str, password_str)
            print(f"✓ Created user: {username_str}")
            count += 1
        except Exception as e:
            print(f"⚠️  Could not create user {username_str}: {e}")

    print(f"✓ Migrated {count} user(s)")


def migrate_user_data() -> None:
    """Import existing portfolio data from user_data/<slug>/ CSV/JSON files."""
    if not USER_DATA_DIR.exists():
        print("⚠️  user_data/ directory not found, skipping data migration")
        return

    user_dirs = [d for d in USER_DATA_DIR.iterdir() if d.is_dir()]
    if not user_dirs:
        print("⚠️  No user directories in user_data/, skipping")
        return

    conn = get_db()

    for user_dir in sorted(user_dirs):
        user_slug = user_dir.name
        user_id = get_user_id(user_slug)
        if user_id is None:
            print(f"⚠️  User {user_slug} not in database, skipping data import")
            continue

        # Import portfolio_history.csv
        history_csv = user_dir / "portfolio_history.csv"
        if history_csv.exists():
            try:
                with open(history_csv, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        try:
                            conn.execute(
                                """
                                INSERT OR IGNORE INTO portfolio_history
                                (user_id, date, strategies, investment_amount, total_portfolio_value)
                                VALUES (?, ?, ?, ?, ?)
                                """,
                                (
                                    user_id,
                                    row.get("date", ""),
                                    row.get("strategies", ""),
                                    float(row.get("investment_amount", 0)),
                                    float(row.get("total_portfolio_value", 0)),
                                ),
                            )
                        except Exception as e:
                            print(f"⚠️  Could not import history row: {e}")
                conn.commit()
                print(f"✓ Imported portfolio_history.csv for {user_slug}")
            except Exception as e:
                print(f"⚠️  Could not import history.csv for {user_slug}: {e}")

        # Import portfolio_daily_trend.csv
        trend_csv = user_dir / "portfolio_daily_trend.csv"
        if trend_csv.exists():
            try:
                with open(trend_csv, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        try:
                            conn.execute(
                                """
                                INSERT OR REPLACE INTO portfolio_daily_trend
                                (user_id, date, total_portfolio_value)
                                VALUES (?, ?, ?)
                                """,
                                (
                                    user_id,
                                    row.get("date", ""),
                                    float(row.get("total_portfolio_value", 0)),
                                ),
                            )
                        except Exception as e:
                            print(f"⚠️  Could not import trend row: {e}")
                conn.commit()
                print(f"✓ Imported portfolio_daily_trend.csv for {user_slug}")
            except Exception as e:
                print(f"⚠️  Could not import trend.csv for {user_slug}: {e}")

        # Import current_holdings.json
        holdings_json = user_dir / "current_holdings.json"
        if holdings_json.exists():
            try:
                data = json.loads(holdings_json.read_text(encoding="utf-8"))
                strategies_json = json.dumps(data.get("strategies", []))
                holdings_json_str = json.dumps(data.get("holdings", []))
                conn.execute(
                    """
                    INSERT OR REPLACE INTO current_holdings
                    (user_id, saved_at, strategies, investment_amount, dollar_per_ticker, holdings)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        data.get("saved_at", ""),
                        strategies_json,
                        float(data.get("investment_amount", 0)),
                        float(data.get("dollar_per_ticker", 0)),
                        holdings_json_str,
                    ),
                )
                conn.commit()
                print(f"✓ Imported current_holdings.json for {user_slug}")
            except Exception as e:
                print(f"⚠️  Could not import holdings.json for {user_slug}: {e}")

    conn.close()


def main() -> None:
    """Run the full migration."""
    print("=" * 60)
    print("Stock Portfolio Suggestion Engine — Database Migration")
    print("=" * 60)

    print("\n1. Initializing database schema...")
    try:
        init_db()
        print("✓ Database schema initialized")
    except Exception as e:
        print(f"❌ Failed to initialize database: {e}")
        sys.exit(1)

    print("\n2. Creating users from secrets.toml...")
    migrate_users()

    print("\n3. Importing existing portfolio data...")
    migrate_user_data()

    print("\n" + "=" * 60)
    print("✅ Migration complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("  1. Streamlit: streamlit run app.py")
    print("  2. FastAPI:   uvicorn api.server:app --reload --port 8000")


if __name__ == "__main__":
    main()
