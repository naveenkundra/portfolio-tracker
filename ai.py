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


MODEL = "claude-opus-4-8"
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
        "You are a portfolio analyst. Analyze this portfolio and provide "
        "insights on: allocation & diversification, concentration risks, "
        "notable movers, and risk observations. Be concise and actionable."
    )
    yield from _stream_response(system_prompt, snapshot)


def suggest_rebalance(snapshot: str, targets: dict):
    system_prompt = (
        "You are a portfolio rebalancing advisor. Compare current allocation "
        "vs target weights and suggest specific buy/sell adjustments to "
        "converge. Include a clear disclaimer: 'This is informational only, "
        "not financial advice. Consult a qualified financial advisor before "
        "making investment decisions.'"
    )
    targets_text = "\n".join(f"  {name}: {weight:.1%}" for name, weight in targets.items())
    user_content = f"{snapshot}\n\nTarget allocation weights:\n{targets_text}"
    yield from _stream_response(system_prompt, user_content)


def summarize_news(snapshot: str):
    system_prompt = (
        "You are a financial news summarizer. For each major holding in this "
        "portfolio, provide recent context and developments from your knowledge. "
        "State clearly that your information has a knowledge cutoff and may not "
        "reflect the very latest developments."
    )
    yield from _stream_response(system_prompt, snapshot)
