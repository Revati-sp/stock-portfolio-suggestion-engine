# Database & Secure Authentication Guide

## Overview

The Stock Portfolio Suggestion Engine now uses **SQLite** for persistent data storage and **bcrypt** for secure password hashing. This replaces the previous file-based approach (CSV + JSON) and plain-text secrets.

## Architecture

### Database File
- **Location:** `portfolio.db` (in the project root)
- **Type:** SQLite 3
- **Size:** Typical ~100KB for demo data

### Tables

#### `users`
Stores user credentials with bcrypt-hashed passwords.

```sql
CREATE TABLE users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    UNIQUE NOT NULL,
    password_hash TEXT    NOT NULL,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);
```

#### `portfolio_history`
Replaces `user_data/<slug>/portfolio_history.csv`. Audit log of all portfolio generation runs.

```sql
CREATE TABLE portfolio_history (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id               INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    date                  TEXT    NOT NULL,
    strategies            TEXT    NOT NULL,
    investment_amount     REAL    NOT NULL,
    total_portfolio_value REAL    NOT NULL
);
```

#### `portfolio_daily_trend`
Replaces `user_data/<slug>/portfolio_daily_trend.csv`. Daily portfolio values (max 5 days).

```sql
CREATE TABLE portfolio_daily_trend (
    user_id               INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    date                  TEXT    NOT NULL,
    total_portfolio_value REAL    NOT NULL,
    PRIMARY KEY (user_id, date)
);
```

#### `current_holdings`
Replaces `user_data/<slug>/current_holdings.json`. Saved basket for daily re-pricing.

```sql
CREATE TABLE current_holdings (
    user_id           INTEGER NOT NULL PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    saved_at          TEXT    NOT NULL,
    strategies        TEXT    NOT NULL,   -- JSON array
    investment_amount REAL    NOT NULL,
    dollar_per_ticker REAL    NOT NULL,
    holdings          TEXT    NOT NULL    -- JSON array
);
```

## Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt      # Includes both Streamlit and FastAPI
```

### 2. Run Migration (One-Time)
```bash
python migrate.py
```

**What this does:**
- Initializes the `portfolio.db` schema
- Creates users from `.streamlit/secrets.toml` with bcrypt hashing
- Imports existing portfolio data from `user_data/<slug>/` CSV/JSON files
- Safe to re-run (uses `INSERT OR IGNORE` to prevent duplicates)

**Output:**
```
============================================================
Stock Portfolio Suggestion Engine — Database Migration
============================================================

1. Initializing database schema...
✓ Database schema initialized

2. Creating users from secrets.toml...
✓ Created user: demo
✓ Created user: test
✓ Migrated 2 user(s)

3. Importing existing portfolio data...
✓ Imported portfolio_history.csv for demo
✓ Imported portfolio_daily_trend.csv for demo
✓ Imported current_holdings.json for demo
⚠️  User test_user not in database, skipping data import

============================================================
✅ Migration complete!
============================================================
```

## Authentication

### Password Hashing

Passwords are hashed with **bcrypt** (salted, 12 rounds):
- Original passwords stored in `.streamlit/secrets.toml` are **never saved** to the database
- Instead, they are one-way hashed during migration
- Login attempts hash the input and compare to the stored hash

### How It Works

```python
# Creating a user (during migration)
from db_auth import create_user
create_user("demo", "demo123")  # Hashes "demo123" with bcrypt

# Verifying a password (during login)
from db_auth import verify_password
verify_password("demo", "demo123")  # Returns True
verify_password("demo", "wrongpass")  # Returns False
```

### Modules

| Module | Purpose | Used by |
|--------|---------|---------|
| `db.py` | SQLite connection + schema setup | All layers |
| `db_auth.py` | Bcrypt password hashing + user creation | Both auth modules |
| `auth.py` | Streamlit authentication | `app.py` login form |
| `api_auth.py` | FastAPI + JWT authentication | `api.py` endpoints |

## Running the Application

### Streamlit
```bash
streamlit run app.py
# → Login with demo/demo123
# → Credentials verified against bcrypt hash in database
```

### FastAPI
```bash
python -m uvicorn api.server:app --reload --port 8000
# → POST /api/auth/login with {"username":"demo","password":"demo123"}
# → Password hashed and compared using bcrypt
# → Returns JWT token if valid
```

## Database Queries

### Browse users
```bash
sqlite3 portfolio.db "SELECT username, created_at FROM users;"
```

### View a user's portfolio history
```bash
sqlite3 portfolio.db "
  SELECT date, strategies, investment_amount, total_portfolio_value
  FROM portfolio_history
  WHERE user_id = (SELECT id FROM users WHERE username = 'demo')
  ORDER BY date DESC
  LIMIT 5;
