"""The report is reloaded when a RUN finishes, never when the launch-time scan does (5 Nov 2026).

`ContentView.scheduleReportReloadOnCompletion` used to ask "was this study analysing, and is it
settled now?", where "analysing" includes `.scanning`, the passive manifest read the app does at
launch. A restored launch has its study selected while that read is still going, so the read ending
reloaded the report: a second page load that landed after the restored lens was activated, put the
report back on Project, recorded Project as the lens the researcher had left on, and cleared the
remembered Sessions route. Every restored launch paid a duplicate load as well.

The decision is `CompletionRescan.shouldReloadReport` (pure, unit-tested in
`CompletionRescanTests`). This pins the one thing a unit test cannot see: that the call site uses it.
"""

from __future__ import annotations

import re
from pathlib import Path

_DIR = Path(__file__).resolve().parent.parent / "desktop" / "Bristlenose" / "Bristlenose"


def _function_body(text: str, signature: str) -> str:
    start = text.index(signature)
    brace = text.index("{", start)
    depth, i = 0, brace
    while True:
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        i += 1
        if depth == 0:
            return text[start:i]


def test_the_reload_asks_for_a_finished_run_not_an_analysing_state() -> None:
    body = _function_body(
        (_DIR / "ContentView.swift").read_text(encoding="utf-8"),
        "private func scheduleReportReloadOnCompletion(",
    )
    assert "CompletionRescan.shouldReloadReport(" in body
    assert not re.search(r"isAnalysing\(\s*old", body), (
        "the reload gate is back on the broad `isAnalysing`, which counts the launch-time scan"
    )


def test_a_scan_is_not_a_finished_run_in_the_shared_predicate() -> None:
    text = (_DIR / "CompletionRescan.swift").read_text(encoding="utf-8")
    body = _function_body(text, "static func projectsFinishingRun(")
    assert "if case .running = old[id]" in body  # a run starts from .running, never from .scanning
