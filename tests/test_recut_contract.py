"""The review's re-cut rule, one contract for both sides (root CLAUDE.md § Seams).

``tests/fixtures/recut-contract.json`` holds the cases; this reads them against the
server's ``recut_target``, through the same readings the route makes (the job's stored
lines by ``stored_lines``, the new ones by ``RecutRequest``), and
``frontend/src/utils/recut.test.ts`` reads them against the dialog's ``outcomeZone``.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from bristlenose.server.autocode import DEFAULT_ACCEPT_THRESHOLD, DEFAULT_DENY_THRESHOLD
from bristlenose.server.models import AutoCodeJob, ProposedTag
from bristlenose.server.routes.autocode import (
    RecutRequest,
    _stored_lines_or_none,
    recut_target,
)

CONTRACT = json.loads(
    (Path(__file__).parent / "fixtures" / "recut-contract.json").read_text(encoding="utf-8")
)
STATUS_ZONE = {"accepted": "accepted", "pending": "tentative", "denied": "excluded"}


def test_the_contracts_defaults_are_the_servers() -> None:
    assert CONTRACT["defaults"] == {
        "lower": DEFAULT_DENY_THRESHOLD, "upper": DEFAULT_ACCEPT_THRESHOLD,
    }


@pytest.mark.parametrize("case", CONTRACT["cases"], ids=lambda c: c["name"])
def test_recut_target_follows_the_contract(case: dict[str, Any]) -> None:
    stored = case["stored"] or [None, None]
    job = SimpleNamespace(applied_lower_threshold=stored[0], applied_upper_threshold=stored[1])
    before = _stored_lines_or_none(cast(AutoCodeJob, job))
    lines = RecutRequest(lower=case["lines"][0], upper=case["lines"][1])
    proposal = SimpleNamespace(
        status=case["status"], decided_by=case["decided_by"], confidence=case["confidence"],
    )
    target = recut_target(cast(ProposedTag, proposal), before, lines.lower, lines.upper)
    assert (target or STATUS_ZONE[case["status"]]) == case["expected"]
