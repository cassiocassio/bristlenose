"""The Mac app's feedback sheet opens once, in the window that asked (R82), and can
always be dismissed with Esc (R81).

R82. The status page's "Send feedback" (`project-action: open-feedback`) posted the
app-wide `.showFeedbackSheet`, and every window's `ContentView` answered it, so one
request opened a sheet in every open window. With no project window open at all, the
menu's fallback broadcast reached nobody and nothing opened. It is the shape
desktop/CLAUDE.md names "a per-window callback hung off an app-wide channel", the same
one R90 fixed for toasts (`tests/test_desktop_toast_scope.py`).

Now:

- the status page bumps its own window's `BridgeHandler.feedbackRequests`, which only
  that window observes (the `chooseGuideRequests` idiom);
- the one remaining broadcast is the menu's fallback, `BridgeHandler.openFeedback()`,
  used only with no project window in front, and it stages a one-shot
  `FeedbackFallback` first, so exactly one window takes it; when none does, the menu
  opens a window, which takes it as it appears.

R81. While the sheet waited on `/api/health` it showed only a spinner: the Cancel button
(and with it Esc, its `.cancelAction` shortcut) lived inside the form, which is not drawn
until the probe answers, up to URLSession's 60 s. The button row is now drawn in every
phase.

SwiftUI's per-window `@State` cannot be reached from a test, so this pins the shape in
the source, as `check-menu-routing.sh` does for the menu bar. The one-shot itself is
tested in Swift (`WindowCommandTests`).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

_DESKTOP = Path(__file__).resolve().parent.parent / "desktop"
_TARGET = _DESKTOP / "Bristlenose" / "Bristlenose"


def _sources() -> dict[str, str]:
    files = {p.name: p.read_text(encoding="utf-8") for p in _TARGET.glob("*.swift")}
    for name in ("ContentView.swift", "BridgeHandler.swift", "FeedbackSheet.swift"):
        assert name in files, (_TARGET, name)
    return files


def _block_after(text: str, anchor: str) -> str:
    """The brace-balanced block that opens at the first `{` after `anchor`."""
    start = text.index(anchor)
    open_at = text.index("{", start)
    depth = 0
    for i in range(open_at, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[open_at : i + 1]
    raise AssertionError(f"unbalanced block after {anchor!r}")


def _case_body(text: str, label: str) -> str:
    """A `case "label":` arm, up to the next `case`/`default` of the same switch."""
    start = text.index(f'case "{label}":')
    rest = text[start + len(label) + 8 :]
    end = re.search(r'^\s*(case "|default:)', rest, flags=re.M)
    return rest[: end.start()] if end else rest


def test_the_status_page_asks_its_own_window_not_every_window() -> None:
    arm = _case_body(_sources()["BridgeHandler.swift"], "open-feedback")
    assert "NotificationCenter" not in arm, "the status page's request must not broadcast"
    assert "requestFeedback(mode: mode)" in arm


def _doors() -> str:
    """`FeedbackDoors`, the modifier that holds the doors arriving from outside the view."""
    return _block_after(_sources()["ContentView.swift"], "struct FeedbackDoors: ViewModifier")


def test_each_window_wires_its_own_doors() -> None:
    view = _sources()["ContentView.swift"]
    start = view.index(".modifier(FeedbackDoors(")
    wiring = view[start : view.index("))", start)]
    assert "isShowing: $showingFeedbackSheet" in wiring
    assert "feedbackRequests: bridgeHandler.feedbackRequests" in wiring


def test_the_boot_pane_opens_its_own_windows_sheet() -> None:
    # N08: after a failed retry the boot pane offers Send Feedback…, which sets
    # this window's flag, the sidebar ladybug's door, never a broadcast.
    view = _sources()["ContentView.swift"]
    start = view.index("BootView(phase: .failed(")
    call = view[start : view.index("project: project.id)", start)]
    assert "showingFeedbackSheet = true" in call
    assert "NotificationCenter" not in call
    assert "isRetry: true" in call
    # ...as a problem report, set before the sheet opens, from the pane's own
    # sentence and never the engine output (`BootView.problemReportMessage`).
    assert ".problem(initialMessage:" in call
    assert call.index(".problem(initialMessage:") < call.index("showingFeedbackSheet = true")
    assert "BootView.problemReportMessage(" in call
    assert "outputLines" not in call


def test_a_problem_sheet_does_not_outlive_its_door() -> None:
    # The journey lasts one opening: dismissal puts it back to feedback, and the
    # feedback doors never set it, so the ladybug can't open a problem report.
    view = _sources()["ContentView.swift"]
    assert ".sheet(isPresented: $showingFeedbackSheet, onDismiss: resetFeedbackSheetMode)" in view
    reset = _block_after(view, "private func resetFeedbackSheetMode()")
    assert "feedbackSheetMode = .feedback" in reset
    assert view.count("feedbackSheetMode = .problem(") == 1


def test_the_window_whose_page_asked_presents_the_sheet() -> None:
    handler = _block_after(_doors(), ".onChange(of: feedbackRequests)")
    assert "isShowing = true" in handler
    # ...in the journey the page asked for, set before it opens.
    assert "mode = requestedMode" in handler
    assert handler.index("mode = requestedMode") < handler.index("isShowing = true")


def test_the_report_crash_door_asks_for_a_problem_report() -> None:
    # The crash pane posts `open-feedback` with `{kind: "problem", message}`;
    # the bridge turns that into a mode and records it before the counter moves,
    # and the window passes it to its doors. The status page posts no data.
    bridge = _sources()["BridgeHandler.swift"]
    arm = _case_body(bridge, "open-feedback")
    assert "FeedbackSheetMode.fromBridge(data)" in arm
    assert "requestFeedback(mode: mode)" in arm
    request = _block_after(bridge, "func requestFeedback(mode:")
    assert request.index("requestedFeedbackMode = mode") < request.index("feedbackRequests += 1")
    view = _sources()["ContentView.swift"]
    assert "requestedMode: bridgeHandler.requestedFeedbackMode" in view
    assert "mode: $feedbackSheetMode" in view


def test_the_only_broadcast_is_the_menu_fallback_and_it_stages_one_shot() -> None:
    posters = [
        name
        for name, text in _sources().items()
        if re.search(r"post\(\s*name:\s*\.showFeedbackSheet", text)
    ]
    assert posters == ["BridgeHandler.swift"], posters
    bridge = _sources()["BridgeHandler.swift"]
    assert len(re.findall(r"post\(\s*name:\s*\.showFeedbackSheet", bridge)) == 1
    fallback = _block_after(bridge, "func openFeedback()")
    assert "FeedbackFallback.request()" in fallback
    assert fallback.index("FeedbackFallback.request()") < fallback.index(".showFeedbackSheet")
    # The menu opens a window only when nobody took it, so the answer must be read.
    assert "return !FeedbackFallback.isPending" in fallback


def test_a_window_takes_the_broadcast_only_by_claiming_it() -> None:
    receivers = [
        name for name, text in _sources().items() if "publisher(for: .showFeedbackSheet)" in text
    ]
    assert receivers == ["ContentView.swift"], receivers
    receiver = _block_after(_doors(), "publisher(for: .showFeedbackSheet)")
    assert "FeedbackFallback.claim()" in receiver
    assert receiver.index("FeedbackFallback.claim()") < receiver.index("isShowing = true")


def test_a_window_opened_for_feedback_takes_it_on_appear() -> None:
    # The no-project-window case: the menu opens a window, and that window, not a
    # later one, takes the staged request.
    on_appear = _block_after(_doors(), ".onAppear")
    assert re.search(r"if FeedbackFallback\.claim\(\) \{[^}]*isShowing = true", on_appear)
    menu = _sources()["MenuCommands.swift"]
    help_button = _block_after(menu, 'Button(i18n.t("desktop.menu.help.sendFeedback"))')
    assert 'openWindow(id: "main")' in help_button
    assert "windowCommands.perform(.showFeedback)" in help_button
    # A popout player in front: the report window that owns it, not a broadcast.
    # `.unattached` is observed by no window, so asking it would open nothing.
    assert "} else if bridgeHandler !== BridgeHandler.unattached {" in help_button
    assert "} else if !bridgeHandler.openFeedback() {" in help_button
    assert help_button.index("bridgeHandler.requestFeedback()") < help_button.index(
        "bridgeHandler.openFeedback()"
    )


def test_cancel_and_esc_are_there_while_the_sheet_loads() -> None:
    sheet = _sources()["FeedbackSheet.swift"]
    form = _block_after(sheet, "private var form: some View")
    assert ".cancelAction" not in form, "Cancel inside the form is not drawn during loading"
    buttons = _block_after(sheet, "private var buttons: some View")
    assert ".keyboardShortcut(.cancelAction)" in buttons
    body = _block_after(sheet, "struct FeedbackSheet: View")
    body = _block_after(body, "var body: some View")
    loading = _block_after(body, "if model.phase == .loading")
    # `buttons` is drawn by the body itself, outside the loading/form branch.
    assert re.search(r"^\s*buttons\s*$", body, flags=re.M)
    assert "buttons" not in loading


def test_cancel_stops_a_send_in_flight() -> None:
    # Cancel (and Esc with it) left the send running: a failure then wrote the
    # clipboard and toasted "copied", and in the expired-alpha flow a success
    # routed to "Thanks", after the person had cancelled. The model owns the
    # send so Cancel can stop it (`FeedbackSheetModelTests` pins the model);
    # this pins the sheet's wiring to it.
    sheet = _sources()["FeedbackSheet.swift"]
    buttons = _block_after(sheet, "private var buttons: some View")
    cancel = buttons[buttons.index("Button(model.cancelLabel)") : buttons.index(".cancelAction")]
    assert "model.cancelSend()" in cancel
    assert cancel.index("model.cancelSend()") < cancel.index("dismiss()")
    assert "model.startSend(then: deliver)" in buttons
    # An unstructured send the sheet cannot reach is the bug's shape.
    assert "Task {" not in buttons
    body = _block_after(_block_after(sheet, "struct FeedbackSheet: View"), "var body: some View")
    assert re.search(r"\.onDisappear \{ model\.cancelSend\(\) \}", body)


def test_the_sheet_is_one_view_whatever_the_serve_does() -> None:
    # It was `if let port { FeedbackSheet(port:) } else { FeedbackSheet(config:) }`,
    # so a serve starting or stopping mid-send swapped the view, and the old one's
    # `.onDisappear` cancelled a send the person never cancelled.
    view = _sources()["ContentView.swift"]
    sheet = _block_after(
        view, ".sheet(isPresented: $showingFeedbackSheet, onDismiss: resetFeedbackSheetMode)"
    )
    assert sheet.count("FeedbackSheet(") == 1, sheet
    assert "FeedbackSheet(port: serveManager?.runningPort" in sheet
    assert "mode: feedbackSheetMode" in sheet
    assert not re.search(r"\bif\b|\?\s*FeedbackSheet|\bswitch\b", sheet), sheet


# Build output, caches and bundles: generated, never edited, and gigabytes of it.
# The bundled sidecar is gitignored and absent on CI, so scanning it would make the
# walk's reach depend on the machine.
_SKIP_DIRS = {
    "build",
    "DerivedData",
    ".build",
    "node_modules",
    "__pycache__",
    ".git",
    "bristlenose-sidecar",
}
_SOURCE_SUFFIXES = {
    ".swift",
    ".m",
    ".h",
    ".md",
    ".sh",
    ".js",
    ".mjs",
    ".json",
    ".py",
    ".plist",
    ".entitlements",
    ".xcconfig",
    ".strings",
    ".xcstrings",
    ".pbxproj",
    ".spec",
    ".txt",
}


def test_the_feedback_trace_diagnostic_is_gone() -> None:
    # `FeedbackTrace` (15a80c71) logged every door into the sheet and drew the
    # trigger chain in an English-only caption on the sheet itself, to chase the
    # sheet that opened in every window. R82 fixed that (178b7dce) and the trace
    # was removed (21 Oct 2026). It was marked "remove before release" and had to be
    # parked off the tree for the 0.42.0 run, so this keeps it out for good.
    scanned = 0
    found = []
    for directory, dirs, files in os.walk(_DESKTOP):
        dirs[:] = [
            d
            for d in dirs
            if d not in _SKIP_DIRS and not d.endswith((".xcresult", ".app", ".xcarchive"))
        ]
        for name in files:
            path = Path(directory, name)
            if path.suffix not in _SOURCE_SUFFIXES:
                continue
            scanned += 1
            if "FeedbackTrace" in path.read_text(encoding="utf-8", errors="replace"):
                found.append(str(path.relative_to(_DESKTOP)))
    # A walk that reached nothing would pass vacuously.
    assert scanned > 100 and "FeedbackSheet.swift" in {p.name for p in _TARGET.iterdir()}
    assert found == [], found
