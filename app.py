import streamlit as st
import pandas as pd
import plotly.express as px
from portfolio import load_holdings, fetch_prices, build_portfolio, get_portfolio_snapshot
from ai import generate_insights, suggest_rebalance, summarize_news, risk_assessment, tax_strategy, ai_chat
from excel_converter import load_excel, split_holdings, to_portfolio_csv, get_summary_by_dimension
from price_updater import update_portfolio_prices, fetch_exchange_rate

st.set_page_config(page_title="Portfolio Tracker", page_icon="📊", layout="wide")

# --- Sidebar ---
with st.sidebar:
    st.title("📊 Portfolio Tracker")
    st.caption("AI-powered investment portfolio analysis")

    uploaded_file = st.file_uploader(
        "Upload holdings (CSV or Excel)",
        type=["csv", "xlsx", "xls"],
    )

    use_sample = st.button("Use Sample Data")

    st.divider()
    refresh_prices = st.button("📡 Refresh Live Prices", use_container_width=True, type="primary")
    if refresh_prices:
        st.cache_data.clear()
        st.session_state["live_prices"] = True

    if st.session_state.get("live_prices"):
        st.success("Live prices active")
    else:
        st.caption("Using Excel values. Click above for live prices.")

    st.divider()
    with st.expander("Supported Formats"):
        st.markdown("**CSV** — simple format:")
        st.code("ticker,quantity,cost_basis\nAAPL,15,175.50", language="csv")
        st.markdown("**Excel** — full format with columns: TICK, Units, Book_Pr_U, Name, Platf, Acc_Type, Curr, etc.")

# --- Load Data ---
is_excel = False

if use_sample:
    st.session_state["source"] = "sample"
if uploaded_file:
    st.session_state["source"] = "upload"
    st.session_state["uploaded_file"] = uploaded_file

import os
DEFAULT_PORTFOLIO = os.path.join(os.path.dirname(__file__), "data", "portfolio.xlsx")

if "source" not in st.session_state:
    if os.path.exists(DEFAULT_PORTFOLIO):
        st.session_state["source"] = "default"
    else:
        st.title("📊 Portfolio Tracker")
        st.info("Upload a CSV or Excel file, or click **Use Sample Data** in the sidebar to get started.")
        st.stop()

try:
    if st.session_state["source"] == "sample":
        holdings_df = load_holdings("sample_holdings.csv")
    elif st.session_state["source"] == "default":
        is_excel = True
        excel_df = load_excel(DEFAULT_PORTFOLIO)
    else:
        file = st.session_state["uploaded_file"]
        if file.name.endswith((".xlsx", ".xls")):
            is_excel = True
            excel_df = load_excel(file)
        else:
            holdings_df = load_holdings(file)
except ValueError as e:
    st.error(str(e))
    st.stop()


