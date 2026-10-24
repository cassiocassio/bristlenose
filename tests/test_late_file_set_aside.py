"""A file that joins an already-analysed session later is set aside (decision #129).

Owner, 23 Oct 2026: for v1 an analysed session keeps exactly the input files it
was analysed from. Until then a file that ingest folded into an analysed session
changed it under the researcher's feet (measured by RE#114 on this rig):

- **Case A**, a transcript beside an analysed recording (``Interview 3.vtt``
  beside ``Interview 3.mp4``, or a ``.vtt`` dropped into a Zoom folder): ``run``
  replaced the transcript, re-paid the session and the study-wide clustering,
  renumbered its speakers (the registry keys codes by label, and the VTT names
  people where Whisper said "Speaker B"), duplicated every curated quote as an
  uncurated twin, brought a hidden quote back and left a phantom participant.
- **Case B**, a recording joining a Zoom folder: Whisper ran again.

Now the late file is set aside at ingest: not read, not in the session's
fingerprint, and named on the run's summary with its reason. A new session, and
a fresh start (``--clean``), read everything as before.

The rig is ``tests/lifecycle_rig.py`` — the real ``bristlenose run`` (real
ingest over real files, the session registry, the manifest, the VTT parser) and
the real serve — with fakes that know who is speaking, so a change of
transcript shows up as a change of speaker codes and of quotes. No LLM is
called: every paid stage is a fake that records which sessions it was sent.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from bristlenose.events import StageOutcome
from bristlenose.models import (
    FileType,
    PiiCleanTranscript,
    SessionTopicMap,
    SpeakerRole,
    TranscriptSegment,
)
from bristlenose.refusals import MESSAGES, UnusableReason
from tests.conftest import iter_transcribe_from
from tests.lifecycle_rig import Study, _cli_app, _quiet_cli
from tests.test_serve_project_root import fast_watcher as fast_watcher  # noqa: F401

LINES = [
    "Welcome, thanks for joining us today, shall we begin with the dashboard?",
    "Sure, I open the dashboard every morning to check the review queue first thing.",
    "Tell me about what you check first and why that matters to you.",
    "Honestly the queue is the only thing I trust, the charts always look stale.",
    "What would make the charts more useful for your morning routine?",
    "If they showed me what changed overnight I would actually read them every day.",
]

ZOOM = "2026-10-02 13.33.12 Talismanic interview"


def _whisper(name: str) -> list[TranscriptSegment]:
    return [
        TranscriptSegment(start_time=float(i * 20), end_time=float(i * 20 + 18),
                          text=f"{t} [{name}]", speaker_label=None, source="whisper")
        for i, t in enumerate(LINES)
    ]


def _vtt(path: Path, names: tuple[str, str] = ("Mod Mia", "Pat")) -> None:
    """A Teams-style transcript of the same interview, naming its speakers."""

    def ts(x: float) -> str:
        return f"00:{int(x // 60):02d}:{x % 60:06.3f}"

    cues = [
        f"{ts(i * 20)} --> {ts(i * 20 + 18)}\n<v {names[i % 2]}>{t}</v>\n"
        for i, t in enumerate(LINES)
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("WEBVTT\n\n" + "\n".join(cues), encoding="utf-8")


@dataclass
class Rig(Study):
    #: Per run: which sessions each paid stage was sent.
    log: list[dict] = field(default_factory=list)

    def run(self, *, clean: bool = False, fail=None, command: str = "run") -> None:  # noqa: ARG002
        rec: dict = {"transcribed": [], "split": [], "roles": [], "topics": [], "quotes": [],
                     "ffmpeg": 0}

        def _ffmpeg(**_kw):
            rec["ffmpeg"] += 1

        async def _stage2(sessions, _tmp, **_kw):
            # As the real stage 2: an audio file is used, a session with a
            # transcript file is not decoded, a video stands in for its audio.
            for s in sessions:
                usable = [f for f in s.files if f.error is None]
                aud = [f for f in usable if f.file_type == FileType.AUDIO]
                vid = [f for f in usable if f.file_type == FileType.VIDEO]
                if aud:
                    s.audio_path = aud[0].path
                elif s.has_existing_transcript:
                    continue
                elif vid:
                    s.audio_path = vid[0].path
            return sessions

        def _transcribe(sessions, _settings, **_kw):
            names = [Path(s.audio_path or s.files[0].path).name for s in sessions]
            rec["transcribed"].extend(names)
            return ({s.session_id: _whisper(n) for s, n in zip(sessions, names, strict=True)},
                    {}, StageOutcome(attempted=len(sessions), succeeded=len(sessions)))

        async def _split(segments, _client, errors=None):
            rec["split"].append(len(segments))
            for i, seg in enumerate(segments):
                seg.speaker_label = "Speaker A" if i % 2 == 0 else "Speaker B"
            return segments

        async def _roles(segments, _client, errors=None):
            rec["roles"].append(sorted({s.speaker_label or "" for s in segments}))
            for seg in segments:
                lab = seg.speaker_label or ""
                seg.speaker_role = (SpeakerRole.RESEARCHER
                                    if lab == "Speaker A" or lab.startswith("Mod")
                                    else SpeakerRole.PARTICIPANT)
            return []

        async def _topics(transcripts, *_a, **_kw):
            rec["topics"].extend(t.session_id for t in transcripts)
            maps = [SessionTopicMap(session_id=t.session_id, participant_id=t.participant_id,
                                    boundaries=[]) for t in transcripts]
            return maps, StageOutcome(attempted=len(maps), succeeded=len(maps))

        async def _quotes(transcripts, *_a, **_kw):
            from bristlenose.models import (
                EmotionalTone,
                ExtractedQuote,
                JourneyStage,
                QuoteIntent,
                QuoteType,
            )

            assert all(isinstance(t, PiiCleanTranscript) for t in transcripts)
            rec["quotes"].extend(t.session_id for t in transcripts)
            out = [
                ExtractedQuote(
                    session_id=t.session_id, participant_id=seg.speaker_code,
                    start_timecode=seg.start_time, end_timecode=seg.end_time,
                    text=seg.text, verbatim_excerpt=seg.text, topic_label="general",
                    quote_type=QuoteType.GENERAL_CONTEXT, researcher_context="",
                    intent=QuoteIntent.NARRATION, emotion=EmotionalTone.NEUTRAL,
                    journey_stage=JourneyStage.OTHER,
                )
                for t in transcripts for seg in t.segments
                if seg.speaker_code.startswith("p")
            ]
            return out, StageOutcome(attempted=len(transcripts), succeeded=len(transcripts))

        async def _cluster(quotes, *_a, **_kw):
            from bristlenose.models import ScreenCluster

            return [ScreenCluster(screen_label="Dashboard", description="", display_order=1,
                                  quotes=list(quotes))], StageOutcome(attempted=1, succeeded=1)

        async def _empty(*_a, **_kw):
            return [], StageOutcome(attempted=1, succeeded=1)

        targets = {
            "bristlenose.stages.s02_extract_audio.extract_audio_for_sessions": _stage2,
            "bristlenose.preflight.whisper.preflight_whisper": lambda **_kw: None,
            "bristlenose.preflight.ffmpeg.preflight_ffmpeg": _ffmpeg,
            "bristlenose.stages.s05_transcribe.iter_transcribe_sessions":
                iter_transcribe_from(_transcribe),
            "bristlenose.stages.s05b_identify_speakers.split_single_speaker_llm": _split,
            "bristlenose.stages.s05b_identify_speakers.identify_speaker_roles_llm": _roles,
            "bristlenose.stages.s08_topic_segmentation.segment_topics": _topics,
            "bristlenose.stages.s09_quote_extraction.extract_quotes": _quotes,
            "bristlenose.stages.s10_quote_clustering.cluster_by_screen": _cluster,
            "bristlenose.stages.s11_thematic_grouping.group_by_theme": _empty,
        }
        args = (["run", str(self.folder), "--no-serve", "--llm", "claude"]
                if command == "run" else [command, str(self.folder)])
        if clean:
            args += ["--clean", "--yes"]
        with _quiet_cli():
            stack = [patch(t, new=f) for t, f in targets.items()]
            stack.append(patch("bristlenose.llm.client.LLMClient", MagicMock()))
            for p in stack:
                p.start()
            try:
                result = CliRunner().invoke(_cli_app(), args, catch_exceptions=False)
            finally:
                for p in reversed(stack):
                    p.stop()
        self.log.append(rec)
        self.transcribed.append(rec["transcribed"])
        self.last_output = result.output
        assert result.exit_code == 0, f"run exited {result.exit_code}:\n{result.output}"

    # ── evidence ───────────────────────────────────────────────────────────

    @property
    def out(self) -> Path:
        return self.folder / "bristlenose-output"

    def registry_speakers(self, sid: str) -> dict[str, str]:
        reg = json.loads((self.out / ".bristlenose" / "sessions.json").read_text())
        return reg.get("speakers", {}).get(sid, {})

    def raw(self, sid: str) -> str:
        return (self.out / "transcripts-raw" / f"{sid}.txt").read_text(encoding="utf-8")

    def db_quotes(self, sid: str) -> list[tuple]:
        con = sqlite3.connect(self.out / ".bristlenose" / "bristlenose.db")
        try:
            return con.execute(
                """SELECT q.participant_id, q.start_timecode, q.text,
                          COALESCE(s.is_starred, 0), COALESCE(s.is_hidden, 0),
                          (SELECT group_concat(td.name) FROM quote_tags qt
                             JOIN tag_definitions td ON td.id = qt.tag_definition_id
                            WHERE qt.quote_id = q.id)
                     FROM quotes q LEFT JOIN quote_states s ON s.quote_id = q.id
                    WHERE q.session_id = ?
                    ORDER BY q.start_timecode, q.participant_id""", (sid,),
            ).fetchall()
        finally:
            con.close()

    def set_aside(self) -> list[tuple[str, str | None]]:
        """The last run's summary rows for files set aside: (file, reason)."""
        rows = (self.last_summary().get("ingest") or {}).get("failed") or []
        return [(r.get("source_file"), (r.get("cause") or {}).get("reason")) for r in rows]


