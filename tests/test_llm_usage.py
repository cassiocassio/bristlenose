"""Tests for LLM usage tracking and cost estimation."""

from __future__ import annotations

import pytest

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

    def test_returns_none_when_no_data_anywhere(self, tmp_path, monkeypatch) -> None:
        """No local JSONL + empty shipped baselines → forecast unavailable.

        The baselines are stubbed empty rather than read from disk. Until
        2026-09-21 this test got its emptiness from the shipped file, which
        really was empty — so it passed by describing the defect it was
        sitting on, and would have gone red the moment anyone fixed it.
        """
        from bristlenose.llm import pricing
        from bristlenose.llm.pricing import estimate_pipeline_cost

        monkeypatch.setattr(pricing, "_load_baselines", lambda: [])
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


# ---------------------------------------------------------------------------
# Shipped baselines — the new-user path
# ---------------------------------------------------------------------------


class TestShippedBaselinesServeNewUsers:
    """The forecast must fire for a user who has never run the pipeline.

    Every test here reads the **real** ``cohort-baselines.json`` and a
    genuinely empty ``run_dir`` — no stubbed cohorts. That is the whole
    point: the suite above passes against synthetic fixtures and stayed
    green for five months while ``estimate_pipeline_cost`` returned ``None``
    for every user on every model, because the shipped file was the empty
    Slice A placeholder and no test ever read it.
    """

    def test_shipped_baselines_are_populated(self) -> None:
        """The file nothing read. An empty one disables the whole feature."""
        from bristlenose.llm.pricing import _load_baselines

        _load_baselines.cache_clear()
        cohorts = _load_baselines()
        assert cohorts, "cohort-baselines.json is empty — the forecast cannot fire"
        for row in cohorts:
            assert isinstance(row.get("median_input_tokens"), int)
            assert isinstance(row.get("median_output_tokens"), int)
            assert row.get("stage_id")

    def test_baselines_carry_no_reidentifying_fields(self) -> None:
        """The baselines are derived from logs that are re-identification keys."""
        import json
        from pathlib import Path

        from bristlenose.llm import pricing

        blob = json.loads(Path(pricing._BASELINES_PATH).read_text(encoding="utf-8"))
        for forbidden in ("session_id", "run_id", "prompt_sha", "elapsed_ms"):
            assert forbidden not in json.dumps(blob)

    @pytest.mark.parametrize("model", sorted(PRICING))
    def test_every_priced_model_forecasts_for_a_new_user(
        self, model: str, tmp_path,
    ) -> None:
        """A priced model must never forecast ``None`` on an empty run_dir.

        Driven from ``PRICING`` itself rather than a hand-written list, so a
        model added to the table without baseline coverage fails here instead
        of shipping a silently absent forecast.
        """
        from bristlenose.llm.pricing import _load_baselines, estimate_pipeline_cost

        _load_baselines.cache_clear()
        assert not list(tmp_path.iterdir()), "run_dir must be genuinely empty"

        cost = estimate_pipeline_cost(model, 15, run_dir=tmp_path)
        assert cost is not None, f"{model} is priced but forecasts None"
        assert cost > 0

    def test_every_cloud_provider_default_model_forecasts(self, tmp_path) -> None:
        """The models a new user actually lands on, via the provider registry.

        Three of the four cloud defaults normalise to a cohort with no
        measured rows (``gpt-5.6-terra`` → ``("gpt-5.6-terra", "0")``,
        ``gemini-3.8-flash`` → ``("gemini-flash", "3")``), which is why the
        pooled ``*`` cohort exists. Azure is excluded: its deployment names
        are opaque user strings and have never been priceable.
        """
        from bristlenose.llm.pricing import _load_baselines, estimate_pipeline_cost
        from bristlenose.providers import PROVIDERS

        _load_baselines.cache_clear()
        checked = 0
        for name, spec in PROVIDERS.items():
            if name in {"azure", "local"} or not spec.default_model:
                continue
            checked += 1
            cost = estimate_pipeline_cost(spec.default_model, 15, run_dir=tmp_path)
            assert cost is not None, (
                f"{name} default {spec.default_model!r} forecasts None"
            )
        assert checked >= 3

    def test_unseen_major_uses_the_same_family(self, tmp_path) -> None:
        """``claude-sonnet-5`` is priced but unmeasured; sonnet-4 rows serve it.

        A generation bump does not change how many tokens a transcript is.
        """
        from bristlenose.llm.pricing import (
            _baseline_lookup,
            _load_baselines,
            estimate_pipeline_cost,
        )

        _load_baselines.cache_clear()
        rows = _baseline_lookup("claude-sonnet", "5")
        assert rows, "no fallback rows for an unseen major"
        assert {r["model_family"] for r in rows} == {"claude-sonnet"}
        assert estimate_pipeline_cost("claude-sonnet-5", 10, run_dir=tmp_path) is not None

    def test_unseen_family_uses_the_pooled_cohort(self) -> None:
        """A family with no rows at all resolves to ``("*", "*")``."""
        from bristlenose.llm.pricing import _baseline_lookup, _load_baselines

        _load_baselines.cache_clear()
        rows = _baseline_lookup("gpt-5.6-terra", "0")
        assert rows
        assert {r["model_family"] for r in rows} == {"*"}

    def test_lookup_returns_one_row_per_stage(self) -> None:
        """A forecast sums across stages — two rows for one stage bills twice."""
        from bristlenose.llm.pricing import _baseline_lookup, _load_baselines

        _load_baselines.cache_clear()
        for family, major in [
            ("claude-sonnet", "4"), ("claude-sonnet", "5"), ("gpt-5.6-terra", "0"),
        ]:
            stage_ids = [r["stage_id"] for r in _baseline_lookup(family, major)]
            assert len(stage_ids) == len(set(stage_ids)), (family, major)


