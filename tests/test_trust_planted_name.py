"""Trust gate: a participant's real name never leaves through a model-facing or
anonymised path.

A distinctive fake name is planted the way a researcher plants it, through the
people API (which writes the DB and ``people.yaml``), on a copy of the smoke
fixture. Then every path that must not carry it is exercised for real, and a
positive control on each shows the planted name was reachable, so an absence
means the guard held rather than the name never arriving.

Covered: the chat lens's LLM payloads (answer + support check), the MCP
speaker-name map under the Anonymise switch, the anonymised quotes CSV export,
and log output across all of it. Not covered here: AutoCode, Signals
elaboration and the codebook builder payloads; their quote formatters take a
participant code by construction (``autocode.build_quote_batch``) but are not
driven end to end in this file.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import bristlenose
from bristlenose.llm.structured import (
    ChatLensAnswer,
    ChatLensClaim,
    ChatLensSupportResult,
    ChatLensSupportVerdict,
)
from bristlenose.server.app import create_app
from tests.conftest import AuthTestClient

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"

FULL_NAME = "Zephyrine Quillfeather"
SHORT_NAME = "Zephyrine"
_MARKERS = (FULL_NAME, SHORT_NAME, "Quillfeather")


def _carries_name(text: str) -> bool:
    return any(m in text for m in _MARKERS)


def test_imports_this_tree() -> None:
    assert Path(bristlenose.__file__).is_relative_to(Path(__file__).parents[1])


def _mock_settings() -> MagicMock:
    s = MagicMock()
    s.llm_provider = "anthropic"
    s.llm_model = "test-model"
    s.llm_max_tokens = 1000
    s.anthropic_api_key = "not-a-real-token-1"
    return s


@pytest.fixture
def planted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """An app on a copy of the fixture, with p1 named through the people API."""
    monkeypatch.delenv("BRISTLENOSE_MCP_ANONYMISE", raising=False)
    project_dir = tmp_path / "input"
    shutil.copytree(_FIXTURE_DIR, project_dir)
    app = create_app(project_dir=project_dir, dev=False, db_url="sqlite://")
    app.state.settings = _mock_settings()
    client = AuthTestClient(app)
    r = client.put(
        "/api/projects/1/people",
        json={"p1": {"full_name": FULL_NAME, "short_name": SHORT_NAME, "role": ""}},
    )
    assert r.status_code == 200, r.text
    people = client.get("/api/projects/1/people").json()
    assert _carries_name(str(people)), "the planted name must be in the DB"
    return app, client


def _ask(client: AuthTestClient) -> AsyncMock:
    mock = AsyncMock(
        side_effect=[
            ChatLensAnswer(
                claims=[ChatLensClaim(text="People were confused.", quote_indices=[1])],
                unsupported="",
                abstain_reason="",
            ),
            ChatLensSupportResult(
                verdicts=[ChatLensSupportVerdict(claim_index=0, supported=True)]
            ),
        ]
    )
    llm = MagicMock()
    llm.analyze = mock
    llm.tracker = MagicMock(input_tokens=0, output_tokens=0)
    with patch("bristlenose.llm.client.LLMClient", return_value=llm):
        r = client.post(
            "/api/dev/chat-lens/ask", json={"question": "Who was confused, by name?"}
        )
    assert r.status_code == 200, r.text
    return mock


def _payload(mock: AsyncMock) -> str:
    return "\n".join(f"{c.args!r} {c.kwargs!r}" for c in mock.call_args_list)


def test_chat_lens_payloads_never_carry_the_planted_name(planted) -> None:
    _, client = planted
    mock = _ask(client)
    assert mock.call_count == 2, "answer + support check should both have run"
    payload = _payload(mock)
    assert "p1" in payload, "positive control: the quotes reached the model by code"
    assert not _carries_name(payload)


def test_mcp_speaker_names_honour_anonymise(planted, monkeypatch) -> None:
    from bristlenose.server.grounding import resolve_speaker_names

    app, _ = planted
    db = app.state.db_factory()
    try:
        assert _carries_name(str(resolve_speaker_names(db, 1))), "positive control"
        monkeypatch.setenv("BRISTLENOSE_MCP_ANONYMISE", "1")
        assert not _carries_name(str(resolve_speaker_names(db, 1)))
    finally:
        db.close()


def test_anonymised_quotes_csv_never_carries_the_planted_name(planted) -> None:
    _, client = planted
    named = client.get("/api/projects/1/export/quotes.csv", params={"anonymise": "false"})
    assert named.status_code == 200
    assert _carries_name(named.text), "positive control: a named export carries it"
    anon = client.get("/api/projects/1/export/quotes.csv", params={"anonymise": "true"})
    assert anon.status_code == 200
    assert "p1" in anon.text
    assert not _carries_name(anon.text)


def test_logs_never_carry_the_planted_name(tmp_path, monkeypatch, caplog) -> None:
    caplog.set_level(logging.DEBUG)
    monkeypatch.delenv("BRISTLENOSE_MCP_ANONYMISE", raising=False)
    project_dir = tmp_path / "input"
    shutil.copytree(_FIXTURE_DIR, project_dir)
    app = create_app(project_dir=project_dir, dev=False, db_url="sqlite://")
    app.state.settings = _mock_settings()
    client = AuthTestClient(app)
    r = client.put(
        "/api/projects/1/people",
        json={"p1": {"full_name": FULL_NAME, "short_name": SHORT_NAME, "role": ""}},
    )
    assert r.status_code == 200
    _ask(client)
    client.get("/api/projects/1/export/quotes.csv", params={"anonymise": "true"})
    client.get("/api/projects/1/export/quotes.csv", params={"anonymise": "false"})
    assert caplog.records, "positive control: something was logged"
    leaked = [rec.getMessage() for rec in caplog.records if _carries_name(rec.getMessage())]
    assert not leaked, leaked
