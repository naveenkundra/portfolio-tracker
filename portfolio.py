import json
import pandas as pd
import requests
import streamlit as st
import yfinance as yf

try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

_session = requests.Session()


def load_holdings(source) -> pd.DataFrame:
    try:
        if isinstance(source, str):
            df = pd.read_csv(source)
        else:
            df = pd.read_csv(source)
    except Exception as e:
        raise ValueError(f"Failed to parse CSV: {e}")

    df.columns = df.columns.str.strip().str.lower()

    if "ticker" not in df.columns or "quantity" not in df.columns:
        raise ValueError("CSV must contain 'ticker' and 'quantity' columns.")

    df["ticker"] = df["ticker"].astype(str).str.strip().str.upper()
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")

    if "cost_basis" in df.columns:
        df["cost_basis"] = pd.to_numeric(df["cost_basis"], errors="coerce")
    else:
        df["cost_basis"] = None

    if "target_weight" in df.columns:
        df["target_weight"] = pd.to_numeric(df["target_weight"], errors="coerce")
    else:
        df["target_weight"] = None

    bad_rows = df[df["quantity"].isna()]
    if not bad_rows.empty:
        st.warning(f"Skipping {len(bad_rows)} row(s) with invalid quantity.")
        df = df.dropna(subset=["quantity"])

    df = df[df["quantity"] > 0].reset_index(drop=True)
    return df


@st.cache_data(ttl=300)
def fetch_prices(tickers: list) -> dict:
    prices = {}
    for ticker in tickers:
        try:
            t = yf.Ticker(ticker, session=_session)
            hist = t.history(period="5d")
            if hist.empty or len(hist) < 1:
                prices[ticker] = {"price": None, "previous_close": None}
                continue
            current_price = hist["Close"].iloc[-1]
            previous_close = hist["Close"].iloc[-2] if len(hist) >= 2 else current_price
            prices[ticker] = {
                "price": float(current_price),
                "previous_close": float(previous_close),
            }
        except Exception:
            prices[ticker] = {"price": None, "previous_close": None}
    return prices


def build_portfolio(holdings_df: pd.DataFrame, prices: dict) -> pd.DataFrame:
    df = holdings_df.copy()

    df["price"] = df["ticker"].map(lambda t: prices.get(t, {}).get("price"))
    df["previous_close"] = df["ticker"].map(lambda t: prices.get(t, {}).get("previous_close"))

    resolved = df["price"].notna()
    if not resolved.all():
        unresolved = df.loc[~resolved, "ticker"].tolist()
        st.warning(f"Could not fetch prices for: {', '.join(unresolved)}")

    df["current_value"] = df["quantity"] * df["price"]
    total_value = df.loc[resolved, "current_value"].sum()
    df["weight"] = df["current_value"] / total_value if total_value > 0 else 0

    df["pnl"] = None
    df["pnl_pct"] = None
    has_cost = df["cost_basis"].notna() & resolved
    if has_cost.any():
        df.loc[has_cost, "pnl"] = (df.loc[has_cost, "price"] - df.loc[has_cost, "cost_basis"]) * df.loc[has_cost, "quantity"]
        df.loc[has_cost, "pnl_pct"] = (df.loc[has_cost, "price"] - df.loc[has_cost, "cost_basis"]) / df.loc[has_cost, "cost_basis"]

    df["day_change"] = None
    has_prev = df["previous_close"].notna() & resolved
    if has_prev.any():
        df.loc[has_prev, "day_change"] = (df.loc[has_prev, "price"] - df.loc[has_prev, "previous_close"]) / df.loc[has_prev, "previous_close"]

    return df


def get_portfolio_snapshot(portfolio_df: pd.DataFrame) -> str:
    df = portfolio_df.dropna(subset=["price"])
    total_value = df["current_value"].sum()
    total_pnl = df["pnl"].sum() if df["pnl"].notna().any() else None

    holdings = []
    for _, row in df.iterrows():
        holding = {
            "ticker": row["ticker"],
            "quantity": row["quantity"],
            "price": round(row["price"], 2),
            "value": round(row["current_value"], 2),
            "weight": f"{row['weight']:.1%}",
        }
        if pd.notna(row.get("pnl")):
            holding["pnl"] = round(row["pnl"], 2)
            holding["pnl_pct"] = f"{row['pnl_pct']:.1%}"
        if pd.notna(row.get("target_weight")):
            holding["target_weight"] = f"{row['target_weight']:.1%}"
        holdings.append(holding)

    snapshot = {
        "total_value": round(total_value, 2),
        "total_pnl": round(total_pnl, 2) if total_pnl is not None else None,
        "num_holdings": len(holdings),
        "holdings": holdings,
    }

    return json.dumps(snapshot, indent=2)