# ============================================================
# EXCEL VIEW — owner-level summary with drill-down
# ============================================================
if is_excel:
    splits = split_holdings(excel_df)
    active = splits["active"]
    cash = splits["cash"]
    sold = splits["sold"]

    # Live price refresh
    if st.session_state.get("live_prices"):
        with st.spinner("Fetching live market prices..."):
            active, cash, live_fx_rate, price_timestamp, price_errors = update_portfolio_prices(active, cash)
        if price_errors:
            for err in price_errors:
                st.warning(f"Price update: {err}")
        st.sidebar.caption(f"Prices as of: {price_timestamp}")
        st.sidebar.caption(f"USD/CAD: {live_fx_rate:.4f}")

    has_mv = "market_value_cad" in active.columns
    has_bv = "book_value_cad" in active.columns

    # Display name mapping: holder → display label with gender
    HOLDER_DISPLAY = {
        "Naveen": "👨 Male",
        "Shweta": "👩 Female",
    }
    def _display_holder(name):
        return HOLDER_DISPLAY.get(name, name)

    # --- Global color styling ---
    PNL_CSS = """
    <style>
    .pnl-gain { color: #2e7d32; background-color: #e8f5e9; padding: 2px 8px; border-radius: 4px; font-weight: 600; }
    .pnl-loss { color: #c62828; background-color: #ffebee; padding: 2px 8px; border-radius: 4px; font-weight: 600; }
    .pnl-neutral { color: #666; }
    .summary-card { padding: 12px; border-radius: 8px; margin-bottom: 8px; }
    .summary-card-gain { border-left: 4px solid #2e7d32; background-color: #f1f8e9; }
    .summary-card-loss { border-left: 4px solid #c62828; background-color: #fce4ec; }
    .total-banner { padding: 16px 24px; border-radius: 10px; margin: 12px 0; font-size: 1.1em; text-align: center; }
    .total-banner-gain { background: linear-gradient(135deg, #e8f5e9, #c8e6c9); border: 2px solid #4caf50; }
    .total-banner-loss { background: linear-gradient(135deg, #ffebee, #ffcdd2); border: 2px solid #ef5350; }
    .total-banner b { font-size: 1.4em; }
    .owner-pnl { display: inline-block; padding: 4px 12px; border-radius: 6px; font-weight: 700; font-size: 1.05em; margin-left: 8px; }
    .owner-pnl-gain { background-color: #e8f5e9; color: #2e7d32; }
    .owner-pnl-loss { background-color: #ffebee; color: #c62828; }
    </style>
    """
    st.markdown(PNL_CSS, unsafe_allow_html=True)

    def _pnl_html(val, show_sign=True):
        if pd.isna(val) or val == 0:
            return '<span class="pnl-neutral">—</span>'
        sign = "+" if val > 0 and show_sign else ""
        cls = "pnl-gain" if val > 0 else "pnl-loss"
        return f'<span class="{cls}">{sign}${val:,.0f}</span>'

    def _pct_html(val):
        if pd.isna(val):
            return '<span class="pnl-neutral">—</span>'
        sign = "+" if val > 0 else ""
        cls = "pnl-gain" if val > 0 else "pnl-loss"
        return f'<span class="{cls}">{sign}{val:.1%}</span>'

    # --- Helper: format money ---
    def _money(val):
        if pd.isna(val) or val == 0:
            return "—"
        return f"${val:,.0f}"

    def _pct(val):
        if pd.isna(val):
            return "—"
        return f"{val:.1%}"

    # --- Helper: color P&L cells in dataframes ---
    def _style_pnl(val):
        if not isinstance(val, (int, float)) or pd.isna(val) or val == 0:
            return ""
        if val > 0:
            return "color: #2e7d32; background-color: #e8f5e9"
        return "color: #c62828; background-color: #ffebee"

    # --- Helper: build summary row ---
    def _summarize(df, cash_df=None):
        mv = df["market_value_cad"].sum() if has_mv else 0
        bv = df["book_value_cad"].sum() if has_bv else 0
        pnl = mv - bv
        pnl_pct = pnl / bv if bv else None
        cash_val = cash_df["total_cash_cad"].sum() if cash_df is not None and not cash_df.empty else 0
        return {"market_value_cad": mv, "book_value_cad": bv, "pnl": pnl, "pnl_pct": pnl_pct, "cash_cad": cash_val, "total": mv + cash_val, "count": len(df)}

    # ── Realized P&L from sold positions ──
    real_sold = sold[sold["book_cost_sold"].notna() | sold["sold_market_value"].notna() | sold["realized_pnl_cad"].notna()] if not sold.empty else pd.DataFrame()
    total_realized_cad = real_sold["realized_pnl_cad"].sum() if not real_sold.empty and "realized_pnl_cad" in real_sold.columns else 0
    total_sold_mv = real_sold["sold_market_value"].sum() if not real_sold.empty and "sold_market_value" in real_sold.columns else 0
    total_bk_sold = real_sold["book_cost_sold"].sum() if not real_sold.empty and "book_cost_sold" in real_sold.columns else 0

    # ── FAMILY PORTFOLIO SUMMARY ──
    family = _summarize(active, cash)
    holders = sorted(active["holder"].dropna().unique()) if "holder" in active.columns else []
    acc_type_order = ["Cash", "TFSA", "RSP", "RESP"]

    st.markdown("### 👨‍👩‍👧‍👦 Family Portfolio Summary")

    # Bold total P&L banner
    combined_pnl = family["pnl"] + total_realized_cad
    pnl_banner_cls = "total-banner-gain" if combined_pnl >= 0 else "total-banner-loss"
    pnl_sign = "+" if family["pnl"] > 0 else ""
    real_sign = "+" if total_realized_cad > 0 else ""
    comb_sign = "+" if combined_pnl > 0 else ""
    st.markdown(f"""<div class="total-banner {pnl_banner_cls}">
        Total Portfolio: <b>${family['total']:,.0f}</b> &nbsp;|&nbsp;
        Unrealized: <b>{pnl_sign}${family['pnl']:,.0f}</b> &nbsp;|&nbsp;
        Realized: <b>{real_sign}${total_realized_cad:,.0f}</b> &nbsp;|&nbsp;
        Combined P&L: <b>{comb_sign}${combined_pnl:,.0f}</b>
    </div>""", unsafe_allow_html=True)

    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Total Value (CAD)", _money(family["total"]))
    m2.metric("Market Value", _money(family["market_value_cad"]))
    m3.metric("Book Value", _money(family["book_value_cad"]))
    m4.metric("Unrealized P&L", _money(family["pnl"]),
              delta=_pct(family["pnl_pct"]) if family["pnl_pct"] else None)
    m5.metric("Realized P&L (CAD)", _money(total_realized_cad))
    m6.metric("Cash (CAD)", _money(family["cash_cad"]))

    # ── Family-level account type breakdown ──
    family_acc_types = sorted(active["account_type"].dropna().unique()) if "account_type" in active.columns else []
    ordered_family_acc = [a for a in acc_type_order if a in family_acc_types] + [a for a in family_acc_types if a not in acc_type_order]

    if ordered_family_acc:
        st.markdown("#### By Account Type")
        acc_cols = st.columns(len(ordered_family_acc) + 1)
        for col, acc_type in zip(acc_cols, ordered_family_acc):
            acc_active = active[active["account_type"] == acc_type]
            acc_cash_df = cash[cash["account_type"] == acc_type] if not cash.empty and "account_type" in cash.columns else pd.DataFrame()
            a = _summarize(acc_active, acc_cash_df)
            with col:
                border_cls = "summary-card-gain" if a["pnl"] >= 0 else "summary-card-loss"
                st.markdown(f"""<div class="summary-card {border_cls}">
                    <b>{acc_type}</b> ({a['count']})<br>
                    MV: ${a['market_value_cad']:,.0f}<br>
                    BV: ${a['book_value_cad']:,.0f}<br>
                    P&L: {_pnl_html(a['pnl'])} ({_pct_html(a['pnl_pct'])})<br>
                    Cash: ${a['cash_cad']:,.0f}<br>
                    <b>Total: ${a['total']:,.0f}</b>
                </div>""", unsafe_allow_html=True)
        # Grand total card
        with acc_cols[-1]:
            border_cls = "summary-card-gain" if family["pnl"] >= 0 else "summary-card-loss"
            st.markdown(f"""<div class="summary-card {border_cls}" style="border-left-width: 6px;">
                <b>TOTAL</b> ({family['count']})<br>
                MV: ${family['market_value_cad']:,.0f}<br>
                BV: ${family['book_value_cad']:,.0f}<br>
                P&L: {_pnl_html(family['pnl'])} ({_pct_html(family['pnl_pct'])})<br>
                Cash: ${family['cash_cad']:,.0f}<br>
                <b>Total: ${family['total']:,.0f}</b>
            </div>""", unsafe_allow_html=True)

    # ── Family-level charts ──
    if has_mv:
        chart1, chart2 = st.columns(2)
        with chart1:
            if len(holders) > 1:
                holder_alloc = active.groupby("holder")["market_value_cad"].sum().reset_index()
                cash_alloc = cash.groupby("holder")["total_cash_cad"].sum().reset_index() if not cash.empty else pd.DataFrame(columns=["holder", "total_cash_cad"])
                family_alloc = holder_alloc.merge(cash_alloc, on="holder", how="left").fillna(0)
                family_alloc["total_cad"] = family_alloc["market_value_cad"] + family_alloc["total_cash_cad"]
                family_alloc["display_name"] = family_alloc["holder"].map(_display_holder)
                fig_family = px.pie(family_alloc, values="total_cad", names="display_name", hole=0.4,
                                    title="By Owner")
                fig_family.update_traces(texttemplate="$%{value:,.0f}", hovertemplate="%{label}: $%{value:,.0f}<extra></extra>")
                fig_family.update_layout(margin=dict(t=40, b=20, l=20, r=20), height=300)
                st.plotly_chart(fig_family, use_container_width=True)

        with chart2:
            if ordered_family_acc:
                acc_alloc_all = active.groupby("account_type")["market_value_cad"].sum().reset_index()
                acc_cash_all = cash.groupby("account_type")["total_cash_cad"].sum().reset_index() if not cash.empty else pd.DataFrame(columns=["account_type", "total_cash_cad"])
                acc_merged_all = acc_alloc_all.merge(acc_cash_all, on="account_type", how="outer").fillna(0)
                acc_merged_all["total"] = acc_merged_all["market_value_cad"] + acc_merged_all["total_cash_cad"]
                fig_acc_family = px.pie(acc_merged_all, values="total", names="account_type", hole=0.4,
                                        title="By Account Type")
                fig_acc_family.update_traces(texttemplate="$%{value:,.0f}", hovertemplate="%{label}: $%{value:,.0f}<extra></extra>")
                fig_acc_family.update_layout(margin=dict(t=40, b=20, l=20, r=20), height=300)
                st.plotly_chart(fig_acc_family, use_container_width=True)

        # ── Family P&L by Holding (aggregated by parent_ticker) ──
        ticker_col = "parent_ticker" if "parent_ticker" in active.columns else "ticker"
        family_pnl = active.groupby(ticker_col).agg(
            mv=("market_value_cad", "sum"),
            bv=("book_value_cad", "sum"),
        ).reset_index()
        family_pnl["pnl"] = family_pnl["mv"] - family_pnl["bv"]
        family_pnl = family_pnl[family_pnl["pnl"].abs() > 0].sort_values("pnl")
        if not family_pnl.empty:
            fig_family_pnl = px.bar(
                family_pnl, x=ticker_col, y="pnl",
                color=family_pnl["pnl"].apply(lambda x: "Gain" if x >= 0 else "Loss"),
                color_discrete_map={"Gain": "#4caf50", "Loss": "#ef5350"},
                title="P&L by Holding — Family (CAD)",
            )
            fig_family_pnl.update_traces(hovertemplate="%{x}: $%{y:,.0f}<extra></extra>", texttemplate="$%{y:,.0f}", textposition="outside")
            fig_family_pnl.update_layout(
                margin=dict(t=40, b=20, l=20, r=20), height=400,
                showlegend=False, yaxis_title="P&L (CAD)",
                xaxis_title="",
                yaxis_tickformat="$,.0f",
            )
            st.plotly_chart(fig_family_pnl, use_container_width=True)

    st.divider()

    # ── PER-OWNER SECTIONS ──
    for holder in holders:
        holder_active = active[active["holder"] == holder]
        holder_cash = cash[cash["holder"] == holder] if "holder" in cash.columns else pd.DataFrame()
        h = _summarize(holder_active, holder_cash)

        owner_pnl_cls = "owner-pnl-gain" if h["pnl"] >= 0 else "owner-pnl-loss"
        owner_pnl_sign = "+" if h["pnl"] > 0 else ""
        st.markdown(f'### {_display_holder(holder)} <span class="{owner_pnl_cls}">{owner_pnl_sign}${h["pnl"]:,.0f} ({owner_pnl_sign}{h["pnl_pct"]:.1%})</span>', unsafe_allow_html=True)
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Total Value", _money(h["total"]))
        c2.metric("Market Value", _money(h["market_value_cad"]))
        c3.metric("Book Value", _money(h["book_value_cad"]))
        c4.metric("P&L", _money(h["pnl"]),
                  delta=_pct(h["pnl_pct"]) if h["pnl_pct"] else None)
        c5.metric("Cash", _money(h["cash_cad"]))

        # Owner-level charts
        if has_mv:
            owner_chart1, owner_chart2 = st.columns(2)
            with owner_chart1:
                acc_alloc = holder_active.groupby("account_type")["market_value_cad"].sum().reset_index()
                acc_cash = holder_cash.groupby("account_type")["total_cash_cad"].sum().reset_index() if not holder_cash.empty else pd.DataFrame(columns=["account_type", "total_cash_cad"])
                acc_merged = acc_alloc.merge(acc_cash, on="account_type", how="outer").fillna(0)
                acc_merged["total"] = acc_merged["market_value_cad"] + acc_merged["total_cash_cad"]
                if acc_merged["total"].sum() > 0:
                    fig_acc = px.pie(acc_merged, values="total", names="account_type", hole=0.4,
                                    title=f"{_display_holder(holder)} — by Account Type")
                    fig_acc.update_traces(texttemplate="$%{value:,.0f}", hovertemplate="%{label}: $%{value:,.0f}<extra></extra>")
                    fig_acc.update_layout(margin=dict(t=40, b=10, l=10, r=10), height=280)
                    st.plotly_chart(fig_acc, use_container_width=True)

            with owner_chart2:
                ticker_col = "parent_ticker" if "parent_ticker" in holder_active.columns else "ticker"
                pnl_by_ticker = holder_active.groupby(ticker_col).agg(
                    mv=("market_value_cad", "sum"),
                    bv=("book_value_cad", "sum"),
                ).reset_index()
                pnl_by_ticker["pnl"] = pnl_by_ticker["mv"] - pnl_by_ticker["bv"]
                pnl_by_ticker = pnl_by_ticker[pnl_by_ticker["pnl"] != 0].sort_values("pnl")
                if not pnl_by_ticker.empty:
                    fig_pnl = px.bar(
                        pnl_by_ticker, x=ticker_col, y="pnl",
                        color=pnl_by_ticker["pnl"].apply(lambda x: "Gain" if x >= 0 else "Loss"),
                        color_discrete_map={"Gain": "#00cc66", "Loss": "#ff4444"},
                        title=f"{_display_holder(holder)} — P&L by Holding",
                    )
                    fig_pnl.update_traces(hovertemplate="%{x}: $%{y:,.0f}<extra></extra>", texttemplate="$%{y:,.0f}", textposition="outside")
                    fig_pnl.update_layout(margin=dict(t=40, b=10, l=10, r=10), height=280, showlegend=False, yaxis_title="P&L (CAD)", yaxis_tickformat="$,.0f")
                    st.plotly_chart(fig_pnl, use_container_width=True)

        # ── DRILL-DOWN BY ACCOUNT TYPE ──
        owner_acc_types = sorted(holder_active["account_type"].dropna().unique()) if "account_type" in holder_active.columns else []
        ordered_acc = [a for a in acc_type_order if a in owner_acc_types] + [a for a in owner_acc_types if a not in acc_type_order]

        if ordered_acc:
            tab_labels = ["📊 Total"] + [f"📁 {a}" for a in ordered_acc]
            all_tabs = st.tabs(tab_labels)

            # ── TOTAL tab (all holdings for this owner) ──
            with all_tabs[0]:
                ac1, ac2, ac3, ac4 = st.columns(4)
                ac1.metric("Market Value", _money(h["market_value_cad"]))
                ac2.metric("Book Value", _money(h["book_value_cad"]))
                ac3.metric("P&L", _money(h["pnl"]),
                          delta=_pct(h["pnl_pct"]) if h["pnl_pct"] else None)
                ac4.metric("Cash", _money(h["cash_cad"]))

                detail_cols = ["parent_ticker", "account_type", "platform", "currency", "investment_type",
                               "units", "cost_per_unit", "book_value_cad", "market_value_cad"]
                avail = [c for c in detail_cols if c in holder_active.columns]
                detail = holder_active[avail].copy()

                if has_mv and has_bv:
                    detail["P&L (CAD)"] = detail["market_value_cad"] - detail["book_value_cad"]
                    detail["Return %"] = (detail["P&L (CAD)"] / detail["book_value_cad"]).where(detail["book_value_cad"] != 0)

                detail.columns = [c.replace("_", " ").title() if "P&L" not in c and "Return" not in c else c for c in detail.columns]

                detail_fmt = {}
                for col in detail.columns:
                    if any(k in col.lower() for k in ["value", "book", "p&l"]):
                        detail_fmt[col] = lambda x: f"${x:,.0f}" if isinstance(x, (int, float)) and pd.notna(x) else ("—" if not isinstance(x, str) else x)
                    elif "return" in col.lower():
                        detail_fmt[col] = lambda x: f"{x:.1%}" if isinstance(x, (int, float)) and pd.notna(x) else ("—" if not isinstance(x, str) else x)
                    elif "units" in col.lower():
                        detail_fmt[col] = lambda x: f"{x:,.2f}" if isinstance(x, (int, float)) and pd.notna(x) else ("—" if not isinstance(x, str) else x)
                    elif "per unit" in col.lower():
                        detail_fmt[col] = lambda x: f"${x:,.2f}" if isinstance(x, (int, float)) and pd.notna(x) else ("—" if not isinstance(x, str) else x)

                if not detail.empty:
                    totals = {}
                    for col in detail.columns:
                        if col == detail.columns[0]:
                            totals[col] = "TOTAL"
                        elif any(k in col.lower() for k in ["value", "book", "p&l", "cost"]):
                            totals[col] = pd.to_numeric(detail[col], errors="coerce").sum()
                        elif "return" in col.lower():
                            bv_col = "Book Value Cad" if "Book Value Cad" in detail.columns else None
                            pnl_col = "P&L (CAD)" if "P&L (CAD)" in detail.columns else None
                            if bv_col and pnl_col:
                                total_bv = pd.to_numeric(detail[bv_col], errors="coerce").sum()
                                total_pnl = pd.to_numeric(detail[pnl_col], errors="coerce").sum()
                                totals[col] = total_pnl / total_bv if total_bv else None
                            else:
                                totals[col] = None
                        else:
                            totals[col] = ""
                    detail = pd.concat([detail, pd.DataFrame([totals])], ignore_index=True)

                    pnl_style_cols = [c for c in detail.columns if "p&l" in c.lower() or "return" in c.lower()]

                    def _style_total_row(row):
                        if row.iloc[0] == "TOTAL":
                            return ["font-weight: bold; border-top: 2px solid #333; background-color: #f5f5f5"] * len(row)
                        return [""] * len(row)

                    styled = detail.style.format(detail_fmt).apply(_style_total_row, axis=1)
                    if pnl_style_cols:
                        styled = styled.map(_style_pnl, subset=pnl_style_cols)
                    st.dataframe(styled, use_container_width=True, hide_index=True)

            # ── Per account type tabs ──
            for tab, acc_type in zip(all_tabs[1:], ordered_acc):
                with tab:
                    acc_holdings = holder_active[holder_active["account_type"] == acc_type]
                    acc_cash_rows = holder_cash[holder_cash["account_type"] == acc_type] if not holder_cash.empty and "account_type" in holder_cash.columns else pd.DataFrame()
                    a = _summarize(acc_holdings, acc_cash_rows)

                    ac1, ac2, ac3, ac4 = st.columns(4)
                    ac1.metric("Market Value", _money(a["market_value_cad"]))
                    ac2.metric("Book Value", _money(a["book_value_cad"]))
                    ac3.metric("P&L", _money(a["pnl"]),
                              delta=_pct(a["pnl_pct"]) if a["pnl_pct"] else None)
                    ac4.metric("Cash", _money(a["cash_cad"]))

                    # Holdings table for this account type
                    detail_cols = ["parent_ticker", "platform", "currency", "investment_type",
                                   "units", "cost_per_unit", "book_value_cad", "market_value_cad"]
                    avail = [c for c in detail_cols if c in acc_holdings.columns]
                    detail = acc_holdings[avail].copy()

                    if has_mv and has_bv:
                        detail["P&L (CAD)"] = detail["market_value_cad"] - detail["book_value_cad"]
                        detail["Return %"] = (detail["P&L (CAD)"] / detail["book_value_cad"]).where(detail["book_value_cad"] != 0)

                    detail.columns = [c.replace("_", " ").title() if "P&L" not in c and "Return" not in c else c for c in detail.columns]

                    detail_fmt = {}
                    for col in detail.columns:
                        if any(k in col.lower() for k in ["value", "book", "p&l"]):
                            detail_fmt[col] = lambda x: f"${x:,.0f}" if isinstance(x, (int, float)) and pd.notna(x) else ("—" if not isinstance(x, str) else x)
                        elif "return" in col.lower():
                            detail_fmt[col] = lambda x: f"{x:.1%}" if isinstance(x, (int, float)) and pd.notna(x) else ("—" if not isinstance(x, str) else x)
                        elif "units" in col.lower():
                            detail_fmt[col] = lambda x: f"{x:,.2f}" if isinstance(x, (int, float)) and pd.notna(x) else ("—" if not isinstance(x, str) else x)
                        elif "per unit" in col.lower():
                            detail_fmt[col] = lambda x: f"${x:,.2f}" if isinstance(x, (int, float)) and pd.notna(x) else ("—" if not isinstance(x, str) else x)

                    if not detail.empty:
                        # Add totals row
                        totals = {}
                        for col in detail.columns:
                            if col in ("Parent Ticker",) or col == detail.columns[0]:
                                totals[col] = "TOTAL"
                            elif any(k in col.lower() for k in ["value", "book", "p&l", "cost"]):
                                totals[col] = pd.to_numeric(detail[col], errors="coerce").sum()
                            elif "return" in col.lower():
                                bv_col = "Book Value Cad" if "Book Value Cad" in detail.columns else None
                                pnl_col = "P&L (CAD)" if "P&L (CAD)" in detail.columns else None
                                if bv_col and pnl_col:
                                    total_bv = pd.to_numeric(detail[bv_col], errors="coerce").sum()
                                    total_pnl = pd.to_numeric(detail[pnl_col], errors="coerce").sum()
                                    totals[col] = total_pnl / total_bv if total_bv else None
                                else:
                                    totals[col] = None
                            else:
                                totals[col] = ""
                        totals_row = pd.DataFrame([totals])
                        detail = pd.concat([detail, totals_row], ignore_index=True)

                        pnl_style_cols = [c for c in detail.columns if "p&l" in c.lower() or "return" in c.lower()]

                        def _style_total_row(row):
                            if row.iloc[0] == "TOTAL":
                                return ["font-weight: bold; border-top: 2px solid #333; background-color: #f5f5f5"] * len(row)
                            return [""] * len(row)

                        styled = detail.style.format(detail_fmt).apply(_style_total_row, axis=1)
                        if pnl_style_cols:
                            styled = styled.map(_style_pnl, subset=pnl_style_cols)
                        st.dataframe(
                            styled,
                            use_container_width=True,
                            hide_index=True,
                        )

        st.divider()

    # --- Restatement: Account Type as header, Owners as dimensions ---
    st.markdown("### 📋 Restatement by Account Type")
    all_acc_types = [a for a in acc_type_order if a in active["account_type"].dropna().unique()]

    restate_tab_labels = [f"📁 {a}" for a in all_acc_types] + ["📊 Grand Total"]
    restate_tabs = st.tabs(restate_tab_labels)

    for rtab, acc_type in zip(restate_tabs[:-1], all_acc_types):
        with rtab:
            acc_data = active[active["account_type"] == acc_type]
            acc_cash_data = cash[cash["account_type"] == acc_type] if not cash.empty and "account_type" in cash.columns else pd.DataFrame()

            # Summary table: one row per holder + total
            summary_rows = []
            for holder in holders:
                h_acc = acc_data[acc_data["holder"] == holder]
                h_cash = acc_cash_data[acc_cash_data["holder"] == holder] if not acc_cash_data.empty and "holder" in acc_cash_data.columns else pd.DataFrame()
                s = _summarize(h_acc, h_cash)
                summary_rows.append({
                    "Owner": _display_holder(holder),
                    "Holdings": s["count"],
                    "Market Value": s["market_value_cad"],
                    "Book Value": s["book_value_cad"],
                    "P&L (CAD)": s["pnl"],
                    "Return %": s["pnl_pct"],
                    "Cash": s["cash_cad"],
                    "Total Value": s["total"],
                })
            # Total row
            acc_sum = _summarize(acc_data, acc_cash_data)
            summary_rows.append({
                "Owner": "TOTAL",
                "Holdings": acc_sum["count"],
                "Market Value": acc_sum["market_value_cad"],
                "Book Value": acc_sum["book_value_cad"],
                "P&L (CAD)": acc_sum["pnl"],
                "Return %": acc_sum["pnl_pct"],
                "Cash": acc_sum["cash_cad"],
                "Total Value": acc_sum["total"],
            })

            summary_df = pd.DataFrame(summary_rows)
            sfmt = {
                "Market Value": lambda x: f"${x:,.0f}" if isinstance(x, (int, float)) and pd.notna(x) else "—",
                "Book Value": lambda x: f"${x:,.0f}" if isinstance(x, (int, float)) and pd.notna(x) else "—",
                "P&L (CAD)": lambda x: f"${x:,.0f}" if isinstance(x, (int, float)) and pd.notna(x) else "—",
                "Return %": lambda x: f"{x:.1%}" if isinstance(x, (int, float)) and pd.notna(x) else "—",
                "Cash": lambda x: f"${x:,.0f}" if isinstance(x, (int, float)) and pd.notna(x) else "—",
                "Total Value": lambda x: f"${x:,.0f}" if isinstance(x, (int, float)) and pd.notna(x) else "—",
            }

            def _style_restate(row):
                if row["Owner"] == "TOTAL":
                    return ["font-weight: bold; border-top: 2px solid #333; background-color: #f5f5f5"] * len(row)
                return [""] * len(row)

            styled_summary = summary_df.style.format(sfmt).apply(_style_restate, axis=1).map(
                _style_pnl, subset=["P&L (CAD)", "Return %"]
            )
            st.dataframe(styled_summary, use_container_width=True, hide_index=True)

            # Detail holdings per owner within this account type
            for holder in holders:
                h_acc = acc_data[acc_data["holder"] == holder]
                if h_acc.empty:
                    continue
                h_cash = acc_cash_data[acc_cash_data["holder"] == holder] if not acc_cash_data.empty and "holder" in acc_cash_data.columns else pd.DataFrame()
                hs = _summarize(h_acc, h_cash)
                pnl_cls = "owner-pnl-gain" if hs["pnl"] >= 0 else "owner-pnl-loss"
                pnl_s = "+" if hs["pnl"] > 0 else ""
                st.markdown(f'**{_display_holder(holder)}** <span class="{pnl_cls}">{pnl_s}${hs["pnl"]:,.0f}</span>', unsafe_allow_html=True)

                detail_cols = ["parent_ticker", "platform", "currency", "units", "cost_per_unit", "book_value_cad", "market_value_cad"]
                avail = [c for c in detail_cols if c in h_acc.columns]
                detail = h_acc[avail].copy()
                if has_mv and has_bv:
                    detail["P&L (CAD)"] = detail["market_value_cad"] - detail["book_value_cad"]
                    detail["Return %"] = (detail["P&L (CAD)"] / detail["book_value_cad"]).where(detail["book_value_cad"] != 0)
                detail.columns = [c.replace("_", " ").title() if "P&L" not in c and "Return" not in c else c for c in detail.columns]

                dfmt = {}
                for col in detail.columns:
                    if any(k in col.lower() for k in ["value", "book", "p&l"]):
                        dfmt[col] = lambda x: f"${x:,.0f}" if isinstance(x, (int, float)) and pd.notna(x) else ("—" if not isinstance(x, str) else x)
                    elif "return" in col.lower():
                        dfmt[col] = lambda x: f"{x:.1%}" if isinstance(x, (int, float)) and pd.notna(x) else ("—" if not isinstance(x, str) else x)
                    elif "units" in col.lower():
                        dfmt[col] = lambda x: f"{x:,.2f}" if isinstance(x, (int, float)) and pd.notna(x) else ("—" if not isinstance(x, str) else x)
                    elif "per unit" in col.lower():
                        dfmt[col] = lambda x: f"${x:,.2f}" if isinstance(x, (int, float)) and pd.notna(x) else ("—" if not isinstance(x, str) else x)

                if not detail.empty:
                    totals = {}
                    for col in detail.columns:
                        if col == detail.columns[0]:
                            totals[col] = "TOTAL"
                        elif any(k in col.lower() for k in ["value", "book", "p&l", "cost"]):
                            totals[col] = pd.to_numeric(detail[col], errors="coerce").sum()
                        elif "return" in col.lower():
                            bv_col = "Book Value Cad" if "Book Value Cad" in detail.columns else None
                            pnl_col = "P&L (CAD)" if "P&L (CAD)" in detail.columns else None
                            if bv_col and pnl_col:
                                t_bv = pd.to_numeric(detail[bv_col], errors="coerce").sum()
                                t_pnl = pd.to_numeric(detail[pnl_col], errors="coerce").sum()
                                totals[col] = t_pnl / t_bv if t_bv else None
                            else:
                                totals[col] = None
                        else:
                            totals[col] = ""
                    detail = pd.concat([detail, pd.DataFrame([totals])], ignore_index=True)
                    pnl_cols = [c for c in detail.columns if "p&l" in c.lower() or "return" in c.lower()]

                    def _style_total_row_r(row):
                        if row.iloc[0] == "TOTAL":
                            return ["font-weight: bold; border-top: 2px solid #333; background-color: #f5f5f5"] * len(row)
                        return [""] * len(row)

                    styled_d = detail.style.format(dfmt).apply(_style_total_row_r, axis=1)
                    if pnl_cols:
                        styled_d = styled_d.map(_style_pnl, subset=pnl_cols)
                    st.dataframe(styled_d, use_container_width=True, hide_index=True)

    # Grand Total tab
    with restate_tabs[-1]:
        grand_rows = []
        for acc_type in all_acc_types:
            acc_data = active[active["account_type"] == acc_type]
            acc_cash_data = cash[cash["account_type"] == acc_type] if not cash.empty and "account_type" in cash.columns else pd.DataFrame()
            s = _summarize(acc_data, acc_cash_data)
            row = {"Account Type": acc_type}
            for holder in holders:
                h_acc = acc_data[acc_data["holder"] == holder]
                h_cash = acc_cash_data[acc_cash_data["holder"] == holder] if not acc_cash_data.empty and "holder" in acc_cash_data.columns else pd.DataFrame()
                hs = _summarize(h_acc, h_cash)
                dn = _display_holder(holder)
                row[f"{dn} MV"] = hs["market_value_cad"]
                row[f"{dn} BV"] = hs["book_value_cad"]
                row[f"{dn} P&L"] = hs["pnl"]
            row["Total MV"] = s["market_value_cad"]
            row["Total BV"] = s["book_value_cad"]
            row["Total P&L"] = s["pnl"]
            grand_rows.append(row)

        # Grand total row
        grand_total_row = {"Account Type": "TOTAL"}
        for holder in holders:
            h_all = active[active["holder"] == holder]
            h_cash_all = cash[cash["holder"] == holder] if "holder" in cash.columns else pd.DataFrame()
            hs = _summarize(h_all, h_cash_all)
            dn = _display_holder(holder)
            grand_total_row[f"{dn} MV"] = hs["market_value_cad"]
            grand_total_row[f"{dn} BV"] = hs["book_value_cad"]
            grand_total_row[f"{dn} P&L"] = hs["pnl"]
        grand_total_row["Total MV"] = family["market_value_cad"]
        grand_total_row["Total BV"] = family["book_value_cad"]
        grand_total_row["Total P&L"] = family["pnl"]
        grand_rows.append(grand_total_row)

        grand_df = pd.DataFrame(grand_rows)
        gfmt = {}
        for col in grand_df.columns:
            if col == "Account Type":
                continue
            elif "p&l" in col.lower():
                gfmt[col] = lambda x: f"${x:,.0f}" if isinstance(x, (int, float)) and pd.notna(x) else "—"
            else:
                gfmt[col] = lambda x: f"${x:,.0f}" if isinstance(x, (int, float)) and pd.notna(x) else "—"

        pnl_grand_cols = [c for c in grand_df.columns if "p&l" in c.lower()]

        def _style_grand_total(row):
            if row["Account Type"] == "TOTAL":
                return ["font-weight: bold; border-top: 2px solid #333; background-color: #f5f5f5"] * len(row)
            return [""] * len(row)

        styled_grand = grand_df.style.format(gfmt).apply(_style_grand_total, axis=1)
        if pnl_grand_cols:
            styled_grand = styled_grand.map(_style_pnl, subset=pnl_grand_cols)
        st.dataframe(styled_grand, use_container_width=True, hide_index=True)

    st.divider()

    # --- Sold Positions ---
    if not real_sold.empty:
        with st.expander(f"📦 Sold Positions ({len(real_sold)}) — Realized P&L: {_pnl_html(total_realized_cad)}", expanded=False):
            st.markdown(f"Book Cost: **${total_bk_sold:,.0f}** → Sold For: **${total_sold_mv:,.0f}** → Realized P&L (CAD): {_pnl_html(total_realized_cad)}", unsafe_allow_html=True)

            sold_display_cols = ["ticker", "parent_ticker", "holder", "account_type", "currency",
                                 "sold_units", "book_cost_sold", "sold_market_value", "realized_pnl", "realized_pnl_cad"]
            sold_avail = [c for c in sold_display_cols if c in real_sold.columns]
            sold_table = real_sold[sold_avail].copy()
            sold_table["holder"] = sold_table["holder"].map(_display_holder)
            # Use parent_ticker if available, fall back to ticker
            if "parent_ticker" in sold_table.columns and "ticker" in sold_table.columns:
                sold_table["ticker"] = sold_table["parent_ticker"].where(sold_table["parent_ticker"].notna() & (sold_table["parent_ticker"].astype(str).str.strip() != "nan"), sold_table["ticker"])
                sold_table = sold_table.drop(columns=["parent_ticker"])

            sold_table.columns = [c.replace("_", " ").title() for c in sold_table.columns]

            sold_fmt = {}
            for col in sold_table.columns:
                if any(k in col.lower() for k in ["cost", "value", "pnl", "market"]):
                    sold_fmt[col] = lambda x: f"${x:,.0f}" if isinstance(x, (int, float)) and pd.notna(x) else "—"
                elif "units" in col.lower():
                    sold_fmt[col] = lambda x: f"{x:,.0f}" if isinstance(x, (int, float)) and pd.notna(x) else "—"

            pnl_sold_cols = [c for c in sold_table.columns if "pnl" in c.lower()]

            # Add totals row
            sold_totals = {}
            for col in sold_table.columns:
                if col == sold_table.columns[0]:
                    sold_totals[col] = "TOTAL"
                elif any(k in col.lower() for k in ["cost", "value", "pnl", "market"]):
                    sold_totals[col] = pd.to_numeric(sold_table[col], errors="coerce").sum()
                else:
                    sold_totals[col] = ""
            sold_table = pd.concat([sold_table, pd.DataFrame([sold_totals])], ignore_index=True)

            def _style_sold_total(row):
                if row.iloc[0] == "TOTAL":
                    return ["font-weight: bold; border-top: 2px solid #333; background-color: #f5f5f5"] * len(row)
                return [""] * len(row)

            styled_sold = sold_table.style.format(sold_fmt).apply(_style_sold_total, axis=1)
            if pnl_sold_cols:
                styled_sold = styled_sold.map(_style_pnl, subset=pnl_sold_cols)
            st.dataframe(styled_sold, use_container_width=True, hide_index=True)

    # --- AI on Excel data ---
    st.divider()
    st.subheader("AI Analysis")

    has_api_key = False
    try:
        if st.secrets["ANTHROPIC_API_KEY"] != "your-api-key-here":
            has_api_key = True
    except (KeyError, FileNotFoundError):
        pass

    if not has_api_key:
        st.warning("Add your ANTHROPIC_API_KEY to `.streamlit/secrets.toml` to enable AI features.")
    else:
        import json as _json
        snapshot_data = {
            "family_total_cad": round(family["total"], 2),
            "family_market_value_cad": round(family["market_value_cad"], 2),
            "family_book_value_cad": round(family["book_value_cad"], 2),
            "family_unrealized_pnl_cad": round(family["pnl"], 2),
            "family_unrealized_pnl_pct": round(family["pnl_pct"], 4) if family["pnl_pct"] else None,
            "family_realized_pnl_cad": round(total_realized_cad, 2),
            "family_total_sold_value": round(total_sold_mv, 2),
            "family_total_book_cost_sold": round(total_bk_sold, 2),
            "family_combined_pnl_cad": round(family["pnl"] + total_realized_cad, 2),
            "family_cash_cad": round(family["cash_cad"], 2),
            "sold_positions_count": len(real_sold),
            "account_type_breakdown": {},
            "holders": {},
        }

        for acc_type in ordered_family_acc:
            acc_a = active[active["account_type"] == acc_type]
            acc_c = cash[cash["account_type"] == acc_type] if not cash.empty and "account_type" in cash.columns else pd.DataFrame()
            a_sum = _summarize(acc_a, acc_c)
            snapshot_data["account_type_breakdown"][acc_type] = {
                "market_value_cad": round(a_sum["market_value_cad"], 2),
                "book_value_cad": round(a_sum["book_value_cad"], 2),
                "pnl_cad": round(a_sum["pnl"], 2),
                "cash_cad": round(a_sum["cash_cad"], 2),
                "holdings_count": a_sum["count"],
            }

        for holder in holders:
            h_active = active[active["holder"] == holder]
            h_cash_df = cash[cash["holder"] == holder] if "holder" in cash.columns else pd.DataFrame()
            h_sum = _summarize(h_active, h_cash_df)
            h_sold = real_sold[real_sold["holder"] == holder] if not real_sold.empty and "holder" in real_sold.columns else pd.DataFrame()
            h_realized = h_sold["realized_pnl_cad"].sum() if not h_sold.empty and "realized_pnl_cad" in h_sold.columns else 0
            holder_data = {
                "display_name": _display_holder(holder),
                "total_cad": round(h_sum["total"], 2),
                "market_value_cad": round(h_sum["market_value_cad"], 2),
                "book_value_cad": round(h_sum["book_value_cad"], 2),
                "unrealized_pnl_cad": round(h_sum["pnl"], 2),
                "unrealized_pnl_pct": round(h_sum["pnl_pct"], 4) if h_sum["pnl_pct"] else None,
                "realized_pnl_cad": round(h_realized, 2),
                "combined_pnl_cad": round(h_sum["pnl"] + h_realized, 2),
                "sold_positions": len(h_sold),
                "cash_cad": round(h_sum["cash_cad"], 2),
                "accounts": {},
                "holdings": [],
            }
            for acc_type in h_active["account_type"].dropna().unique():
                acc_h = h_active[h_active["account_type"] == acc_type]
                acc_c = h_cash_df[h_cash_df["account_type"] == acc_type] if not h_cash_df.empty and "account_type" in h_cash_df.columns else pd.DataFrame()
                a_s = _summarize(acc_h, acc_c)
                holder_data["accounts"][acc_type] = {
                    "market_value_cad": round(a_s["market_value_cad"], 2),
                    "book_value_cad": round(a_s["book_value_cad"], 2),
                    "pnl_cad": round(a_s["pnl"], 2),
                }
            for _, row in h_active.iterrows():
                ticker_col = "parent_ticker" if "parent_ticker" in h_active.columns else "ticker"
                holding = {
                    "ticker": str(row.get(ticker_col, "")),
                    "account": str(row.get("account_type", "")),
                    "platform": str(row.get("platform", "")),
                    "currency": str(row.get("currency", "")),
                    "investment_type": str(row.get("investment_type", "")),
                    "units": float(row.get("units", 0) or 0),
                    "cost_per_unit": round(float(row.get("cost_per_unit", 0) or 0), 2),
                    "book_value_cad": round(float(row.get("book_value_cad", 0) or 0), 2),
                    "market_value_cad": round(float(row.get("market_value_cad", 0) or 0), 2),
                }
                holding["pnl_cad"] = round(holding["market_value_cad"] - holding["book_value_cad"], 2)
                holding["return_pct"] = round(holding["pnl_cad"] / holding["book_value_cad"], 4) if holding["book_value_cad"] else None
                holder_data["holdings"].append(holding)
            snapshot_data["holders"][holder] = holder_data

        snapshot = _json.dumps(snapshot_data, indent=2)

        # AI Analysis tabs
        ai_tab1, ai_tab2, ai_tab3, ai_tab4, ai_tab5, ai_tab6 = st.tabs([
            "💡 Portfolio Insights",
            "⚖️ Rebalance Plan",
            "🛡️ Risk Assessment",
            "🏦 Tax Strategy",
            "📰 News & Research",
            "💬 Ask Anything",
        ])

        with ai_tab1:
            st.caption("Comprehensive portfolio analysis — concentration, diversification, account optimization")
            if st.button("Run Portfolio Analysis", use_container_width=True, key="btn_insights"):
                try:
                    st.write_stream(generate_insights(snapshot))
                except Exception as e:
                    st.error(f"AI error: {e}")

        with ai_tab2:
            st.caption("Specific buy/sell recommendations to optimize allocation and cash deployment")
            if st.button("Generate Rebalancing Plan", use_container_width=True, key="btn_rebalance"):
                try:
                    st.write_stream(suggest_rebalance(snapshot, {}))
                except Exception as e:
                    st.error(f"AI error: {e}")

        with ai_tab3:
            st.caption("Risk score, currency exposure, drawdown scenarios, and mitigation steps")
            if st.button("Run Risk Assessment", use_container_width=True, key="btn_risk"):
                try:
                    st.write_stream(risk_assessment(snapshot))
                except Exception as e:
                    st.error(f"AI error: {e}")

        with ai_tab4:
            st.caption("Canadian tax optimization — TFSA/RSP placement, tax-loss harvesting, capital gains planning")
            if st.button("Generate Tax Strategy", use_container_width=True, key="btn_tax"):
                try:
                    st.write_stream(tax_strategy(snapshot))
                except Exception as e:
                    st.error(f"AI error: {e}")

        with ai_tab5:
            st.caption("Latest context, outlook, and risk rating for each holding")
            if st.button("Get News & Research", use_container_width=True, key="btn_news"):
                try:
                    st.write_stream(summarize_news(snapshot))
                except Exception as e:
                    st.error(f"AI error: {e}")

        with ai_tab6:
            st.caption("Ask any question about your portfolio — uses your actual data to answer")
            question = st.text_input("What would you like to know?", placeholder="e.g., Which holdings should I sell first for tax-loss harvesting?")
            if question:
                if st.button("Ask", use_container_width=True, key="btn_chat"):
                    try:
                        st.write_stream(ai_chat(snapshot, question))
                    except Exception as e:
                        st.error(f"AI error: {e}")

    st.stop()


