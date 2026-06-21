# Excel Portfolio Processing

## When to use
Use this skill when modifying, enhancing, or debugging the Excel file import pipeline for the portfolio tracker. This covers: adding new columns, changing parsing logic, updating the UI to show new data, or fixing import errors.

## Architecture — File Processing Pipeline

All Excel file processing MUST go through `excel_converter.py`. Never parse Excel directly in `app.py` or any other module.

```
Excel Upload (app.py)
  → load_excel() [excel_converter.py]
    → auto-detect header row (handles offset headers, row 0 or deeper)
    → drop NaN/empty columns and rows with blank tickers
    → rename columns via COLUMN_MAP → clean internal names
    → _clean_numeric() on all NUMERIC_COLS (handles commas, dashes, #VALUE!)
    → _clean_pct() on percentage columns
    → parse dates
  → split_holdings() [excel_converter.py]
    → separates: cash (zCash rows), active holdings, sold positions
    → resolves .NE/.ME tickers → parent ticker for price lookups
  → app.py renders using the split DataFrames
```

## Key Rules

1. **COLUMN_MAP is the single source of truth** for Excel → internal column name mapping. To add a new Excel column, add it to `COLUMN_MAP` in `excel_converter.py` and if numeric, also add to `NUMERIC_COLS`.

2. **_clean_numeric() must NOT check `dtype == object`** — Pandas 3.x uses `StringDtype` when reading with `dtype=str`, not `object`. Always cast to str and clean unconditionally.

3. **Header auto-detection** — the Excel file may have summary rows above the actual headers. `load_excel()` scans the first 10 rows looking for "TICK" or "Date_Updated" to find the header row. Both row-0 headers and offset headers work.

4. **zCash → Cash renaming** — Ticker "zCash" in the Excel means cash balances, not stock holdings. `split_holdings()` separates them into the `cash` DataFrame and renames the ticker and parent_ticker from "zCash" to "Cash" for display. `resolve_ticker()` returns `None` for both "zcash" and "cash" so they are excluded from price lookups.

5. **Canadian tickers** use `.NE` suffix (e.g., `MSFT.NE`). Legacy `.ME` suffix is also supported. `resolve_ticker()` strips the suffix and returns the `parent_ticker` for yfinance lookups.

6. **The UI uses `market_value_cad` and `book_value_cad` from the Excel** for all portfolio summary calculations — it does NOT fetch live prices for the Excel view. Live prices are only used for CSV uploads and AI analysis.

## Column Reference

| Excel Column | Internal Name | Type | Description |
|---|---|---|---|
| Date_Updated | date_updated | date | Snapshot date |
| TICK | ticker | str | Ticker (.NE = Canadian) |
| Par_TICK | parent_ticker | str | Underlying ticker |
| Name | holder | str | Account owner |
| Platf | platform | str | DI/ET/WS |
| Acc_Type | account_type | str | Cash/TFSA/RSP/RESP |
| Curr | currency | str | CAD/USD |
| Inv_Type | investment_type | str | Cash/Stock/Index |
| Book_Pr_U | cost_per_unit | float | Cost per share |
| Units | units | float | Shares held |
| Book_Value_CAD | book_value_cad | float | Book value in CAD |
| MK_Val_CAD | market_value_cad | float | Market value in CAD |
| T_Cash_Bal_In_CAD | total_cash_cad | float | Cash balance in CAD |
| Ret_Abs | unrealized_pnl | float | P&L original currency |
| Ret_CAD | unrealized_pnl_cad | float | P&L in CAD |
| %ge Return | return_pct | float | Return percentage |
| Stock_Eqv_USD | stock_equiv_usd | float | Stock equivalent USD |

## Testing

Always run `test_excel.py` AND test with the real file before UI changes:
```bash
python test_excel.py
python -c "from excel_converter import load_excel, split_holdings; df = load_excel(r'd:\Personal\Financial Accounts Trading Etc\Claude_File_19_June.xlsx'); s = split_holdings(df); print(f'Active: {len(s[\"active\"])}, Cash: {len(s[\"cash\"])}, Sold: {len(s[\"sold\"])}')"
```

## Common Pitfalls

- Streamlit caches imported modules — after changing `excel_converter.py`, kill all `python` processes running streamlit and clear `__pycache__/` before restarting
- Excel files may have trailing empty columns (NaN headers) — `load_excel()` drops these
- Some values contain `#VALUE!` from Excel formula errors — `_clean_numeric()` handles this
- `pd.read_excel(dtype=str)` in Pandas 3.x produces `StringDtype`, not `object` dtype