def new_rig(tmp_path: Path, *recordings: str) -> Rig:
    folder = tmp_path / "Studies" / "Talismanic"
    folder.mkdir(parents=True)
    work = tmp_path / "work"
    work.mkdir()
    rig = Rig(folder=folder, work=work)
    for name in recordings:
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"RIFF fake recording " + name.encode() * 64)
    return rig


LATE = UnusableReason.ADDED_AFTER_ANALYSIS


def _said_set_aside(rig: Rig, name: str) -> None:
    """The file is on the summary, with its reason, and in the terminal."""
    assert (name, LATE.value) in rig.set_aside(), rig.set_aside()
    flat = re.sub(r"\s+", " ", rig.last_output)
    assert name in flat, rig.last_output
    assert re.sub(r"\s+", " ", MESSAGES[LATE]) in flat, rig.last_output


def _nothing_paid(rig: Rig) -> None:
    rec = rig.log[-1]
    assert rec["transcribed"] == [], rec
    assert rec["split"] == [] and rec["roles"] == [], rec
    assert rec["topics"] == [] and rec["quotes"] == [], rec


# ── Case A: a transcript joins an analysed recording ────────────────────────


def test_a_transcript_beside_an_analysed_video_is_set_aside(tmp_path: Path, fast_watcher) -> None:
    rig = new_rig(tmp_path, "Interview 1.wav", "Interview 2.wav", "Interview 3.mp4")
    with rig.serve() as client:
        rig.run()
        rig.sessions(client, expect=3)
        ids = [q for q in rig.quote_ids(client) if q.startswith("q-p3-")]
        star, tag, hide = ids[0], ids[1], ids[2]
        assert client.patch("/api/projects/1/starred", json={star: True}).status_code == 200
        assert client.patch("/api/projects/1/tags",
                            json={tag: {"add": ["pain-point"], "remove": []}}).status_code == 200
        assert client.patch("/api/projects/1/hidden", json={hide: True}).status_code == 200
        speakers_before = rig.registry_speakers("s3")
        raw_before = rig.raw("s3")
        quotes_before = rig.db_quotes("s3")

        _vtt(rig.folder / "Interview 3.vtt")
        rig.run()
        rig.sessions(client, expect=3)

        _said_set_aside(rig, "Interview 3.vtt")
        _nothing_paid(rig)
        # The session is what it was: its transcript, its speakers, its quotes
        # and their curation — no twin, no phantom participant, no hide undone.
        assert rig.raw("s3") == raw_before
        assert rig.registry_speakers("s3") == speakers_before
        assert "Mod Mia" not in rig.registry_speakers("s3")
        assert rig.db_quotes("s3") == quotes_before
        assert client.get("/api/projects/1/hidden").json().get(hide), "the hide stands"
        # And the next run with nothing new still sets it aside, paying nothing.
        rig.run()
        _said_set_aside(rig, "Interview 3.vtt")
        _nothing_paid(rig)