# ============================================================
# CSV VIEW — original simple dashboard
# ============================================================
tickers = holdings_df["ticker"].tolist()

with st.spinner("Fetching live prices..."):
    prices = fetch_prices(tickers)

portfolio_df = build_portfolio(holdings_df, prices)
resolved = portfolio_df["price"].notna()
resolved_df = portfolio_df[resolved]

total_value = resolved_df["current_value"].sum()
total_pnl = resolved_df["pnl"].sum() if resolved_df["pnl"].notna().any() else None
total_pnl_pct = (total_pnl / (total_value - total_pnl)) if total_pnl and total_value else None

# --- Top Metrics ---
col1, col2, col3 = st.columns(3)
col1.metric("Total Portfolio Value", f"${total_value:,.2f}")
if total_pnl is not None:
    col2.metric("Total P&L", f"${total_pnl:,.2f}", delta=f"{total_pnl_pct:.1%}" if total_pnl_pct else None)
else:
    col2.metric("Total P&L", "N/A")
col3.metric("Holdings", len(resolved_df))

st.divider()

# --- Holdings Table ---
st.subheader("Holdings")
display_df = resolved_df[["ticker", "quantity", "price", "current_value", "weight", "cost_basis", "pnl", "pnl_pct", "day_change"]].copy()
display_df.columns = ["Ticker", "Qty", "Price", "Value", "Weight", "Cost Basis", "P&L ($)", "P&L (%)", "Day Change"]

