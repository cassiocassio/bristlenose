"""The pipeline on a platform transcript — driven through the real ``Pipeline.run``.

Pytest ports of the stubbed harnesses that reproduced every pipeline defect in
``docs/design-cloud-import-transcripts.md`` §2 (the originals live in the
maintainer's gitignored scratch area). The orchestrator, ingest grouping,
the transcript parsers, the splitter gate, the manifest and the people file
are all real; Whisper and every LLM call are stubbed. Nothing here makes a
network call or reads a real recording.

Why through ``run`` and not unit by unit: each defect here was a *wiring*
defect — a correct function the orchestrator never reached, or reached with
the wrong session — and the per-function tests were green throughout.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from bristlenose.config import BristlenoseSettings
from bristlenose.events import StageOutcome
from bristlenose.models import (
    FileType,
    InputFile,
    InputSession,
    PiiCleanTranscript,
    SessionTopicMap,
    SpeakerRole,
    TranscriptSegment,
)
from bristlenose.pipeline import Pipeline
from bristlenose.stages.s05b_identify_speakers import SpeakerInfo

_T0 = datetime(2026, 9, 24, 10, 0, tzinfo=timezone.utc)


# ── Session builders ────────────────────────────────────────────────────────


def _media(input_dir: Path, stem: str, *, when: datetime = _T0) -> InputFile:
    path = input_dir / f"{stem}.wav"
    if not path.exists():
        path.write_bytes(b"RIFF fake " + stem.encode("utf-8"))
    return InputFile(
        path=path, file_type=FileType.AUDIO, created_at=when,
        size_bytes=path.stat().st_size, duration_seconds=1800.0,
    )


def write_vtt(input_dir: Path, stem: str, cues: list[tuple[str | None, str]]) -> Path:
    """A vendor-style VTT: one cue per turn, ``<v Name>`` when a name is given."""
    lines = ["WEBVTT", ""]
    t = 0
    for speaker, text in cues:
        lines.append(f"00:{t // 60:02d}:{t % 60:02d}.000 --> 00:{(t + 8) // 60:02d}:{(t + 8) % 60:02d}.000")
        lines.append(f"<v {speaker}>{text}</v>" if speaker else text)
        lines.append("")
        t += 10
    path = input_dir / f"{stem}.vtt"
    content = "\n".join(lines)
    # Rewriting an unchanged file would move its mtime, and mtime is part of
    # the transcribe stage's input hash — the harness must not look like a
    # researcher who re-saved the transcript.
    if not path.exists() or path.read_text(encoding="utf-8") != content:
        path.write_text(content, encoding="utf-8")
    return path


def audio_session(input_dir: Path, n: int, stem: str, *, when: datetime = _T0) -> InputSession:
    """A bare recording: Whisper transcribes it, the splitter may run."""
    media = _media(input_dir, stem, when=when)
    return InputSession(
        session_id=f"s{n}", session_number=n, participant_id=f"p{n}", participant_number=n,
        files=[media], audio_path=media.path, has_existing_transcript=False, session_date=when,
    )


def pair_session(
    input_dir: Path, n: int, stem: str, cues: list[tuple[str | None, str]],
    *, when: datetime = _T0,
) -> InputSession:
    """A recording beside its platform transcript: parsed, never Whispered."""
    media = _media(input_dir, stem, when=when)
    vtt_path = write_vtt(input_dir, stem, cues)
    vtt = InputFile(
        path=vtt_path, file_type=FileType.SUBTITLE_VTT, created_at=when,
        size_bytes=vtt_path.stat().st_size,
    )
    return InputSession(
        session_id=f"s{n}", session_number=n, participant_id=f"p{n}", participant_number=n,
        files=[media, vtt], audio_path=None, has_existing_transcript=True, session_date=when,
    )


# ── The harness ─────────────────────────────────────────────────────────────


def _quote(sid: str, pid: str, n: int):
    """A real quote — a fake returning ``[]`` makes ``mark_stage_complete`` refuse
    on its empty-content guard and the stage never reaches COMPLETE."""
    from bristlenose.models import (
        EmotionalTone,
        ExtractedQuote,
        JourneyStage,
        QuoteIntent,
        QuoteType,
    )

    text = f"Quote {n} from {sid}, long enough to clear the word floor."
    return ExtractedQuote(
        session_id=sid, participant_id=pid,
        start_timecode=float(n), end_timecode=float(n) + 5.0, text=text, verbatim_excerpt=text,
        topic_label="general", quote_type=QuoteType.GENERAL_CONTEXT,
        researcher_context="", intent=QuoteIntent.NARRATION,
        emotion=EmotionalTone.NEUTRAL, journey_stage=JourneyStage.OTHER,
    )


@dataclass
class Harness:
    input_dir: Path
    output_dir: Path
    #: Per run, the session ids handed to (stubbed) Whisper.
    transcribed: list[list[str]] = field(default_factory=list)
    #: Per splitter call, the text of the first segment it was given.
    split_calls: list[str] = field(default_factory=list)
    #: Per role-pass call, the labels it saw.
    role_calls: list[set[str]] = field(default_factory=list)
    #: Per run, the session ids the (stubbed) quote extractor was given.
    quoted: list[list[str]] = field(default_factory=list)

    @property
    def intermediate(self) -> Path:
        return self.output_dir / ".bristlenose" / "intermediate"

    def session_segments(self) -> dict[str, list[TranscriptSegment]]:
        raw = json.loads((self.intermediate / "session_segments.json").read_text("utf-8"))
        return {sid: [TranscriptSegment.model_validate(s) for s in segs] for sid, segs in raw.items()}

    def speaker_segments(self, sid: str) -> list[TranscriptSegment]:
        data = json.loads((self.intermediate / "speaker-info" / f"{sid}.json").read_text("utf-8"))
        return [TranscriptSegment.model_validate(s) for s in data["segments_with_roles"]]

    def log(self) -> str:
        return (self.output_dir / ".bristlenose" / "bristlenose.log").read_text("utf-8")

    def people(self) -> dict:
        import yaml

        return yaml.safe_load((self.output_dir / "people.yaml").read_text("utf-8"))


def _whisper_segments(sid: str) -> list[TranscriptSegment]:
    """What Whisper gives us for a bare recording: text, no speakers."""
    texts = [
        f"Welcome, thanks for joining the {sid} session today.",
        "My name is Brian and I work in product design.",
        "Thank you Brian, happy to be here and talk about the app.",
        "So tell me about how you use the dashboard day to day.",
        "I open it every morning to check my tasks and the review queue.",
        "That is helpful, can you show me the part that frustrates you?",
    ]
    return [
        TranscriptSegment(
            start_time=float(i * 30), end_time=float(i * 30 + 25), text=t,
            speaker_label=None, source="whisper",
        )
        for i, t in enumerate(texts)
    ]


def run_pipeline(
    tmp_path: Path,
    sessions_for_run: Callable[[Path, int], list[InputSession]],
    *,
    runs: int = 1,
    role_pass: Callable[[list[TranscriptSegment]], list[SpeakerInfo]] | None = None,
) -> Harness:
    """Drive the real ``Pipeline.run`` ``runs`` times over ``tmp_path``.

    ``sessions_for_run(input_dir, run_index)`` builds the sessions ingest
    "finds" on each run, so a later run can add a file to an existing
    session or add a session. ``role_pass`` stands in for the LLM role pass
    and may return names, which is how the LLM-vs-platform naming contract
    is exercised.
    """
    input_dir = tmp_path / "input"
    input_dir.mkdir(exist_ok=True)
    output_dir = tmp_path / "output"
    h = Harness(input_dir=input_dir, output_dir=output_dir)

    settings = BristlenoseSettings(
        project_name="pair-test",
        skip_transcription=False,
        write_intermediate=True,
        llm_concurrency=1,
        no_fetch=True,
        pii_enabled=False,
        whisper_language="auto",
    )
    pipeline = Pipeline(settings)

    run_index = {"n": 0}

    def _fake_ingest(_input_dir: Path, _declined=None):
        return sessions_for_run(input_dir, run_index["n"])

    async def _passthrough(sess, _tmp, **_kw):
        return sess

    def _fake_transcribe(sessions, _settings, **_kw):
        sids = [s.session_id for s in sessions]
        h.transcribed.append(sids)
        return (
            {sid: _whisper_segments(sid) for sid in sids},
            {},
            StageOutcome(attempted=len(sids), succeeded=len(sids)),
        )

    async def _fake_split(segments, _client, errors=None):
        h.split_calls.append(segments[0].text if segments else "")
        for i, seg in enumerate(segments):
            seg.speaker_label = "Speaker A" if i % 2 == 0 else "Speaker B"
        return segments

    async def _fake_roles(segments, _client, errors=None):
        h.role_calls.append({seg.speaker_label or "Unknown" for seg in segments})
        if role_pass is None:
            return []
        infos = role_pass(segments)
        role_map = {info.speaker_label: info.role for info in infos}
        for seg in segments:
            label = seg.speaker_label or "Unknown"
            if label in role_map:
                seg.speaker_role = role_map[label]
        return infos

    async def _fake_segment_topics(transcripts, *_a, **_kw):
        maps = [
            SessionTopicMap(session_id=t.session_id, participant_id=t.participant_id, boundaries=[])
            for t in transcripts
        ]
        return maps, StageOutcome(attempted=len(maps), succeeded=len(maps))

    async def _fake_extract_quotes(transcripts, *_a, **_kw):
        assert all(isinstance(t, PiiCleanTranscript) for t in transcripts)
        h.quoted.append([t.session_id for t in transcripts])
        quotes = [
            _quote(t.session_id, t.participant_id, n) for t in transcripts for n in range(3)
        ]
        return quotes, StageOutcome(attempted=len(transcripts), succeeded=len(transcripts))

    async def _fake_cluster(quotes, *_a, **_kw):
        return [], StageOutcome(attempted=1, succeeded=1)

    async def _fake_group(quotes, *_a, **_kw):
        return [], StageOutcome(attempted=1, succeeded=1)

    with (
        patch("bristlenose.stages.s01_ingest.ingest", new=_fake_ingest),
        patch("bristlenose.stages.s02_extract_audio.extract_audio_for_sessions", new=_passthrough),
        patch("bristlenose.preflight.whisper.preflight_whisper", new=lambda **_kw: None),
        patch("bristlenose.stages.s05_transcribe.transcribe_sessions", new=_fake_transcribe),
        patch("bristlenose.stages.s05b_identify_speakers.split_single_speaker_llm", new=_fake_split),
        patch("bristlenose.stages.s05b_identify_speakers.identify_speaker_roles_llm", new=_fake_roles),
        patch("bristlenose.stages.s08_topic_segmentation.segment_topics", new=_fake_segment_topics),
        patch("bristlenose.stages.s09_quote_extraction.extract_quotes", new=_fake_extract_quotes),
        patch("bristlenose.stages.s10_quote_clustering.cluster_by_screen", new=_fake_cluster),
        patch("bristlenose.stages.s11_thematic_grouping.group_by_theme", new=_fake_group),
        patch("bristlenose.llm.client.LLMClient", MagicMock()),
    ):
        for i in range(runs):
            run_index["n"] = i
            asyncio.run(pipeline.run(input_dir, output_dir))

    return h


# ── 1b: the splitter never runs on a named platform transcript ──────────────

TEAMS_PAIR = [
    ("Martin Storey", "Shall we start with the kiosk?"),
    ("Priya Nair", "Yes, I used it last week and got stuck at the basket."),
    ("Martin Storey", "Tell me what you were expecting there."),
    ("Priya Nair", "A button, honestly. There was nothing to press."),
] * 3

IN_ROOM_ONE_ACCOUNT = [("Martin Storey", t) for _, t in TEAMS_PAIR]


class TestSplitterGateWiring:
    def test_a_bare_recording_still_reaches_the_splitter(self, tmp_path: Path) -> None:
        """Control: proves the harness exercises the gate at all."""
        h = run_pipeline(tmp_path, lambda d, _i: [audio_session(d, 1, "bare")])
        assert h.transcribed == [["s1"]]
        assert len(h.split_calls) == 1
        assert {s.speaker_label for s in h.speaker_segments("s1")} == {"Speaker A", "Speaker B"}

    def test_a_named_pair_bypasses_whisper_and_the_splitter(self, tmp_path: Path) -> None:
        """The Teams case the audit set out to verify: two real names, every
        turn attributed, no LLM guessing anywhere in the chain."""
        h = run_pipeline(
            tmp_path,
            lambda d, _i: [pair_session(d, 1, "P07 Interview", TEAMS_PAIR)],
        )
        assert h.transcribed == [[]] or h.transcribed == [], "Whisper must not see a paired session"
        assert h.split_calls == []
        labels = [s.speaker_label for s in h.speaker_segments("s1")]
        assert set(labels) == {"Martin Storey", "Priya Nair"}
        assert all(labels), "every turn keeps its platform name"

    def test_one_named_account_is_kept_whole_and_stated(self, tmp_path: Path) -> None:
        """Two people in a room, one Teams account. Yesterday the splitter
        overwrote the real name with Speaker A/B from a 5–8 minute sample;
        today the name stays and the run says why."""
        h = run_pipeline(
            tmp_path,
            lambda d, _i: [pair_session(d, 1, "In-room", IN_ROOM_ONE_ACCOUNT)],
        )
        assert h.split_calls == []
        assert {s.speaker_label for s in h.speaker_segments("s1")} == {"Martin Storey"}
        assert "speakers not separated" in h.log()
        assert "Martin Storey" in h.log()

    def test_a_nameless_cloud_transcript_reaches_the_splitter(self, tmp_path: Path) -> None:
        """`speakers: none` kept the interview as one voice until 4 Oct 2026;
        now the whole-transcript splitter guesses, and nothing is "stated"."""
        fixture = Path(__file__).parent / "fixtures" / "platform-transcripts" / "cloud-transcript-unnamed.vtt"

        def sessions(d: Path, _i: int) -> list[InputSession]:
            media = _media(d, "Kiosk round 2")
            vtt_path = d / "Kiosk round 2.vtt"
            if not vtt_path.exists():
                vtt_path.write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")
            vtt = InputFile(
                path=vtt_path, file_type=FileType.SUBTITLE_VTT, created_at=_T0,
                size_bytes=vtt_path.stat().st_size,
            )
            return [InputSession(
                session_id="s1", session_number=1, participant_id="p1", participant_number=1,
                files=[media, vtt], audio_path=None, has_existing_transcript=True,
                session_date=_T0,
            )]

        h = run_pipeline(tmp_path, sessions)
        assert h.split_calls == ["Right, shall we start with the kiosk?"]
        assert "speakers not separated" not in h.log()

    def test_mixed_project_splits_only_the_bare_recording(self, tmp_path: Path) -> None:
        h = run_pipeline(
            tmp_path,
            lambda d, _i: [
                pair_session(d, 1, "P07 Interview", TEAMS_PAIR),
                audio_session(d, 2, "P08 Interview"),
            ],
        )
        assert h.transcribed == [["s2"]]
        assert len(h.split_calls) == 1
        assert "s2" in h.split_calls[0]
        assert {s.speaker_label for s in h.speaker_segments("s1")} == {"Martin Storey", "Priya Nair"}
        assert {s.speaker_label for s in h.speaker_segments("s2")} == {"Speaker A", "Speaker B"}
        # And the roles the heuristic finds are the real ones: the moderator
        # asks the questions, the participant answers.
        roles = {
            s.speaker_label: s.speaker_role for s in h.speaker_segments("s1")
        }
        assert roles["Martin Storey"] == SpeakerRole.RESEARCHER
        assert roles["Priya Nair"] == SpeakerRole.PARTICIPANT


# ── 1d: the platform's name beats the LLM's guess ────────────────────────────


def _guessing_role_pass(segments: list[TranscriptSegment]) -> list[SpeakerInfo]:
    """The LLM role pass as it behaves on a named transcript: right about the
    roles, and confidently wrong about the participant's name."""
    labels = {seg.speaker_label or "Unknown" for seg in segments}
    infos = []
    for label in sorted(labels):
        if label == "Martin Storey":
            infos.append(SpeakerInfo(speaker_label=label, role=SpeakerRole.RESEARCHER))
        elif label == "Priya Nair":
            infos.append(SpeakerInfo(
                speaker_label=label, role=SpeakerRole.PARTICIPANT,
                person_name="Pri", job_title="Designer",
            ))
        elif label == "Speaker B":
            infos.append(SpeakerInfo(
                speaker_label=label, role=SpeakerRole.PARTICIPANT, person_name="Brian",
            ))
        else:
            infos.append(SpeakerInfo(speaker_label=label, role=SpeakerRole.RESEARCHER))
    return infos


