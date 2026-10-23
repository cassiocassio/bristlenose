"""The Mac app seeds the report's saved preferences into every new web view (R89).

The report keeps zoom, quote grouping and its panels' open state and widths in
localStorage, which the app's `.nonPersistent()` web views lose on every relaunch.
`BridgeHandler` saves each `report-pref` post and builds a document-start script
(`reportPrefsSeedScript`) that puts them back. `ReportPrefsMirrorTests` proves the
save and the script; nothing there can see whether the web view is ever given the
script, and without it every saved value is written and never read. A `WKWebView`
built in `makeNSView` cannot be reached from a test, so this pins the wiring in the
source, as `test_desktop_toast_scope.py` does for the toast store.
"""

from __future__ import annotations

import re
from pathlib import Path

_TARGET = Path(__file__).resolve().parent.parent / "desktop" / "Bristlenose" / "Bristlenose"


def _web_view() -> str:
    return (_TARGET / "WebView.swift").read_text(encoding="utf-8")


def test_the_report_view_is_given_the_seed_at_document_start() -> None:
    src = _web_view()
    wired = re.findall(
        r"userContentController\.addUserScript\(WKUserScript\(\s*"
        r"source:\s*BridgeHandler\.reportPrefsSeedScript\(\),\s*"
        r"injectionTime:\s*\.atDocumentStart,\s*"
        r"forMainFrameOnly:\s*true\s*\)\)",
        src,
    )
    assert len(wired) == 1, "WebView.swift must add reportPrefsSeedScript() as a document-start user script"


def test_the_seed_is_added_where_the_report_view_is_built() -> None:
    # In makeNSView, before the configuration is handed to the view: a script added
    # to a controller after the view exists never runs for the document it loaded.
    src = _web_view()
    make = src.index("func makeNSView(")
    seed = src.index("BridgeHandler.reportPrefsSeedScript()")
    handed = src.index("config.userContentController = userContentController", make)
    assert make < seed < handed