"
```

### View daily trend
```bash
sqlite3 portfolio.db "
  SELECT date, total_portfolio_value
  FROM portfolio_daily_trend
  WHERE user_id = (SELECT id FROM users WHERE username = 'demo')
  ORDER BY date DESC;
"
```

### Export all data for a user
```bash
sqlite3 portfolio.db ".mode csv" \
  "SELECT * FROM portfolio_history WHERE user_id = 1;" \
  > export_history.csv
```

## JWT Secret Key

For the FastAPI layer, JWT tokens are signed with a secret key:

### Priority (in order):
1. **Environment variable** `JWT_SECRET_KEY`
   ```bash
   export JWT_SECRET_KEY="your-secret-key-here"
   ```

2. **secrets.toml** `[jwt]` section
   ```toml
   [jwt]
   secret_key = "your-secret-key-here"
   ```

3. **Fallback** (dev only)
   ```
   "dev-insecure-key-change-in-production"
   ```

### For Production
Set `JWT_SECRET_KEY` environment variable to a strong random value:
```bash
export JWT_SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
```

## Backing Up Data

### SQLite is a single file
```bash
cp portfolio.db portfolio.db.backup
```

### Export to CSV
```bash
sqlite3 portfolio.db ".mode csv" ".output history.csv" \
  "SELECT * FROM portfolio_history;"
```

## Troubleshooting

### "No users found in the database"
**Solution:** Run `python migrate.py` to create users from secrets.toml

### "Unable to create user: UNIQUE constraint failed"
**Solution:** User already exists. This is safe to ignore or re-run `python migrate.py`.

### JWT token rejected with "Token has expired"
**Solution:** JWT tokens expire after 1 hour. Login again to get a new token.

### Database is locked
**Solution:** SQLite uses WAL (Write-Ahead Logging) mode for concurrency. If you see lock errors:
- Check if other processes are accessing the DB
- Restart the application
- On production, consider PostgreSQL for true multi-process concurrency

## Migration from CSV/JSON to Database

The `migrate.py` script handles all migration automatically:

1. **Users** — Read from `.streamlit/secrets.toml` `[users]` table, hash passwords with bcrypt
2. **Portfolio History** — Read CSV, insert into database with correct `user_id` foreign key
3. **Daily Trend** — Read CSV, insert into database
4. **Current Holdings** — Read JSON, serialize strategies/holdings as JSON in database

### What happens to the old files?
- Old CSV/JSON files remain in `user_data/<slug>/` (for backup purposes)
- No new files are written there (all I/O goes through the database)
- Safe to delete after verifying the migration succeeded

## Performance Notes

### Single-file SQLite
- ✅ Zero setup, works on laptops/servers
- ✅ Excellent for up to 1000s of users
- ✅ Built-in backup (just copy the file)
- ⚠️ Not ideal for 100k+ concurrent users

### For higher scale
Consider migrating to **PostgreSQL**:
- True client-server architecture
- Multi-process concurrency handling
- Replication and high availability
- Same Python API (swap connection string)

## Security Checklist

- [x] Passwords hashed with bcrypt (12 rounds salt)
- [x] No plain-text passwords in the database
- [x] Foreign keys enabled (referential integrity)
- [x] DELETE CASCADE on users (clean up orphaned data)
- [x] JWT expiry (1 hour)
- [ ] HTTPS in production
- [ ] Environment variable for JWT secret key
- [ ] Database backups automated
- [ ] Access control / role-based permissions (future)

## References

- **SQLite:** https://www.sqlite.org/
- **bcrypt:** https://github.com/pyca/bcrypt
- **PyJWT:** https://pyjwt.readthedocs.io/
