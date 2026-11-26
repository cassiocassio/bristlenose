"""The HTML export leaves hidden quotes out, as every other export does.

Miro, FigJam, CSV, clips and Screens choose through ``export_core``, which drops a
hidden quote. The HTML export embeds the lenses' own payloads, which carry one
flagged so the app can un-hide it, and its hidden-quotes counter let a reader of
the file open every quote the researcher had set aside (owner, 25 Nov 2026).

The endpoint test captures the payload instead of building the HTML, so it runs
in CI without a frontend build.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from bristlenose.server.app import create_app
from bristlenose.server.routes import export as export_mod
from bristlenose.server.routes.export import _drop_hidden_quotes
from tests.conftest import AuthTestClient

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"
_P = "/api/projects/1"


@pytest.fixture()
def client() -> AuthTestClient:
    return AuthTestClient(create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://"))


def _exported(client: AuthTestClient, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    box: dict[str, Any] = {}

    def capture(export_data: dict[str, Any], theme_css: str) -> str:
        box["data"] = export_data
        return "<html></html>"

    monkeypatch.setattr(export_mod, "_build_export_html", capture)
    assert client.get(f"{_P}/export").status_code == 200
    endpoints: dict[str, Any] = box["data"]["endpoints"]
    return endpoints


def _quote_ids(quotes: dict[str, Any]) -> list[str]:
    ids = [q["dom_id"] for k in ("sections", "themes") for g in quotes[k] for q in g["quotes"]]
    ids += [q["dom_id"] for k in ("uncategorised", "unjoined") for q in quotes.get(k, [])]
    return ids


def test_a_hidden_quote_is_nowhere_in_the_file_but_its_words_in_the_transcript(
    client: AuthTestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hides one quote of a two-quote section, the only quote of another section and
    the only quote of a theme (the smoke fixture's whole layout)."""
    listed = client.get(f"{_P}/quotes").json()
    by_id = {q["dom_id"]: q for k in ("sections", "themes") for g in listed[k] for q in g["quotes"]}
    hide = ["q-p1-10", "q-p1-46", "q-p1-66"]
    assert set(hide) < set(by_id), "the fixture moved; these ids no longer name its quotes"
    before = _exported(client, monkeypatch)
    # Not vacuous: unhidden, each quote is in the file and the transcript marks it.
    for dom in hide:
        assert dom in _quote_ids(before["/quotes"])
        segs = before[f"/transcripts/{by_id[dom]['session_id']}"]["segments"]
        assert any(dom in seg["quote_ids"] for seg in segs)

    assert client.patch(f"{_P}/hidden", json=dict.fromkeys(hide, True)).status_code == 200
    after = _exported(client, monkeypatch)

    # The sweep: every embedded payload, today's and any added later.
    blob = json.dumps(after)
    speechless = copy.deepcopy(after)
    for key, tx in speechless.items():
        if key.startswith("/transcripts/"):
            tx["segments"] = []
    for dom in hide:
        assert dom not in blob
        assert by_id[dom]["text"][:40] not in json.dumps(speechless)
    # The words stay: a transcript is the whole conversation, hidden or not.
    for key in [k for k in before if k.startswith("/transcripts/")]:
        assert [g["text"] for g in after[key]["segments"]] == [g["text"] for g in before[key]["segments"]]

    quotes = after["/quotes"]
    assert _quote_ids(quotes) == ["q-p1-26"]
    assert (quotes["total_quotes"], quotes["total_hidden"]) == (1, 0)
    # A section or theme the hiding emptied goes, with its dashboard link and count.
    assert [g["cluster_id"] for g in quotes["sections"]] == [1] and quotes["themes"] == []
    dashboard = after["/dashboard"]
    assert [n["anchor"] for n in dashboard["sections"]] == ["section-1"]
    assert dashboard["themes"] == []
    assert (dashboard["stats"]["sections_count"], dashboard["stats"]["themes_count"]) == (1, 0)


def test_every_other_payload_that_holds_a_hidden_quote_lets_it_go() -> None:
    """The places the fixture reaches none of: the uncategorised floor and the unjoined
    list, the dashboard's candidates, the discussion record, the parked
    moderator-question keys and a transcript segment two quotes share."""
    seen = {"dom_id": "q-p1-10", "is_hidden": False, "is_starred": True}
    gone = {"dom_id": "q-p1-40", "is_hidden": True, "is_starred": True}
    endpoints: dict[str, Any] = {
        "/quotes": {
            "sections": [{"quotes": [dict(seen), dict(gone)]}], "themes": [],
            "uncategorised": [{"dom_id": "q-p2-5", "is_hidden": True, "is_starred": True}],
            "unjoined": [{"dom_id": "q-p3-7", "is_hidden": True}],
            "total_quotes": 4, "total_hidden": 3, "total_starred": 3, "total_uncategorised": 1,
        },
        "/dashboard": {"featured_quotes": [dict(seen), dict(gone)]},
        "/discussion": {"status": "ready", "record": {"quotes": [{"dom_id": "q-p1-10"}, {"dom_id": "q-p1-40"}]}},
        "/quotes/q-p1-10/moderator-question": {"text": "a"},
        "/quotes/q-p1-40/moderator-question": {"text": "b"},
        "/transcripts/s1": {
            "annotations": {
                "q-p1-10": {"verbatim_excerpt": "first part", "is_hidden": False},
                "q-p1-40": {"verbatim_excerpt": "second part", "is_hidden": True},
            },
            "segments": [
                {"text": "first part and second part", "quote_ids": ["q-p1-10", "q-p1-40"],
                 "is_quoted": True, "html_text": "stale"},
                {"text": "second part alone", "quote_ids": ["q-p1-40"],
                 "is_quoted": True, "html_text": "stale"},
            ],
        },
    }
    _drop_hidden_quotes(endpoints)

    quotes = endpoints["/quotes"]
    assert [q["dom_id"] for q in quotes["sections"][0]["quotes"]] == ["q-p1-10"]
    assert (quotes["uncategorised"], quotes["unjoined"], quotes["total_uncategorised"]) == ([], [], 0)
    assert (quotes["total_quotes"], quotes["total_hidden"], quotes["total_starred"]) == (1, 0, 1)
    assert [q["dom_id"] for q in endpoints["/dashboard"]["featured_quotes"]] == ["q-p1-10"]
    assert [q["dom_id"] for q in endpoints["/discussion"]["record"]["quotes"]] == ["q-p1-10"]
    assert "/quotes/q-p1-40/moderator-question" not in endpoints
    assert "/quotes/q-p1-10/moderator-question" in endpoints

    for gone_id in ("q-p1-40", "q-p2-5", "q-p3-7"):
        assert gone_id not in json.dumps(endpoints)
    shared, alone = endpoints["/transcripts/s1"]["segments"]
    # The other quote keeps its mark; the words stay.
    assert shared["quote_ids"] == ["q-p1-10"] and shared["is_quoted"] is True
    assert 'data-quote-id="q-p1-10"' in shared["html_text"]
    assert shared["text"] == "first part and second part"
    assert alone == {"text": "second part alone", "quote_ids": [], "is_quoted": False, "html_text": None}
