"""Pure-function tests for the dev Run Inspector data layer.

Stdlib-only imports (no fastapi) so these run without the server stack —
``bristlenose.server.run_inspector`` deliberately depends on nothing heavy.
Endpoint/integration tests live in ``tests/test_serve_dev_run.py``.
"""

from __future__ import annotations

import json
from pathlib import Path

from bristlenose.server import run_inspector as ri


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def _call(stage="quote_extraction", system="anthropic", model="claude-opus-4-8-20260101",
          tin=1000, tout=200, cache=0, ms=3000, retries=0, finish="stop",
          cost=0.05, pred=0.04, ts="2026-06-27T14:22:39Z", run_id="r1"):
    return {
        "ts": ts, "run_id": run_id, "stage": stage,
        "gen_ai.system": system, "gen_ai.request.model": model,
        "gen_ai.usage.input_tokens": tin, "gen_ai.usage.output_tokens": tout,
        "gen_ai.usage.cache_read_input_tokens": cache,
        "elapsed_ms": ms, "retry_count": retries, "finish_reason": finish,
        "cost_usd_actual_estimate": cost, "cost_usd_predicted": pred,
    }


# --- readers ---------------------------------------------------------------

def test_read_jsonl_missing_returns_empty(tmp_path):
    assert ri.read_jsonl(tmp_path / "nope.jsonl") == []


def test_read_jsonl_skips_blank_and_bad_lines(tmp_path):
    p = tmp_path / "x.jsonl"
    p.write_text('{"a":1}\n\n   \nnot json\n{"b":2}\n', encoding="utf-8")
    assert ri.read_jsonl(p) == [{"a": 1}, {"b": 2}]


def test_load_llm_calls_normalises_aliases_and_provider(tmp_path):
    _write_jsonl(tmp_path / ri.JSONL_LLM, [_call(cache=600)])
    calls = ri.load_llm_calls(tmp_path)
    assert len(calls) == 1
    c = calls[0]
    assert c["provider"] == "Claude"          # gen_ai.system mapped to product name
    assert c["model"] == "opus-4-8"           # prefix + date stamp trimmed
    assert c["in"] == 1000 and c["out"] == 200 and c["cache"] == 600
    assert c["cost"] == 0.05 and c["cost_pred"] == 0.04


def test_load_llm_calls_handles_openai_and_missing_cost(tmp_path):
    row = _call(system="openai", model="gpt-4o", cost=None, pred=None)
    row["cost_usd_actual_estimate"] = None
    row["cost_usd_predicted"] = None
    _write_jsonl(tmp_path / ri.JSONL_LLM, [row])
    c = ri.load_llm_calls(tmp_path)[0]
    assert c["provider"] == "ChatGPT" and c["model"] == "gpt-4o"
    assert c["cost"] is None and c["cost_pred"] is None


# --- stats -----------------------------------------------------------------

def test_percentile():
    assert ri.percentile([], 0.5) == 0.0
    assert ri.percentile([5], 0.9) == 5
    assert ri.percentile([1, 2, 3, 4], 0.5) == 2.5
    assert ri.percentile([10, 20, 30], 1.0) == 30


def test_summarise_calls_aggregates():
    calls = [
        {"ms": 1000, "in": 100, "out": 10, "cache": 0, "cost": 0.01, "cost_pred": 0.01, "retries": 0, "stage": "a"},
        {"ms": 3000, "in": 300, "out": 30, "cache": 100, "cost": 0.03, "cost_pred": 0.02, "retries": 2, "stage": "b"},
    ]
    s = ri.summarise_calls(calls)
    assert s["n"] == 2 and s["retries"] == 2
    assert s["in"] == 400 and s["out"] == 40 and s["cache"] == 100
    assert s["cost"] == 0.04 and s["cost_pred"] == 0.03
    assert s["stage_count"] == 2
    assert round(s["cache_ratio"], 3) == round(100 / 500, 3)


def test_summarise_calls_cost_none_when_unrecorded_not_zero():
    # No call recorded a cost → cost is None ("—" / not recorded in the UI),
    # NOT 0.0 (which reads as a genuinely-free run, e.g. local Ollama).
    base = {"ms": 1000, "in": 100, "out": 10, "cache": 0, "retries": 0, "stage": "a"}
    unrecorded = ri.summarise_calls([{**base, "cost": None, "cost_pred": None}])
    assert unrecorded["cost"] is None and unrecorded["cost_pred"] is None
    # A genuine zero (free model) stays 0.0, distinct from None.
    free = ri.summarise_calls([{**base, "cost": 0.0, "cost_pred": 0.0}])
    assert free["cost"] == 0.0 and free["cost_pred"] == 0.0


def test_cost_by_stage_sorted_desc():
    calls = [
        {"stage": "cheap", "cost": 0.01, "in": 10, "out": 1, "cache": 0},
        {"stage": "pricey", "cost": 0.50, "in": 99, "out": 9, "cache": 0},
        {"stage": "pricey", "cost": 0.10, "in": 11, "out": 1, "cache": 0},
    ]
    rows = ri.cost_by_stage(calls)
    assert [r["stage"] for r in rows] == ["pricey", "cheap"]
    assert rows[0]["cost"] == 0.6


def test_calibration_only_pairs_with_both_values():
    calls = [
        {"stage": "a", "cost": 0.05, "cost_pred": 0.04, "in": 1, "out": 1, "cache": 0},
        {"stage": "a", "cost": None, "cost_pred": 0.04, "in": 1, "out": 1, "cache": 0},
    ]
    cal = ri.calibration(calls)
    assert len(cal) == 1 and cal[0]["pred"] == 0.04 and cal[0]["act"] == 0.05


# --- events / gantt --------------------------------------------------------

