"""Tests for the LLM telemetry writer + retention helpers.

Slice A scope: schema round-trip, file mode, contextvar isolation across
async tasks, retention trim, missing-usage handling, kill switch. The
hot-path wiring (client.py, run_lifecycle.py) lands in Slice B.
"""

from __future__ import annotations

import asyncio
import json
import stat
from pathlib import Path

import pytest

from bristlenose.llm import telemetry
from bristlenose.llm.telemetry import (
    JSONL_FILENAME,
    LLMCallEvent,
    iter_rows,
    record_call,
    reset_run_context,
    session,
    set_run_context,
    stage,
    trim_to_cap,
)


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BRISTLENOSE_LLM_TELEMETRY", raising=False)
    monkeypatch.delenv("BRISTLENOSE_LLM_CALLS_RETAIN", raising=False)


def _record_basic(run_dir: Path, **overrides: object) -> None:
    kwargs: dict[str, object] = {
        "provider": "anthropic",
        "request_model": "claude-sonnet-4-20250514",
        "response_model": "claude-sonnet-4-20250514",
        "input_chars": 1234,
        "elapsed_ms": 567,
        "outcome": "ok",
        "price_table_version": "v1",
        "input_tokens": 800,
        "output_tokens": 200,
        "run_dir": run_dir,
        "run_id": "run-abc",
        "stage_override": "s09_quote_extraction",
    }
    kwargs.update(overrides)
    record_call(**kwargs)  # type: ignore[arg-type]


def test_event_roundtrip_with_otel_aliases() -> None:
    event = LLMCallEvent(
        ts="2026-04-27T10:00:00.000Z",
        run_id="r1",
        stage="s09",
        input_chars=10,
        elapsed_ms=20,
        outcome="ok",
        model_family="claude-sonnet",
        model_major="4",
        price_table_version="v1",
        **{
            "gen_ai.system": "anthropic",
            "gen_ai.request.model": "claude-sonnet-4-20250514",
            "gen_ai.usage.input_tokens": 100,
            "gen_ai.usage.output_tokens": 50,
        },  # type: ignore[arg-type]
    )
    serialised = event.model_dump_json(by_alias=True)
    payload = json.loads(serialised)
    assert payload["gen_ai.system"] == "anthropic"
    assert payload["gen_ai.usage.input_tokens"] == 100
    assert "input_tokens" not in payload  # alias must win
    # Round-trip
    parsed = LLMCallEvent.model_validate_json(serialised)
    assert parsed.input_tokens == 100
    assert parsed.gen_ai_request_model == "claude-sonnet-4-20250514"


def test_record_call_writes_jsonl_row(tmp_path: Path) -> None:
    _record_basic(tmp_path)
    path = tmp_path / JSONL_FILENAME
    assert path.exists()
    rows = list(iter_rows(tmp_path))
    assert len(rows) == 1
    assert rows[0]["gen_ai.system"] == "anthropic"
    assert rows[0]["gen_ai.usage.input_tokens"] == 800
    assert rows[0]["model_family"] == "claude-sonnet"
    assert rows[0]["model_major"] == "4"
    assert rows[0]["run_id"] == "run-abc"
    assert rows[0]["stage"] == "s09_quote_extraction"


def test_record_call_file_mode_is_0o600(tmp_path: Path) -> None:
    _record_basic(tmp_path)
    path = tmp_path / JSONL_FILENAME
    mode = stat.S_IMODE(path.stat().st_mode)
    # umask may strip permission bits but never add them; 0o600 is the
    # ceiling. Group/other must be zero.
    assert mode & 0o077 == 0


