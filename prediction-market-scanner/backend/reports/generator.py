"""Generate research reports using Claude API (streaming)."""
import anthropic
from database import settings

_client: anthropic.AsyncAnthropic | None = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client


SYSTEM_PROMPT = """You are a financial research analyst specializing in prediction markets.
When given a prediction market question and its current probability, produce a concise
research report to help an independent investor verify the probability and decide whether
to trade.

Your report must contain exactly these sections, using markdown:

## Summary
One or two sentences on what the market is asking and the current probability.

## Why the Probability Is High
Key factors driving the current consensus. Be specific — cite known policy stances,
historical patterns, institutional commitments, or recent data where relevant.

## Key Risks / What Could Move the Market
Specific scenarios that could cause the probability to drop significantly.
Be realistic, not hypothetical.

## What to Research Independently
A bulleted checklist of concrete sources and data points the investor should check
before trading (e.g., specific CME FedWatch data, scheduled announcements, official
statements, recent news sources).

## Bottom Line
One sentence verdict on whether the probability appears well-calibrated based on
available information, and what signal would change your view.

Be direct and factual. Avoid generic disclaimers. Assume the reader is financially literate."""


async def generate_report(
    question: str,
    probability: float,
    source: str,
    volume_24h: float,
    closes_at: str,
) -> str:
    """Stream a research report from Claude and return the full text."""
    client = _get_client()

    pct = f"{probability * 100:.1f}%"
    user_prompt = f"""Prediction Market Research Request

**Platform**: {source.title()}
**Question**: {question}
**Current Probability (YES)**: {pct}
**24h Volume**: ${volume_24h:,.0f}
**Closes**: {closes_at or "Not specified"}

Please produce a research report following the format specified."""

    full_text = ""
    async with client.messages.stream(
        model="claude-opus-4-6",
        max_tokens=1500,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    ) as stream:
        async for text in stream.text_stream:
            full_text += text

    return full_text
