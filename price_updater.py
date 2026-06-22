try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

import pandas as pd
import requests
import streamlit as st
from datetime import datetime

_session = requests.Session()
_session.headers.update({"User-Agent": "Mozilla/5.0"})

# Canadian ETFs/stocks that need .TO (TSX) suffix for Yahoo
TSX_TICKERS = {"VDY", "XIU", "XSP", "XIC", "XEI", "ZAG", "VAB", "VCN", "HXT"}


def _resolve_yf_ticker(row: pd.Series) -> str:
    ticker = str(row.get("ticker", "")).strip()

    if ticker.lower() in ("cash", "zcash", ""):
        return None

    # Fix .ME → .NE (Canadian NEO exchange typo)
    if ticker.endswith(".ME"):
        ticker = ticker[:-3] + ".NE"

    # Canadian TSX ETFs need .TO suffix
    base = ticker.split(".")[0]
    if base in TSX_TICKERS and "." not in ticker:
        ticker = f"{base}.TO"

    return ticker


def _fetch_price_direct(ticker: str) -> float:
    try:
        url = f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker}?range=1d&interval=1d"
        r = _session.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return data["chart"]["result"][0]["meta"]["regularMarketPrice"]
    except Exception:
        pass
    return None


@st.cache_data(ttl=300)
def fetch_live_prices(tickers: tuple) -> dict:
    prices = {}
    for t in tickers:
        if not t:
            continue
        price = _fetch_price_direct(t)
        if price is not None:
            prices[t] = price
    return prices


@st.cache_data(ttl=300)
def fetch_exchange_rate() -> float:
    price = _fetch_price_direct("USDCAD=X")
    return price if price else 1.37


def update_portfolio_prices(active_df: pd.DataFrame, cash_df: pd.DataFrame) -> tuple:
    active = active_df.copy()
    cash = cash_df.copy()
    errors = []

    active["_yf_ticker"] = active.apply(_resolve_yf_ticker, axis=1)
    unique_tickers = tuple(sorted(set(t for t in active["_yf_ticker"].dropna().unique())))

    prices = fetch_live_prices(unique_tickers)
    usd_cad = fetch_exchange_rate()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if not prices:
        errors.append("Could not fetch any prices.")
        return active, cash, usd_cad, timestamp, errors

    active.loc[:, "exchange_rate"] = usd_cad

    for idx, row in active.iterrows():
        yf_ticker = row.get("_yf_ticker")
        if not yf_ticker or pd.isna(yf_ticker):
            continue

        if yf_ticker not in prices:
            errors.append(f"{yf_ticker}: price not found")
            continue

        price = prices[yf_ticker]
        units = row.get("units", 0)
        if pd.isna(units) or units == 0:
            continue

        # Price currency is determined by the TICKER, not the account currency:
        # .NE (NEO) and .TO (TSX) tickers → price is in CAD → no FX needed
        # All other tickers → price is in USD → multiply by exchange rate
        is_cad_listed = yf_ticker.endswith(".NE") or yf_ticker.endswith(".TO")
        multiplier = 1.0 if is_cad_listed else usd_cad
        active.at[idx, "currency_multiplier"] = multiplier

        book_cost = row.get("book_cost", 0) or 0
        book_value_cad = row.get("book_value_cad", 0) or 0

        mkt_val = units * price
        active.at[idx, "market_value"] = mkt_val
        active.at[idx, "market_value_curr"] = mkt_val

        mkt_val_cad = mkt_val * multiplier
        active.at[idx, "market_value_cad"] = mkt_val_cad

        if book_cost and not pd.isna(book_cost):
            active.at[idx, "unrealized_pnl"] = mkt_val - book_cost

        if book_cost and not pd.isna(book_cost) and book_cost != 0:
            active.at[idx, "return_pct"] = (mkt_val - book_cost) / book_cost

        if book_value_cad and not pd.isna(book_value_cad):
            active.at[idx, "unrealized_pnl_cad"] = mkt_val_cad - book_value_cad

        active.at[idx, "total_value_cad"] = mkt_val_cad

    if not cash.empty and "currency" in cash.columns:
        cash.loc[cash["currency"].str.upper() == "USD", "exchange_rate"] = usd_cad
        cash.loc[cash["currency"].str.upper() == "USD", "currency_multiplier"] = usd_cad

    active = active.drop(columns=["_yf_ticker"], errors="ignore")

    fetched = len(prices)
    total = len(unique_tickers)
    if fetched < total:
        errors.append(f"Fetched {fetched}/{total}. Missing: {[t for t in unique_tickers if t not in prices]}")

    return active, cash, usd_cad, timestamp, errors
