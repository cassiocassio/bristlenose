"""Round-trip the smoke fixture's events file through the current Pydantic
discriminated union.

Why: the v0.15.4 → v0.15.10 release gap was caused by the events schema
changing on main while ``tests/fixtures/smoke-test/.../pipeline-events.jsonl``
stayed frozen — the server-side mount path silently fell back to the
status page, breaking every E2E against the smoke fixture. This test
catches that class of bug at the cheapest layer: any drift between
``bristlenose/events.py`` and the fixture fails fast in pytest.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from bristlenose.events import (
    RunCancelledEvent,
    RunCompletedEvent,
    RunFailedEvent,
    RunStartedEvent,
)

FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "smoke-test"
    / "input"
    / "bristlenose-output"
    / ".bristlenose"
    / "pipeline-events.jsonl"
)

_EventUnion = RunStartedEvent | RunCompletedEvent | RunCancelledEvent | RunFailedEvent
_adapter: TypeAdapter[_EventUnion] = TypeAdapter(_EventUnion)


def test_smoke_fixture_events_roundtrip() -> None:
    assert FIXTURE.exists(), f"smoke fixture missing: {FIXTURE}"
    lines = [ln for ln in FIXTURE.read_text().splitlines() if ln.strip()]
    assert lines, "smoke fixture pipeline-events.jsonl is empty"
    for i, line in enumerate(lines):
        payload = json.loads(line)
        try:
            _adapter.validate_python(payload)
        except ValidationError as exc:
            pytest.fail(
                f"line {i + 1} of smoke fixture failed schema validation: {exc}",
            )


def test_smoke_fixture_has_terminus_event() -> None:
    """Without a terminus event, ``app.state.last_run`` doesn't populate and
    the SPA mount falls through to the status page — see CLAUDE.md gotcha."""
    lines = [ln for ln in FIXTURE.read_text().splitlines() if ln.strip()]
    terminus_types = {"run_completed", "run_cancelled", "run_failed"}
    assert any(json.loads(ln).get("event") in terminus_types for ln in lines), (
        "smoke fixture has no terminus event; SPA mount will fall through "
        "to the status page and any /report/* test will fail"
    )