def test_a_transcript_dropped_into_an_analysed_zoom_folder_is_set_aside(
    tmp_path: Path, fast_watcher,
) -> None:
    rig = new_rig(tmp_path, "Interview 1.wav", f"{ZOOM}/audio1234567890.m4a",
                  f"{ZOOM}/video1234567890.mp4")
    rig.run()
    _vtt(rig.folder / ZOOM / "closed_caption.vtt")
    rig.run()
    _said_set_aside(rig, "closed_caption.vtt")
    _nothing_paid(rig)


# ── Case B: a recording joins an analysed Zoom folder ───────────────────────


@pytest.mark.parametrize("added", [
    "Audio Record/audioPat21234567890.m4a", "video2_1234567890.mp4",
], ids=["participant-track", "second-video"])
def test_a_recording_added_to_an_analysed_zoom_folder_is_not_transcribed(
    tmp_path: Path, fast_watcher, added: str,
) -> None:
    rig = new_rig(tmp_path, "Interview 1.wav", f"{ZOOM}/audio1234567890.m4a",
                  f"{ZOOM}/video1234567890.mp4")
    rig.run()
    path = rig.folder / ZOOM / added
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"RIFF a late recording" * 99)
    rig.run()
    _said_set_aside(rig, path.name)
    _nothing_paid(rig)


def test_a_video_beside_an_analysed_audio_file_is_set_aside(
    tmp_path: Path, fast_watcher,
) -> None:
    """The video would name the session (a video before an audio file), and the
    session — keyed by its audio's content — would be found by nothing and
    analysed again as a new one. It keeps its number and its recording."""
    rig = new_rig(tmp_path, "Interview 1.wav", "Interview 2.wav")
    rig.run()
    speakers = rig.registry_speakers("s2")
    (rig.folder / "Interview 2.mp4").write_bytes(b"RIFF a later video" * 64)
    rig.run()
    _said_set_aside(rig, "Interview 2.mp4")
    _nothing_paid(rig)
    assert rig.log[-1]["ffmpeg"] == 0, "no video is used, so ffmpeg is not needed"
    reg = json.loads((rig.out / ".bristlenose" / "sessions.json").read_text())
    assert sorted(set(reg["sessions"].values())) == ["s1", "s2"], reg["sessions"]
    assert rig.registry_speakers("s2") == speakers


def test_transcribe_leaves_the_late_file_out_too(tmp_path: Path, fast_watcher) -> None:
    """``transcribe`` reuses run's transcription per session (R115), so it
    must agree with run on what the session is made from."""
    rig = new_rig(tmp_path, "Interview 1.wav", "Interview 2.mp4")
    rig.run()
    _vtt(rig.folder / "Interview 2.vtt")
    rig.run(command="transcribe")
    assert rig.log[-1]["transcribed"] == [], "nothing Whispered or re-read"
    flat = re.sub(r"\s+", " ", rig.last_output)
    assert "Interview 2.vtt" in flat and re.sub(r"\s+", " ", MESSAGES[LATE]) in flat, flat
    assert "Mod Mia" not in rig.raw("s2")


# ── What the freeze leaves alone ────────────────────────────────────────────


def test_a_recording_joining_a_transcript_only_session_is_not_set_aside(
    tmp_path: Path, fast_watcher,
) -> None:
    """Judgement call (RE#129, pending the owner): a session analysed from its
    transcript alone still reads that transcript when its recording arrives, so
    nothing it was analysed from changes; the recording joins it, as before."""
    rig = new_rig(tmp_path, "Interview 1.wav")
    _vtt(rig.folder / "Interview 2.vtt")
    rig.run()
    speakers, raw = rig.registry_speakers("s2"), rig.raw("s2")
    (rig.folder / "Interview 2.mp4").write_bytes(b"RIFF the recording" * 64)
    rig.run()
    assert rig.set_aside() == []
    _nothing_paid(rig)
    assert rig.registry_speakers("s2") == speakers
    assert rig.raw("s2") == raw


def test_a_new_session_reads_its_transcript(tmp_path: Path, fast_watcher) -> None:
    """A recording and its transcript arriving together form a new session,
    which is analysed from the transcript as ever."""
    rig = new_rig(tmp_path, "Interview 1.wav", "Interview 2.wav")
    rig.run()
    (rig.folder / "Interview 3.mp4").write_bytes(b"RIFF new recording" * 64)
    _vtt(rig.folder / "Interview 3.vtt")
    rig.run()
    assert rig.set_aside() == []
    assert rig.log[-1]["transcribed"] == [], "the transcript was read, not Whisper"
    assert "Mod Mia" in rig.registry_speakers("s3")
    assert rig.log[-1]["quotes"] == ["s3"]


def test_a_fresh_start_reads_the_late_transcript(tmp_path: Path, fast_watcher) -> None:
    """Re-analyse (``--clean``) starts again from every file in the folder."""
    rig = new_rig(tmp_path, "Interview 1.wav", "Interview 2.mp4")
    rig.run()
    _vtt(rig.folder / "Interview 2.vtt")
    rig.run()
    _said_set_aside(rig, "Interview 2.vtt")
    rig.run(clean=True)
    assert rig.set_aside() == []
    assert "Mod Mia" in rig.registry_speakers("s2")
    assert "<v " not in rig.raw("s2") and "Pat" in rig.raw("s2")


