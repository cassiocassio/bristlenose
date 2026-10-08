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


def test_016_adds_the_reassignment_columns_on_a_015_database(tmp_path: Path) -> None:
    import sqlalchemy as sa

    from bristlenose.server.db import init_db, run_migrations

    engine = sa.create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    init_db(engine)
    with engine.connect() as conn:
        conn.execute(sa.text("ALTER TABLE transcript_layout_edits DROP COLUMN speaker_code"))
        conn.execute(sa.text("ALTER TABLE transcript_segments DROP COLUMN moved_from"))
        conn.execute(sa.text("UPDATE alembic_version SET version_num = '015'"))
        conn.commit()
    run_migrations(engine)
    with engine.connect() as conn:
        inspect = sa.inspect(conn)
        assert "speaker_code" in {c["name"] for c in inspect.get_columns("transcript_layout_edits")}
        assert "moved_from" in {c["name"] for c in inspect.get_columns("transcript_segments")}


def _reassign(client: TestClient, position: int, verify: str, slot: str) -> int:
    resp = client.post("/api/projects/1/transcripts/s1/reassign",
                       json={"position": position, "verify": verify, "slot": slot})
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


class TestReassign:
    """§K, the picker's Paragraph scope: one paragraph credited to another
    speaker of its session. Recorded and replayed like a split; a quote from
    words moved off the participant leaves the evidence."""

    def test_one_paragraph_moves_and_the_others_stay(self, tmp_path: Path) -> None:
        from tests.test_serve_participant_recode import _with_quotes

        client = _client(_with_quotes(tmp_path))
        _reassign(client, 1, "Thanks for having me, it is", "m1")
        assert [c for c, _ in _texts(client)] == ["m1", "m1", "m1"]

    def test_its_quote_leaves_the_evidence_and_comes_back_on_undo(self, tmp_path: Path) -> None:
        from tests.test_serve_participant_recode import _quote_ids, _with_quotes

        client = _client(_with_quotes(tmp_path))
        assert _quote_ids(client) == {"q-p1-10", "q-p2-10"}
        edit = _reassign(client, 1, "Thanks for having me, it is", "m1")
        assert _quote_ids(client) == {"q-p2-10"}, "the other session's quote stays"
        assert not any(s["is_quoted"] for s in _segments(client))
        client.delete(f"/api/projects/1/transcripts/s1/layout-edits/{edit}")
        assert _quote_ids(client) == {"q-p1-10", "q-p2-10"}

    def test_it_outlives_a_re_import(self, tmp_path: Path) -> None:
        from tests.test_serve_participant_recode import _quote_ids, _with_quotes

        project = _with_quotes(tmp_path)
        client = _client(project)
        _reassign(client, 1, "Thanks for having me, it is", "m1")
        _reimport(client, project)
        assert [c for c, _ in _texts(client)] == ["m1", "m1", "m1"]
        assert _quote_ids(client) == {"q-p2-10"}

    def test_moving_it_back_restores_the_evidence(self, tmp_path: Path) -> None:
        from tests.test_serve_participant_recode import _quote_ids, _with_quotes

        client = _client(_with_quotes(tmp_path))
        _reassign(client, 1, "Thanks for having me, it is", "m1")
        _reassign(client, 1, "Thanks for having me, it is", "p1")
        assert _quote_ids(client) == {"q-p1-10", "q-p2-10"}

    def test_a_quote_spanning_a_moved_and_a_kept_paragraph_stays(self, tmp_path: Path) -> None:
        from tests.test_serve_participant_recode import _quote_ids, _with_quotes

        client = _client(_with_quotes(tmp_path))
        # Split p1's paragraph inside the quote's window (10–18), then move
        # only the second half: the quote still has words of p1's.
        _split(client, 1, 4, "it is good to be here.")
        segs = _segments(client)
        assert 10.0 < segs[2]["start_time"] < 18.0
        _reassign(client, 2, "it is good to be here.", "m1")
        assert "q-p1-10" in _quote_ids(client)

    def test_refused_for_a_speaker_not_in_the_session_or_changed_words(
        self, tmp_path: Path,
    ) -> None:
        client = _client(_project(tmp_path, _TWO))
        bad = client.post("/api/projects/1/transcripts/s1/reassign",
                          json={"position": 1, "verify": "Thanks for having me, it is", "slot": "o7"})
        assert bad.status_code == 409
        bad = client.post("/api/projects/1/transcripts/s1/reassign",
                          json={"position": 1, "verify": "other words", "slot": "m1"})
        assert bad.status_code == 409
        bad = client.post("/api/projects/1/transcripts/s1/reassign",
                          json={"position": 1, "verify": "Thanks for having me, it is", "slot": "p1"})
        assert bad.status_code == 409, "already that speaker's"

    def test_a_moved_paragraph_is_not_joined_to_the_speakers_own(self, tmp_path: Path) -> None:
        """Joining would lose whose words they were, and the quote would count again."""
        from tests.test_serve_participant_recode import _quote_ids, _with_quotes

        client = _client(_with_quotes(tmp_path))
        _reassign(client, 1, "Thanks for having me, it is", "m1")
        resp = client.post("/api/projects/1/transcripts/s1/join",
                           json={"position": 1, "verify": "Thanks for having me, it is"})
        assert resp.status_code == 409
        assert "q-p1-10" not in _quote_ids(client)