class TestPlatformNamesReachThePeopleFile:
    def test_platform_name_beats_the_llm_guess(self, tmp_path: Path) -> None:
        h = run_pipeline(
            tmp_path,
            lambda d, _i: [pair_session(d, 1, "P07 Interview", TEAMS_PAIR)],
            role_pass=_guessing_role_pass,
        )
        participants = h.people()["participants"]
        p1 = participants["p1"]["editable"]
        assert p1["full_name"] == "Priya Nair"
        assert p1["role"] == "Designer", "the LLM still supplies what the platform cannot"

    def test_llm_name_still_used_when_whisper_had_no_label(self, tmp_path: Path) -> None:
        """Control: on a bare recording the splitter's labels are placeholders,
        so the LLM's name is the best there is and is kept."""
        h = run_pipeline(
            tmp_path,
            lambda d, _i: [audio_session(d, 1, "bare")],
            role_pass=_guessing_role_pass,
        )
        participants = h.people()["participants"]
        names = {code: p["editable"]["full_name"] for code, p in participants.items()}
        assert "Brian" in names.values()


# ── 0a: a session whose files changed is recomputed; the others are not ─────
#
# The defects these pin (docs/design-cloud-import-transcripts.md §2):
#   * a transcript arriving after the video was analysed was IGNORED if the
#     same batch brought a new recording (the new recording kept the stage
#     off the full-cache path, and the per-session path trusted every record);
#   * otherwise it re-Whispered EVERY session (the stage record was popped).


