## Stock Portfolio Suggestion Engine

**Course-style group project scaffold** demonstrating how introductory Python tooling can emulate a disciplined asset-allocation spreadsheet with a Streamlit façade. The codebase intentionally favors readable structure over speculative trading logic.

---

### What your team submits

Students collaborate on polishing narrative copy, customizing strategy universes (`data.py`), and rehearsing demos that highlight live quotes, KPI cards, persisted CSV history, and Plotly visuals.

---

### Feature checklist

| Requirement | Implementation pointer |
| --- | --- |
| Strategy maps (≥3 names each) | `data.py` |
| Allocation math | `portfolio_engine.build_portfolio_table` |
| Live quotes | Yahoo Finance ↔ `yfinance` |
| 5-record trend | `history.py` + Plotly chart in `app.py` |

---

### Local setup

1. **Pick Python 3.9+** (virtualenv recommended).

   ```bash
   cd stock_portfolio_engine
   python3 -m venv .venv && source .venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

2. **Launch Streamlit** (already inside the activated virtualenv):

   ```bash
   streamlit run app.py
   ```

   Your browser opens automatically unless you pass `--server.headless true`.

---

### Libraries & informal “API surface”

- **pandas** manipulates allocations, merges warning flags, prepares Plotly ingest frames  
- **yfinance** retrieves delayed/public Yahoo summaries without API secrets  
- **plotly express** sketches the freshest five persisted simulator executions  
- **streamlit** composes sidebar context, validations, KPI `st.metric` rows, styled tables  

No authentication, brokerage connectivity, or paid data vendors --- ideal for undergrad presentations.

---

### Investment methodology (elevator explanation)

Five canonical styles anchor the selectable menus:

| Strategy hook | Thesis in one sentence |
| --- | --- |
| Ethical Investing | Large, relatively transparent cash generators with durable brands |
| Growth Investing | Narrative-heavy innovators with asymmetric revenue ramps |
| Index Investing | Dirt-cheap core/satellite ETFs covering US stock, abroad, bonds |
| Quality Investing | Household staples anchored by ROIC-heavy operators |
| Value Investing | Franchise balance sheets favored when spreads widen |

Selecting **two** strategies unions their symbol lists (**duplicates vanish**) then applies **egalitarian slicing** --- every surviving ticker absorbs `budget ÷ N` USD so teams can intuitively reconcile rows with calculators.

Shares become `allocation ÷ last_price`; performance rows show **immediate mark-to-parity gains** (~0 absent bid/ask separation) reinforcing that this is pedagogy-grade simulation, not a trading terminal.

Historical CSV rows capture **`date`**, **`strategies`**, **`investment_amount`**, and **`total_portfolio_value`** each time presenters click **Generate**, enabling repeatable storytelling.

---

### Operational caveats classroom hosts should cite

Yahoo intermittently limits automated JSON pulls; rerun after a polite pause.

---

### Quick commands recap

From the activated virtual environment inside `stock_portfolio_engine/`:

```bash
pip install -r requirements.txt
streamlit run app.py
```

---

© Academic sample code — educational use only, not fiduciary advice.