class TestReassignToANewModerator:
    """§K: a call collapsed into one voice has no moderator to move a paragraph
    to, so Paragraph scope can make one — an unknown moderator, named later."""

    V = "Thanks for having me, it is"

    def _new(self, client: TestClient) -> int:
        resp = client.post("/api/projects/1/transcripts/s1/reassign",
                           json={"position": 1, "verify": self.V, "new": "moderator"})
        assert resp.status_code == 200, resp.text
        return resp.json()["id"]

    def _s1(self, client: TestClient) -> list[str]:
        sessions = client.get("/api/projects/1/sessions").json()["sessions"]
        return sorted(sp["slot_code"] for s in sessions if s["session_id"] == "s1" for sp in s["speakers"])

    def test_it_makes_an_unknown_moderator_and_moves_the_paragraph(self, tmp_path: Path) -> None:
        from tests.test_serve_participant_recode import _quote_ids, _with_quotes

        client = _client(_with_quotes(tmp_path))
        self._new(client)
        assert self._s1(client) == ["m1", "m2", "p1"]
        # Unknown, and lettered beside the session's other moderator (§J8.9).
        assert _segments(client)[1]["speaker_code"] == "mB?"
        assert _segments(client)[1]["is_moderator"] is True
        assert "q-p1-10" not in _quote_ids(client)

    def test_it_survives_a_re_import_that_drops_unheard_moderators(self, tmp_path: Path) -> None:
        from tests.test_serve_participant_recode import _with_quotes

        project = _with_quotes(tmp_path)
        client = _client(project)
        self._new(client)
        _reimport(client, project)
        assert self._s1(client) == ["m1", "m2", "p1"]
        assert _segments(client)[1]["speaker_code"] == "mB?"

    def test_undo_takes_the_new_moderator_away_too(self, tmp_path: Path) -> None:
        from tests.test_serve_participant_recode import _quote_ids, _with_quotes

        client = _client(_with_quotes(tmp_path))
        edit = self._new(client)
        client.delete(f"/api/projects/1/transcripts/s1/layout-edits/{edit}")
        assert self._s1(client) == ["m1", "p1"]
        assert "q-p1-10" in _quote_ids(client)

    def test_it_never_lands_on_a_speaker_a_later_run_hears(self, tmp_path: Path) -> None:
        """A re-run hears a second moderator and issues them m2: the move made
        for an unknown m2 is refused, not credited to that real person."""
        from tests.test_serve_participant_recode import _with_quotes

        project = _with_quotes(tmp_path)
        client = _client(project)
        self._new(client)
        raw = project / "bristlenose-output" / "transcripts-raw" / "s1.txt"
        text = raw.read_text(encoding="utf-8")
        assert "[m1] Shall we" in text
        raw.write_text(text.replace("[m1] Shall we", "[m2] Shall we"), encoding="utf-8")
        _reimport(client, project)
        segs = _segments(client)
        assert segs[1]["speaker_code"] == "p1", "the move was refused, the words stay p1's"

    def test_it_is_numbered_above_every_code_the_pipeline_issued(self, tmp_path: Path) -> None:
        from tests.test_serve_participant_recode import _registry, _with_quotes

        project = _with_quotes(tmp_path)
        _registry(project, {"s1": {"Me": "m1", "Wylie": "p1", "Gone": "m4"}})
        client = _client(project)
        self._new(client)
        assert "m5" in self._s1(client)


