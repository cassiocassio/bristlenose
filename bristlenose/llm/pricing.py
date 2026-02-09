"""LLM pricing estimates for token usage reporting.

Prices are approximate and may be outdated — users see a verification link
in the CLI output so they can check current rates.
"""

from __future__ import annotations

# Pricing per million tokens: (input_rate_usd, output_rate_usd).
PRICING: dict[str, tuple[float, float]] = {
    # Anthropic (Claude)
    "claude-sonnet-4-20250514": (3.0, 15.0),
    "claude-haiku-3-5-20241022": (0.80, 4.0),
    # OpenAI (ChatGPT)
    "gpt-4o": (2.50, 10.0),
    "gpt-4o-mini": (0.15, 0.60),
    # Google (Gemini)
    "gemini-2.5-flash": (0.15, 3.50),
    "gemini-2.5-pro": (1.25, 10.0),
}

PRICING_URLS: dict[str, str] = {
    "anthropic": "https://docs.anthropic.com/en/docs/about-claude/models",
    "openai": "https://platform.openai.com/docs/pricing",
    "azure": "https://azure.microsoft.com/pricing/details/cognitive-services/openai-service/",
    "google": "https://ai.google.dev/gemini-api/docs/pricing",
    # Local provider has no pricing — models are free
}


def estimate_cost(
    model: str, input_tokens: int, output_tokens: int,
) -> float | None:
    """Return estimated cost in USD, or None if model not in pricing table."""
    if model not in PRICING:
        return None
    inp_rate, out_rate = PRICING[model]
    return (input_tokens * inp_rate + output_tokens * out_rate) / 1_000_000