st.dataframe(
    display_df.style.format({
        "Price": "${:,.2f}",
        "Value": "${:,.2f}",
        "Weight": "{:.1%}",
        "Cost Basis": lambda x: f"${x:,.2f}" if pd.notna(x) else "—",
        "P&L ($)": lambda x: f"${x:,.2f}" if pd.notna(x) else "—",
        "P&L (%)": lambda x: f"{x:.1%}" if pd.notna(x) else "—",
        "Day Change": lambda x: f"{x:.2%}" if pd.notna(x) else "—",
    }).map(
        lambda x: "color: green" if isinstance(x, (int, float)) and x > 0 else ("color: red" if isinstance(x, (int, float)) and x < 0 else ""),
        subset=["P&L ($)", "P&L (%)", "Day Change"],
    ),
    use_container_width=True,
    hide_index=True,
)

# --- Charts ---
chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.subheader("Allocation")
    fig_pie = px.pie(
        resolved_df,
        values="current_value",
        names="ticker",
        hole=0.4,
    )
    fig_pie.update_traces(texttemplate="$%{value:,.0f}", hovertemplate="%{label}: $%{value:,.0f}<extra></extra>")
    fig_pie.update_layout(margin=dict(t=20, b=20, l=20, r=20), height=350)
    st.plotly_chart(fig_pie, use_container_width=True)

