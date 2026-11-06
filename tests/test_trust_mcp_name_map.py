"""The MCP speaker-name map is the one gate to the persons table (grounding.resolve_speaker_names).

A direct test on the function: a positive control (names ON returns the planted name) and the gate
(Anonymise ON returns nothing). The earlier version drove this through the MCP tool and passed with the
guard removed (audit n6a1, 6 Nov 2026), so it asserted nothing. Proven with
docs/private/trust-map/audit_tools.py mutate (remove the _mcp_anonymise_active clause: this must fail).
"""

from __future__ import annotations

from pathlib import Path

import pytest

import bristlenose
from bristlenose.server.grounding import resolve_speaker_names
from tests.test_trust_planted_name import FULL_NAME, SHORT_NAME, planted  # noqa: F401


def test_imports_this_tree() -> None:
    assert Path(bristlenose.__file__).is_relative_to(Path(__file__).parents[1])


def test_names_are_returned_when_anonymise_is_off(planted) -> None:  # noqa: F811
    app, _client = planted
    db = app.state.db_factory()
    try:
        names = resolve_speaker_names(db, 1)
    finally:
        db.close()
    assert SHORT_NAME in names.values() or FULL_NAME in names.values(), names  # positive control


def test_no_names_when_anonymise_is_on(planted, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    app, _client = planted
    monkeypatch.setenv("BRISTLENOSE_MCP_ANONYMISE", "1")
    db = app.state.db_factory()
    try:
        names = resolve_speaker_names(db, 1)
    finally:
        db.close()
    assert names == {}
