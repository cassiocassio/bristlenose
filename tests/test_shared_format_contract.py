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


def test_documented_divergences_are_still_real() -> None:
    """A `divergent` entry that has quietly become aligned is a stale catalogue.

    This does NOT assert that the divergence is correct — it asserts that the
    register still describes reality. When you close one of these gaps the
    assertion below fires, which is the reminder to promote the entry to
    `aligned` rather than leave a fixed format filed as broken.
    """
    from bristlenose.models import format_timecode as tc_models
    from bristlenose.server.export_core import _format_timecode as tc_export
    from bristlenose.utils.timecodes import format_timecode as tc_utils

    spec = _formats()["timecode"]
    if spec.get("status") != "divergent":
        return  # already promoted; the aligned path covers it

    inputs = spec["observed"]["_inputs"]
    padded = [tc_utils(i) for i in inputs]
    assert padded == [tc_models(i) for i in inputs], (
        "the two shared-library Python timecode helpers have drifted from each "
        "other — that is a new gap, not the one on file"
    )
    assert padded != [tc_export(i) for i in inputs], (
        "Python timecode implementations now agree. Promote the `timecode` entry "
        f"in {CONTRACT.name} to `aligned`, register its implementation in "
        "_python_impl, and give it `cases`."
    )


def test_observed_values_in_the_register_are_accurate() -> None:
    """The catalogued Python outputs are measured, not typed from memory."""
    from bristlenose.models import format_timecode as tc_models
    from bristlenose.server.export_core import _format_timecode as tc_export
    from bristlenose.server.mcp_server import _format_timecode as tc_mcp
    from bristlenose.utils.markdown import format_finder_filename
    from bristlenose.utils.timecodes import format_timecode as tc_utils

    tc = _formats()["timecode"]["observed"]
    inputs = tc["_inputs"]
    for key, impl in (
        ("bristlenose/utils/timecodes.py::format_timecode", tc_utils),
        ("bristlenose/models.py::format_timecode", tc_models),
        ("bristlenose/server/export_core.py::_format_timecode", tc_export),
        ("bristlenose/server/mcp_server.py::_format_timecode", tc_mcp),
    ):
        assert [impl(i) for i in inputs] == tc[key], (
            f"{key} no longer renders what the register says it does — "
            f"update the `observed` block in {CONTRACT.name}"
        )

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