with chart_col2:
    st.subheader("P&L by Holding")
    pnl_df = resolved_df[resolved_df["pnl"].notna()][["ticker", "pnl"]].copy()
    if not pnl_df.empty:
        fig_bar = px.bar(
            pnl_df,
            x="ticker",
            y="pnl",
            color=pnl_df["pnl"].apply(lambda x: "Gain" if x >= 0 else "Loss"),
            color_discrete_map={"Gain": "#00cc66", "Loss": "#ff4444"},
        )
        fig_bar.update_traces(hovertemplate="%{x}: $%{y:,.0f}<extra></extra>", texttemplate="$%{y:,.0f}", textposition="outside")
        fig_bar.update_layout(
            margin=dict(t=20, b=20, l=20, r=20),
            height=350,
            showlegend=False,
            yaxis_title="P&L ($)",
            yaxis_tickformat="$,.0f",
        )
        st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.info("Provide cost_basis in your CSV to see P&L.")

st.divider()

# --- AI Analysis ---
st.subheader("AI Analysis")

has_api_key = False
try:
    if st.secrets["ANTHROPIC_API_KEY"] != "your-api-key-here":
        has_api_key = True
except (KeyError, FileNotFoundError):
    pass

if not has_api_key:
    st.warning("Add your ANTHROPIC_API_KEY to `.streamlit/secrets.toml` to enable AI features.")
else:
    snapshot = get_portfolio_snapshot(portfolio_df)

    ai_col1, ai_col2, ai_col3 = st.columns(3)

    with ai_col1:
        if st.button("💡 Get Insights", use_container_width=True):
            with st.expander("Portfolio Insights", expanded=True):
                try:
                    st.write_stream(generate_insights(snapshot))
                except Exception as e:
                    st.error(f"AI error: {e}")

    with ai_col2:
        if st.button("⚖️ Rebalance", use_container_width=True):
            with st.expander("Rebalancing Suggestions", expanded=True):
                targets = {}
                tw = resolved_df[resolved_df["target_weight"].notna()]
                if not tw.empty:
                    targets = dict(zip(tw["ticker"], tw["target_weight"]))
                if not targets:
                    st.info("Add a target_weight column to your CSV for specific rebalancing advice.")
                try:
                    st.write_stream(suggest_rebalance(snapshot, targets))
                except Exception as e:
                    st.error(f"AI error: {e}")

    with ai_col3:
        if st.button("📰 News Summary", use_container_width=True):
            with st.expander("News & Context", expanded=True):
                try:
                    st.write_stream(summarize_news(snapshot))
                except Exception as e:
                    st.error(f"AI error: {e}")
