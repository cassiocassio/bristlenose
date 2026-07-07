"""Shape-only acceptance invariants — assert structure, never LLM content.

Built from the 2026-07-07 review of docs/testing/acceptance-matrix.md. The whole
point of the acceptance tier is to catch *fake success*, so the guards must not
themselves false-green. Eight review findings were one bug — *grep-for-absence /
read-a-field passes vacuously over an empty / errored / None artifact* — so the
core here is a single discipline applied everywhere:

  1. **size floor** before any absence check (an empty export trivially "has no PII");
  2. **positive control** for every absence assertion (prove the thing you claim is
     gone was actually THERE to begin with);
  3. **fail-closed on None / missing** (a field we cannot read is a FAIL, not a pass).

Every helper raises `InvariantError` on failure; callers turn that into a FAIL row.
These are unit-tested in tests/test_acceptance_invariants.py — the guards are proven
to bite before they guard anything.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class InvariantError(AssertionError):
    """A shape invariant was violated (or could not be confirmed — fail-closed)."""


# ---------------------------------------------------------------------------
# Core discipline: size floor + fail-closed reads
# ---------------------------------------------------------------------------


def assert_nonempty_file(path: Path, floor_bytes: int = 1) -> None:
    """An artifact must exist and clear a size floor before any content check.

    Guards the #1 false-green: a grep-for-absence over an empty or 50-byte-error
    artifact passes trivially. Fail-closed: a missing file is a FAIL.
    """
    if not path.exists():
        raise InvariantError(f"artifact absent (fail-closed): {path}")
    size = path.stat().st_size
    if size < floor_bytes:
        raise InvariantError(f"artifact below size floor ({size} < {floor_bytes} bytes): {path}")


def assert_absent_over_decoded(needle: str, decoded_text: str, *, source_had_it: str) -> None:
    """Assert `needle` is absent from `decoded_text`, WITH a positive control.

    `source_had_it` is the original (pre-export) text that MUST contain `needle` —
    otherwise the absence assertion is measuring nothing (you can "prove" any string
    absent from a blank file). Both halves, or it is not a check.

    Operate on the *decoded* payload: exports embed JSON with ensure_ascii=True, so a
    non-ASCII name (José → Jos\\u00e9) is present-but-escaped and a raw byte-grep
    false-negatives — precisely where anonymisation matters most.
    """
    if needle not in source_had_it:
        raise InvariantError(
            f"positive control failed: {needle!r} was not in the source, so its "
            f"absence from the export proves nothing"
        )
    if needle in decoded_text:
        raise InvariantError(f"leak: {needle!r} crossed into the export")


# ---------------------------------------------------------------------------
# Pipeline terminus + non-emptiness (the durable signals; NOT the disk HTML,
# which is coupled to the static render being removed — F18)
# ---------------------------------------------------------------------------


def _events_path(output_dir: Path) -> Path:
    return output_dir / ".bristlenose" / "pipeline-events.jsonl"


def read_terminus_event(output_dir: Path) -> dict:
    """Return the last pipeline event, fail-closed. Absent/empty file = FAIL."""
    path = _events_path(output_dir)
    if not path.exists():
        raise InvariantError(f"no pipeline-events.jsonl (fail-closed): {path}")
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if not lines:
        raise InvariantError(f"pipeline-events.jsonl empty (fail-closed): {path}")
    return json.loads(lines[-1])


def assert_terminus_completed(output_dir: Path) -> dict:
    """The run's terminus must be a completed run, not failed/cancelled/absent."""
    event = read_terminus_event(output_dir)
    name = event.get("event")
    outcome = event.get("outcome")
    if name != "run_completed":
        raise InvariantError(f"terminus is {name!r}, not run_completed (outcome={outcome!r})")
    if outcome not in (None, "completed"):
        raise InvariantError(f"run_completed but outcome={outcome!r}")
    return event


def assert_no_abandoned_stage(terminus_event: dict) -> None:
    """Catch the gemma4 class: a stage where attempted>0 but succeeded==0.

    Secondary to the terminus check. `summary` is legitimately None on some completed
    runs (the smoke fixture is one) — the terminus already vouched success there, so
    an absent summary is NOT failed-closed here (that would reject valid runs). But a
    summary that IS present and shows a fully-failed stage is a blocking FAIL, even if
    the process exited 0.
    """
    summary = terminus_event.get("summary")
    if summary is None:
        return  # terminus vouched; no per-stage data to contradict it
    stages = summary.get("stages", summary) if isinstance(summary, dict) else {}
    for name, s in (stages.items() if isinstance(stages, dict) else []):
        if not isinstance(s, dict):
            continue
        attempted = s.get("attempted")
        succeeded = s.get("succeeded")
        if attempted and succeeded == 0:
            raise InvariantError(f"stage {name!r} fully failed (attempted={attempted}, succeeded=0)")


