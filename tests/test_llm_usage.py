"""Tests for LLM usage tracking and cost estimation."""

from __future__ import annotations

from bristlenose.llm.client import LLMUsageTracker
from bristlenose.llm.pricing import (
    PRICING,
    PRICING_URLS,
    estimate_cost,
)

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

    def test_pricing_urls_have_all_cloud_providers(self) -> None:
        assert "anthropic" in PRICING_URLS
        assert "openai" in PRICING_URLS
        assert "google" in PRICING_URLS


# ---------------------------------------------------------------------------
# Pipeline cost estimate
# ---------------------------------------------------------------------------


class TestEstimatePipelineCost:
    """Forecast resolution: legacy env-var → local JSONL → shipped baseline → None.

    Slice C made the forecast data-driven. Earlier constant-based tests
    are replaced with cohort-aware fixtures. The
    ``test_reasonable_cost_for_20_sessions`` sanity check is deferred until
    ``cohort-baselines.json`` is populated from a FOSSDA dogfood run.
    """

    def test_unknown_model_returns_none(self) -> None:
        from bristlenose.llm.pricing import estimate_pipeline_cost

        assert estimate_pipeline_cost("unknown-model-v99", 10) is None

    def test_zero_sessions_returns_none(self) -> None:
        from bristlenose.llm.pricing import estimate_pipeline_cost

        assert estimate_pipeline_cost("claude-sonnet-4-20250514", 0) is None

    def test_returns_none_when_no_data_anywhere(self, tmp_path) -> None:
        """No local JSONL + empty shipped baselines → forecast unavailable."""
        from bristlenose.llm.pricing import _load_baselines, estimate_pipeline_cost

        _load_baselines.cache_clear()
        cost = estimate_pipeline_cost(
            "claude-sonnet-4-20250514", 10, run_dir=tmp_path,
        )
        assert cost is None

    def test_returns_baseline_when_no_local_jsonl(self, tmp_path, monkeypatch) -> None:
        """With baselines populated and no local JSONL, forecast uses shipped medians."""
        from bristlenose.llm import pricing
        from bristlenose.llm.pricing import estimate_pipeline_cost

        fake_baselines = [
            {
                "stage_id": "s09_quote_extraction",
                "prompt_id": "quote-extraction",
                "prompt_version": "0.1.0",
                "model_family": "claude-sonnet",
                "model_major": "4",
                "median_input_tokens": 10_000,
                "median_output_tokens": 5_000,
                "sample_count": 12,
            },
            {
                "stage_id": "s10_quote_clustering",
                "prompt_id": "quote-clustering",
                "prompt_version": "0.1.0",
                "model_family": "claude-sonnet",
                "model_major": "4",
                "median_input_tokens": 8_000,
                "median_output_tokens": 4_000,
                "sample_count": 12,
            },
        ]
        monkeypatch.setattr(pricing, "_load_baselines", lambda: fake_baselines)

        cost = estimate_pipeline_cost(
            "claude-sonnet-4-20250514", 10, run_dir=tmp_path,
        )
        # s09 is per-session (×10), s10 is per-run (×1).
        # input  = 10_000 * 10 + 8_000 * 1 = 108_000
        # output = 5_000 * 10 + 4_000 * 1  = 54_000
        # cost   = (108_000 * 3.0 + 54_000 * 15.0) / 1_000_000 = 1.134
        expected = (108_000 * 3.0 + 54_000 * 15.0) / 1_000_000
        assert cost is not None
        assert abs(cost - expected) < 0.0001

    def test_returns_local_median_when_3_plus_rows(
        self, tmp_path, monkeypatch,
    ) -> None:
        """Local JSONL with N≥3 per stage outweighs shipped baselines."""
        from bristlenose.llm import pricing
        from bristlenose.llm.pricing import estimate_pipeline_cost
        from bristlenose.llm.telemetry import JSONL_FILENAME, record_call

        # Baselines exist but should be ignored once local data is sufficient.
        fake_baselines = [
            {
                "stage_id": "s09_quote_extraction",
                "prompt_id": "quote-extraction",
                "prompt_version": "0.1.0",
                "model_family": "claude-sonnet",
                "model_major": "4",
                "median_input_tokens": 999_999,
                "median_output_tokens": 999_999,
                "sample_count": 12,
            },
        ]
        monkeypatch.setattr(pricing, "_load_baselines", lambda: fake_baselines)

        # Write 5 fake rows for s09 — input medians 12_000, output 6_000.
        for in_tok, out_tok in [
            (10_000, 5_000),
            (12_000, 6_000),  # median
            (14_000, 7_000),
            (11_000, 5_500),
            (13_000, 6_500),
        ]:
            record_call(
                provider="anthropic",
                request_model="claude-sonnet-4-20250514",
                response_model="claude-sonnet-4-20250514",
                input_chars=50_000,
                elapsed_ms=2000,
                outcome="ok",
                price_table_version="2026-04-25",
                input_tokens=in_tok,
                output_tokens=out_tok,
                run_dir=tmp_path,
                run_id="test-run-1",
                stage_override="s09_quote_extraction",
                session_id_override="p1",
            )
        assert (tmp_path / JSONL_FILENAME).exists()

        cost = estimate_pipeline_cost(
            "claude-sonnet-4-20250514", 10, run_dir=tmp_path,
        )
        # median_in=12_000, median_out=6_000 (per-session, ×10).
        # cost = (120_000 * 3.0 + 60_000 * 15.0) / 1_000_000 = 1.26
        expected = (120_000 * 3.0 + 60_000 * 15.0) / 1_000_000
        assert cost is not None
        assert abs(cost - expected) < 0.0001

    def test_falls_back_to_baseline_when_local_below_threshold(
        self, tmp_path, monkeypatch,
    ) -> None:
        """Below N=3 local samples per stage → baseline path wins."""
        from bristlenose.llm import pricing
        from bristlenose.llm.pricing import estimate_pipeline_cost
        from bristlenose.llm.telemetry import record_call

        fake_baselines = [
            {
                "stage_id": "s09_quote_extraction",
                "prompt_id": "quote-extraction",
                "prompt_version": "0.1.0",
                "model_family": "claude-sonnet",
                "model_major": "4",
                "median_input_tokens": 10_000,
                "median_output_tokens": 5_000,
                "sample_count": 12,
            },
        ]
        monkeypatch.setattr(pricing, "_load_baselines", lambda: fake_baselines)

        # Only 2 local rows — below threshold.
        for in_tok, out_tok in [(50_000, 25_000), (60_000, 30_000)]:
            record_call(
                provider="anthropic",
                request_model="claude-sonnet-4-20250514",
                response_model="claude-sonnet-4-20250514",
                input_chars=50_000,
                elapsed_ms=2000,
                outcome="ok",
                price_table_version="2026-04-25",
                input_tokens=in_tok,
                output_tokens=out_tok,
                run_dir=tmp_path,
                run_id="test-run-1",
                stage_override="s09_quote_extraction",
                session_id_override="p1",
            )

        cost = estimate_pipeline_cost(
            "claude-sonnet-4-20250514", 10, run_dir=tmp_path,
        )
        # Baseline numbers, not local: 100_000 in, 50_000 out → 1.05
        expected = (100_000 * 3.0 + 50_000 * 15.0) / 1_000_000
        assert cost is not None
        assert abs(cost - expected) < 0.0001

    def test_legacy_kill_switch(self, monkeypatch) -> None:
        """``BRISTLENOSE_LLM_FORECAST=legacy`` returns the pre-Slice-C constant."""
        from bristlenose.llm.pricing import estimate_cost, estimate_pipeline_cost

        monkeypatch.setenv("BRISTLENOSE_LLM_FORECAST", "legacy")
        cost = estimate_pipeline_cost("claude-sonnet-4-20250514", 10)
        # 17_000 input + 10_000 output per session, ×10
        expected = estimate_cost("claude-sonnet-4-20250514", 170_000, 100_000)
        assert cost is not None
        assert expected is not None
        assert abs(cost - expected) < 0.0001

    def test_legacy_kill_switch_ignores_local_and_baselines(
        self, tmp_path, monkeypatch,
    ) -> None:
        """Legacy mode bypasses both data sources."""
        from bristlenose.llm import pricing
        from bristlenose.llm.pricing import estimate_pipeline_cost

        monkeypatch.setenv("BRISTLENOSE_LLM_FORECAST", "legacy")
        monkeypatch.setattr(
            pricing,
            "_load_baselines",
            lambda: [
                {
                    "stage_id": "s09_quote_extraction",
                    "model_family": "claude-sonnet",
                    "model_major": "4",
                    "median_input_tokens": 1,
                    "median_output_tokens": 1,
                },
            ],
        )
        cost = estimate_pipeline_cost(
            "claude-sonnet-4-20250514", 10, run_dir=tmp_path,
        )
        # Should match legacy: 170_000 in, 100_000 out.
        assert cost is not None
        expected = (170_000 * 3.0 + 100_000 * 15.0) / 1_000_000
        assert abs(cost - expected) < 0.0001

    def test_serve_autocode_rows_excluded(self, tmp_path, monkeypatch) -> None:
        """Rows with stage='serve_autocode' must not influence the pipeline forecast."""
        from bristlenose.llm import pricing
        from bristlenose.llm.pricing import estimate_pipeline_cost
        from bristlenose.llm.telemetry import record_call

        monkeypatch.setattr(pricing, "_load_baselines", lambda: [])

        # Five autocode rows that would otherwise satisfy the N≥3 threshold.
        for _ in range(5):
            record_call(
                provider="anthropic",
                request_model="claude-sonnet-4-20250514",
                response_model="claude-sonnet-4-20250514",
                input_chars=50_000,
                elapsed_ms=2000,
                outcome="ok",
                price_table_version="2026-04-25",
                input_tokens=999_999,
                output_tokens=999_999,
                run_dir=tmp_path,
                run_id="test-run-1",
                stage_override="serve_autocode",
            )

        cost = estimate_pipeline_cost(
            "claude-sonnet-4-20250514", 10, run_dir=tmp_path,
        )
        # No pipeline rows + no baselines → None.
        assert cost is None
