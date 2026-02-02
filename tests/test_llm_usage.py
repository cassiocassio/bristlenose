"""Tests for LLM usage tracking and cost estimation."""

from __future__ import annotations

from bristlenose.llm.client import LLMUsageTracker
from bristlenose.llm.pricing import PRICING, PRICING_URLS, estimate_cost

# ---------------------------------------------------------------------------
# LLMUsageTracker
# ---------------------------------------------------------------------------


class TestLLMUsageTracker:
    def test_starts_at_zero(self) -> None:
        t = LLMUsageTracker()
        assert t.input_tokens == 0
        assert t.output_tokens == 0
        assert t.calls == 0
        assert t.total_tokens == 0

    def test_record_accumulates(self) -> None:
        t = LLMUsageTracker()
        t.record(100, 50)
        t.record(200, 75)
        assert t.input_tokens == 300
        assert t.output_tokens == 125
        assert t.calls == 2
        assert t.total_tokens == 425

    def test_single_record(self) -> None:
        t = LLMUsageTracker()
        t.record(1000, 500)
        assert t.input_tokens == 1000
        assert t.output_tokens == 500
        assert t.calls == 1
        assert t.total_tokens == 1500


# ---------------------------------------------------------------------------
# Pricing
# ---------------------------------------------------------------------------


class TestEstimateCost:
    def test_known_model_sonnet(self) -> None:
        # claude-sonnet-4-20250514: $3/MTok in, $15/MTok out
        cost = estimate_cost("claude-sonnet-4-20250514", 1_000_000, 1_000_000)
        assert cost is not None
        assert cost == 3.0 + 15.0

    def test_known_model_small_usage(self) -> None:
        # 10k in, 2k out at Sonnet rates
        cost = estimate_cost("claude-sonnet-4-20250514", 10_000, 2_000)
        assert cost is not None
        expected = (10_000 * 3.0 + 2_000 * 15.0) / 1_000_000
        assert abs(cost - expected) < 0.0001

    def test_known_model_gpt4o(self) -> None:
        cost = estimate_cost("gpt-4o", 1_000_000, 1_000_000)
        assert cost is not None
        assert cost == 2.5 + 10.0

    def test_unknown_model_returns_none(self) -> None:
        assert estimate_cost("unknown-model-v99", 1000, 1000) is None

    def test_zero_tokens(self) -> None:
        cost = estimate_cost("claude-sonnet-4-20250514", 0, 0)
        assert cost == 0.0

    def test_default_model_in_pricing_table(self) -> None:
        """The default model from config.py must have a pricing entry."""
        assert "claude-sonnet-4-20250514" in PRICING

    def test_pricing_urls_have_both_providers(self) -> None:
        assert "anthropic" in PRICING_URLS
        assert "openai" in PRICING_URLS