def count_quotes(output_dir: Path) -> int:
    """Total quotes placed in screen clusters (the durable intermediate JSON)."""
    path = output_dir / ".bristlenose" / "intermediate" / "screen_clusters.json"
    assert_nonempty_file(path, floor_bytes=2)  # "[]" is 2 bytes; real content is more
    clusters = json.loads(path.read_text(encoding="utf-8"))
    return sum(len(c.get("quotes", [])) for c in clusters)


def assert_report_non_empty(output_dir: Path, *, quote_floor: int) -> None:
    """A completed run must have placed quotes SOMEWHERE.

    F8: `themes >= 1` alone is vacuous — a small fixture can legitimately have zero
    theme_groups (all quotes classified SCREEN_SPECIFIC → s11 empty). The real "quotes
    got placed" invariant is `screen_clusters >= 1 OR theme_groups >= 1`, plus a pinned
    per-fixture quote floor.
    """
    inter = output_dir / ".bristlenose" / "intermediate"
    screen = json.loads((inter / "screen_clusters.json").read_text(encoding="utf-8"))
    themes_path = inter / "theme_groups.json"
    themes = json.loads(themes_path.read_text(encoding="utf-8")) if themes_path.exists() else []
    if len(screen) < 1 and len(themes) < 1:
        raise InvariantError("no screen clusters AND no theme groups — quotes went nowhere")
    n = count_quotes(output_dir)
    if n < quote_floor:
        raise InvariantError(f"quotes below floor ({n} < {quote_floor})")


# ---------------------------------------------------------------------------
# Governance: re-identification keys must never reach the shareable root
# ---------------------------------------------------------------------------

_REID_KEYS = ("pii_summary.txt", "llm-calls.jsonl")


def assert_reid_keys_not_shareable(output_dir: Path) -> None:
    """pii_summary.txt + llm-calls.jsonl live in .bristlenose/ only — never in the
    shareable output root, and (checked elsewhere) never in an export."""
    for name in _REID_KEYS:
        stray = output_dir / name
        if stray.exists():
            raise InvariantError(f"re-identification key in shareable root: {stray}")


# ---------------------------------------------------------------------------
# Provider-state taxonomy (F7) — reconciles "non-Claude failure = signal, not
# regression" with "provider failure is fail-stop"
# ---------------------------------------------------------------------------


class CellOutcome(str, Enum):
    PASS = "PASS"
    SKIP = "SKIP"  # declared, counted — a prerequisite (key/model) was absent
    FAIL_EXPECTED = "FAIL_EXPECTED"  # configured provider failed; signal, non-blocking
    FAIL_BLOCKING = "FAIL_BLOCKING"  # empty report / shape breach / crash — the real bug
    ERROR = "ERROR"  # undeclared skip: a promised fixture/cell did not run at all


@dataclass
class CellResult:
    cell_id: str
    outcome: CellOutcome
    detail: str = ""

    @property
    def is_green(self) -> bool:
        # A declared skip and an expected non-Claude failure are both "green" for the
        # grid's overall verdict; only blocking failures and undeclared errors are red.
        return self.outcome in (CellOutcome.PASS, CellOutcome.SKIP, CellOutcome.FAIL_EXPECTED)


def classify_provider_outcome(
    *,
    configured: bool,
    process_exit: int | None,
    empty_report: bool,
) -> CellOutcome:
    """Map a provider cell's raw result onto the taxonomy.

    - not configured                       -> SKIP (declared, counted)
    - configured, ran, empty report        -> FAIL_BLOCKING (the gemma4 class)
    - configured, non-zero exit            -> FAIL_EXPECTED (signal, non-blocking)
    - configured, clean                    -> PASS
    """
    if not configured:
        return CellOutcome.SKIP
    if empty_report:
        return CellOutcome.FAIL_BLOCKING
    if process_exit not in (0, None):
        return CellOutcome.FAIL_EXPECTED
    return CellOutcome.PASS
