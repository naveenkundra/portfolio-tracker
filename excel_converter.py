import pandas as pd
import streamlit as st

COLUMN_MAP = {
    "date_updated": "date_updated",
    "tick": "ticker",
    "par_tick": "parent_ticker",
    "name": "holder",
    "platf": "platform",
    "acc_type": "account_type",
    "curr": "currency",
    "inv_type": "investment_type",
    "dt. pur": "date_purchased",
    "date sold": "date_sold",
    "cash": "cash_balance",
    "cash_eqv": "cash_equivalent",
    "mkt_val": "market_value",
    "t_cash": "total_cash",
    "t_cash_bal_in_cad": "total_cash_cad",
    "book_p": "book_cost",
    "bk_cst_sold": "book_cost_sold",
    "book_pr_u": "cost_per_unit",
    "units": "units",
    "sold_units": "sold_units",
    "sold_mv": "sold_market_value",
    "sold_stock_price": "sold_price",
    "proft / loss booked (curr)": "realized_pnl",
    "proft / loss booked (cad)": "realized_pnl_cad",
    "ex_rt": "exchange_rate",
    "usd_ind": "currency_multiplier",
    "mkt_val_curr": "market_value_curr",
    "book_value_cad": "book_value_cad",
    "mk_val_cad": "market_value_cad",
    "ret_abs": "unrealized_pnl",
    "ret_cad": "unrealized_pnl_cad",
    "%ge return": "return_pct",
    "cash_cad_mk_val_cad": "total_value_cad",
    "stock_eqv_usd": "stock_equiv_usd",
}

PLATFORM_NAMES = {
    "DI": "TD Direct Investing",
    "ET": "E*Trade/National Bank",
    "WS": "Wealthsimple",
}

NUMERIC_COLS = [
    "cash_balance", "cash_equivalent", "market_value", "total_cash",
    "total_cash_cad", "book_cost", "book_cost_sold", "cost_per_unit",
    "units", "sold_units", "sold_market_value", "sold_price",
    "realized_pnl", "realized_pnl_cad", "exchange_rate",
    "currency_multiplier", "market_value_curr", "book_value_cad",
    "market_value_cad", "unrealized_pnl", "unrealized_pnl_cad",
    "total_value_cad",
    "stock_equiv_usd",
]


def _clean_numeric(series: pd.Series) -> pd.Series:
    series = series.astype(str).str.replace(",", "", regex=False)
    series = series.replace(["", "-", "N/A", "#VALUE!", "nan", "None", "NaN"], pd.NA)
    return pd.to_numeric(series, errors="coerce")


def _clean_pct(series: pd.Series) -> pd.Series:
    series = series.astype(str).str.replace("%", "", regex=False).str.replace(",", "", regex=False)
    series = series.replace(["", "-", "N/A", "#VALUE!", "nan", "None", "NaN"], pd.NA)
    return pd.to_numeric(series, errors="coerce") / 100


def load_excel(source) -> pd.DataFrame:
    try:
        df = pd.read_excel(source, header=None, dtype=str)
    except Exception as e:
        raise ValueError(f"Failed to read Excel file: {e}")

    # Auto-detect header row: find the row containing "TICK" or "Date_Updated"
    header_row = None
    for i in range(min(10, len(df))):
        row_vals = df.iloc[i].astype(str).str.strip().tolist()
        if any(v in ("TICK", "Date_Updated", "Dt. Pur") for v in row_vals):
            header_row = i
            break

    if header_row is not None:
        df.columns = df.iloc[header_row]
        df = df.iloc[header_row + 1:].reset_index(drop=True)

    # Drop columns with NaN/empty headers
    df = df.loc[:, df.columns.notna()]
    df = df.loc[:, df.columns.astype(str).str.strip() != ""]
    df.columns = df.columns.astype(str).str.strip().str.lower().str.replace(r"\s+", " ", regex=True)

    # Drop rows where ticker is empty/NaN (subtotal rows, blank rows)
    if "tick" in df.columns:
        df = df[df["tick"].astype(str).str.strip().replace(["", "nan", "None"], pd.NA).notna()]
        df = df.reset_index(drop=True)
    elif "ticker" in df.columns:
        df = df[df["ticker"].astype(str).str.strip().replace(["", "nan", "None"], pd.NA).notna()]
        df = df.reset_index(drop=True)

    rename = {}
    for orig, mapped in COLUMN_MAP.items():
        if orig in df.columns:
            rename[orig] = mapped
    df = df.rename(columns=rename)

    # Fallback: if "ticker" column is missing, look for partial matches
    if "ticker" not in df.columns:
        for col in df.columns:
            if isinstance(col, str) and "tick" in col and col != "parent_ticker":
                df = df.rename(columns={col: "ticker"})
                break

    for col in NUMERIC_COLS:
        if col in df.columns:
            df[col] = _clean_numeric(df[col])

    if "return_pct" in df.columns:
        df["return_pct"] = _clean_pct(df["return_pct"])

    if "date_updated" in df.columns:
        df["date_updated"] = pd.to_datetime(df["date_updated"], format="mixed", errors="coerce")
    if "date_purchased" in df.columns:
        df["date_purchased"] = pd.to_datetime(df["date_purchased"], format="mixed", errors="coerce")
    if "date_sold" in df.columns:
        df["date_sold"] = pd.to_datetime(df["date_sold"], format="mixed", errors="coerce")

    if "platform" in df.columns:
        df["platform_name"] = df["platform"].map(PLATFORM_NAMES).fillna(df["platform"])

    return df


