# Stock Portfolio Suggestion Engine — REST API Guide

## Overview

The new FastAPI layer decouples the backend logic from Streamlit, enabling mobile apps, external integrations, and other services to consume the same business logic. The Streamlit app continues to work unchanged.

## Architecture

```
Streamlit App (unchanged)
├── Uses: auth.py, portfolio_engine.py, history.py, data.py

FastAPI Server (new)
├── Uses: api_auth.py (Streamlit-free), portfolio_engine.py, history.py, data.py
├── Provides: REST endpoints with JWT authentication
└── Stores: Same user_data directory as Streamlit
```

## Running Both Services

**Terminal 1 — Streamlit** (unchanged):
```bash
streamlit run app.py
```

**Terminal 2 — FastAPI** (new):
```bash
# Start the API server (dependencies already installed from requirements.txt)
python3 -m uvicorn api.server:app --reload --port 8000
```

**Swagger UI** (auto-generated docs):
```
http://localhost:8000/docs
```

## API Endpoints

### 1. Authentication

#### `POST /api/auth/login`
Get a JWT access token.

**Request:**
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "demo",
    "password": "demo123"
  }'
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

---

### 2. Strategies

#### `GET /api/strategies`
List all investment strategies with their tickers.

**Request:**
```bash
curl http://localhost:8000/api/strategies
```

**Response:**
```json
{
  "strategies": [
    {
      "name": "Ethical Investing",
      "tickers": ["AAPL", "ADBE", "MSFT"]
    },
    {
      "name": "Growth Investing",
      "tickers": ["NVDA", "AMZN", "TSLA"]
    }
  ]
}
```

---

### 3. Portfolio Generation

#### `POST /api/portfolio/generate`
Generate a new portfolio from selected strategies and investment amount.

**Request:**
```bash
TOKEN="<your-jwt-token>"
curl -X POST http://localhost:8000/api/portfolio/generate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "investment_amount": 10000,
    "strategies": ["Ethical Investing", "Growth Investing"]
  }'
```

**Response:**
```json
{
  "rows": [
    {
      "Ticker": "AAPL",
      "Strategy": "Ethical Investing",
      "Allocation (USD)": 5000.0,
      "Current Price (USD)": 293.26,
      "Shares": 17.05,
      "Current Value (USD)": 5000.0,
      "Gain/Loss (USD)": 0.0
    }
  ],
  "dollar_per_ticker": 2000.0,
  "total_portfolio_value": 10000.0,
  "failed_tickers": []
}
```

---

### 4. Portfolio Holdings

#### `GET /api/portfolio/holdings`
Load the user's currently saved holdings.

**Request:**
```bash
curl -X GET http://localhost:8000/api/portfolio/holdings \
  -H "Authorization: Bearer $TOKEN"
```

**Response:**
```json
{
  "holdings": [["AAPL", 17.05], ["ADBE", 19.76]],
  "strategies": ["Ethical Investing"],
  "investment_amount": 10000.0,
  "dollar_per_ticker": 3333.33,
  "saved_at": "2026-05-10T19:10:51"
}
```

---

### 5. Mark-to-Market

#### `POST /api/portfolio/mark-to-market`
Re-price the user's saved holdings with fresh quotes.

**Request:**
```bash
curl -X POST http://localhost:8000/api/portfolio/mark-to-market \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Response:**
```json
{
  "rows": [
    {
      "Ticker": "AAPL",
      "Strategy": "Ethical Investing",
      "Allocation (USD)": 3333.33,
      "Current Price (USD)": 293.26,
      "Shares": 11.37,
      "Current Value (USD)": 3333.33,
      "Gain/Loss (USD)": 0.0
    }
  ],
  "total_portfolio_value": 9999.99,
  "gains": [
    {
      "ticker": "AAPL",
      "gain_loss": 0.0
    }
  ]
}
```

---

### 6. Portfolio History

#### `GET /api/portfolio/history`
Load recent portfolio generation records (last 5 by default).

**Request:**
```bash
curl -X GET "http://localhost:8000/api/portfolio/history?limit=10" \
  -H "Authorization: Bearer $TOKEN"
```

**Response:**
```json
[
  {
    "date": "2026-05-10 19:10:51",
    "strategies": "Ethical Investing + Growth Investing",
    "investment_amount": 10000.0,
    "total_portfolio_value": 10000.02
  }
]
```

---

### 7. Daily Trend

#### `GET /api/portfolio/trend`
Load the daily portfolio value trend (up to 5 days).

**Request:**
```bash
curl -X GET "http://localhost:8000/api/portfolio/trend?limit=5" \
  -H "Authorization: Bearer $TOKEN"
```

**Response:**
```json
[
  {
    "date": "2026-05-10",
    "total_portfolio_value": 10000.0
  }
]
```

#### `POST /api/portfolio/trend`
Update today's portfolio value in the trend.

**Request:**
```bash
curl -X POST http://localhost:8000/api/portfolio/trend \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "total_portfolio_value": 10250.50
  }'
```

**Response:**
```json
{
  "status": "updated"
}
```

---

## Authentication

All endpoints except `/api/auth/login` and `/api/strategies` require JWT authentication.

**Header format:**
```
Authorization: Bearer <your-jwt-token>
```

**Token expiry:** 1 hour from creation

---

## Error Responses

**Invalid credentials (401):**
```json
{
  "detail": "Invalid credentials"
}
```

**Missing authorization (401):**
```json
{
  "detail": "Missing or invalid Authorization header"
}
```

**Invalid input (400):**
```json
{
  "detail": "Investment amount must be at least $5,000; Please pick either one or exactly two investment strategies"
}
```

---

## Using with curl (Quick Start)

```bash
#!/bin/bash

# 1. Login
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"demo","password":"demo123"}' | jq -r '.access_token')

# 2. Generate portfolio
curl -s -X POST http://localhost:8000/api/portfolio/generate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"investment_amount":10000,"strategies":["Ethical Investing"]}' | jq .

# 3. Mark-to-market
curl -s -X POST http://localhost:8000/api/portfolio/mark-to-market \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}' | jq .

# 4. Get history
curl -s http://localhost:8000/api/portfolio/history \
  -H "Authorization: Bearer $TOKEN" | jq .
```

---

## Integration with Python Clients

```python
import requests

BASE_URL = "http://localhost:8000"

# Login
response = requests.post(f"{BASE_URL}/api/auth/login", json={
    "username": "demo",
    "password": "demo123"
})
token = response.json()["access_token"]

headers = {"Authorization": f"Bearer {token}"}

# Generate portfolio
response = requests.post(
    f"{BASE_URL}/api/portfolio/generate",
    json={"investment_amount": 10000, "strategies": ["Ethical Investing"]},
    headers=headers
)
portfolio = response.json()
print(portfolio)

# Get holdings
response = requests.get(f"{BASE_URL}/api/portfolio/holdings", headers=headers)
holdings = response.json()
print(holdings)
```

---

## Notes

- **No Streamlit changes:** The original `app.py`, `auth.py`, and all other modules remain unchanged.
- **Shared data:** Both Streamlit and the API use the same `user_data/` directory for persistence.
- **JWT secret:** Reads from `JWT_SECRET_KEY` environment variable or `[jwt]` section in `secrets.toml`. Falls back to a dev-only insecure key if neither is set.
- **Scalability:** The API can be deployed independently of Streamlit to any server (Heroku, AWS, Azure, etc.).