def test_an_edited_transcript_is_read_again(tmp_path: Path, fast_watcher) -> None:
    """Editing a file the session was analysed from is not a file joining it:
    the session is read again, as before (#58)."""
    rig = new_rig(tmp_path, "Interview 1.wav")
    _vtt(rig.folder / "Interview 2.vtt")
    rig.run()
    _vtt(rig.folder / "Interview 2.vtt", names=("Mod Mia", "Sam"))
    rig.run()
    assert rig.set_aside() == []
    assert "Sam" in rig.registry_speakers("s2")


# ── The search itself: which files a session was analysed from ──────────────


def _file(path: Path, data: bytes) -> object:
    from datetime import datetime, timezone

    from bristlenose.models import InputFile
    from bristlenose.stages.s01_ingest import classify_file

    path.write_bytes(data)
    return InputFile(path=path, file_type=classify_file(path),
                     created_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
                     size_bytes=len(data))


def _session(sid: str, *files) -> object:
    from datetime import datetime, timezone

    from bristlenose.models import InputSession

    return InputSession(
        session_id=sid, session_number=int(sid[1:]), participant_id=f"p{sid[1:]}",
        participant_number=int(sid[1:]), files=list(files),
        has_existing_transcript=any(
            f.file_type in (FileType.SUBTITLE_VTT, FileType.SUBTITLE_SRT, FileType.DOCX)
            for f in files),
        session_date=datetime(2026, 10, 1, tzinfo=timezone.utc),
    )


def _analysed(tmp_path: Path, session, *, quotes: bool = True):
    """A previous manifest that analysed ``session`` from the files it holds now."""
    from bristlenose.manifest import (
        STAGE_QUOTE_EXTRACTION,
        STAGE_TRANSCRIBE,
        create_manifest,
        mark_session_complete,
        mark_session_failed,
    )
    from bristlenose.pipeline import _session_input_fingerprint

    m = create_manifest("t", "0")
    mark_session_complete(m, STAGE_TRANSCRIBE, session.session_id,
                          input_hash=_session_input_fingerprint(session, tmp_path))
    if quotes:
        mark_session_complete(m, STAGE_QUOTE_EXTRACTION, session.session_id)
    else:
        mark_session_failed(m, STAGE_QUOTE_EXTRACTION, session.session_id)
    return m


def _freeze(tmp_path: Path, session, manifest) -> list[str]:
    from bristlenose.pipeline import _set_aside_late_files
    from bristlenose.session_registry import SessionRegistry

    _set_aside_late_files([session], manifest, tmp_path,
                          SessionRegistry(path=tmp_path / "sessions.json"))
    return [f.path.name for f in session.files if f.error == LATE.value]


def test_a_session_whose_quotes_failed_is_not_analysed(tmp_path: Path) -> None:
    mp4 = _file(tmp_path / "a.mp4", b"RIFF a" * 64)
    m = _analysed(tmp_path, _session("s1", mp4), quotes=False)
    late = _session("s1", mp4, _file(tmp_path / "a.vtt", b"WEBVTT\n\n"))
    assert _freeze(tmp_path, late, m) == []
    assert late.has_existing_transcript


def test_an_edited_file_is_not_an_addition(tmp_path: Path) -> None:
    mp4 = _file(tmp_path / "a.mp4", b"RIFF a" * 64)
    m = _analysed(tmp_path, _session("s1", mp4, _file(tmp_path / "a.vtt", b"WEBVTT\n\nold")))
    edited = _session("s1", mp4, _file(tmp_path / "a.vtt", b"WEBVTT\n\nnew"),
                      _file(tmp_path / "a.srt", b"1\n"))
    assert _freeze(tmp_path, edited, m) == []


def test_the_analysed_files_are_kept_and_the_session_reads_as_before(tmp_path: Path) -> None:
    mp4 = _file(tmp_path / "a.mp4", b"RIFF a" * 64)
    m = _analysed(tmp_path, _session("s1", mp4))
    s = _session("s1", _file(tmp_path / "a.srt", b"1\n"), mp4,
                 _file(tmp_path / "a.vtt", b"WEBVTT\n\n"))
    assert sorted(_freeze(tmp_path, s, m)) == ["a.srt", "a.vtt"]
    assert not s.has_existing_transcript, "the session is a recording again"
    assert s.files[0].path.name == "a.mp4", "a kept file names the transcript's source"


def test_of_two_identical_files_the_one_listed_last_is_set_aside(tmp_path: Path) -> None:
    mp4 = _file(tmp_path / "a.mp4", b"RIFF a" * 64)
    vtt = _file(tmp_path / "a.vtt", b"WEBVTT\n\nsame")
    m = _analysed(tmp_path, _session("s1", mp4, vtt))
    s = _session("s1", mp4, vtt, _file(tmp_path / "a copy.vtt", b"WEBVTT\n\nsame"))
    assert _freeze(tmp_path, s, m) == ["a copy.vtt"]


def test_a_search_past_its_bound_reads_everything(tmp_path: Path, monkeypatch) -> None:
    from bristlenose import pipeline

    mp4 = _file(tmp_path / "a.mp4", b"RIFF a" * 64)
    m = _analysed(tmp_path, _session("s1", mp4))
    s = _session("s1", mp4, _file(tmp_path / "a.vtt", b"WEBVTT\n\n"),
                 _file(tmp_path / "a.srt", b"1\n"))
    monkeypatch.setattr(pipeline, "_LATE_FILE_SEARCH_BOUND", 2)
    assert _freeze(tmp_path, s, m) == []