class TestPerSessionFingerprints:
    def test_late_transcript_with_new_recording_is_not_ignored(self, tmp_path: Path) -> None:
        early = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
        later = datetime(2026, 9, 8, 10, 0, tzinfo=timezone.utc)

        def sessions(d: Path, run: int) -> list[InputSession]:
            if run == 0:
                return [audio_session(d, 1, "P07 Interview", when=early)]
            return [
                pair_session(d, 1, "P07 Interview", TEAMS_PAIR, when=early),
                audio_session(d, 2, "P08 Interview", when=later),
            ]

        h = run_pipeline(tmp_path, sessions, runs=2)

        # Run 1 Whispered the bare recording; run 2 Whispered only the new one.
        assert h.transcribed == [["s1"], ["s2"]]
        # The late transcript replaced the Whisper text for s1 …
        segs = h.session_segments()
        assert {s.source for s in segs["s1"]} == {"vtt"}
        assert {s.speaker_label for s in h.speaker_segments("s1")} == {
            "Martin Storey", "Priya Nair",
        }
        # … and everything downstream of it was redone for s1, not served stale.
        assert sorted(h.quoted[1]) == ["s1", "s2"]

    def test_adding_a_recording_does_not_rewhisper_the_others(self, tmp_path: Path) -> None:
        def sessions(d: Path, run: int) -> list[InputSession]:
            out = [audio_session(d, 1, "A"), audio_session(d, 2, "B")]
            if run == 1:
                out.append(audio_session(d, 3, "C"))
            return out

        h = run_pipeline(tmp_path, sessions, runs=2)
        assert h.transcribed == [["s1", "s2"], ["s3"]]
        # Speaker ID, topics and quotes likewise ran only for the new session.
        assert len(h.split_calls) == 3
        assert h.quoted[1] == ["s3"]

    def test_an_untouched_project_is_served_from_cache(self, tmp_path: Path) -> None:
        h = run_pipeline(
            tmp_path,
            lambda d, _i: [pair_session(d, 1, "P07", TEAMS_PAIR), audio_session(d, 2, "P08")],
            runs=2,
        )
        assert h.transcribed == [["s2"]], "run 2 Whispered nothing"
        assert len(h.split_calls) == 1
        assert len(h.quoted) == 1, "run 2 extracted nothing"

    def test_a_parser_change_reparses_platform_sessions_only(
        self, tmp_path: Path, monkeypatch,
    ) -> None:
        """Bumping the subtitle parser version re-reads every session that has
        a transcript file and leaves the Whisper sessions cached."""
        from bristlenose.stages import s03_parse_subtitles

        def sessions(d: Path, _run: int) -> list[InputSession]:
            return [pair_session(d, 1, "P07", TEAMS_PAIR), audio_session(d, 2, "P08")]

        h = run_pipeline(tmp_path, sessions, runs=1)
        parsed_once = h.log().count("Parsed 12 segments from P07.vtt")
        assert parsed_once == 1
        monkeypatch.setattr(s03_parse_subtitles, "SUBTITLE_PARSER_VERSION", 999)
        h2 = run_pipeline(tmp_path, sessions, runs=1)

        assert h.transcribed == [["s2"]]
        assert h2.transcribed in ([], [[]]), "the Whisper session stayed cached"
        assert h2.log().count("Parsed 12 segments from P07.vtt") == 2, "s1 was re-read"
        # The re-parse produced the same segments, so everything downstream
        # was rightly served from cache: the content-hash cascade only moves
        # when the output moves. A parser that changed its output would carry
        # on through speaker ID, topics and quotes for s1 alone.
        assert h2.quoted == []
        assert {s.source for s in h2.session_segments()["s1"]} == {"vtt"}


