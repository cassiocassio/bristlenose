"""Every ``_BRISTLENOSE_*`` variable the Mac app sets is one the sidecar reads.

The desktop shell and the Python sidecar share a contract written as
environment-variable names, in two languages that cannot share a constant.
A name misspelt or renamed on one side fails silently: the sidecar just never
sees the switch. This reads the Swift literals instead of copying them, so it
fails when the source drifts. Same shape as ``test_accepted_extension_parity``.

What it proves, and what it does not: every name Swift sets is a name some Python
source *mentions* as a quoted string. A name Python only writes, or only holds in
a constant, would pass. Names without the leading underscore (``BRISTLENOSE_*``,
read through the settings prefix) are a different mechanism and are out of scope.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SWIFT_ROOTS = [
    REPO / "desktop" / "Bristlenose" / "Bristlenose",
    REPO / "desktop" / "mcp-helper",
    REPO / "desktop" / "speech-helper",
]

# A quoted FULL name. The JS globals (`window.__BRISTLENOSE_…__ = true;`) sit inside
# longer strings, so requiring the quote on both sides leaves them out.
NAME = re.compile(r'"(_BRISTLENOSE_[A-Z0-9_]+)"')


def _names(root: Path, suffix: str) -> set[str]:
    found: set[str] = set()
    for path in root.rglob(f"*{suffix}"):
        found |= set(NAME.findall(path.read_text(encoding="utf-8", errors="ignore")))
    return found


def test_swift_env_names_are_names_python_reads() -> None:
    python = _names(REPO / "bristlenose", ".py")
    missing = [str(r.relative_to(REPO)) for r in SWIFT_ROOTS if not r.is_dir()]
    assert not missing, f"scanned Swift roots moved or were deleted: {missing}"
    swift: set[str] = set()
    for root in SWIFT_ROOTS:
        swift |= _names(root, ".swift")
    assert swift, "found no Swift env names: the pattern or the path has drifted"
    assert python, "found no Python env names: the pattern or the path has drifted"
    unread = sorted(swift - python)
    assert not unread, f"Swift sets variables no Python code reads: {unread}"