def test_a_placeholder_with_no_fingerprint_beside_the_analysed_set_is_set_aside(
    tmp_path: Path, monkeypatch,
) -> None:
    from bristlenose.utils import fingerprint

    mp4 = _file(tmp_path / "a.mp4", b"RIFF a" * 64)
    m = _analysed(tmp_path, _session("s1", mp4))
    s = _session("s1", mp4, _file(tmp_path / "a.vtt", b"WEBVTT\n\n"))
    real = fingerprint.content_fingerprint
    monkeypatch.setattr(fingerprint, "content_fingerprint",
                        lambda p: None if p.suffix == ".vtt" else real(p))
    assert _freeze(tmp_path, s, m) == ["a.vtt"]


def test_a_set_aside_file_does_not_date_the_session(tmp_path: Path) -> None:
    """A late file's name or clock is not the session's: its start comes from
    the files it keeps (the registry then keeps the start it already has)."""
    from bristlenose.utils.session_start import resolve_session_start

    wav = _file(tmp_path / "a.wav", b"RIFF a" * 64)
    m = _analysed(tmp_path, _session("s1", wav))
    late = _file(tmp_path / "2026-08-12 1400 — a.mp4", b"RIFF b" * 64)
    s = _session("s1", wav, late)
    whole = resolve_session_start([wav, late])
    s.session_date, s.session_start_source = whole.instant, whole.source.value
    assert whole.source.value != "birthtime", "the late file would date the session"
    assert _freeze(tmp_path, s, m) == [late.path.name]
    kept = resolve_session_start([wav])
    assert (s.session_date, s.session_start_source) == (kept.instant, kept.source.value)


def test_a_late_video_listed_first_does_not_rename_the_session(tmp_path: Path) -> None:
    """The registry finds a session by the recording it was keyed by, even when
    a video that arrived later is listed before it (``_primary_file`` would take
    the first video), so the session keeps its number."""
    from bristlenose.session_registry import SessionRegistry

    folder = tmp_path / ZOOM
    folder.mkdir()
    audio = _file(folder / "audio1.m4a", b"RIFF mixed" * 64)
    video = _file(folder / "video1.mp4", b"RIFF video" * 64)
    reg = SessionRegistry(path=tmp_path / "out" / "sessions.json")
    first = reg.apply([_session("s1", audio, video)], tmp_path)
    assert [s.session_id for s in first] == ["s1"]
    reg.apply([_session("s1", _file(tmp_path / "Interview 9.wav", b"RIFF other" * 64))],
              tmp_path)  # a second session, so a new one would not be s1 by chance
    late = _file(folder / "video0.mp4", b"RIFF a later video" * 64)
    again = reg.apply([_session("s1", late, audio, video)], tmp_path)
    assert [s.session_id for s in again] == ["s1"]


def test_a_late_video_beside_an_evicted_recording_does_not_rename_the_session(
    tmp_path: Path, monkeypatch,
) -> None:
    """The analysed audio is a cloud placeholder (no bytes, no fingerprint):
    it is still the recording the session was keyed by, known by its place."""
    from bristlenose import session_registry
    from bristlenose.session_registry import SessionRegistry

    audio = _file(tmp_path / "Interview 1.wav", b"RIFF mixed" * 64)
    reg = SessionRegistry(path=tmp_path / "out" / "sessions.json")
    assert [s.session_id for s in reg.apply([_session("s1", audio)], tmp_path)] == ["s1"]
    reg.apply([_session("s1", _file(tmp_path / "Interview 9.wav", b"RIFF other" * 64))],
              tmp_path)
    real = session_registry._fingerprint
    monkeypatch.setattr(session_registry, "_fingerprint",
                        lambda p: None if p is not None and p.name == "Interview 1.wav"
                        else real(p))
    late = _file(tmp_path / "Interview 1.mp4", b"RIFF a later video" * 64)
    again = reg.apply([_session("s1", audio, late)], tmp_path)
    assert [s.session_id for s in again] == ["s1"]


def test_a_set_aside_video_is_not_what_the_session_shows(tmp_path: Path, monkeypatch) -> None:
    """Thumbnails, scene colours and the first-analysis facts come from the
    files a session uses, never from a video it set aside."""
    from bristlenose.readable_chain import ingest_facts
    from bristlenose.utils import scene_colour, video

    wav = _file(tmp_path / "a.wav", b"RIFF a" * 64)
    late = _file(tmp_path / "a.mp4", b"RIFF b" * 64)
    late.error, late.error_stage = LATE.value, "s01_ingest"
    s = _session("s1", wav, late)

    facts = ingest_facts([s])[0]
    assert facts["has_video"] is False and facts["source"] == "a.wav"
    vtt = _file(tmp_path / "b.vtt", b"")
    _vtt(vtt.path)
    vtt.error, vtt.error_stage = LATE.value, "s01_ingest"
    assert "duration_seconds" not in ingest_facts(
        [_session("s2", _file(tmp_path / "b.mp4", b"RIFF c" * 64), vtt)])[0], (
        "a set-aside transcript's last cue does not time the session")

    cut: list[Path] = []
    monkeypatch.setattr(video, "extract_thumbnail",
                        lambda path, out, _t: cut.append(path) or None)
    video.extract_thumbnails([s], [], tmp_path / "thumbs")
    assert cut == []

    read: list[Path] = []
    monkeypatch.setattr(scene_colour, "turns_of", lambda _t: read.append(1) or [])

    class _T:
        session_id = "s1"

    scene_colour.extract_scene_colours([s], [_T()], tmp_path / "colours")
    assert read == [], "no video to colour, so its turns are never read"


# ── When the run cannot tell: every file is read, and the run says so ───────
#
# Fable review of 745c346c5 (finding 1): a session whose record cannot say which
# files it was analysed from — written 12–15 Oct 2026 in the metadata form, or a
# manifest with no per-session quote records — reads every file, a late one
# included, and said so only in the log. The read is kept; the terminal now names
# the session, on its own warning line. Never on the run summary as a failure:
# nothing was left out (a second review: the Mac counted such a row as a failure
# and the run read "Partial completion"). Said only where a file could have
# joined (more than one file) and only where the transcription cache in fact
# reads the session again, decided where the cache decides.


