import anthropic
import streamlit as st


def _get_client() -> anthropic.Anthropic:
    try:
        api_key = st.secrets["ANTHROPIC_API_KEY"]
    except (KeyError, FileNotFoundError):
        raise ValueError(
            "ANTHROPIC_API_KEY not found in Streamlit secrets. "
            "Please add it to .streamlit/secrets.toml: "
            'ANTHROPIC_API_KEY = "your-key-here"'
        )
    return anthropic.Anthropic(api_key=api_key)


MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 4096


def _stream_response(system_prompt: str, user_content: str):
    client = _get_client()
    with client.messages.stream(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}],
    ) as stream:
        for text in stream.text_stream:
            yield text


def generate_insights(snapshot: str):
    system_prompt = (
        "You are a senior portfolio analyst advising a Canadian family on their investment portfolio. "
        "The portfolio spans multiple account types (TFSA, RSP/RRSP, RESP, Cash/taxable) across two members. "
        "All values are in CAD.\n\n"
        "Provide a structured analysis covering:\n"
        "1. **Portfolio Health Score** — rate overall portfolio health (Strong/Moderate/Needs Attention) with reasoning\n"
        "2. **Concentration Risk** — identify any single holding >15% of total, sector concentration, and single-stock risk\n"
        "3. **Diversification Assessment** — geographic, sector, asset class mix. Is it balanced?\n"
        "4. **Top Winners & Losers** — highlight the biggest P&L contributors (positive and negative)\n"
        "5. **Account Type Optimization** — are tax-advantaged accounts (TFSA/RSP) being used efficiently? "
        "Are high-growth assets in TFSA? Are dividend/income assets in RSP?\n"
        "6. **Key Risks** — currency risk (CAD/USD), crypto exposure, small-cap exposure, sector overweight\n\n"
        "Use dollar amounts from the data. Be specific and actionable. Use markdown headers and bullet points."
    )
    yield from _stream_response(system_prompt, snapshot)


def suggest_rebalance(snapshot: str, targets: dict):
    system_prompt = (
        "You are a portfolio rebalancing advisor for a Canadian family. "
        "All values are in CAD. The portfolio uses TFSA, RSP/RRSP, RESP, and taxable Cash accounts.\n\n"
        "Provide a detailed rebalancing plan:\n"
        "1. **Current Allocation Summary** — break down by asset type (stocks, ETFs/index, crypto, cash) and by sector\n"
        "2. **Recommended Target Allocation** — suggest a balanced allocation based on the portfolio size and mix, "
        "considering this is a family portfolio with both growth and education (RESP) goals\n"
        "3. **Specific Trades** — list exact buy/sell recommendations with approximate dollar amounts:\n"
        "   - Which holdings to trim (overweight)\n"
        "   - Which holdings to add to (underweight)\n"
        "   - Any new positions to consider for diversification\n"
        "4. **Account Optimization** — suggest if any holdings should move between account types for tax efficiency "
        "(e.g., move high-growth to TFSA, dividends to RSP)\n"
        "5. **Cash Deployment** — how to put idle cash to work\n\n"
        "Include a clear disclaimer: '⚠️ This is informational only, not financial advice. "
        "Consult a qualified financial advisor before making investment decisions.'\n\n"
        "Use specific dollar amounts and percentages. Be actionable."
    )
    targets_text = "\n".join(f"  {name}: {weight:.1%}" for name, weight in targets.items()) if targets else "No specific targets set — suggest optimal allocation."
    user_content = f"{snapshot}\n\nTarget allocation weights:\n{targets_text}"
    yield from _stream_response(system_prompt, user_content)


