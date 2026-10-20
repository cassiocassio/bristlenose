"""Every Finder drop in the Mac app takes the sidebar's one route.

A Finder drop is decided in `processDroppedURLs` (`ContentView.swift`): drop
unsupported files, select a folder that is already listed instead of adding it
again, follow a study whose folder has moved. The handlers `handleDrop`,
`handleDropOnFolder` and `handleDropOnProject` are the doors into that logic.

The empty "Drop a folder" pane had its own door. It called
`createProjectFromURLs` directly, so re-dropping a listed folder there made a
second row for the same study and started a second run, and a drop of PDFs
left an empty project behind (R46, 20 Oct 2026). Nothing compared the drop
sites, and the SwiftUI closure that held the shortcut cannot be reached from a
Swift unit test.

This is the comparison. It parses the Swift source, so it fails when a new
drop site skips the handlers, not when someone remembers to check.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SWIFT = REPO / "desktop" / "Bristlenose" / "Bristlenose"
CONTENT_VIEW = SWIFT / "ContentView.swift"

HANDLERS = ("handleDrop(", "handleDropOnFolder(", "handleDropOnProject(")


def _strip_comments(text: str) -> str:
    """Drop `//` line comments (not `://` inside a string) so prose that
    names a function cannot satisfy or trip the checks."""
    return re.sub(r"(^|\s)//.*$", r"\1", text, flags=re.MULTILINE)


def _block_after(text: str, start: int) -> tuple[int, int]:
    """Span of the brace block opening at the first `{` at or after `start`."""
    open_at = text.index("{", start)
    depth = 0
    for i in range(open_at, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return open_at, i + 1
    raise AssertionError("unbalanced braces")


def _url_drop_closures() -> list[tuple[str, int, str]]:
    """Every SwiftUI drop closure that can carry a Finder URL: `URL.self`, and
    `SidebarDrop.self`, whose `.url` case is a Finder item."""
    found = []
    for source in sorted(SWIFT.glob("*.swift")):
        text = _strip_comments(source.read_text(encoding="utf-8"))
        pattern = r"\.dropDestination\(for:\s*(?:URL|SidebarDrop)\.self\)"
        for match in re.finditer(pattern, text):
            begin, end = _block_after(text, match.end())
            line = text.count("\n", 0, match.start()) + 1
            found.append((source.name, line, text[begin:end]))
    return found


def test_finds_the_drop_sites() -> None:
    # The sidebar root, a folder row, a project row, the empty-project pane and
    # the empty "Drop a folder" pane at least: if the pattern stops matching,
    # the checks below pass on nothing.
    sites = _url_drop_closures()
    assert len(sites) >= 5, f"expected the known Finder drop sites, found {sites}"


def test_the_drop_a_folder_pane_is_still_a_drop_site() -> None:
    # The door R46 closed: deleting it would leave every other check green.
    text = _strip_comments(CONTENT_VIEW.read_text(encoding="utf-8"))
    pane = text.index('"desktop.welcome.dropFolderTitle"')
    drop = text.find(".dropDestination(for: URL.self)", pane)
    assert drop != -1 and "noSelectionDropTargeted" in text[drop : drop + 400], (
        "the empty \"Drop a folder\" pane no longer has its Finder drop"
    )


def test_the_appkit_sidebar_routes_every_drop_target_to_a_handler() -> None:
    # The outline is the sidebar the app runs; its Finder drops arrive through
    # `onExternalDrop`, not a `.dropDestination`.
    text = _strip_comments(CONTENT_VIEW.read_text(encoding="utf-8"))
    hook = re.search(r"onExternalDrop:\s*\{", text)
    assert hook, "onExternalDrop not found in ContentView.swift — renamed?"
    begin, end = _block_after(text, hook.start())
    arms = re.findall(r"case\s+\.(\w+)[^:]*:\s*([^\n]*)", text[begin:end])
    assert {name for name, _ in arms} == {"root", "folder", "project"}, arms
    unrouted = [name for name, call in arms if not call.startswith(HANDLERS)]
    assert not unrouted, f"onExternalDrop arms skip the shared handlers: {unrouted}"


def test_every_finder_drop_site_goes_through_a_shared_handler() -> None:
    bypasses = [
        f"{name}:{line}"
        for name, line, body in _url_drop_closures()
        if not any(handler in body for handler in HANDLERS)
    ]
    assert not bypasses, (
        "A `.dropDestination(for: URL.self)` closure skips the shared drop "
        f"handlers ({', '.join(h.rstrip('(') for h in HANDLERS)}), so it "
        "misses the tracked-folder dedupe and the moved-study match: "
        + ", ".join(bypasses)
    )


def test_projects_are_created_from_a_drop_only_after_the_dedupe() -> None:
    text = _strip_comments(CONTENT_VIEW.read_text(encoding="utf-8"))
    decide = re.search(r"func processDroppedURLs\(", text)
    assert decide, "processDroppedURLs not found in ContentView.swift — renamed?"
    begin, end = _block_after(text, decide.end())

    calls = [
        m.start()
        for m in re.finditer(r"(?<!func )\bcreateProjectFromURLs\(", text)
    ]
    assert calls, "createProjectFromURLs not found in ContentView.swift — renamed?"
    outside = [
        text.count("\n", 0, at) + 1 for at in calls if not begin <= at < end
    ]
    assert not outside, (
        "createProjectFromURLs is called outside processDroppedURLs, so that "
        f"drop skips the dedupe (ContentView.swift lines {outside})"
    )
