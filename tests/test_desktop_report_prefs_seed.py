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
    # Every document-start script comes from one builder, `reportUserScripts` (whose output
    # `SidebarAutoCodeCapabilityTests` reads); the seed must be one of them, and makeNSView must
    # add each of them at document start.
    src = _web_view()
    builder = src[src.index("static func reportUserScripts(") : src.index("func makeCoordinator(")]
    assert builder.count("scripts.append(BridgeHandler.reportPrefsSeedScript(defaults: defaults))") == 1
    wired = re.findall(
        r"for source in Self\.reportUserScripts\(authToken: authToken\) \{\s*"
        r"userContentController\.addUserScript\(WKUserScript\(\s*"
        r"source:\s*source,\s*"
        r"injectionTime:\s*\.atDocumentStart,\s*"
        r"forMainFrameOnly:\s*true\s*\)\)",
        src,
    )
    assert len(wired) == 1, "makeNSView must add every reportUserScripts() source at document start"


def test_the_seed_is_added_where_the_report_view_is_built() -> None:
    # In makeNSView, before the configuration is handed to the view: a script added
    # to a controller after the view exists never runs for the document it loaded.
    src = _web_view()
    make = src.index("func makeNSView(")
    seed = src.index("Self.reportUserScripts(authToken: authToken)", make)
    handed = src.index("config.userContentController = userContentController", make)
    assert make < seed < handed
