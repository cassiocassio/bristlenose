"""An inaudible segment is a gap, not words: it survives paragraph merging and
the transcript files' round trip as a flag, and is never joined to speech."""

from __future__ import annotations

from datetime import datetime, timezone

from bristlenose.models import INAUDIBLE_TOKEN, FullTranscript, TranscriptSegment
from bristlenose.pipeline import load_transcripts_from_dir
from bristlenose.stages.s06_merge_transcript import (
    _merge_same_speaker,
    write_raw_transcripts,
    write_raw_transcripts_md,
)


def _seg(start: float, end: float, text: str = "", *, inaudible: bool = False) -> TranscriptSegment:
    return TranscriptSegment(
        start_time=start, end_time=end, text=text, inaudible=inaudible,
        speaker_label="Speaker A", speaker_code="p1",
    )


def _transcript(segments: list[TranscriptSegment]) -> FullTranscript:
    return FullTranscript(
        session_id="s1", participant_id="p1", source_file="s1.wav",
        session_date=datetime(2026, 10, 12, tzinfo=timezone.utc),
        duration_seconds=60.0, segments=segments,
    )


class TestMerge:
    def test_a_gap_is_never_joined_to_speech(self) -> None:
        merged = _merge_same_speaker([
            _seg(0, 2, "We bought the sofa."),
            _seg(2, 5, inaudible=True),
            _seg(5, 7, "It was in May."),
        ])
        assert [(m.text, m.inaudible) for m in merged] == [
            ("We bought the sofa.", False), ("", True), ("It was in May.", False),
        ]

    def test_two_gaps_side_by_side_become_one(self) -> None:
        merged = _merge_same_speaker([_seg(2, 5, inaudible=True), _seg(5, 9, inaudible=True)])
        assert [(m.start_time, m.end_time, m.text, m.inaudible) for m in merged] == [
            (2, 9, "", True),
        ]


class TestTranscriptFiles:
    def test_the_flag_round_trips_and_the_token_is_never_text(self, tmp_path) -> None:
        write_raw_transcripts([_transcript([
            _seg(0, 2, "We bought the sofa."), _seg(2, 5, inaudible=True),
        ])], tmp_path)
        assert INAUDIBLE_TOKEN in (tmp_path / "s1.txt").read_text()

        [loaded] = load_transcripts_from_dir(tmp_path)
        assert [(s.inaudible, s.text) for s in loaded.segments] == [
            (False, "(Speaker A) We bought the sofa."), (True, ""),
        ]

    def test_markdown_carries_the_token_unescaped(self, tmp_path) -> None:
        write_raw_transcripts_md([_transcript([_seg(2, 5, inaudible=True)])], tmp_path)
        assert f" {INAUDIBLE_TOKEN}" in (tmp_path / "s1.md").read_text()


class TestServe:
    """The importer stores the token as the flag; the page gets a gap, not words."""

    def _client(self, tmp_path):
        from tests.test_serve_moderator_identities import _TWO, _client, _project

        project = _project(tmp_path, _TWO)
        raw = project / "bristlenose-output" / "transcripts-raw" / "s1.txt"
        text = raw.read_text(encoding="utf-8")
        gapped = text.replace("[00:20] [m1]", f"[00:15] [p1] (Speaker B) {INAUDIBLE_TOKEN}\n[00:20] [m1]")
        assert gapped != text
        raw.write_text(gapped, encoding="utf-8")
        return _client(project)

    def test_the_gap_reaches_the_page_as_a_flag_with_no_text(self, tmp_path) -> None:
        segs = self._client(tmp_path).get("/api/projects/1/transcripts/s1").json()["segments"]
        assert [(s["start_time"], s["end_time"], s["text"], s["inaudible"]) for s in segs][1:3] == [
            (10.0, 15.0, "Thanks for having me, it is good to be here.", False),
            (15.0, 20.0, "", True),
        ]

    def test_a_gap_is_not_joined_to_speech(self, tmp_path) -> None:
        client = self._client(tmp_path)
        resp = client.post("/api/projects/1/transcripts/s1/join", json={"position": 2, "verify": ""})
        assert resp.status_code == 409