def _rewrite_manifest(rig: Rig, edit) -> None:
    from bristlenose.manifest import load_manifest, write_manifest

    m = load_manifest(rig.out)
    assert m is not None
    edit(m)
    write_manifest(m, rig.out)


def _input_session(rig: Rig, sid: str, *names: str):
    from bristlenose.models import InputFile
    from bristlenose.stages.s01_ingest import classify_file

    files = [InputFile(path=rig.folder / n, file_type=classify_file(rig.folder / n),
                       created_at=_session("s1").session_date,
                       size_bytes=(rig.folder / n).stat().st_size) for n in names]
    s = _session("s1", *files)
    s.session_id = sid
    return s


def _record(sid: str, value):
    """Set the session's transcription record's fingerprint to *value*, or to
    what *value(rig)* computes."""
    from bristlenose.manifest import STAGE_TRANSCRIBE

    def edit(m) -> None:
        m.stages[STAGE_TRANSCRIBE].sessions[sid].input_hash = value

    return edit


def _as_written_12_to_15_oct(rig: Rig, sid: str, *names: str):
    """The session's transcription record in the metadata form a run wrote
    between 12 and 15 Oct 2026, for the files it holds now."""
    from bristlenose.pipeline import _session_metadata_fingerprint

    return _record(sid, _session_metadata_fingerprint(
        _input_session(rig, sid, *names), rig.folder))


def _said(rig: Rig) -> str:
    from bristlenose.pipeline import READ_UNCONFIRMED

    return re.sub(r"\s+", " ", READ_UNCONFIRMED)


def _summary_states_no_failure(rig: Rig) -> None:
    """The run summary — what the Mac reads — carries no row for it."""
    from bristlenose.events import PipelineSummary
    from bristlenose.run_condition import summary_is_degraded

    summary = rig.last_summary()
    ingest = summary["ingest"]
    assert ingest["attempted"] == ingest["succeeded"] + len(ingest["failed"]), ingest
    assert not summary_is_degraded(PipelineSummary.model_validate(summary)), summary


def _said_unconfirmed(rig: Rig, name: str) -> None:
    flat = re.sub(r"\s+", " ", rig.last_output)
    assert f"{name} — {_said(rig)}" in flat, rig.last_output
    assert "not analysed" not in flat, rig.last_output
    _summary_states_no_failure(rig)


def _not_said(rig: Rig) -> None:
    assert _said(rig) not in re.sub(r"\s+", " ", rig.last_output), rig.last_output


def test_a_late_transcript_on_a_record_from_before_content_keys_is_read_and_said(
    tmp_path: Path, fast_watcher,
) -> None:
    rig = new_rig(tmp_path, "Interview 1.wav", "Interview 2.mp4")
    rig.run()
    _rewrite_manifest(rig, _as_written_12_to_15_oct(rig, "s2", "Interview 2.mp4"))
    _vtt(rig.folder / "Interview 2.vtt")
    rig.run()
    assert "Mod Mia" in rig.registry_speakers("s2"), "every file is read, as built"
    _said_unconfirmed(rig, "Interview 2.mp4")
    assert rig.set_aside() == []


def test_transcribe_says_it_too(tmp_path: Path, fast_watcher) -> None:
    rig = new_rig(tmp_path, "Interview 1.wav", "Interview 2.mp4")
    rig.run()
    _rewrite_manifest(rig, _as_written_12_to_15_oct(rig, "s2", "Interview 2.mp4"))
    _vtt(rig.folder / "Interview 2.vtt")
    rig.run(command="transcribe")
    flat = re.sub(r"\s+", " ", rig.last_output)
    assert f"Interview 2.mp4 — {_said(rig)}" in flat, rig.last_output


def test_an_unchanged_session_on_a_record_from_before_content_keys_says_nothing(
    tmp_path: Path, fast_watcher,
) -> None:
    rig = new_rig(tmp_path, "Interview 1.wav", "Interview 2.mp4")
    _vtt(rig.folder / "Interview 2.vtt")
    rig.run()
    _rewrite_manifest(
        rig, _as_written_12_to_15_oct(rig, "s2", "Interview 2.mp4", "Interview 2.vtt"))
    rig.run()
    assert rig.set_aside() == []
    _not_said(rig)
    assert rig.log[-1]["transcribed"] == [] and rig.log[-1]["quotes"] == []


def test_a_record_that_vouches_for_nothing_says_nothing_when_the_stage_serves_it(
    tmp_path: Path, fast_watcher,
) -> None:
    """Second review, finding 3: a per-session record that matches no spelling
    of the files, on a stage whose inputs and cache are intact. The stage
    serves the session whole, so "every file was read" would be false."""
    rig = new_rig(tmp_path, "Interview 1.wav", "Interview 2.mp4")
    _vtt(rig.folder / "Interview 2.vtt")
    rig.run()
    _rewrite_manifest(rig, _record("s2", "0" * 64))
    rig.run()
    _not_said(rig)
    assert rig.log[-1]["transcribed"] == [] and rig.log[-1]["quotes"] == []


def _without_quote_records(m) -> None:
    from bristlenose.manifest import STAGE_QUOTE_EXTRACTION, StageStatus

    m.stages[STAGE_QUOTE_EXTRACTION].sessions = None
    assert m.stages[STAGE_QUOTE_EXTRACTION].status == StageStatus.COMPLETE


def _without_any_session_records(m) -> None:
    from bristlenose.manifest import STAGE_TRANSCRIBE

    _without_quote_records(m)
    m.stages[STAGE_TRANSCRIBE].sessions = None


@pytest.mark.parametrize("strip", [_without_quote_records, _without_any_session_records],
                         ids=["no-quote-records", "no-session-records"])
def test_a_late_transcript_with_no_quote_records_is_read_and_said(
    tmp_path: Path, fast_watcher, strip,
) -> None:
    rig = new_rig(tmp_path, "Interview 1.wav", "Interview 2.mp4")
    rig.run()
    _rewrite_manifest(rig, strip)
    _vtt(rig.folder / "Interview 2.vtt")
    rig.run()
    assert "Mod Mia" in rig.registry_speakers("s2")
    _said_unconfirmed(rig, "Interview 2.mp4")
    assert "Interview 1.wav — " not in re.sub(r"\s+", " ", rig.last_output), (
        "a session of one file could not have gained one")