def test_kill_switch_no_op(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRISTLENOSE_LLM_TELEMETRY", "0")
    _record_basic(tmp_path)
    assert not (tmp_path / JSONL_FILENAME).exists()


def test_record_call_silent_without_run_context(tmp_path: Path) -> None:
    # No run_dir / run_id passed — and no contextvars set — should no-op.
    record_call(
        provider="anthropic",
        request_model="claude-sonnet-4-20250514",
        response_model="claude-sonnet-4-20250514",
        input_chars=10,
        elapsed_ms=5,
        outcome="ok",
        price_table_version="v1",
    )
    assert not (tmp_path / JSONL_FILENAME).exists()


def test_record_call_uses_contextvars(tmp_path: Path) -> None:
    tokens = set_run_context("run-from-ctx", tmp_path)
    try:
        with stage("s10_quote_clustering"):
            with session("p001"):
                record_call(
                    provider="openai",
                    request_model="gpt-4o",
                    response_model="gpt-4o-2024-08-06",
                    input_chars=42,
                    elapsed_ms=99,
                    outcome="ok",
                    price_table_version="v1",
                    input_tokens=10,
                    output_tokens=20,
                )
    finally:
        reset_run_context(tokens)
    rows = list(iter_rows(tmp_path))
    assert len(rows) == 1
    assert rows[0]["run_id"] == "run-from-ctx"
    assert rows[0]["stage"] == "s10_quote_clustering"
    assert rows[0]["session_id"] == "p001"
    assert rows[0]["model_family"] == "gpt-4o"


def test_missing_usage_handled(tmp_path: Path) -> None:
    _record_basic(
        tmp_path,
        input_tokens=None,
        output_tokens=None,
        usage_source="missing",
    )
    rows = list(iter_rows(tmp_path))
    assert rows[0]["gen_ai.usage.input_tokens"] is None
    assert rows[0]["gen_ai.usage.output_tokens"] is None
    assert rows[0]["usage_source"] == "missing"


def test_truncated_outcome_recorded(tmp_path: Path) -> None:
    _record_basic(tmp_path, outcome="truncated", finish_reason="length")
    rows = list(iter_rows(tmp_path))
    assert rows[0]["outcome"] == "truncated"
    assert rows[0]["finish_reason"] == "length"


def test_retry_count_recorded(tmp_path: Path) -> None:
    _record_basic(tmp_path, retry_count=2)
    rows = list(iter_rows(tmp_path))
    assert rows[0]["retry_count"] == 2


def test_trim_to_cap_truncates_oldest(tmp_path: Path) -> None:
    path = tmp_path / JSONL_FILENAME
    # Write 1500 hand-crafted rows; trim to 1000 keeps the last 1000.
    with path.open("w", encoding="utf-8") as f:
        for i in range(1500):
            f.write(json.dumps({"i": i}) + "\n")
    kept = trim_to_cap(path, cap=1000)
    assert kept == 1000
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(rows) == 1000
    assert rows[0]["i"] == 500
    assert rows[-1]["i"] == 1499
    # Mode preserved/reset to 0o600 on rewrite.
    mode = stat.S_IMODE(path.stat().st_mode)
    assert mode & 0o077 == 0


def test_trim_to_cap_no_op_when_under_cap(tmp_path: Path) -> None:
    path = tmp_path / JSONL_FILENAME
    path.write_text('{"i": 1}\n{"i": 2}\n', encoding="utf-8")
    kept = trim_to_cap(path, cap=100)
    assert kept == 2


def test_trim_to_cap_missing_file_returns_zero(tmp_path: Path) -> None:
    assert trim_to_cap(tmp_path / "missing.jsonl", cap=10) == 0


def test_retention_env_var_overrides(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BRISTLENOSE_LLM_CALLS_RETAIN", "5")
    path = tmp_path / JSONL_FILENAME
    with path.open("w", encoding="utf-8") as f:
        for i in range(20):
            f.write(json.dumps({"i": i}) + "\n")
    kept = trim_to_cap(path)  # cap=None → reads env
    assert kept == 5


def test_async_contextvar_isolation(tmp_path: Path) -> None:
    tokens = set_run_context("run-async", tmp_path)

    async def runner() -> None:
        async def one(pid: str) -> None:
            with stage("s09"):
                with session(pid):
                    # Yield to scheduler so other tasks interleave.
                    await asyncio.sleep(0)
                    record_call(
                        provider="anthropic",
                        request_model="claude-sonnet-4-20250514",
                        response_model="claude-sonnet-4-20250514",
                        input_chars=1,
                        elapsed_ms=1,
                        outcome="ok",
                        price_table_version="v1",
                        input_tokens=1,
                        output_tokens=1,
                    )

            return None

        await asyncio.gather(*[one(f"p{i}") for i in range(20)])

    try:
        asyncio.run(runner())
    finally:
        reset_run_context(tokens)

    rows = list(iter_rows(tmp_path))
    assert len(rows) == 20
    pids = sorted(r["session_id"] for r in rows)  # type: ignore[type-var]
    assert pids == sorted([f"p{i}" for i in range(20)])
    # Every row must see the run-level stage; no leakage of None.
    assert all(r["stage"] == "s09" for r in rows)


def test_record_call_normalises_response_model(tmp_path: Path) -> None:
    # response_model differs from request_model (provider returned a
    # dated string); cohort key reflects the response.
    _record_basic(
        tmp_path,
        request_model="gpt-4o",
        response_model="gpt-4o-2024-08-06",
        provider="openai",
    )
    rows = list(iter_rows(tmp_path))
    assert rows[0]["model_family"] == "gpt-4o"
    assert rows[0]["model_major"] == "4"


def test_no_fsync_per_call_does_not_corrupt(tmp_path: Path) -> None:
    # Sanity: ten sequential rows arrive intact (no per-call fsync but
    # single os.write per row).
    for _ in range(10):
        _record_basic(tmp_path)
    rows = list(iter_rows(tmp_path))
    assert len(rows) == 10


def test_telemetry_module_does_not_import_provider_sdks() -> None:
    # Lazy-import discipline: importing telemetry must not pull anthropic
    # / openai / google.
    import importlib
    import sys

    for mod in ("anthropic", "openai", "google", "google.genai"):
        sys.modules.pop(mod, None)
    importlib.import_module("bristlenose.llm.telemetry")
    for mod in ("anthropic", "openai", "google.genai"):
        assert mod not in sys.modules, f"{mod} pulled in by telemetry import"


def test_writer_creates_target_directory(tmp_path: Path) -> None:
    nested = tmp_path / ".bristlenose" / "deeper"
    _record_basic(nested)
    assert (nested / JSONL_FILENAME).exists()


def test_telemetry_module_constants_exported() -> None:
    assert telemetry.JSONL_FILENAME == "llm-calls.jsonl"
    assert telemetry.DEFAULT_RETENTION == 1000


# ---------------------------------------------------------------------------
# Cost fields
# ---------------------------------------------------------------------------
#
# ``cost_usd_actual_estimate`` and ``cost_usd_predicted`` were declared on
# LLMCallEvent in Slice A and written by nothing until 2026-09-21, so every
# row in every llm-calls.jsonl in the tree carried ``null`` for both. The
# schema round-trip test above passed throughout — it asserts the fields
# exist, which was never the thing in doubt.


def test_record_call_derives_actual_cost(tmp_path: Path) -> None:
    """A priced model gets a cost without the caller computing one."""
    from bristlenose.llm.pricing import estimate_cost

    _record_basic(tmp_path, input_tokens=10_000, output_tokens=5_000)
    row = next(iter_rows(tmp_path))

    expected = estimate_cost("claude-sonnet-4-20250514", 10_000, 5_000)
    assert expected is not None
    assert row["cost_usd_actual_estimate"] == pytest.approx(expected)


def test_record_call_derives_predicted_cost_from_cohort_median(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Predicted is the cohort's median call, not this call.

    The residual ``actual - predicted`` is the point of the pair, so the two
    must be computed from different inputs. Feeding tokens far off the median
    is what distinguishes a real prediction from a copy of the actual.
    """
    from bristlenose.llm import pricing

    monkeypatch.setattr(pricing, "_load_baselines", lambda: [
        {
            "stage_id": "s09_quote_extraction",
            "model_family": "claude-sonnet", "model_major": "4",
            "median_input_tokens": 4_000, "median_output_tokens": 2_000,
        },
    ])
    _record_basic(tmp_path, input_tokens=40_000, output_tokens=20_000)
    row = next(iter_rows(tmp_path))

    actual = pricing.estimate_cost("claude-sonnet-4-20250514", 40_000, 20_000)
    predicted = pricing.estimate_cost("claude-sonnet-4-20250514", 4_000, 2_000)
    assert actual is not None and predicted is not None
    assert row["cost_usd_actual_estimate"] == pytest.approx(actual)
    assert row["cost_usd_predicted"] == pytest.approx(predicted)
    assert row["cost_usd_actual_estimate"] != row["cost_usd_predicted"]


def test_unpriced_response_model_falls_back_to_request_model(
    tmp_path: Path,
) -> None:
    """OpenAI answers ``gpt-4o`` with ``gpt-4o-2024-08-06``, which is unpriced.

    Every OpenAI row in the corpus has this shape, so pricing the response
    model alone would leave the whole provider costless.
    """
    from bristlenose.llm.pricing import PRICING, estimate_cost

    assert "gpt-4o-2024-08-06" not in PRICING
    _record_basic(
        tmp_path, provider="openai", request_model="gpt-4o",
        response_model="gpt-4o-2024-08-06",
        input_tokens=10_000, output_tokens=5_000,
    )
    row = next(iter_rows(tmp_path))

    expected = estimate_cost("gpt-4o", 10_000, 5_000)
    assert expected is not None
    assert row["cost_usd_actual_estimate"] == pytest.approx(expected)


def test_unpriced_model_leaves_costs_null(tmp_path: Path) -> None:
    """An Azure deployment name is an opaque user string, never priceable.

    Token counts are still worth recording, so a null cost is correct here
    and not a failure.
    """
    _record_basic(
        tmp_path, provider="azure", request_model="my-deployment",
        response_model="my-deployment",
    )
    row = next(iter_rows(tmp_path))
    assert row["cost_usd_actual_estimate"] is None
    assert row["cost_usd_predicted"] is None
    assert row["gen_ai.usage.input_tokens"] == 800


def test_missing_usage_leaves_actual_cost_null(tmp_path: Path) -> None:
    """No token counts means no cost — never a zero, which reads as free."""
    _record_basic(
        tmp_path, input_tokens=None, output_tokens=None,
        usage_source="missing", outcome="error",
    )
    row = next(iter_rows(tmp_path))
    assert row["cost_usd_actual_estimate"] is None


def test_caller_supplied_cost_is_not_overwritten(tmp_path: Path) -> None:
    """The derivation fills a gap; it does not override an explicit value."""
    _record_basic(tmp_path, cost_usd_actual_estimate=0.4242)
    row = next(iter_rows(tmp_path))
    assert row["cost_usd_actual_estimate"] == pytest.approx(0.4242)