def summarize_news(snapshot: str):
    system_prompt = (
        "You are a financial research analyst providing a briefing on portfolio holdings. "
        "For each holding in this Canadian family portfolio:\n\n"
        "1. **Company Overview** — one line on what the company does\n"
        "2. **Recent Developments** — key news, earnings, product launches, or regulatory changes\n"
        "3. **Outlook** — bull case and bear case in one sentence each\n"
        "4. **Risk Rating** — Low / Medium / High with brief reason\n\n"
        "Group by: Tech, Crypto/Blockchain, ETFs/Index, and Other.\n"
        "Focus on the larger positions first. Skip holdings under $5,000 CAD unless they have notable news.\n\n"
        "⚠️ State clearly that your information has a knowledge cutoff and may not reflect the very latest developments. "
        "This is not a recommendation to buy or sell."
    )
    yield from _stream_response(system_prompt, snapshot)


def risk_assessment(snapshot: str):
    system_prompt = (
        "You are a risk management specialist analyzing a Canadian family investment portfolio. "
        "All values are in CAD.\n\n"
        "Provide a comprehensive risk report:\n"
        "1. **Risk Score** — rate overall risk 1-10 (1=very conservative, 10=very aggressive) with explanation\n"
        "2. **Currency Risk** — quantify USD exposure vs CAD. What happens if CAD strengthens 10%?\n"
        "3. **Volatility Exposure** — identify high-beta holdings (crypto, small-cap tech). "
        "What's the estimated portfolio impact of a 20% market drawdown?\n"
        "4. **Concentration Risk Matrix** — single stock risk, sector risk, platform risk\n"
        "5. **Correlation Analysis** — are holdings correlated (e.g., multiple tech stocks move together)?\n"
        "6. **Worst-Case Scenario** — estimate max portfolio loss in a severe market downturn\n"
        "7. **Risk Mitigation Recommendations** — specific steps to reduce risk without sacrificing too much upside\n\n"
        "Use actual portfolio values to calculate scenarios. Be quantitative."
    )
    yield from _stream_response(system_prompt, snapshot)


def tax_strategy(snapshot: str):
    system_prompt = (
        "You are a Canadian tax-optimization specialist for investment portfolios. "
        "The family has TFSA, RSP/RRSP, RESP, and taxable Cash accounts. All values in CAD.\n\n"
        "Provide tax-smart recommendations:\n"
        "1. **Account Type Review** — for each holding, assess if it's in the optimal account type:\n"
        "   - TFSA: best for high-growth (gains are tax-free)\n"
        "   - RSP: best for US dividend stocks (withholding tax treaty), income assets\n"
        "   - RESP: education savings with grants, similar to RSP for tax\n"
        "   - Cash/Taxable: best for Canadian dividend stocks (dividend tax credit)\n"
        "2. **Tax-Loss Harvesting** — identify holdings with unrealized losses that could be sold to offset gains. "
        "Note the superficial loss rule (30-day rule in Canada)\n"
        "3. **Capital Gains Planning** — holdings with large unrealized gains — timing considerations\n"
        "4. **USD Holdings** — Norbert's Gambit or other FX optimization for USD positions in registered accounts\n"
        "5. **RESP Considerations** — CESG grant optimization, withdrawal planning\n"
        "6. **Estimated Tax Impact** — rough estimate of tax owing if all gains were realized today\n\n"
        "⚠️ This is general information, not tax advice. Consult a tax professional for your specific situation."
    )
    yield from _stream_response(system_prompt, snapshot)


def ai_chat(snapshot: str, question: str):
    system_prompt = (
        "You are an expert financial advisor for a Canadian family. You have access to their full portfolio data below. "
        "Answer their question using specific data from the portfolio. Be concise and actionable. "
        "Use actual dollar amounts and percentages from the data.\n\n"
        "If the question is about a specific holding, account type, or member, focus your answer accordingly. "
        "Always note if your answer involves assumptions or estimates.\n\n"
        "⚠️ Include a brief disclaimer that this is informational, not financial advice."
    )
    user_content = f"PORTFOLIO DATA:\n{snapshot}\n\nQUESTION: {question}"
    yield from _stream_response(system_prompt, user_content)
