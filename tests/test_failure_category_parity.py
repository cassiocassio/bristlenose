"""Failure category vocabulary: one list, read from every language that holds it.

`CauseCategoryEnum` (`bristlenose/events.py`) is the source. The Mac decodes it
twice — `CauseCategory` for the events log and `PipelineFailureCategory` for the
row and popover — and an unrecognised raw value decodes as `.unknown`, so a
category added only in Python ships green and the row reads "Run failed". The
test this replaces compared the Python enum with a literal typed into the test
and read no Swift, which is how the popover design doc came to record that drift
twice (`docs/design-pipeline-diagnostic-popover.md`).

Each assertion reads the other language's source, as
`tests/test_pipeline_failure_keys.py` does. Every deliberate difference is a
named set with its reason; widening one is a decision, not a fix.
"""

from __future__ import annotations

import re
from pathlib import Path

from bristlenose.events import CauseCategoryEnum
from bristlenose.llm.failure_classifier import LLMFailureKind
from bristlenose.run_lifecycle import _LLM_KIND_TO_CAUSE
from bristlenose.server.status_page import _FAILURE_LEAF

_ROOT = Path(__file__).resolve().parents[1]
_APP = _ROOT / "desktop" / "Bristlenose" / "Bristlenose"
_SUMMARY = _APP / "PipelineSummary.swift"
_RUNNER = _APP / "PipelineRunner.swift"
_AUTOCODE_TS = _ROOT / "frontend" / "src" / "utils" / "autocodeFailure.ts"

_PYTHON = {c.value for c in CauseCategoryEnum}

# In the events log, but never a run's category on the Mac row.
_NOT_A_RUN_CATEGORY_ON_THE_MAC = {
    "cloud_fetch",  # read per recording from `CauseCategory`, in the popover's file rows
    "deferred",  # per-session wait for Whisper, read from `CauseCategory`; not a failure
}
# Mac-only: the Mac decides these before or outside a Python run's lifecycle.
_MAC_ONLY = {
    "output_exists",  # the CLI's refusal to overwrite output, read from its exit
    "provider_not_set_up",  # no usable provider; refused before the run opens
}
# Cause categories the status page has no sentence for, on purpose.
_STATUS_PAGE_WITHOUT_SENTENCE = {
    "model_unavailable",  # its sentence sends the researcher to a Mac Settings place
    "user_signal",  # a cancelled run returns before any sentence is looked up
    "unusable_input",  # per-file `StageFailure` only, never a terminus cause
    "cloud_fetch",  # no `desktop.pipeline.failure` sentence; the page shows the cause's message
    "deferred",  # per-session, never a terminus cause; no sentence exists
}


def _swift_raw_values(path: Path, enum: str) -> set[str]:
    """The raw values of a top-level `enum <name>: String`, case by case.

    A bare `case foo` has the raw value `foo`; `case foo = "bar"` has `bar`.
    Switch arms (`case .foo:`) never match, so the body's methods are safe.
    """
    src = path.read_text(encoding="utf-8")
    m = re.search(rf"^enum {enum}: String\b[^{{]*\{{(.*?)^\}}", src, re.DOTALL | re.MULTILINE)
    assert m, f"enum {enum} not found in {path.name} — did it move or get renamed?"
    values: set[str] = set()
    for line in re.findall(r"^\s*case ([^.\n][^\n]*)$", m.group(1), re.MULTILINE):
        for item in line.split(","):
            item_m = re.fullmatch(r'\s*(\w+)\s*(?:=\s*"([^"]+)")?\s*', item)
            assert item_m, f"unparsed case in {enum}: {line!r}"
            values.add(item_m.group(2) or item_m.group(1))
    assert values, f"enum {enum} has no cases"
    return values


def _autocode_failure_keys() -> set[str]:
    src = _AUTOCODE_TS.read_text(encoding="utf-8")
    m = re.search(r"const FAILURES: Record<string, Failure> = \{(.*?)\n\};", src, re.DOTALL)
    assert m, "FAILURES not found in autocodeFailure.ts"
    keys = set(re.findall(r"^  (\w+): \{", m.group(1), re.MULTILINE))
    assert keys, "FAILURES has no entries"
    return keys


def test_swift_cause_category_equals_python() -> None:
    assert _swift_raw_values(_SUMMARY, "CauseCategory") == _PYTHON


def test_swift_pipeline_failure_category_equals_python_with_named_differences() -> None:
    assert _NOT_A_RUN_CATEGORY_ON_THE_MAC <= _PYTHON, "an exclusion names no Python category"
    assert not _MAC_ONLY & _PYTHON, "a Mac-only case now exists in Python too"
    expected = (_PYTHON - _NOT_A_RUN_CATEGORY_ON_THE_MAC) | _MAC_ONLY
    assert _swift_raw_values(_RUNNER, "PipelineFailureCategory") == expected


def test_status_page_has_a_sentence_for_every_category_but_the_named_ones() -> None:
    assert _STATUS_PAGE_WITHOUT_SENTENCE <= _PYTHON, "an exclusion names no Python category"
    assert set(_FAILURE_LEAF) == _PYTHON - _STATUS_PAGE_WITHOUT_SENTENCE


def test_every_llm_failure_kind_maps_to_a_cause() -> None:
    # UNKNOWN falls through to the transport and text rules after the table.
    assert set(_LLM_KIND_TO_CAUSE) == set(LLMFailureKind) - {LLMFailureKind.UNKNOWN}


def test_autocode_failures_cover_every_llm_failure_kind() -> None:
    assert _autocode_failure_keys() == {k.value for k in LLMFailureKind}