def test_reconstruct_stages_from_progress_stream():
    events = [
        {"kind": "progress", "stage": "transcribe", "elapsed_seconds": 0.0, "stage_fraction": 0.0},
        {"kind": "progress", "stage": "transcribe", "elapsed_seconds": 5.0, "stage_fraction": 0.9},
        {"kind": "progress", "stage": "quote_extraction", "elapsed_seconds": 10.0, "stage_fraction": 0.1},
        {"kind": "progress", "stage": "quote_extraction", "elapsed_seconds": 16.0, "stage_fraction": 0.9},
    ]
    stages, total = ri.reconstruct_stages(events)
    assert total == 16.0
    assert [s["id"] for s in stages] == ["transcribe", "quote_extraction"]
    assert stages[0]["dur"] == 10.0          # 0 → next stage start (10)
    assert stages[0]["status"] == "ran"
    assert stages[1]["status"] == "llm"      # quote_extraction is an LLM stage
    assert stages[1]["dur"] == 6.0           # 10 → run end (16)


def test_reconstruct_stages_empty_when_no_progress():
    assert ri.reconstruct_stages([{"kind": "started"}]) == ([], 0.0)


def test_event_stream_tail_and_glyphs():
    events = [{"kind": "started", "ts": "2026-06-27T14:00:00Z", "started_at": "x"}]
    events += [{"kind": "progress", "stage": "transcribe", "ts": f"2026-06-27T14:00:0{i}Z", "stage_fraction": 0.5} for i in range(3)]
    events.append({"kind": "completed", "ts": "2026-06-27T14:05:00Z"})
    out = ri.event_stream(events, limit=3)
    assert len(out) == 3
    assert out[-1]["glyph"] == "✓" and out[-1]["cls"] == "ok"


# --- timing ----------------------------------------------------------------

def test_load_timing_missing(tmp_path):
    assert ri.load_timing(tmp_path) == {"version": 1, "profiles": {}}


def test_timing_compare_matches_metrics_to_actuals():
    timing = {"profiles": {"mac": {
        "quotes": {"mean": 40.0, "m2": 200.0, "n": 11},   # var = 200/10 = 20, σ≈4.47
        "transcribe": {"mean": 100.0, "m2": 0.0, "n": 1},  # n<2 → σ=0
    }}}
    rows = ri.timing_compare(timing, {"quote_extraction": 47.6, "transcribe": 142.0})
    by_name = {r["name"]: r for r in rows}
    assert "Quote extraction" in by_name and "Transcribe" in by_name
    q = by_name["Quote extraction"]
    assert q["mu"] == 40.0 and q["n"] == 11 and round(q["sig"], 2) == 4.47 and q["act"] == 47.6
    # sorted by actual desc → Transcribe (142) first
    assert rows[0]["name"] == "Transcribe"


def test_timing_compare_empty_profiles():
    assert ri.timing_compare({"profiles": {}}, {"transcribe": 1.0}) == []


# --- assembly + html -------------------------------------------------------

def test_build_run_data_empty_dirs(tmp_path):
    data = ri.build_run_data(tmp_path, tmp_path, version="0.16.0")
    assert data["ok"] is False
    assert data["calls"] == [] and data["stages"] == []


def test_build_run_data_full(tmp_path):
    _write_jsonl(tmp_path / ri.JSONL_LLM, [
        _call(stage="topic_segmentation", cost=0.20, pred=0.18),
        _call(stage="quote_extraction", cost=0.40, pred=0.42, retries=1, finish="length"),
    ])
    _write_jsonl(tmp_path / ri.JSONL_EVENTS, [
        {"kind": "started", "run_id": "r1", "started_at": "2026-06-27T14:00:00Z",
         "process": {"os": "darwin-arm64", "bristlenose_version": "0.16.0"}},
        {"kind": "progress", "stage": "topic_segmentation", "elapsed_seconds": 0.0, "stage_fraction": 0.5},
        {"kind": "progress", "stage": "quote_extraction", "elapsed_seconds": 18.0, "stage_fraction": 0.5},
        {"kind": "completed", "run_id": "r1", "ended_at": "2026-06-27T14:04:12Z"},
    ])
    data = ri.build_run_data(tmp_path, tmp_path, version="0.16.0", sha="abc1234",
                             project_name="FOSSDA", db_path="/x/db")
    assert data["ok"] is True
    assert data["prov"]["provider"] == "Claude"
    assert data["prov"]["status"] == "completed"
    assert data["prov"]["duration_s"] == 252.0     # 4m12s
    assert data["prov"]["hardware"] == "darwin-arm64"
    assert data["summary"]["n"] == 2
    assert len(data["stages"]) == 2
    assert len(data["calibration"]) == 2
    # html builder injects the data and escapes </script>
    html = ri.build_run_inspector_html(data)
    assert "FOSSDA" in html
    assert ri._DATA_TOKEN not in html          # token was replaced
    assert "</script>" in html                 # the page's own closing tag


def test_html_escapes_script_breakout(tmp_path):
    # A project name containing </script> must not break out of the data block.
    data = ri.build_run_data(tmp_path, tmp_path, version="0.16.0",
                             project_name="</script><script>alert(1)</script>")
    html = ri.build_run_inspector_html(data)
    assert "<script>alert(1)" not in html
    assert "\\u003c" in html or "\\u003C" in html  # ensure_ascii escaped the <


def test_resolve_internal_dir(tmp_path):
    (tmp_path / "bristlenose-output").mkdir()
    assert ri.resolve_internal_dir(tmp_path) == tmp_path / "bristlenose-output" / ".bristlenose"
    # fallback: caller already points at the output dir
    other = tmp_path / "already-output"
    other.mkdir()
    assert ri.resolve_internal_dir(other) == other / ".bristlenose"
