"""A Mac app toast is drawn in the window whose action raised it (R90).

There was one `ToastStore` for the whole app (`BristlenoseApp.swift`), injected into every
window and drawn by an overlay on every window, so a drop refused in one window put its
toast in all of them. Every `toast.show` is a per-window act (a drop, a copy, the feedback
sheet), so each window owns its store and draws only that one. It is the shape
desktop/CLAUDE.md names "a per-window callback hung off an app-wide channel".

SwiftUI's `@StateObject` storage cannot be reached from a test, so this pins the shape in the
source, as `desktop/scripts/check-menu-routing.sh` does for the menu bar:

- the `App` makes no `ToastStore` and hands none out;
- every `ToastStore()` is a view's own `@StateObject` (one per window), drawn by its own overlay;
- nothing takes one from the environment except `ToastOverlay`, which its owner hands it.
"""

from __future__ import annotations

import re
from pathlib import Path

_TARGET = Path(__file__).resolve().parent.parent / "desktop" / "Bristlenose" / "Bristlenose"


def _sources() -> dict[str, str]:
    files = {p.name: p.read_text(encoding="utf-8") for p in _TARGET.glob("*.swift")}
    assert "ContentView.swift" in files and "BristlenoseApp.swift" in files, _TARGET
    return files


def test_the_app_owns_no_toast_store() -> None:
    app = _sources()["BristlenoseApp.swift"]
    assert "ToastStore" not in app
    assert "ToastOverlay" not in app


def test_each_toast_store_is_a_views_own_state_object() -> None:
    made = {
        name: re.findall(r"^.*ToastStore\(\).*$", text, flags=re.M)
        for name, text in _sources().items()
    }
    made = {name: lines for name, lines in made.items() if lines}
    assert "ContentView.swift" in made, "the window's root view owns its toast store"
    for name, lines in made.items():
        for line in lines:
            owned = re.match(r"\s*@StateObject private var (\w+) = ToastStore\(\)", line)
            assert owned, (name, line)
            # ...and draws it, or its toasts go nowhere.
            assert f"ToastOverlay().environmentObject({owned.group(1)})" in _sources()[name], name


def test_only_the_overlay_reads_a_toast_store_from_the_environment() -> None:
    readers = [
        name
        for name, text in _sources().items()
        if re.search(r"@EnvironmentObject\s+(private\s+)?var\s+\w+\s*:\s*ToastStore", text)
    ]
    assert readers == ["ToastView.swift"]
