"""An anonymised export names no participant in any bucket of /quotes.

``_anonymise_data`` blanked ``speaker_name`` only in ``/quotes`` ``sections`` and
``themes``. The same payload also carries ``uncategorised`` (pinned quotes the
current analysis files nowhere) and ``unjoined`` (quotes in no section or theme and
not on the floor), and the Uncategorised floor, the by-session quotes view and
View Source all showed the participant's name from them (N145, found 25 Oct 2026).
No existing test seeded either bucket, so the boundary test passed on a fixture
that could not leak. This one seeds both, drives the real export route, and walks
every string in the embed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from starlette.requests import Request

from bristlenose.server.db import create_session_factory, get_engine, init_db
from bristlenose.server.models import (
    ClusterQuote,
    Person,
    Project,
    Quote,
    QuoteState,
    ScreenCluster,
    SessionSpeaker,
    ThemeGroup,
    ThemeQuote,
    TranscriptSegment,
)
from bristlenose.server.models import Session as SessionModel
from bristlenose.server.routes import export as export_mod

_NAME = "Zelda Quixotic"
_SHORT = "Zelda"


def _seed(tmp_path: Path) -> tuple[FastAPI, int]:
    engine = get_engine(f"sqlite:///{tmp_path / 'anon.db'}")
    init_db(engine)
    factory = create_session_factory(engine)
    db = factory()
    p = Project(name="P", input_dir=str(tmp_path), output_dir=str(tmp_path / "out"))
    db.add(p)
    db.flush()
    s = SessionModel(project_id=p.id, session_id="s1", session_number=1)
    db.add(s)
    db.flush()
    jane = Person(full_name=_NAME, short_name=_SHORT, code="p1")
    mod = Person(full_name="Mo Derator", short_name="Mo", code="m1")
    db.add_all([jane, mod])
    db.flush()
    db.add(SessionSpeaker(session_id=s.id, person_id=jane.id, speaker_code="p1",
                          speaker_role="participant"))
    db.add(SessionSpeaker(session_id=s.id, person_id=mod.id, speaker_code="m1",
                          speaker_role="researcher"))
    for i, (spk, t0, t1, text) in enumerate([
        ("m1", 0.0, 4.0, "what do you think"),
        ("p1", 5.0, 8.0, "filed in a section"),
        ("p1", 20.0, 24.0, "starred floor quote"),
        ("p1", 30.0, 34.0, "joined to nothing at all"),
    ]):
        db.add(TranscriptSegment(session_id=s.id, speaker_code=spk, start_time=t0,
                                 end_time=t1, text=text, segment_index=i))
    quotes = {}
    for key, (t0, t1, text) in {
        "filed": (5.0, 8.0, "filed in a section"),
        "floor": (20.0, 24.0, "starred floor quote"),
        "unjoined": (30.0, 34.0, "joined to nothing at all"),
    }.items():
        quotes[key] = Quote(project_id=p.id, session_id="s1", participant_id="p1",
                            start_timecode=t0, end_timecode=t1, text=text,
                            quote_type="general_context")
    db.add_all(quotes.values())
    db.flush()
    cluster = ScreenCluster(project_id=p.id, screen_label="Basket", description="",
                            display_order=1)
    theme = ThemeGroup(project_id=p.id, theme_label="Trust", description="")
    db.add_all([cluster, theme])
    db.flush()
    db.add(ClusterQuote(cluster_id=cluster.id, quote_id=quotes["filed"].id))
    db.add(ThemeQuote(theme_id=theme.id, quote_id=quotes["filed"].id))
    # The floor: pinned (starred) and filed nowhere.
    db.add(QuoteState(quote_id=quotes["floor"].id, is_starred=True))
    # unjoined: no state, no join.
    pid = p.id
    db.commit()
    db.close()
    app = FastAPI()
    app.state.db_factory = factory
    app.state.project_dir = tmp_path
    return app, pid


def _export(app: FastAPI, pid: int, *, anonymise: bool) -> dict[str, Any]:
    req = Request({"type": "http", "app": app, "headers": [], "method": "GET",
                   "path": "/", "query_string": b""})
    captured: dict[str, Any] = {}
    orig = export_mod._build_export_html

    def spy(export_data: dict[str, Any], css: str) -> str:
        captured["data"] = export_data
        return orig(export_data, css)

    export_mod._build_export_html = spy  # type: ignore[assignment]
    try:
        export_mod.export_report(pid, req, anonymise=anonymise, locale="")
    finally:
        export_mod._build_export_html = orig  # type: ignore[assignment]
    return captured["data"]


def _walk_leaks(node: object, path: str, needles: tuple[str, ...]) -> list[str]:
    out: list[str] = []
    if isinstance(node, dict):
        for k, v in node.items():
            out += _walk_leaks(v, f"{path}.{k}", needles)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            out += _walk_leaks(v, f"{path}[{i}]", needles)
    elif isinstance(node, str) and any(n in node for n in needles):
        out.append(path)
    return out


@pytest.fixture()
def seeded(tmp_path: Path) -> tuple[FastAPI, int]:
    return _seed(tmp_path)


def test_the_seed_reaches_both_buckets(seeded: tuple[FastAPI, int]) -> None:
    """Without this, a seed that landed no quote in either bucket would let the
    anonymise assertions below pass while asserting nothing."""
    app, pid = seeded
    q = _export(app, pid, anonymise=False)["endpoints"]["/quotes"]
    assert [x["speaker_name"] for x in q["uncategorised"]] == [_SHORT]
    assert [x["speaker_name"] for x in q["unjoined"]] == [_SHORT]
    assert q["sections"] and q["themes"]


def test_anonymised_export_names_no_participant_in_any_quote_bucket(
    seeded: tuple[FastAPI, int],
) -> None:
    app, pid = seeded
    data = _export(app, pid, anonymise=True)
    q = data["endpoints"]["/quotes"]
    assert len(q["uncategorised"]) == 1 and len(q["unjoined"]) == 1
    leaks = _walk_leaks(data["endpoints"], "endpoints", ("Zelda", "Quixot"))
    assert not leaks, f"participant name in an anonymised export at {leaks}"
    # The embed as shipped (serialised into the HTML) carries it nowhere either.
    html = export_mod._build_export_html(data, "")
    for needle in ("Zelda", "Quixot"):
        assert needle not in html


def test_anonymised_export_still_names_the_moderator(
    seeded: tuple[FastAPI, int],
) -> None:
    """The boundary is the participant line (docs/design-people.md section E)."""
    app, pid = seeded
    data = _export(app, pid, anonymise=True)
    assert "Mo Derator" in json.dumps(data["endpoints"]["/people"])