# ── 0b: an older recording arriving later renumbers nothing ─────────────────
#
# The defect (docs/design-cloud-import-transcripts.md §2, "Adding an older
# recording"): sessions were numbered by recording date on every run, so a
# recording older than the analysed ones renumbered all of them — one
# interview's transcript, stars and names moved onto another. ``_fake_ingest``
# returns what the real ingest returns, date order with ids from 1, so the
# renumbering the registry has to undo is genuinely there.

ANN = [("Martin Storey", "Thanks for joining, Ann."), ("Ann Archer", "Ann speaking: the kiosk lost my basket.")] * 3
BEA = [("Martin Storey", "Thanks for joining, Bea."), ("Bea Baker", "Bea speaking: I never found the till.")] * 3
CAL = [("Martin Storey", "Thanks for joining, Cal."), ("Cal Cooper", "Cal speaking: the receipt was blank.")] * 3


class TestStickySessions:
    @staticmethod
    def _sessions(d: Path, run: int) -> list[InputSession]:
        day = lambda n: datetime(2026, 9, n, 10, 0, tzinfo=timezone.utc)  # noqa: E731
        if run == 0:
            return [
                pair_session(d, 1, "Bea interview", BEA, when=day(10)),
                pair_session(d, 2, "Cal interview", CAL, when=day(11)),
            ]
        # Ann was recorded first and dropped in last: by date she is s1.
        return [
            pair_session(d, 1, "Ann interview", ANN, when=day(9)),
            pair_session(d, 2, "Bea interview", BEA, when=day(10)),
            pair_session(d, 3, "Cal interview", CAL, when=day(11)),
        ]

    def test_adding_an_older_recording_does_not_cross_wire_transcripts(
        self, tmp_path: Path,
    ) -> None:
        h = run_pipeline(tmp_path, self._sessions, runs=2)
        raw = h.output_dir / "transcripts-raw"
        assert "Bea speaking" in (raw / "s1.txt").read_text("utf-8")
        assert "Cal speaking" in (raw / "s2.txt").read_text("utf-8")
        assert "Ann speaking" in (raw / "s3.txt").read_text("utf-8")
        # Only the newcomer was analysed on run 2; the others were served from
        # cache under the ids they already had.
        assert h.quoted == [["s1", "s2"], ["s3"]]

    def test_star_stays_with_its_interview_after_an_older_recording_is_added(
        self, tmp_path: Path,
    ) -> None:
        """A star hangs off its quote, and the quote is keyed by
        (session, participant code, start). Keys surviving is not enough —
        without stickiness the newcomer *reuses* ``(s1, p1)`` — so each key
        must still point at the same interview."""

        def interviews(h: Harness) -> dict[tuple, str]:
            raw = h.output_dir / "transcripts-raw"
            who = {}
            for q in json.loads((h.intermediate / "extracted_quotes.json").read_text("utf-8")):
                text = (raw / f"{q['session_id']}.txt").read_text("utf-8")
                name = next(n for n in ("Ann", "Bea", "Cal") if f"{n} speaking" in text)
                who[(q["session_id"], q["participant_id"], q["start_timecode"])] = name
            return who

        once = interviews(run_pipeline(tmp_path, self._sessions, runs=1))
        twice = interviews(run_pipeline(tmp_path, lambda d, _i: self._sessions(d, 1), runs=1))
        assert {k: twice.get(k) for k in once} == once, "every starred quote stays with its interview"
        assert {who for k, who in twice.items() if k not in once} == {"Ann"}

    def test_typed_name_stays_with_its_speaker_after_a_session_is_inserted(
        self, tmp_path: Path,
    ) -> None:
        h = run_pipeline(tmp_path, self._sessions, runs=1)
        codes = lambda h: {  # noqa: E731
            p["editable"]["full_name"]: code for code, p in h.people()["participants"].items()
            if code.startswith("p")
        }
        before = codes(h)
        h2 = run_pipeline(tmp_path, lambda d, _i: self._sessions(d, 1), runs=1)
        after = codes(h2)
        assert after["Bea Baker"] == before["Bea Baker"]
        assert after["Cal Cooper"] == before["Cal Cooper"]
        assert after["Ann Archer"] not in before.values(), "Ann gets a new number"


