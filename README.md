# Portfolio Tracker

AI-powered investment portfolio dashboard for Canadian families. Built with Streamlit, Plotly, and Claude AI.

## What It Does

Tracks a multi-person, multi-account investment portfolio with real-time price updates, P&L analysis, and AI-powered insights. Designed for Canadian investors managing TFSA, RSP/RRSP, RESP, and taxable Cash accounts across multiple brokerage platforms.

### Key Features

- **Family Portfolio Dashboard** — aggregated view across all holders and account types with drill-down to individual positions
- **Live Market Prices** — one-click refresh fetches current prices from Yahoo Finance, converts USD holdings to CAD, and recalculates all market values
- **Live Market Dashboard** — appears on price refresh with:
  - P&L Impact Treemap (size = dollar impact, color = gain/loss direction)
  - Side-by-side Gainers & Losers with charts and tables
  - Waterfall attribution chart showing each holding's contribution to total P&L
  - Owner-level breakdown (Male / Female)
  - Account-type breakdown (Cash / TFSA / RSP / RESP)
  - Full position-level detail table
- **Realized P&L Tracking** — sold positions with book cost, sale proceeds, and realized gains/losses
- **Restatement Views** — portfolio restated by account type with per-owner breakdowns and grand total cross-tab
- **AI Analysis** (powered by Claude) — six analysis modules:
  - Portfolio Insights — health score, concentration risk, top winners/losers
  - Rebalance Plan — specific buy/sell recommendations with live web search for current market context
  - Risk Assessment — risk score, currency exposure, drawdown scenarios
  - Tax Strategy — Canadian tax optimization (TFSA/RSP placement, tax-loss harvesting, capital gains planning)
  - News & Research — live web search for latest news, earnings, and outlook per holding
  - Ask Anything — free-form Q&A against your actual portfolio data

### Data Privacy

Portfolio data is **never stored in the GitHub repo**. The Excel file is base64-encoded and stored in Streamlit Cloud's encrypted secrets management. Holder names are masked during encoding. The repo contains only application code.

## Architecture

```
app.py                  Main Streamlit application (dashboard + AI tabs)
├── excel_converter.py  Excel import pipeline (column mapping, cleaning, splitting)
├── portfolio.py        CSV-based portfolio loader + yfinance price fetcher
├── price_updater.py    Live price fetcher (Yahoo Finance API + USD/CAD FX rate)
└── ai.py               Claude AI integration (insights, rebalance, news, risk, tax, chat)

encode_portfolio.py     Local-only helper to encode Excel → base64 for secrets (gitignored)
data/portfolio.xlsx     Local-only portfolio file (gitignored)
```

### Data Flow

```
Excel File (local)
  → encode_portfolio.py masks names, encodes to base64
  → base64 chunks stored in Streamlit Cloud Secrets
  → app.py decodes on startup → load_excel() → split_holdings()
  → Dashboard renders active holdings, cash, sold positions
  → "Refresh Live Prices" → price_updater.py fetches from Yahoo Finance
  → Live Market Dashboard compares live vs uploaded values
```

### Excel Format

The app expects an Excel file with these columns (case-insensitive):

| Column | Description |
|---|---|
| TICK | Ticker symbol (.NE = Canadian NEO exchange) |
| Par_TICK | Parent ticker (e.g., MSFT for MSFT.NE) |
| Name | Account holder |
| Platf | Platform code (DI = TD Direct Investing, ET = E*Trade/National Bank, WS = Wealthsimple) |
| Acc_Type | Account type (Cash, TFSA, RSP, RESP) |
| Curr | Currency (CAD, USD) |
| Units | Number of shares/units |
| Book_Pr_U | Cost per unit |
| Book_Value_CAD | Total book value in CAD |
| MK_Val_CAD | Market value in CAD |
| T_Cash_Bal_In_CAD | Cash balance in CAD |

A sample file with fake data is included: **`sample_portfolio.xlsx`**. Use it as a template for your own data.

See `excel_converter.py` → `COLUMN_MAP` for the full column mapping.

## Setup

### Prerequisites

- Python 3.10+
- An [Anthropic API key](https://console.anthropic.com/) for AI features

### Local Development

```bash
pip install -r requirements.txt
```

Create `.streamlit/secrets.toml`:

```toml
ANTHROPIC_API_KEY = "your-api-key"
```

Place your portfolio Excel file at `data/portfolio.xlsx`, then:

```bash
streamlit run app.py
```

### Streamlit Cloud Deployment

1. Push the repo to GitHub (can be public — no sensitive data in code)
2. Connect the repo to [Streamlit Community Cloud](https://share.streamlit.io)
3. Encode your portfolio file locally:
   ```bash
   python encode_portfolio.py path/to/your_portfolio.xlsx
   ```
4. In Streamlit Cloud → Settings → Secrets, add:
   ```toml
   ANTHROPIC_API_KEY = "your-api-key"
   PORTFOLIO_DATA_1 = "base64-chunk-1..."
   PORTFOLIO_DATA_2 = "base64-chunk-2..."
   ```
   (Copy contents from the generated `portfolio_b64.txt`)
5. Reboot the app

### Updating Portfolio Data

When you have a new Excel file:

```bash
python encode_portfolio.py path/to/new_portfolio.xlsx
```

Then copy the contents of `portfolio_b64.txt` into the Streamlit Cloud secrets, replacing the old `PORTFOLIO_DATA_*` keys. Remove any extra chunks if the new file produces fewer.

## Dependencies

| Package | Purpose |
|---|---|
| streamlit | Web application framework |
| pandas | Data manipulation |
| plotly | Interactive charts (treemap, waterfall, bar, pie) |
| anthropic | Claude AI API client |
| yfinance | Yahoo Finance price data |
| openpyxl | Excel file reading |
| truststore | System SSL certificate trust (for corporate environments) |

## Price Handling

- **Canadian-listed tickers** (`.NE`, `.TO`) — prices returned in CAD, no FX conversion needed
- **US-listed tickers** — prices returned in USD, multiplied by live USD/CAD exchange rate
- **TSX ETFs** (VDY, XIU, XSP, etc.) — automatically appended with `.TO` suffix for Yahoo Finance
- **Exchange rate** — fetched from Yahoo Finance (`USDCAD=X`), falls back to 1.37

## File Privacy Summary

| File | In Repo | Contains Sensitive Data |
|---|---|---|
| `app.py`, `ai.py`, `portfolio.py`, etc. | Yes | No |
| `data/portfolio.xlsx` | No (gitignored) | Yes — local only |
| `encode_portfolio.py` | No (gitignored) | Yes — contains name mapping |
| `portfolio_b64.txt` | No (gitignored) | Yes — encoded portfolio data |
| `.streamlit/secrets.toml` | No (gitignored) | Yes — API key + portfolio data |
| `test_excel.py` | No (gitignored) | Yes — sample data with names |