class TestSplitKeepsTheTextsOwnSpelling:
    """A timed paragraph is cut where the researcher sees it, in Whisper's
    words, but its text keeps its own case and punctuation (6 Oct 2026: split
    used to rebuild the text from the words, lower-cased and unpunctuated)."""

    # From a real platform transcript: the words start mid-sentence, are lower
    # case, carry no punctuation and know nothing of "(Speaker B)".
    TEXT = ("(Speaker B) Interesting that you clicked on that, but you told me you would go "
            "straight to search. Yes. Well, because that's it.")
    WORDS = "told me you would go straight to search um yes well because that's it".split()

    def test_the_text_is_cut_at_the_aligned_word(self) -> None:
        from bristlenose.server.transcript_layout import text_cut

        at = text_cut(self.TEXT, self.WORDS, self.WORDS.index("yes"))
        assert self.TEXT[:at].rstrip().endswith("go straight to search.")
        assert self.TEXT[at:] == "Yes. Well, because that's it."

    def test_a_word_with_no_partner_moves_the_cut_to_the_next_that_has_one(self) -> None:
        from bristlenose.server.transcript_layout import text_cut

        # "um" is not in the text: cutting before it lands before "Yes."
        at = text_cut(self.TEXT, self.WORDS, self.WORDS.index("um"))
        assert self.TEXT[at:].startswith("Yes.")

    def test_with_nothing_aligned_the_cut_falls_by_share(self) -> None:
        from bristlenose.server.transcript_layout import text_cut

        text = "uno dos tres cuatro"
        assert text[text_cut(text, ["a", "b", "c", "d"], 2):] == "tres cuatro"

    def test_a_split_through_the_api_keeps_both_halves_spelling(self, tmp_path: Path) -> None:
        from bristlenose.server.models import TranscriptSegment

        client = _client(_project(tmp_path, _TWO))
        db = client.app.state.db_factory()
        try:
            seg = db.query(TranscriptSegment).filter_by(speaker_code="p1").first()
            seg.text = "Thanks for having me, it is good to be here."
            words = "thanks for having me it is good to be here".split()
            seg.words_json = json.dumps(
                [{"t": w, "s": 10.0 + i, "e": 10.5 + i} for i, w in enumerate(words)])
            db.commit()
        finally:
            db.close()
        _split(client, 1, 4, "it is good to be here")
        assert [t for _, t in _texts(client)][1:3] == [
            "Thanks for having me,", "it is good to be here.",
        ]


def test_the_transcript_carries_the_sessions_language(tmp_path: Path) -> None:
    """The page sets it as the paragraphs' lang, so a drawn capital follows the
    language (Turkish i → İ); None when nothing knew it."""
    from bristlenose.server.models import Session as SessionModel

    client = _client(_project(tmp_path, _TWO))
    assert client.get("/api/projects/1/transcripts/s1").json()["language"] is None
    db = client.app.state.db_factory()
    try:
        db.query(SessionModel).filter_by(session_id="s1").one().language = "tr"
        db.commit()
    finally:
        db.close()
    assert client.get("/api/projects/1/transcripts/s1").json()["language"] == "tr"
