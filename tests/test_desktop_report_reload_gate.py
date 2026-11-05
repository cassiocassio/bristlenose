"""The report reloads when a RUN finishes, never when the launch-time scan does (5 Nov 2026).

The decision is `CompletionRescan.shouldReloadReport`, unit-tested in `CompletionRescanTests`.
This pins what a unit test cannot see: that the call site in `ContentView` uses it.
"""

from __future__ import annotations

from pathlib import Path

_CONTENT_VIEW = (
    Path(__file__).resolve().parent.parent
    / "desktop" / "Bristlenose" / "Bristlenose" / "ContentView.swift"
)


def test_the_reload_asks_for_a_finished_run_not_an_analysing_state() -> None:
    text = _CONTENT_VIEW.read_text(encoding="utf-8")
    start = text.index("private func scheduleReportReloadOnCompletion(")
    assert "CompletionRescan.shouldReloadReport(" in text[start : start + 3000]