@pytest.mark.parametrize("strip", [_without_quote_records, _without_any_session_records],
                         ids=["no-quote-records", "no-session-records"])
def test_with_no_quote_records_an_unchanged_study_says_nothing(
    tmp_path: Path, fast_watcher, strip,
) -> None:
    rig = new_rig(tmp_path, "Interview 1.wav", "Interview 2.mp4")
    _vtt(rig.folder / "Interview 2.vtt")
    rig.run()
    _rewrite_manifest(rig, strip)
    rig.run()
    assert rig.set_aside() == []
    _not_said(rig)
    assert rig.log[-1]["transcribed"] == [], rig.log[-1]


def test_with_no_quote_records_a_new_session_does_not_name_the_served_ones(
    tmp_path: Path, fast_watcher,
) -> None:
    """A new recording sends the stage down the per-session path; a session
    its fingerprint still vouches for is served from the cache, so it is not
    named, though nothing records which files it was analysed from."""
    rig = new_rig(tmp_path, "Interview 1.wav", "Interview 2.mp4")
    _vtt(rig.folder / "Interview 2.vtt")
    rig.run()
    _rewrite_manifest(rig, _without_quote_records)
    (rig.folder / "Interview 3.wav").write_bytes(b"RIFF a new interview" * 64)
    rig.run()
    assert rig.log[-1]["transcribed"] == ["Interview 3.wav"], rig.log[-1]
    _not_said(rig)


def test_with_no_session_records_and_no_cache_file_the_reread_is_said(
    tmp_path: Path, fast_watcher,
) -> None:
    """Second review, finding 2: inputs unchanged, but the transcription cache
    file is gone, so the stage is not served whole and a record with no
    fingerprint is never trusted: every session is read again."""
    rig = new_rig(tmp_path, "Interview 1.wav", "Interview 2.mp4")
    _vtt(rig.folder / "Interview 2.vtt")
    rig.run()
    _rewrite_manifest(rig, _without_any_session_records)
    (rig.out / ".bristlenose" / "intermediate" / "session_segments.json").unlink()
    rig.run()
    _said_unconfirmed(rig, "Interview 2.mp4")


# ── A fresh start never freezes, whatever became of the stash ───────────────


def test_a_clean_run_whose_stash_failed_still_reads_the_late_transcript(
    tmp_path: Path, fast_watcher, monkeypatch,
) -> None:
    """Fable review of 745c346c5 (finding 2): ``--clean`` whose stash failed
    wrote over the old output with its manifest in place, so the late file
    was set aside, against the man page's "``--clean`` reads it"."""
    from bristlenose.utils import output_backup

    rig = new_rig(tmp_path, "Interview 1.wav", "Interview 2.mp4")
    rig.run()
    _vtt(rig.folder / "Interview 2.vtt")
    monkeypatch.setattr(output_backup, "stash", lambda *_a, **_k: None)
    rig.run(clean=True)
    assert "Could not set" in re.sub(r"\s+", " ", rig.last_output), rig.last_output
    assert ("Interview 2.vtt", LATE.value) not in rig.set_aside(), rig.set_aside()
    assert "Mod Mia" in rig.registry_speakers("s2")


def _unconfirmed(tmp_path: Path, session, manifest, **kw) -> list[str]:
    from bristlenose.pipeline import _set_aside_late_files
    from bristlenose.session_registry import SessionRegistry

    said = _set_aside_late_files([session], manifest, tmp_path,
                                 SessionRegistry(path=tmp_path / "sessions.json"), **kw)
    return [s.session_id for s in said]


def test_an_edit_beside_an_addition_is_a_candidate_and_logged(tmp_path: Path, caplog) -> None:
    mp4 = _file(tmp_path / "a.mp4", b"RIFF a" * 64)
    m = _analysed(tmp_path, _session("s1", mp4, _file(tmp_path / "a.vtt", b"WEBVTT\n\nold")))
    s = _session("s1", mp4, _file(tmp_path / "a.vtt", b"WEBVTT\n\nnew"),
                 _file(tmp_path / "a.srt", b"1\n"))
    with caplog.at_level("WARNING", logger="bristlenose"):
        assert _unconfirmed(tmp_path, s, m) == ["s1"]
    assert "every file it holds is read" in caplog.text
    assert [f for f in s.files if f.error] == [], "nothing set aside"


def test_an_edited_session_of_one_file_is_logged_not_a_candidate(
    tmp_path: Path, caplog,
) -> None:
    m = _analysed(tmp_path, _session("s1", _file(tmp_path / "a.vtt", b"WEBVTT\n\nold")))
    s = _session("s1", _file(tmp_path / "a.vtt", b"WEBVTT\n\nnew"))
    with caplog.at_level("WARNING", logger="bristlenose"):
        assert _unconfirmed(tmp_path, s, m) == []
    assert "every file it holds is read" in caplog.text


def test_a_record_in_the_metadata_form_that_still_vouches_is_no_candidate(
    tmp_path: Path, caplog,
) -> None:
    from bristlenose.manifest import STAGE_TRANSCRIBE
    from bristlenose.pipeline import _session_metadata_fingerprint

    s = _session("s1", _file(tmp_path / "a.mp4", b"RIFF a" * 64),
                 _file(tmp_path / "a.vtt", b"WEBVTT\n\n"))
    m = _analysed(tmp_path, s)
    m.stages[STAGE_TRANSCRIBE].sessions["s1"].input_hash = (
        _session_metadata_fingerprint(s, tmp_path))
    with caplog.at_level("WARNING", logger="bristlenose"):
        assert _unconfirmed(tmp_path, s, m) == []
    assert "every file it holds is read" not in caplog.text


