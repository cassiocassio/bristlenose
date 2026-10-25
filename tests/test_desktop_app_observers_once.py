"""A notification observer the app registers is registered once per process.

`BristlenoseApp`'s `.onAppear` runs for every main window that appears, and the observer
tokens it assigns are `@State` on the `App`, shared by all of them. An unguarded
`token = NotificationCenter.default.addObserver(...)` therefore adds another observer per
window and overwrites the only handle that could remove the old one: with N windows one Agent
Access change ran N `syncHandshake` calls and one preferences change ran N `applyEnvChange`
sweeps, which is the "several syncs" condition N191's race needed. N193 fixed it for the
not-saved alert; REV-2 (25 Oct 2026) found the two beside it still leaking.

SwiftUI's `@State` on an `App` cannot be reached from a test, so this pins the shape in the
source, as `test_desktop_toast_scope.py` does: each token is assigned only inside an
`if <token> == nil { ... }` guard.
"""

from __future__ import annotations

import re
from pathlib import Path

_APP = (
    Path(__file__).resolve().parent.parent
    / "desktop"
    / "Bristlenose"
    / "Bristlenose"
    / "BristlenoseApp.swift"
)


def _tokens(text: str) -> list[str]:
    return re.findall(r"@State private var (\w+): \(any NSObjectProtocol\)\?", text)


def test_the_app_holds_observer_tokens() -> None:
    # Guards the guard: if the declarations are renamed, the checks below must not go vacuous.
    tokens = _tokens(_APP.read_text(encoding="utf-8"))
    assert {"prefsFanOut", "agentAccessFanOut", "agentAccessNotSavedObserver"} <= set(tokens)


def test_every_observer_token_is_assigned_once_per_process() -> None:
    text = _APP.read_text(encoding="utf-8")
    for token in _tokens(text):
        assigned = list(re.finditer(rf"^(\s*){token} = NotificationCenter", text, flags=re.M))
        assert assigned, f"{token} is declared and never assigned"
        for hit in assigned:
            before = text[: hit.start()]
            guard = f"if {token} == nil {{"
            assert before.rstrip().endswith(guard), (
                f"{token} is assigned for every main window that appears; "
                f"wrap the registration in `{guard}`"
            )
