"""The HTML export builds moderator-question data only while the SPA can show it.

Building it was six SQL statements per quote (9,346 at 1,500 quotes, 4 Nov 2026) for a pill
that is parked behind ``featureFlags.moderatorQuestionPill``. The server cannot see that
flag, so the constant is mirrored and pinned here.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from bristlenose.server.app import create_app
from bristlenose.server.routes import export, quotes
from tests.conftest import AuthTestClient

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"
_FLAGS = Path(__file__).parents[1] / "frontend" / "src" / "utils" / "featureFlags.ts"


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    (tmp_path / "app.js").write_text("// stub", encoding="utf-8")
    (tmp_path / "app.css").write_text("/* stub */", encoding="utf-8")
    monkeypatch.setattr(export, "_EXPORT_STATIC_DIR", tmp_path)
    return AuthTestClient(create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://"))


def _calls(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    seen: list[str] = []

    def _handler(project_id: int, dom_id: str, request: object) -> dict[str, object]:
        seen.append(dom_id)
        raise HTTPException(status_code=404)

    monkeypatch.setattr(quotes, "get_moderator_question", _handler)
    return seen


def test_the_python_constant_matches_the_frontend_default() -> None:
    match = re.search(r"^\s*moderatorQuestionPill:\s*(true|false),", _FLAGS.read_text("utf-8"), re.M)
    assert match, "featureFlags.ts no longer declares moderatorQuestionPill's default"
    assert (match.group(1) == "true") is export.MODERATOR_QUESTION_PILL_ENABLED


def test_a_parked_pill_costs_the_export_no_lookups(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen = _calls(monkeypatch)
    monkeypatch.setattr(export, "MODERATOR_QUESTION_PILL_ENABLED", False)
    assert client.get("/api/projects/1/export").status_code == 200
    assert seen == []


def test_an_enabled_pill_still_gets_its_data(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen = _calls(monkeypatch)
    monkeypatch.setattr(export, "MODERATOR_QUESTION_PILL_ENABLED", True)
    assert client.get("/api/projects/1/export").status_code == 200
    assert len(seen) > 0
