"""Python side of the cross-language RENDER contract.

`tests/fixtures/shared-format-contract.json` catalogues the formats that must
look identical wherever a user meets them, across Python, TypeScript and Swift.
`frontend/src/utils/sharedFormatContract.test.ts` reads the same file and makes
the same assertions against the TypeScript implementations.

Sibling of `test_swift_contract_parity.py` / `pipeline-summary-contract.json`,
which do this for *parsed* contracts. The distinction is the whole point and is
written up in `docs/design-shared-formats.md`: a parsed mismatch breaks
function, a rendered mismatch is a visible inconsistency. Both are worth
catching; only the second class is what this file covers.

**This file asserts `aligned` entries only.** `divergent` entries in the fixture
record measured reality so the gap is countable — they are documentation, not
expectations, and nothing here treats their observed values as correct. The one
check they do get is that they are still divergent: if you fix one, the test
below fails and tells you to promote it. That is the intended workflow, not an
obstacle to it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

CONTRACT = Path(__file__).resolve().parent / "fixtures" / "shared-format-contract.json"


def _contract() -> dict[str, Any]:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def _formats() -> dict[str, Any]:
    return _contract()["formats"]


# The Python implementation for each *aligned* format. A format cannot be
# marked aligned without an entry here — see the enrolment test at the bottom.
def _python_impl(name: str):
    if name == "duration_human":
        from bristlenose.server.routes.dashboard import _format_duration_human

        return _format_duration_human
    if name == "timecode":
        from bristlenose.utils.timecodes import format_timecode

        return format_timecode
    return None


# ── The aligned set — the actual pins ────────────────────────────────────


def _aligned_cases() -> list[tuple[str, float, str]]:
    out: list[tuple[str, float, str]] = []
    for name, spec in _formats().items():
        if spec.get("status") != "aligned":
            continue
        for seconds, expected in spec.get("cases") or []:
            out.append((name, seconds, expected))
    return out


@pytest.mark.parametrize(("fmt", "seconds", "expected"), _aligned_cases())
def test_aligned_format_matches_contract(fmt: str, seconds: float, expected: str) -> None:
    """Every case in an aligned entry holds on the Python side."""
    impl = _python_impl(fmt)
    assert impl is not None, f"no Python implementation registered for aligned format {fmt!r}"
    assert impl(seconds) == expected, (
        f"{fmt}({seconds}) drifted from the shared contract. "
        f"If this change is intended, update {CONTRACT.name} and the TypeScript "
        f"and Swift implementations in the SAME commit."
    )


def test_aligned_formats_have_cases_and_an_implementation() -> None:
    """An aligned entry with no cases would pass vacuously and pin nothing."""
    for name, spec in _formats().items():
        if spec.get("status") != "aligned":
            continue
        assert spec.get("cases"), f"aligned format {name!r} has no cases — it pins nothing"
        assert _python_impl(name) is not None, (
            f"aligned format {name!r} has no Python implementation registered in "
            f"_python_impl — either register it or mark the entry aligned-by-pair"
        )


# ── The divergent set — catalogue accuracy, not enforcement ──────────────


def test_timecode_has_exactly_one_python_implementation() -> None:
    """The nine-implementation sprawl closed on 22 Aug 2026 — keep it closed.

    `models.format_timecode` is a re-export and the two server modules import
    the canonical helper, so all four names must be the *same object*. A future
    copy-paste would make one of them a distinct function and fail here, which
    is the failure mode the register exists to prevent (8 of the original 9
    were copy-paste twins of a helper that already existed in the same
    language).
    """
    from bristlenose.models import format_timecode as m
    from bristlenose.server.export_core import format_timecode as e
    from bristlenose.server.mcp_server import format_timecode as c
    from bristlenose.utils.timecodes import format_timecode as u

    assert u is m is e is c, (
        "a second Python timecode implementation has appeared — import "
        "bristlenose.utils.timecodes.format_timecode rather than writing a local copy"
    )


def test_observed_values_in_the_register_are_accurate() -> None:
    """The catalogued Python outputs are measured, not typed from memory."""
    from bristlenose.utils.markdown import format_finder_filename

    fn = _formats()["finder_filename"]["observed"]
    key = "bristlenose/utils/markdown.py::format_finder_filename"
    assert [format_finder_filename(n) for n in fn["_inputs"]] == fn[key], (
        f"{key} no longer renders what the register says it does — "
        f"update the `observed` block in {CONTRACT.name}"
    )


# ── Register hygiene ─────────────────────────────────────────────────────


def test_every_format_has_a_known_status() -> None:
    known = {"aligned", "aligned-by-pair", "divergent", "deliberately-forked"}
    for name, spec in _formats().items():
        assert spec.get("status") in known, (
            f"format {name!r} has status {spec.get('status')!r}; expected one of {sorted(known)}"
        )
        assert spec.get("datum"), f"format {name!r} does not say what value it renders"