class TestPerRunStagesDoNotVetoLocalData:
    """A per-run stage has one sample per run, and one is the whole population.

    ``_LOCAL_N_THRESHOLD`` was applied to every bucket, and an under-sampled
    bucket vetoed the entire forecast — so ``s10``/``s11``, which issue
    exactly one call per run by construction, made the local path
    unreachable for any project that had run once. Measured on the FOSSDA
    log 2026-09-21: 39 well-sampled per-session rows discarded because two
    stages had the only sample count they will ever have.
    """

    @staticmethod
    def _write_fossda_shaped_log(run_dir) -> None:
        """Plenty of per-session rows; exactly one row per per-run stage."""
        from bristlenose.llm.telemetry import record_call

        def row(stage: str, i: int, o: int, session: str | None) -> None:
            record_call(
                provider="anthropic",
                request_model="claude-sonnet-4-6",
                response_model="claude-sonnet-4-6",
                input_chars=i * 4,
                elapsed_ms=2000,
                outcome="ok",
                price_table_version="2026-09-04",
                input_tokens=i,
                output_tokens=o,
                run_dir=run_dir,
                run_id="run-1",
                stage_override=stage,
                session_id_override=session,
            )

        for n in range(5):
            row("s08_topic_segmentation", 3000, 400, f"p{n}")
            row("s09_quote_extraction", 4000, 2700, f"p{n}")
        # The per-run stages: one call each, which is all a run ever makes.
        row("s10_quote_clustering", 3100, 550, None)
        row("s11_thematic_grouping", 2600, 500, None)

    def test_local_forecast_survives_single_sample_per_run_stages(
        self, tmp_path, monkeypatch,
    ) -> None:
        from bristlenose.llm import pricing

        monkeypatch.setattr(pricing, "_load_baselines", lambda: [])
        self._write_fossda_shaped_log(tmp_path)

        cost = pricing.estimate_pipeline_cost(
            "claude-sonnet-4-6", 10, run_dir=tmp_path,
        )
        # Per-session medians ×10, per-run medians ×1 — all from local rows.
        exp_in = (3000 + 4000) * 10 + 3100 + 2600
        exp_out = (400 + 2700) * 10 + 550 + 500
        expected = pricing.estimate_cost("claude-sonnet-4-6", exp_in, exp_out)
        assert cost is not None
        assert expected is not None
        assert abs(cost - expected) < 0.0001

    def test_per_run_stages_contribute_rather_than_being_dropped(
        self, tmp_path, monkeypatch,
    ) -> None:
        """Guards the lazy fix: skipping the thin bucket instead of vetoing.

        Dropping s10/s11 would also make the forecast non-None, so a test
        that only asserts ``is not None`` cannot tell the two apart.
        """
        from bristlenose.llm import pricing

        monkeypatch.setattr(pricing, "_load_baselines", lambda: [])
        self._write_fossda_shaped_log(tmp_path)

        buckets = pricing._scan_local_jsonl(tmp_path, "claude-sonnet", "4")
        assert pricing._local_covered_stages(buckets) == {
            "s08_topic_segmentation",
            "s09_quote_extraction",
            "s10_quote_clustering",
            "s11_thematic_grouping",
        }

    def test_thin_per_session_stage_is_topped_up_from_baselines(
        self, tmp_path, monkeypatch,
    ) -> None:
        """Local and shipped sources compose — one thin cell discards neither.

        Two s09 rows is below threshold, so s09 comes from the baseline
        while the well-sampled s08 stays local.
        """
        from bristlenose.llm import pricing
        from bristlenose.llm.telemetry import record_call

        monkeypatch.setattr(pricing, "_load_baselines", lambda: [
            {
                "stage_id": "s09_quote_extraction",
                "model_family": "claude-sonnet", "model_major": "4",
                "median_input_tokens": 1000, "median_output_tokens": 500,
            },
        ])
        for n in range(5):
            record_call(
                provider="anthropic", request_model="claude-sonnet-4-6",
                response_model="claude-sonnet-4-6", input_chars=1, elapsed_ms=1,
                outcome="ok", price_table_version="2026-09-04",
                input_tokens=3000, output_tokens=400, run_dir=tmp_path,
                run_id="r", stage_override="s08_topic_segmentation",
                session_id_override=f"p{n}",
            )
        for n in range(2):  # below threshold
            record_call(
                provider="anthropic", request_model="claude-sonnet-4-6",
                response_model="claude-sonnet-4-6", input_chars=1, elapsed_ms=1,
                outcome="ok", price_table_version="2026-09-04",
                input_tokens=99_999, output_tokens=99_999, run_dir=tmp_path,
                run_id="r", stage_override="s09_quote_extraction",
                session_id_override=f"q{n}",
            )

        cost = pricing.estimate_pipeline_cost(
            "claude-sonnet-4-6", 10, run_dir=tmp_path,
        )
        exp_in = 3000 * 10 + 1000 * 10   # s08 local, s09 baseline
        exp_out = 400 * 10 + 500 * 10
        expected = pricing.estimate_cost("claude-sonnet-4-6", exp_in, exp_out)
        assert cost is not None
        assert expected is not None
        assert abs(cost - expected) < 0.0001
