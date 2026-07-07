"""Meta-tests: prove the acceptance invariants BITE before they guard anything.

A conformance harness whose whole job is catching fake-success is worthless if its
own guards false-green. So each guard is tested twice: it must FAIL on the bad shape
(empty artifact, missing terminus, None-that-can't-be-confirmed, a real leak, a
fully-failed stage) AND pass on the good shape (the committed smoke fixture, a real
completed run).
"""

from __future__ import annotations

import json

# scripts/ is not a package; add it to the path for the import.
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "acceptance"))

from invariants import (  # noqa: E402
    CellOutcome,
    InvariantError,
    assert_absent_over_decoded,
    assert_no_abandoned_stage,
    assert_nonempty_file,
    assert_reid_keys_not_shareable,
    assert_report_non_empty,
    assert_terminus_completed,
    classify_provider_outcome,
    count_quotes,
)

_SMOKE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "smoke-test"
    / "input"
    / "bristlenose-output"
)


# ---------------------------------------------------------------------------
# Size floor
# ---------------------------------------------------------------------------


def test_size_floor_fails_on_empty(tmp_path: Path) -> None:
    empty = tmp_path / "export.html"
    empty.write_text("")
    with pytest.raises(InvariantError, match="size floor"):
        assert_nonempty_file(empty, floor_bytes=500)


def test_size_floor_fails_on_absent(tmp_path: Path) -> None:
    with pytest.raises(InvariantError, match="absent"):
        assert_nonempty_file(tmp_path / "nope.html", floor_bytes=1)


def test_size_floor_passes_on_real(tmp_path: Path) -> None:
    f = tmp_path / "export.html"
    f.write_text("x" * 600)
    assert_nonempty_file(f, floor_bytes=500)  # no raise


# ---------------------------------------------------------------------------
# Positive-control absence (the PII-boundary check)
# ---------------------------------------------------------------------------


def test_absence_requires_positive_control() -> None:
    # The name was never in the source → asserting it's "gone" proves nothing → FAIL.
    with pytest.raises(InvariantError, match="positive control"):
        assert_absent_over_decoded("Jane Smith", "clean export", source_had_it="no name here")


def test_absence_detects_real_leak() -> None:
    with pytest.raises(InvariantError, match="leak"):
        assert_absent_over_decoded(
            "Jane Smith", "quote from Jane Smith", source_had_it="Jane Smith said..."
        )


def test_absence_passes_when_boundary_holds() -> None:
    # Present in the original, absent from the export → boundary held.
    assert_absent_over_decoded("Jane Smith", "quote from p1", source_had_it="Jane Smith said...")


def test_absence_catches_unicode_escaped_name() -> None:
    # ensure_ascii=True escapes José -> José; over the *decoded* text the leak shows.
    raw = json.dumps({"quote": "José said"})  # -> {"quote": "Jos\\u00e9 said"}
    decoded = json.loads(raw)["quote"]
    with pytest.raises(InvariantError, match="leak"):
        assert_absent_over_decoded("José", decoded, source_had_it="José said")
    # And a raw-byte grep would have MISSED it — this is why we decode:
    assert "José" not in raw


# ---------------------------------------------------------------------------
# Terminus — fail-closed
# ---------------------------------------------------------------------------


def test_terminus_fails_closed_on_absent_events(tmp_path: Path) -> None:
    (tmp_path / ".bristlenose").mkdir()
    with pytest.raises(InvariantError, match="no pipeline-events"):
        assert_terminus_completed(tmp_path)


def test_terminus_fails_closed_on_empty_events(tmp_path: Path) -> None:
    d = tmp_path / ".bristlenose"
    d.mkdir()
    (d / "pipeline-events.jsonl").write_text("\n")
    with pytest.raises(InvariantError, match="empty"):
        assert_terminus_completed(tmp_path)


def test_terminus_fails_on_run_failed(tmp_path: Path) -> None:
    d = tmp_path / ".bristlenose"
    d.mkdir()
    (d / "pipeline-events.jsonl").write_text(json.dumps({"event": "run_failed", "outcome": "failed"}))
    with pytest.raises(InvariantError, match="run_failed"):
        assert_terminus_completed(tmp_path)


def test_terminus_passes_on_smoke_fixture() -> None:
    event = assert_terminus_completed(_SMOKE)
    assert event["event"] == "run_completed"


# ---------------------------------------------------------------------------
# Abandoned-stage — catches the gemma4 class, tolerates None (terminus vouched)
# ---------------------------------------------------------------------------


def test_abandoned_stage_detected_when_summary_present() -> None:
    event = {"summary": {"stages": {"s08_topics": {"attempted": 5, "succeeded": 0}}}}
    with pytest.raises(InvariantError, match="fully failed"):
        assert_no_abandoned_stage(event)


def test_abandoned_stage_none_summary_is_tolerated() -> None:
    # None summary on a completed run (the smoke fixture case) must NOT fail here —
    # the terminus already vouched. Fail-closed applies to the terminus read, not this.
    assert_no_abandoned_stage({"summary": None})  # no raise


# ---------------------------------------------------------------------------
# Report non-emptiness (F8 — screen_clusters OR theme_groups, pinned floor)
# ---------------------------------------------------------------------------


def test_report_non_empty_passes_on_smoke() -> None:
    # Smoke fixture has 3 quotes across 2 screen clusters + 1 theme group.
    assert_report_non_empty(_SMOKE, quote_floor=3)
    assert count_quotes(_SMOKE) == 3


def test_report_non_empty_fails_below_floor() -> None:
    with pytest.raises(InvariantError, match="below floor"):
        assert_report_non_empty(_SMOKE, quote_floor=99)


# ---------------------------------------------------------------------------
# Governance
# ---------------------------------------------------------------------------


def test_reid_keys_absent_from_smoke_root() -> None:
    assert_reid_keys_not_shareable(_SMOKE)  # no raise — fixture is clean


def test_reid_key_in_root_is_caught(tmp_path: Path) -> None:
    (tmp_path / "llm-calls.jsonl").write_text("{}")
    with pytest.raises(InvariantError, match="re-identification key"):
        assert_reid_keys_not_shareable(tmp_path)


# ---------------------------------------------------------------------------
# Provider-state taxonomy (F7)
# ---------------------------------------------------------------------------


def test_taxonomy_unconfigured_is_declared_skip() -> None:
    assert classify_provider_outcome(configured=False, process_exit=None, empty_report=False) == (
        CellOutcome.SKIP
    )


def test_taxonomy_empty_report_is_blocking() -> None:
    # The gemma4 class: configured, exited 0, but produced nothing.
    assert classify_provider_outcome(configured=True, process_exit=0, empty_report=True) == (
        CellOutcome.FAIL_BLOCKING
    )


def test_taxonomy_provider_failure_is_expected_signal() -> None:
    # A rate-limited non-Claude key: configured but non-zero exit → signal, non-blocking.
    r = classify_provider_outcome(configured=True, process_exit=2, empty_report=False)
    assert r == CellOutcome.FAIL_EXPECTED


def test_taxonomy_clean_run_passes() -> None:
    assert classify_provider_outcome(configured=True, process_exit=0, empty_report=False) == (
        CellOutcome.PASS
    )