def test_017_adds_the_inaudible_column_on_a_016_database(tmp_path) -> None:
    import sqlalchemy as sa

    from bristlenose.server.db import init_db, run_migrations

    engine = sa.create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    init_db(engine)
    with engine.connect() as conn:
        conn.execute(sa.text("ALTER TABLE transcript_segments DROP COLUMN inaudible"))
        conn.execute(sa.text("UPDATE alembic_version SET version_num = '016'"))
        conn.commit()
    run_migrations(engine)
    with engine.connect() as conn:
        assert "inaudible" in {c["name"] for c in sa.inspect(conn).get_columns("transcript_segments")}


def test_an_ordinary_segment_dumps_exactly_as_before() -> None:
    """The stage fingerprints hash the dump: a new key would re-run, and bill,
    speaker identification, topics and quotes on every existing project."""
    seg = TranscriptSegment(start_time=0, end_time=1, text="Hi.")
    assert "inaudible" not in seg.model_dump(mode="json")
    gap = TranscriptSegment(start_time=0, end_time=1, text="", inaudible=True)
    assert TranscriptSegment.model_validate(gap.model_dump()).inaudible


def test_a_gap_is_neither_covered_nor_omitted() -> None:
    """Coverage counts words; a gap has none, and must not appear as an empty
    "also omitted" fragment."""
    from bristlenose.coverage import calculate_coverage

    stats = calculate_coverage([_transcript([
        _seg(0, 2, "We bought the sofa in May, after a long search."), _seg(2, 5, inaudible=True),
    ])], [])
    omitted = stats.omitted_by_session["s1"]
    assert [f for f, _ in omitted.fragment_counts] == []


def test_a_gap_is_not_split(tmp_path) -> None:
    client = TestServe()._client(tmp_path)
    resp = client.post("/api/projects/1/transcripts/s1/split",
                       json={"position": 2, "token": 1, "verify": ""})
    assert resp.status_code == 409


def test_the_redacted_files_carry_the_gap_and_the_importer_reads_it(tmp_path) -> None:
    """With redaction on, serve imports the cooked files, so they carry the gap
    too. An empty line there once took the next line as its words."""
    from bristlenose.models import PiiCleanTranscript
    from bristlenose.server.importer import _SEGMENT_RE
    from bristlenose.stages.s07_pii_removal import write_cooked_transcripts

    gap = _seg(15, 20, inaudible=True)
    after = TranscriptSegment(start_time=20, end_time=22, text="Shall we start?", speaker_code="m1")
    t = PiiCleanTranscript(**_transcript([_seg(10, 15, "Hi."), gap, after]).model_dump())
    write_cooked_transcripts([t], tmp_path)
    text = (tmp_path / "s1.txt").read_text()

    assert [s.inaudible for s in load_transcripts_from_dir(tmp_path)[0].segments] == [
        False, True, False,
    ]
    assert [m[1:] for m in _SEGMENT_RE.findall(text)] == [
        ("p1", "Hi."), ("p1", INAUDIBLE_TOKEN), ("m1", "Shall we start?"),
    ]
    # And an empty line never swallows the next one.
    assert _SEGMENT_RE.findall("[00:15] [p1] \n[00:20] [m1] Shall we start?") == [
        ("00:20", "m1", "Shall we start?"),
    ]


def test_a_transcribers_aside_beside_the_token_stays_words(tmp_path) -> None:
    """With the session's labels known, only the bare token is a gap: a human
    transcript's "(laughs) [inaudible]" keeps its aside."""
    from tests.test_importer_speaker_labels import _info
    from tests.test_serve_moderator_identities import _TWO, _client, _project

    project = _project(tmp_path, _TWO)
    out = project / "bristlenose-output"
    raw = out / "transcripts-raw" / "s1.txt"
    raw.write_text(raw.read_text().replace(
        "[00:20] [m1]",
        "[00:14] [p1] (Speaker B) (laughs) [inaudible]\n"
        "[00:15] [p1] (Speaker B) [inaudible]\n[00:20] [m1]",
    ))
    _info(out, "s1", ["Speaker A", "Speaker B"], [])
    segs = _client(project).get("/api/projects/1/transcripts/s1").json()["segments"]
    assert [(s["text"], s["inaudible"]) for s in segs][2:4] == [
        ("(laughs) [inaudible]", False), ("", True),
    ]
