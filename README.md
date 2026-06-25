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
  - Owner-level breakdown
  - Account-type breakdown (Cash / TFSA / RSP / RESP)
  - Full position-level detail table
- **Portfolio Update & Download** — after refreshing prices, download the updated Excel with live values baked in, or copy base64-encoded data to update Streamlit secrets directly from the app
- **Realized P&L Tracking** — sold positions with book cost, sale proceeds, and realized gains/losses
- **Restatement Views** — portfolio restated by account type with per-owner breakdowns and grand total cross-tab
- **Demo Mode** — runs with sample data when no portfolio is configured, so anyone can explore the dashboard without real data
- **AI Analysis** (powered by Claude) — six analysis modules:
  - Portfolio Insights — health score, concentration risk, top winners/losers
  - Rebalance Plan — specific buy/sell recommendations with live web search for current market context
  - Risk Assessment — risk score, currency exposure, drawdown scenarios
  - Tax Strategy — Canadian tax optimization (TFSA/RSP placement, tax-loss harvesting, capital gains planning)
  - News & Research — live web search for latest news, earnings, and outlook per holding
  - Ask Anything — free-form Q&A against your actual portfolio data

### Demo Mode

The app ships with `sample_portfolio.xlsx` containing fake data. When no real portfolio is configured (no Streamlit secrets and no local `data/portfolio.xlsx`), the app automatically loads this sample and shows a "Demo Mode" banner. This lets anyone explore the full dashboard without exposing real financial data.

### Data Privacy

Portfolio data is **never stored in the GitHub repo**. The Excel file is base64-encoded and stored in Streamlit Cloud's encrypted secrets management. Holder names are masked during encoding. The repo contains only application code and sample data.

## Architecture

```
app.py                  Main Streamlit application (dashboard + AI tabs)
+-- excel_converter.py  Excel import/export pipeline (column mapping, cleaning, splitting)
+-- portfolio.py        CSV-based portfolio loader + yfinance price fetcher
+-- price_updater.py    Live price fetcher (Yahoo Finance API + USD/CAD FX rate)
+-- ai.py               Claude AI integration (insights, rebalance, news, risk, tax, chat)

sample_portfolio.xlsx   Sample Excel with fake data for demo mode (committed)
encode_portfolio.py     Local-only: encode Excel to base64 with name masking (gitignored)
update_portfolio.py     Local-only: fetch live prices and update Excel + secrets (gitignored)
data/portfolio.xlsx     Local-only: real portfolio file (gitignored)
```

### Data Flow

```
Excel File (local)
  -> encode_portfolio.py masks names, encodes to base64
  -> base64 chunks stored in Streamlit Cloud Secrets
  -> app.py decodes on startup -> load_excel() -> split_holdings()
  -> Dashboard renders active holdings, cash, sold positions
  -> "Refresh Live Prices" -> price_updater.py fetches from Yahoo Finance
  -> Live Market Dashboard compares live vs uploaded values
  -> "Download Updated Portfolio" -> exports Excel with live prices baked in
```

### Excel Format

The app expects an Excel file with these columns (case-insensitive). See `sample_portfolio.xlsx` for a color-coded template showing which columns are user-input (green), calculated (orange), or lookup (blue).

| Column | Type | Description |
|---|---|---|
| Date_Updated | Input | Date of snapshot |
| TICK | Input | Ticker symbol (.NE = Canadian NEO exchange) |
| Par_TICK | Input | Parent ticker (e.g., MSFT for MSFT.NE) |
| Name | Input | Account holder |
| Platf | Input | Platform code (DI = TD Direct Investing, ET = E*Trade/National Bank, WS = Wealthsimple) |
| Acc_Type | Input | Account type (Cash, TFSA, RSP, RESP) |
| Curr | Input | Currency (CAD, USD) |
| Inv_Type | Input | Investment type (Stock, Index, Cash) |
| Book_Pr_U | Input | Cost per unit (purchase price) |
| Units | Input | Shares currently held |
| Mkt_Val | Input | Market value from brokerage |
| Ex_Rt | Lookup | USD/CAD exchange rate |
| Book_P | Calc | = Units x Book_Pr_U |
| USD_Ind | Calc | = 1 if CAD, else Ex_Rt |
| Book_Value_CAD | Calc | = Book_P x USD_Ind |
| MK_Val_CAD | Calc | = Mkt_Val x USD_Ind |
| Ret_Abs | Calc | = Mkt_Val - Book_P |
| Ret_CAD | Calc | = MK_Val_CAD - Book_Value_CAD |
| %ge Return | Calc | = Ret_Abs / Book_P |

See `excel_converter.py` -> `COLUMN_MAP` for the full 34-column mapping.

## Setup

### Prerequisites

- Python 3.10+
- An [Anthropic API key](https://console.anthropic.com/) for AI features

### Quick Start (Demo Mode)

```bash
pip install -r requirements.txt
streamlit run app.py
```

The app will load `sample_portfolio.xlsx` automatically and run in demo mode.

### Local Development (Real Data)

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
4. In Streamlit Cloud -> Settings -> Secrets, add:
   ```toml
   ANTHROPIC_API_KEY = "your-api-key"
   PORTFOLIO_DATA_1 = "base64-chunk-1..."
   PORTFOLIO_DATA_2 = "base64-chunk-2..."
   ```
   (Copy contents from the generated `portfolio_b64.txt`)
5. Reboot the app

### Updating Portfolio Data

**From the app:** Click "Refresh Live Prices", then use the "Download Updated Portfolio" button in the sidebar. The "Update Streamlit Secrets" expander shows the base64 chunks ready to copy.

**From the command line:**

```bash
python update_portfolio.py data/portfolio.xlsx
```

This fetches live prices, saves `data/portfolio_updated.xlsx`, and re-encodes to `portfolio_b64.txt` with name masking. Copy the contents of `portfolio_b64.txt` into Streamlit Cloud secrets.

**Manual update:** Edit your Excel, then re-encode:

```bash
python encode_portfolio.py path/to/updated_portfolio.xlsx
```

## Dependencies

| Package | Purpose |
|---|---|
| streamlit | Web application framework |
| pandas | Data manipulation |
| plotly | Interactive charts (treemap, waterfall, bar, pie) |
| anthropic | Claude AI API client |
| yfinance | Yahoo Finance price data |
| openpyxl | Excel file reading/writing |
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
| `sample_portfolio.xlsx` | Yes | No — fake data only |
| `data/portfolio.xlsx` | No (gitignored) | Yes — local only |
| `encode_portfolio.py` | No (gitignored) | Yes — contains name mapping |
| `update_portfolio.py` | No (gitignored) | Yes — uses real data |
| `portfolio_b64.txt` | No (gitignored) | Yes — encoded portfolio data |
| `.streamlit/secrets.toml` | No (gitignored) | Yes — API key + portfolio data |
| `test_excel.py` | No (gitignored) | Yes — sample data with names |