def resolve_ticker(row: pd.Series) -> str:
    """Get the yfinance-compatible ticker for price lookup."""
    ticker = str(row.get("ticker", "")).strip()
    parent = str(row.get("parent_ticker", "")).strip()

    if ticker.lower() in ("zcash", "cash"):
        return None

    if ticker.endswith(".NE") or ticker.endswith(".ME"):
        return parent if parent and parent.lower() != "nan" else ticker.replace(".NE", "").replace(".ME", "")

    return ticker


def split_holdings(df: pd.DataFrame) -> dict:
    """Split the full DataFrame into cash positions and investment holdings."""
    if "ticker" not in df.columns:
        raise ValueError(f"No 'ticker' column found. Available columns: {list(df.columns)}")

    ticker_lower = df["ticker"].astype(str).str.lower().str.strip()
    is_cash = ticker_lower == "zcash"
    cash_df = df[is_cash].copy()
    cash_df.loc[:, "ticker"] = "Cash"
    if "parent_ticker" in cash_df.columns:
        cash_df.loc[:, "parent_ticker"] = "Cash"
    holdings_df = df[~is_cash].copy()

    holdings_df["lookup_ticker"] = holdings_df.apply(resolve_ticker, axis=1)

    is_sold = holdings_df.get("date_sold", pd.Series(dtype="object")).notna()
    # Rows with sold_market_value or book_cost_sold are completed sales
    has_sold_data = (holdings_df.get("sold_market_value", pd.Series(dtype="float64")).fillna(0) != 0) | \
                    (holdings_df.get("book_cost_sold", pd.Series(dtype="float64")).fillna(0) != 0)
    # Filter out zero-value positions (sold out but no sell date recorded)
    has_value = (holdings_df.get("market_value_cad", pd.Series(dtype="float64")).fillna(0) != 0) | \
                (holdings_df.get("units", pd.Series(dtype="float64")).fillna(0) != 0)
    is_truly_sold = is_sold | has_sold_data | (~is_sold & ~has_value)
    active_df = holdings_df[~is_truly_sold].copy()
    sold_df = holdings_df[is_truly_sold].copy()

    return {
        "cash": cash_df,
        "active": active_df,
        "sold": sold_df,
        "all_holdings": holdings_df,
    }


def to_portfolio_csv(df: pd.DataFrame) -> pd.DataFrame:
    """Convert active holdings to the simple CSV format used by portfolio.py."""
    splits = split_holdings(df)
    active = splits["active"].copy()

    if active.empty:
        return pd.DataFrame(columns=["ticker", "quantity", "cost_basis"])

    active["lookup_ticker"] = active.apply(resolve_ticker, axis=1)

    result = pd.DataFrame({
        "ticker": active["lookup_ticker"],
        "quantity": active["units"],
        "cost_basis": active["cost_per_unit"],
    })

    result = result.dropna(subset=["ticker"])
    result = result[result["quantity"].notna() & (result["quantity"] > 0)]
    return result.reset_index(drop=True)


def get_summary_by_dimension(df: pd.DataFrame, dimension: str) -> pd.DataFrame:
    """Summarize portfolio by a dimension (holder, platform, account_type, currency)."""
    splits = split_holdings(df)
    active = splits["active"]
    cash = splits["cash"]

    holdings_summary = active.groupby(dimension).agg(
        holdings_count=("ticker", "count"),
        market_value_cad=("market_value_cad", "sum"),
        book_value_cad=("book_value_cad", "sum"),
        unrealized_pnl_cad=("unrealized_pnl_cad", "sum"),
    ).reset_index()

    cash_summary = cash.groupby(dimension).agg(
        cash_cad=("total_cash_cad", "sum"),
    ).reset_index()

    summary = holdings_summary.merge(cash_summary, on=dimension, how="outer").fillna(0)
    summary["total_value_cad"] = summary["market_value_cad"] + summary["cash_cad"]

    return summary