# ── Each session's moderator is named from that session ─────────────────────
#
# Moderator codes restart per session, so people.yaml (keyed by code) holds one
# name for every session's m1. The pipeline now also writes each session's own
# moderator and observer names, which is what serve names them from.

JO_PAIR = [
    ("Jo Lee", "Shall we start with the checkout?"),
    ("Sam Okafor", "Sure, I bought a lamp there yesterday."),
] * 3


def _two_moderator_roles(segments: list[TranscriptSegment]) -> list[SpeakerInfo]:
    labels = {seg.speaker_label or "Unknown" for seg in segments}
    infos = []
    for label in sorted(labels):
        if label in ("Martin Storey", "Jo Lee"):
            infos.append(SpeakerInfo(speaker_label=label, role=SpeakerRole.RESEARCHER,
                                     person_name="Marty" if label == "Martin Storey" else "",
                                     job_title="UX researcher"))
        elif label == "Speaker A":
            infos.append(SpeakerInfo(speaker_label=label, role=SpeakerRole.RESEARCHER,
                                     person_name="Dana Whitfield"))
        else:
            infos.append(SpeakerInfo(speaker_label=label, role=SpeakerRole.PARTICIPANT))
    return infos


class TestPerSessionModeratorNames:
    def test_two_sessions_name_their_own_moderator(self, tmp_path: Path) -> None:
        from bristlenose.people import load_session_speakers

        h = run_pipeline(
            tmp_path,
            lambda d, _i: [
                pair_session(d, 1, "P07 Interview", TEAMS_PAIR),
                pair_session(d, 2, "P08 Interview", JO_PAIR),
            ],
            role_pass=_two_moderator_roles,
        )
        names = load_session_speakers(h.output_dir)
        assert names is not None
        # The platform's label beats the LLM's "Marty", as for participants.
        assert names["s1"]["m1"] == {
            "full_name": "Martin Storey", "short_name": "Martin", "role": "UX researcher",
        }
        assert names["s2"]["m1"]["full_name"] == "Jo Lee"
        # Participants are not in it: their codes are study-wide.
        assert all(code[0] in "mo" for per in names.values() for code in per)

    def test_a_whisper_session_takes_the_name_heard_in_it(self, tmp_path: Path) -> None:
        from bristlenose.people import load_session_speakers

        h = run_pipeline(
            tmp_path,
            lambda d, _i: [
                pair_session(d, 1, "P07 Interview", TEAMS_PAIR),
                audio_session(d, 2, "bare"),
            ],
            role_pass=_two_moderator_roles,
        )
        names = load_session_speakers(h.output_dir)
        assert names["s2"]["m1"]["full_name"] == "Dana Whitfield"
        assert names["s1"]["m1"]["full_name"] == "Martin Storey"

# These drive the whole pipeline to test other stages (conftest.no_discussion_stage).
pytestmark = pytest.mark.usefixtures("no_discussion_stage")