def test_an_analysed_record_with_no_fingerprint_is_a_candidate(tmp_path: Path) -> None:
    """Second review, finding 5: the same record the no-quote-records branch
    hands to the cache is not skipped here."""
    from bristlenose.manifest import STAGE_TRANSCRIBE

    s = _session("s1", _file(tmp_path / "a.mp4", b"RIFF a" * 64),
                 _file(tmp_path / "a.vtt", b"WEBVTT\n\n"))
    m = _analysed(tmp_path, s)
    m.stages[STAGE_TRANSCRIBE].sessions["s1"].input_hash = None
    assert _unconfirmed(tmp_path, s, m) == ["s1"]
    assert [f for f in s.files if f.error] == []
    one = _session("s1", _file(tmp_path / "b.mp4", b"RIFF b" * 64))
    assert _unconfirmed(tmp_path, one, m) == []


def test_a_fresh_start_sets_nothing_aside(tmp_path: Path) -> None:
    mp4 = _file(tmp_path / "a.mp4", b"RIFF a" * 64)
    m = _analysed(tmp_path, _session("s1", mp4))
    s = _session("s1", mp4, _file(tmp_path / "a.vtt", b"WEBVTT\n\n"))
    assert _unconfirmed(tmp_path, s, m, fresh_start=True) == []
    assert [f for f in s.files if f.error] == []
    assert s.has_existing_transcript


def _quote_stage_only(session, *, tx_records: bool, complete: bool = True,
                      tx_failed: bool = False):
    from bristlenose.manifest import (
        STAGE_QUOTE_EXTRACTION,
        STAGE_TRANSCRIBE,
        create_manifest,
        mark_session_complete,
        mark_session_failed,
        mark_stage_complete,
        mark_stage_running,
    )

    m = create_manifest("t", "0")
    if tx_records:
        mark = mark_session_failed if tx_failed else mark_session_complete
        mark(m, STAGE_TRANSCRIBE, session.session_id)
    mark_stage_complete(m, STAGE_TRANSCRIBE)
    if complete:
        mark_stage_complete(m, STAGE_QUOTE_EXTRACTION)
    else:
        mark_stage_running(m, STAGE_QUOTE_EXTRACTION)
    return m


def test_with_no_quote_records_the_candidate_rules(tmp_path: Path) -> None:
    """Which sessions could hold a late file; whether each is read again is
    the cache's call, made in ``run`` (the rig tests above)."""
    mp4 = _file(tmp_path / "a.mp4", b"RIFF a" * 64)
    s = _session("s1", mp4, _file(tmp_path / "a.vtt", b"WEBVTT\n\n"))

    def said(m) -> list[str]:
        return _unconfirmed(tmp_path, s, m)

    assert said(_quote_stage_only(s, tx_records=True)) == ["s1"]
    assert said(_quote_stage_only(s, tx_records=True, tx_failed=True)) == [], "a retry"
    assert said(_quote_stage_only(s, tx_records=True, complete=False)) == [], "not analysed"
    assert said(_quote_stage_only(_session("s9", mp4), tx_records=True)) == [], "new"
    assert said(_quote_stage_only(s, tx_records=False)) == ["s1"], "no records at all"
    assert _unconfirmed(tmp_path, _session("s1", mp4),
                        _quote_stage_only(s, tx_records=True)) == [], "one file"


# ── #130, a known v1 limit: a recode out and back ──────────────────────────
#
# Owner, 23 Oct 2026 (decision #130, option A): recoding a participant out to
# observer and back, with an Analyse after each, leaves their curated quotes
# hidden under the old code and adds uncurated duplicates under a new number,
# because a participant number is never issued twice. Recorded as a known limit
# (docs/design-people.md §J7 R3), engineered here as strict xfails so the day it
# is fixed the register is told. The late-file freeze above closes the other path
# to the first invariant: a transcript joining an analysed session (Case A).


def _quote_rows(rig: Rig, sid: str) -> list[tuple]:
    con = sqlite3.connect(rig.out / ".bristlenose" / "bristlenose.db")
    try:
        quotes = con.execute(
            "SELECT participant_id, start_timecode, text FROM quotes WHERE session_id = ?",
            (sid,)).fetchall()
        slots = {code for (code,) in con.execute(
            """SELECT ss.speaker_code FROM session_speakers ss
                 JOIN sessions s ON s.id = ss.session_id WHERE s.session_id = ?""", (sid,))}
    finally:
        con.close()
    return [(pid, start, text, pid in slots) for pid, start, text in quotes]


def _recode_out_and_back(tmp_path: Path) -> list[tuple]:
    rig = new_rig(tmp_path, "Interview 1.wav", "Interview 2.wav")
    with rig.serve() as client:
        rig.run()
        rig.sessions(client, expect=2)
        star = next(q for q in rig.quote_ids(client) if q.startswith("q-p2-"))
        assert client.patch("/api/projects/1/starred", json={star: True}).status_code == 200
        r = client.put("/api/projects/1/sessions/s2/speakers/p2",
                       json={"kind": "observer", "clear": True})
        assert r.status_code == 200, r.text
        rig.run()
        rig.sessions(client, expect=2)
        code = next(c for c in rig.registry_speakers("s2").values() if c.startswith("o"))
        r = client.put(f"/api/projects/1/sessions/s2/speakers/{code}",
                       json={"kind": "participant", "full_name": "Wylie"})
        assert r.status_code == 200, r.text
        rig.run()
        rig.sessions(client, expect=2)
        return _quote_rows(rig, "s2")


@pytest.mark.xfail(strict=True, reason=(
    "#130, known v1 limit: the curated copy stays hidden under the old code and "
    "a fresh one is extracted under the new number"))
def test_a_recode_out_and_back_leaves_no_duplicate_quotes(tmp_path: Path, fast_watcher) -> None:
    rows = _recode_out_and_back(tmp_path)
    at = [(start, text) for _pid, start, text, _slot in rows]
    assert len(at) == len(set(at)), rows


@pytest.mark.xfail(strict=True, reason=(
    "#130, known v1 limit: the curated quotes stay credited to a code with no slot"))
def test_a_recode_out_and_back_leaves_every_quote_with_a_slot(
    tmp_path: Path, fast_watcher,
) -> None:
    rows = _recode_out_and_back(tmp_path)
    assert all(slot for *_rest, slot in rows), rows
