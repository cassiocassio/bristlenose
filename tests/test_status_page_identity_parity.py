"""The status page's identity message must decode on the Swift side.

WHY THIS EXISTS
---------------
The desktop shell derives lens availability from *document identity*: the SPA
posts ``{type: "ready"}``, the server-rendered status page posts
``{type: "status-page", outcome: …}`` (``_IDENTITY_SCRIPT`` in
``status_page.py``), and ``BridgeHandler`` maps the outcome onto
``StatusPageOutcome``. The vocabulary lives in two languages; nothing else
holds the copies together. An outcome emitted by Python that Swift doesn't
name silently decodes to ``.unknown`` — behaviourally still a status page, so
nothing would ever *fail*, the reason would just quietly stop being named.
Same shape as the ``TAB_ROUTES`` gap this test's sibling
(``test_tab_route_parity.py``) was built for.

This test reads both files as text. That is deliberate: the contract is a
cross-language one, and a fixture would be a third copy to drift.
"""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_STATUS_PY = _ROOT / "bristlenose/server/status_page.py"
_DOCSTATE_SWIFT = _ROOT / "desktop/Bristlenose/Bristlenose/DocumentState.swift"
_BRIDGE_SWIFT = _ROOT / "desktop/Bristlenose/Bristlenose/BridgeHandler.swift"


def _python_emitted_outcomes() -> set[str]:
    """Every ``outcome="…"`` a StatusInfo constructor can emit."""
    src = _STATUS_PY.read_text(encoding="utf-8")
    values = set(re.findall(r'outcome="([a-z][a-z-]*)"', src))
    assert values, "status_page.py: no outcome= literals found — shape changed?"
    return values


def _swift_outcome_raw_values() -> set[str]:
    """``StatusPageOutcome``'s raw values — the decode vocabulary."""
    src = _DOCSTATE_SWIFT.read_text(encoding="utf-8")
    body = re.search(r"enum StatusPageOutcome[^{]*\{(.*?)\n\}", src, re.S)
    assert body, "DocumentState.swift: could not find enum StatusPageOutcome"
    values = set(re.findall(r'case \w+ = "([a-z][a-z-]*)"', body.group(1)))
    assert values, "StatusPageOutcome parsed to nothing — raw values removed?"
    return values


def test_every_emitted_outcome_is_named_on_the_swift_side() -> None:
    unnamed = _python_emitted_outcomes() - _swift_outcome_raw_values()
    assert not unnamed, (
        f"status_page.py emits outcome(s) {sorted(unnamed)} that "
        "StatusPageOutcome (DocumentState.swift) does not name — they will "
        "decode as .unknown. Add the case(s), or rename the outcome."
    )


def test_swift_keeps_the_tolerant_unknown_case() -> None:
    assert "unknown" in _swift_outcome_raw_values(), (
        "StatusPageOutcome lost its .unknown case — the tolerant decode for "
        "outcomes a newer serve adds. Put it back."
    )


def test_message_type_literal_matches() -> None:
    """Both sides spell the message type identically."""
    py = _STATUS_PY.read_text(encoding="utf-8")
    assert "type: 'status-page'" in py, (
        "status_page.py identity script no longer posts type 'status-page'"
    )
    swift = _BRIDGE_SWIFT.read_text(encoding="utf-8")
    assert 'case "status-page":' in swift, (
        "BridgeHandler.handleMessage no longer handles \"status-page\""
    )
