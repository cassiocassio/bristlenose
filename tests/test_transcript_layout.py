"""Split and join of transcript paragraphs, stage 1.

``design-transcript-editing.md`` §"Split and join, stage 1". A long paragraph
split in two with the same speaker — the common case — and two paragraphs
joined. Recorded and replayed on every import, so a split outlives a re-run;
undone by forgetting the record and rebuilding the session's paragraphs.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from tests.test_serve_moderator_identities import _TWO, _client, _project, _reimport


def _segments(client: TestClient, sid: str = "s1") -> list[dict]:
    return client.get(f"/api/projects/1/transcripts/{sid}").json()["segments"]


def _texts(client: TestClient) -> list[tuple[str, str]]:
    return [(s["speaker_code"], s["text"]) for s in _segments(client)]


def _split(client: TestClient, position: int, token: int, verify: str) -> int:
    resp = client.post("/api/projects/1/transcripts/s1/split",
                       json={"position": position, "token": token, "verify": verify})
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


class TestSplit:
    def test_a_paragraph_splits_in_two_with_the_same_speaker(self, tmp_path: Path) -> None:
        client = _client(_project(tmp_path, _TWO))
        _split(client, 1, 4, "it is good to be here.")
        assert _texts(client) == [
            ("m1", "Welcome, thanks for coming in today."),
            ("p1", "Thanks for having me,"),
            ("p1", "it is good to be here."),
            ("m1", "Shall we start?"),
        ]
        segs = _segments(client)
        # No word timings: the time is shared by how much text each half holds.
        assert segs[1]["start_time"] == 10.0
        assert 10.0 < segs[2]["start_time"] < 20.0
        assert segs[1]["end_time"] == segs[2]["start_time"]

    def test_the_split_outlives_a_re_import(self, tmp_path: Path) -> None:
        project = _project(tmp_path, _TWO)
        client = _client(project)
        _split(client, 1, 4, "it is good to be here.")
        _reimport(client, project)
        assert [t for _, t in _texts(client)][1:3] == ["Thanks for having me,", "it is good to be here."]

    def test_undo_takes_it_back_and_survives_a_re_import(self, tmp_path: Path) -> None:
        project = _project(tmp_path, _TWO)
        client = _client(project)
        before = _texts(client)
        edit = _split(client, 1, 4, "it is good to be here.")
        resp = client.delete(f"/api/projects/1/transcripts/s1/layout-edits/{edit}")
        assert resp.status_code == 200, resp.text
        assert _texts(client) == before
        _reimport(client, project)
        assert _texts(client) == before

    def test_a_split_where_the_words_have_moved_is_refused(self, tmp_path: Path) -> None:
        client = _client(_project(tmp_path, _TWO))
        resp = client.post("/api/projects/1/transcripts/s1/split",
                           json={"position": 1, "token": 4, "verify": "something else entirely"})
        assert resp.status_code == 409
        resp = client.post("/api/projects/1/transcripts/s1/split",
                           json={"position": 1, "token": 0, "verify": "Thanks for having me,"})
        assert resp.status_code == 409, "a split needs words on both sides"

    def test_a_split_with_word_timings_starts_the_second_half_on_its_first_word(
        self, tmp_path: Path,
    ) -> None:
        from bristlenose.server.models import TranscriptSegment

        client = _client(_project(tmp_path, _TWO))
        db = client.app.state.db_factory()
        try:
            seg = db.query(TranscriptSegment).filter_by(speaker_code="p1").first()
            words = [{"t": w, "s": 10.0 + i, "e": 10.5 + i} for i, w in enumerate(seg.text.split())]
            seg.words_json = json.dumps(words)
            db.commit()
        finally:
            db.close()
        _split(client, 1, 4, "it is good to be here.")
        segs = _segments(client)
        assert segs[2]["start_time"] == 14.0
        assert [w["text"] for w in segs[2]["words"]][:2] == ["it", "is"]
        assert len(segs[1]["words"]) == 4


    def test_an_untimed_paragraph_split_twice_keeps_its_reading_order(
        self, tmp_path: Path,
    ) -> None:
        """No time to share (end == start): splitting the first half again must
        put the new piece between the halves, not after the tail."""
        from bristlenose.server.models import TranscriptSegment

        client = _client(_project(tmp_path, _TWO))
        db = client.app.state.db_factory()
        try:
            seg = db.query(TranscriptSegment).filter_by(speaker_code="p1").first()
            seg.end_time = seg.start_time
            db.commit()
        finally:
            db.close()
        _split(client, 1, 8, "be here.")
        _split(client, 1, 3, "me, it is good to")
        assert [t for _, t in _texts(client)][1:4] == [
            "Thanks for having", "me, it is good to", "be here.",
        ]


class TestJoin:
    def test_two_halves_join_back(self, tmp_path: Path) -> None:
        client = _client(_project(tmp_path, _TWO))
        before = _texts(client)
        _split(client, 1, 4, "it is good to be here.")
        resp = client.post("/api/projects/1/transcripts/s1/join",
                           json={"position": 2, "verify": "it is good to be here."})
        assert resp.status_code == 200, resp.text
        assert _texts(client) == before

    def test_two_speakers_are_not_joined(self, tmp_path: Path) -> None:
        client = _client(_project(tmp_path, _TWO))
        resp = client.post("/api/projects/1/transcripts/s1/join",
                           json={"position": 1, "verify": "Thanks for having me, it is"})
        assert resp.status_code == 409

    def test_the_quote_still_marks_both_halves(self, tmp_path: Path) -> None:
        from tests.test_serve_participant_recode import _with_quotes

        client = _client(_with_quotes(tmp_path))
        _split(client, 1, 4, "it is good to be here.")
        segs = _segments(client)
        assert segs[1]["is_quoted"] and segs[2]["is_quoted"]


def test_015_creates_the_table_on_a_014_database(tmp_path: Path) -> None:
    import sqlalchemy as sa

    from bristlenose.server.db import init_db, run_migrations

    engine = sa.create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    init_db(engine)
    with engine.connect() as conn:
        conn.execute(sa.text("DROP TABLE transcript_layout_edits"))
        conn.execute(sa.text("UPDATE alembic_version SET version_num = '014'"))
        conn.commit()
    run_migrations(engine)
    with engine.connect() as conn:
        assert "transcript_layout_edits" in sa.inspect(conn).get_table_names()
