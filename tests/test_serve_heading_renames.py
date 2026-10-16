"""A researcher's rename shows wherever the section or theme appears.

Owner's rule (16 Oct 2026): once a researcher renames a section or theme, every
lens and every output shows the new name. The pipeline's name stays on the row
(the quotes endpoint returns it beside ``edited_label``, for reset-to-original
and the "edited" indicator) and is never what a surface prints.

Every test renames through the real write path, ``PUT /edits`` with the durable
id keys the Quotes lens sends, then reads one surface. Smoke fixture: sections
"Dashboard" (q-p1-10, q-p1-26) and "Search" (q-p1-46); theme "Onboarding gaps"
(q-p1-66).
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bristlenose.server.app import create_app
from bristlenose.server.export_core import extract_quotes_for_export
from bristlenose.server.grounding import assemble_corpus_context, load_signals
from bristlenose.server.mcp_server import _tool_get_project_overview, _tool_search_quotes
from tests.conftest import AuthTestClient

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"

SECTION = "Checkout friction"
THEME = "Getting started"


@pytest.fixture()
def app_fx():
    return create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")


@pytest.fixture()
def client(app_fx) -> TestClient:
    return AuthTestClient(app_fx)


@pytest.fixture()
def ids(client: TestClient) -> dict[str, int]:
    """Rename "Dashboard" and "Onboarding gaps" the way the Quotes lens does."""
    data = client.get("/api/projects/1/quotes").json()
    section_id = next(s["cluster_id"] for s in data["sections"] if s["screen_label"] == "Dashboard")
    theme_id = next(t["theme_id"] for t in data["themes"] if t["theme_label"] == "Onboarding gaps")
    resp = client.put("/api/projects/1/edits", json={
        f"section-cluster-{section_id}:title": SECTION,
        f"theme-group-{theme_id}:title": THEME,
    })
    assert resp.status_code == 200
    return {"section": section_id, "theme": theme_id}


@pytest.fixture()
def db(app_fx, ids):
    session = app_fx.state.db_factory()
    yield session
    session.close()


def test_quotes_keep_the_pipeline_name_beside_the_rename(client, ids) -> None:
    data = client.get("/api/projects/1/quotes").json()
    section = next(s for s in data["sections"] if s["cluster_id"] == ids["section"])
    theme = next(t for t in data["themes"] if t["theme_id"] == ids["theme"])
    assert (section["screen_label"], section["edited_label"]) == ("Dashboard", SECTION)
    assert (theme["theme_label"], theme["edited_label"]) == ("Onboarding gaps", THEME)


def test_session_timeline(client, ids) -> None:
    row = client.get("/api/projects/1/tapestry").json()["sessions"][0]
    assert [s["label"] for s in row["sections"]] == [SECTION, "Search"]
    assert (None, THEME) in {(q["section"], q["theme"]) for q in row["quotes"]}


def test_transcript_margin_labels(client, ids) -> None:
    data = client.get("/api/projects/1/transcripts/s1").json()
    labels = {a["label"] for a in data["annotations"].values()}
    assert SECTION in labels and THEME in labels
    assert not labels & {"Dashboard", "Onboarding gaps"}


def test_transcript_journey(client, ids) -> None:
    data = client.get("/api/projects/1/transcripts/s1").json()
    assert data["journey_labels"] == [SECTION, "Search"]


def test_sessions_journey(client, ids) -> None:
    row = client.get("/api/projects/1/sessions").json()["sessions"][0]
    assert row["journey_labels"] == [SECTION, "Search"]
    assert [step["label"] for step in row["journey"]] == [SECTION, "Search"]


def test_dashboard_names_and_anchors(client, ids) -> None:
    data = client.get("/api/projects/1/dashboard").json()
    assert data["sections"][0]["label"] == SECTION
    assert data["themes"][0]["label"] == THEME
    # Anchors key on the durable id, so a rename cannot move them.
    assert data["sections"][0]["anchor"] == f"section-{ids['section']}"
    assert data["themes"][0]["anchor"] == f"theme-{ids['theme']}"


def test_signals_cards_rows_and_links(client, ids) -> None:
    data = client.get("/api/projects/1/signals/codebooks").json()
    signals = [s for cb in data["codebooks"] for s in cb["signals"]]
    locations = {s["location"] for s in signals}
    assert SECTION in locations and "Dashboard" not in locations
    card = next(s for s in signals if s["location"] == SECTION)
    assert card["anchor"] == f"section-{ids['section']}"


def test_sentiment_signal_matrix_rows(client, ids) -> None:
    data = client.get("/api/projects/1/signals/sentiment").json()
    assert data["sectionMatrix"]["rowLabels"] == [SECTION, "Search"]
    assert data["themeMatrix"]["rowLabels"] == [THEME]


def test_chat_lens_corpus(db) -> None:
    corpus = assemble_corpus_context(db, 1)
    assert f"## Section: {SECTION}\n" in corpus.text
    assert f"## Theme: {THEME}\n" in corpus.text
    assert "Section: Dashboard" not in corpus.text
    assert "Onboarding gaps" not in corpus.text


def test_grounded_signals(db) -> None:
    result = load_signals(db, 1, lens="tags")
    assert [(s.location, s.source_type) for s in result.signals] == [(SECTION, "section")]


def test_agent_overview_and_search(db) -> None:
    overview = _tool_get_project_overview(db, 1, None)
    assert [s["label"] for s in overview["sections"]] == [SECTION, "Search"]
    assert [t["label"] for t in overview["themes"]] == [THEME]

    found = _tool_search_quotes(
        db, project_id=1, query=None, tag=None, sentiment=None, participant=None,
        section=SECTION, theme=None, starred_only=False, limit=20, offset=0,
    )
    assert found["total_matched"] == 2
    assert {r["section"] for r in found["quotes"]} == {SECTION}
    themed = _tool_search_quotes(
        db, project_id=1, query=None, tag=None, sentiment=None, participant=None,
        section=None, theme=THEME, starred_only=False, limit=20, offset=0,
    )
    assert [r["themes"] for r in themed["quotes"]] == [[THEME]]


def test_quote_exports(client, db) -> None:
    rows = extract_quotes_for_export(db, 1)
    assert {r.section for r in rows} == {SECTION, "Search", ""}
    assert THEME in {r.theme for r in rows}
    # Section display order still sorts the renamed section first.
    assert rows[0].section == SECTION

    resp = client.get("/api/projects/1/export/quotes.csv")
    assert resp.status_code == 200
    table = list(csv.DictReader(io.StringIO(resp.text.lstrip("﻿"))))
    assert {r["Section"] for r in table} >= {SECTION, "Search"}
    assert "Dashboard" not in {r["Section"] for r in table}
    assert THEME in {r["Theme"] for r in table}
