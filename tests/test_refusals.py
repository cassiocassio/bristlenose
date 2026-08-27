"""Why a file isn't in the report, and whether the run says so.

The corpus these are written against is `experiments/folder-of-horrors/` —
synthesised, because no public corpus tests folder-level ingest robustness
(see the `reference-media-test-corpora` memory). The three damaged shapes here
are the three that corpus actually contains.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bristlenose.events import (
    STAGE_FAILED_MAX,
    Cause,
    CauseCategoryEnum,
    PipelineSummary,
    RunCompletedEvent,
    StageOutcome,
    _truncate_event_summary,
)
from bristlenose.refusals import (
    MESSAGES,
    UnusableReason,
    classify_unreadable,
    looks_like_a_recording,
    stage_failure,
)

# Minimal real container headers. Each is the *start* of a genuine file of that
# type — which is exactly the state a truncated download leaves behind.
_HEADERS = {
    "mp4": b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2",
    "mkv": b"\x1a\x45\xdf\xa3\x01\x00\x00\x00\x00\x00\x00\x1f",
    "wav": b"RIFF\x24\x08\x00\x00WAVEfmt ",
    "ogg": b"OggS\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00",
    "flac": b"fLaC\x00\x00\x00\x22\x12\x00\x12\x00",
    "wmv": b"\x30\x26\xb2\x75\x8e\x66\xcf\x11\xa6\xd9\x00\xaa",
    "mpg": b"\x00\x00\x01\xba\x44\x00\x04\x00\x04\x01\x00\x03",
}


class TestClassifyingWhyAFileFailed:
    """The three shapes a researcher actually hits, told apart."""

    def test_zero_bytes_is_an_empty_file(self, tmp_path: Path) -> None:
        # The everyday shape of a failed upload. `stat` is a fact, so this is
        # checked before any inference from the bytes.
        f = tmp_path / "p07 failed download.mp4"
        f.write_bytes(b"")
        assert classify_unreadable(f) is UnusableReason.EMPTY

    def test_a_truncated_recording_is_incomplete(self, tmp_path: Path) -> None:
        # Truncation removes the tail, so the container header survives. That
        # is the whole tell, and it is what separates "ask them to re-send"
        # from "check what you attached".
        f = tmp_path / "interview half sent.mp4"
        f.write_bytes(_HEADERS["mp4"] + b"\x00" * 4096)
        assert classify_unreadable(f) is UnusableReason.INCOMPLETE

    def test_text_wearing_a_media_extension_is_not_a_recording(
        self, tmp_path: Path
    ) -> None:
        f = tmp_path / "notes-not-video.mp4"
        f.write_text("Met Priya at 10. She hated the onboarding.\n")
        assert classify_unreadable(f) is UnusableReason.NOT_A_RECORDING

    @pytest.mark.parametrize("kind", sorted(_HEADERS))
    def test_every_container_we_accept_is_recognised(
        self, kind: str, tmp_path: Path
    ) -> None:
        # A false "not a recording" on a real format would tell a researcher
        # their file is junk when it is merely broken.
        f = tmp_path / f"clip.{kind}"
        f.write_bytes(_HEADERS[kind])
        assert looks_like_a_recording(f), kind

    def test_a_missing_file_never_raises(self, tmp_path: Path) -> None:
        # A classifier that throws while explaining a failure has made the
        # situation worse.
        assert classify_unreadable(tmp_path / "gone.mp4") is UnusableReason.UNREADABLE

    def test_every_reason_has_a_sentence(self) -> None:
        for reason in UnusableReason:
            assert MESSAGES[reason].strip(), reason


class TestTheMessageIsSafeToWriteDown:
    """`pipeline-events.jsonl` is a re-identification surface."""

    def test_no_participant_detail_reaches_the_cause_message(self) -> None:
        failure = stage_failure(
            source_file="Priya Sharma interview.mp4",
            reason=UnusableReason.EMPTY,
            stage="s02_extract_audio",
        )
        # The basename has exactly one home, and it is the field the Swift side
        # matches on — never interpolated into prose that a support bundle or a
        # copied diagnostic would carry somewhere else.
        assert failure.source_file == "Priya Sharma interview.mp4"
        assert "Priya" not in (failure.cause.message or "")
        assert failure.cause.category is CauseCategoryEnum.UNUSABLE_INPUT


class TestARefusalIsNotARunFailure:
    def test_declines_ride_the_summary_without_changing_the_outcome(self) -> None:
        # Outcome 2 of the taxonomy — "refused by name, with a reason" — is a
        # pass. 38 good sessions out of 58 files is a success with something
        # to say, not a dead run.
        summary = PipelineSummary(
            ingest=StageOutcome(
                attempted=3,
                succeeded=2,
                failed=[
                    stage_failure(
                        source_file="tape.dv",
                        reason=UnusableReason.UNSUPPORTED_FORMAT,
                        stage="s01_ingest",
                    )
                ],
            )
        )
        assert summary.ingest is not None
        assert summary.ingest.succeeded == 2
        assert len(summary.ingest.failed) == 1


class TestTheIngestBucketIsCapped:
    def test_a_folder_of_sixty_refusals_does_not_blow_the_event_line(self) -> None:
        # The bucket most able to overflow was the one bucket the cap did not
        # reach, because the applier listed its four buckets by hand. It now
        # derives them from the model.
        many = [
            stage_failure(
                source_file=f"p{i:02d}.dv",
                reason=UnusableReason.UNSUPPORTED_FORMAT,
                stage="s01_ingest",
            )
            for i in range(60)
        ]
        event = RunCompletedEvent(
            ts="2026-08-19T12:00:30Z",
            run_id="01JT0000000000000000000000",
            kind="run",
            started_at="2026-08-19T12:00:00Z",
            ended_at="2026-08-19T12:00:30Z",
            outcome="completed",
            summary=PipelineSummary(
                ingest=StageOutcome(attempted=60, succeeded=0, failed=many)
            ),
        )
        capped = _truncate_event_summary(event)
        assert capped.summary is not None
        assert capped.summary.ingest is not None
        failed = capped.summary.ingest.failed
        assert len(failed) == STAGE_FAILED_MAX + 1
        assert "more failures truncated" in (failed[-1].cause.message or "")


class TestScannerParity:
    def test_our_own_output_directory_is_never_reported_as_declined(
        self, tmp_path: Path
    ) -> None:
        # The default output directory lives *inside* the input folder, so a
        # re-run scans the last run's artefacts. Before this, the first thing a
        # researcher saw in the refusal list was "bristlenose.db — not a format
        # Bristlenose reads": noise they did not create and cannot act on.
        from bristlenose.stages.s01_ingest import OUTPUT_DIR_NAME, discover_files

        out = tmp_path / OUTPUT_DIR_NAME
        out.mkdir()
        (out / "bristlenose-report.html").write_text("<html></html>")
        (out / "manifest.csv").write_text("a,b\n")
        (tmp_path / "tape.dv").write_bytes(b"\x00" * 16)

        skipped: list = []
        discover_files(tmp_path, skipped)
        names = {s.path.name for s in skipped}
        assert names == {"tape.dv"}, f"unexpected refusals: {names}"


class TestSilentSessionsAreStated:
    """A recording with no speech in it is an outcome, not a success.

    Measured on the torture corpus 20 Aug 2026: the terminus reported
    ``transcripts: attempted=57 succeeded=57 failed=0`` and then
    ``topics: attempted=42``. Fifteen sessions disappeared between the two with
    nothing recorded anywhere — the researcher saw gaps in the session numbering
    (#2, #7, #8 …) and had no way to learn which files they were. Eleven were
    sound effects and test tones; four were the damaged files.

    The gaps themselves are **deliberate** — session ids are not renumbered to
    close them, because a gap makes a failure visible. That only works if
    something explains each gap.
    """

    def test_a_silent_session_is_not_counted_as_a_success(self) -> None:
        from bristlenose.refusals import UnusableReason, stage_failure

        f = stage_failure(
            source_file="Electronic Hit FX 04.caf",
            reason=UnusableReason.NO_SPEECH,
            stage="s05_transcribe",
            session_id="s4",
        )
        assert f.cause.category is CauseCategoryEnum.UNUSABLE_INPUT
        assert f.session_id == "s4"
        assert f.source_file == "Electronic Hit FX 04.caf"

    def test_no_speech_is_distinct_from_no_audio(self) -> None:
        # Different remedies. `NO_AUDIO` means the file has no audio stream at
        # all — re-export it. `NO_SPEECH` means it decoded and transcribed fine
        # and nobody was talking — it is not an interview.
        assert MESSAGES[UnusableReason.NO_AUDIO] != MESSAGES[UnusableReason.NO_SPEECH]
        assert "nothing was said" in MESSAGES[UnusableReason.NO_SPEECH]

    def test_every_reason_still_has_a_sentence(self) -> None:
        # NO_SPEECH is the sixth; the table must keep pace with the enum.
        for reason in UnusableReason:
            assert MESSAGES[reason].strip(), reason


class TestTranscribeOnlyStatesSilenceToo:
    """`transcribe-only` must tell the same story `run` does.

    The fix on 20 Aug 2026 (`6497711a`) landed in ``Pipeline.run`` and not in
    its sibling ``run_transcription_only``, whose rollup kept a comment reading
    "Mirror the run() rollup" while mirroring the shape from *before* that
    commit. The manifestation differs and costs the same participant: ``run``
    reported ``57/57`` and hid the loss behind a clean sweep, while
    ``transcribe-only`` reported ``42/57`` with an empty ``failed`` list — a
    visible gap with no account of which files or why.

    Reachable through ``bristlenose transcribe-only``; the desktop renders
    these runs (``EventLogReader.swift``). Neither existing net watched it —
    the acceptance matrix drives only ``run``, and the corpus-through-the-app
    walk in docs/design-analysis-lifecycle.md §5.3 triggers ``run()``.
    """

    @staticmethod
    def _sessions(tmp_path: Path, n: int) -> list:
        from datetime import datetime, timezone

        from bristlenose.models import FileType, InputFile, InputSession

        out = []
        for i in range(1, n + 1):
            media = tmp_path / f"rec{i}.wav"
            media.write_bytes(b"fake")
            out.append(InputSession(
                session_id=f"s{i}",
                session_number=i,
                participant_id=f"p{i}",
                participant_number=i,
                session_date=datetime.now(timezone.utc),
                files=[InputFile(
                    path=media,
                    file_type=FileType.AUDIO,
                    created_at=datetime.now(timezone.utc),
                    size_bytes=4,
                    duration_seconds=60.0,
                )],
                audio_path=media,
            ))
        return out

    @staticmethod
    def _segment():
        from bristlenose.models import SpeakerRole, TranscriptSegment

        return TranscriptSegment(
            segment_index=0,
            start_time=0.0,
            end_time=5.0,
            text="I could not find the checkout button.",
            speaker_role=SpeakerRole.PARTICIPANT,
        )

    def _run(self, tmp_path: Path, speaking: set[str], n: int = 3):
        """Drive run_transcription_only with a chosen set of speaking sessions.

        ``_gather_all_segments`` is the seam, for the same reason
        test_pipeline_abandon.py patches the transcribe stage rather than the
        backend: the contract under test is the rollup's reaction to a given
        (segments, outcome) pair, not the Whisper wiring.
        """
        import asyncio
        from unittest.mock import MagicMock, patch

        from bristlenose.pipeline import Pipeline

        settings = MagicMock()
        settings.project_name = "silent-mix"
        settings.write_intermediate = False
        settings.color_scheme = "default"
        pipeline = Pipeline(settings)

        input_dir = tmp_path / "in"
        input_dir.mkdir()
        output_dir = tmp_path / "out"
        sessions = self._sessions(input_dir, n)

        async def _fake_gather(_self, _sessions, **_kw):
            segs = {
                s.session_id: ([self._segment()] if s.session_id in speaking else [])
                for s in _sessions
            }
            return segs, StageOutcome(attempted=len(_sessions), succeeded=len(speaking))

        async def _passthrough(sess, _tmp, **_kw):
            return sess

        with (
            patch("bristlenose.stages.s01_ingest.ingest", return_value=sessions),
            patch(
                "bristlenose.stages.s02_extract_audio.extract_audio_for_sessions",
                new=_passthrough,
            ),
            patch.object(Pipeline, "_gather_all_segments", new=_fake_gather),
        ):
            asyncio.run(pipeline.run_transcription_only(input_dir, output_dir))
        return pipeline._summary.transcripts

    def test_a_silent_session_is_named_not_merely_missing(self, tmp_path: Path) -> None:
        # Two of three recordings have speech. The third must be *stated*,
        # not left as the arithmetic difference between two numbers.
        outcome = self._run(tmp_path, speaking={"s1", "s2"})

        assert outcome is not None
        assert outcome.attempted == 3
        assert outcome.succeeded == 2

        silent = [f for f in outcome.failed
                  if f.cause.message == MESSAGES[UnusableReason.NO_SPEECH]]
        assert len(silent) == 1, (
            f"the silent session went unstated: failed={outcome.failed!r}"
        )
        assert silent[0].session_id == "s3"
        # The name is the whole point — a count says something is missing,
        # only the filename says which participant.
        assert silent[0].source_file == "rec3.wav"

    def test_the_summary_accounts_for_every_session(self, tmp_path: Path) -> None:
        # attempted == succeeded + failed. On the pre-fix code this read
        # 3 == 2 + 0, which is the gap the researcher sees and cannot explain.
        outcome = self._run(tmp_path, speaking={"s1", "s2"})
        assert outcome.attempted == outcome.succeeded + len(outcome.failed)

    def test_an_all_silent_folder_is_reported_not_abandoned(self, tmp_path: Path) -> None:
        # `run` treats this as a stated outcome rather than a crash; the
        # sibling must agree. Pre-fix, succeeded==0 tripped the abandon
        # predicate and the researcher got an error instead of an answer.
        outcome = self._run(tmp_path, speaking=set())
        assert outcome.succeeded == 0
        assert len(outcome.failed) == 3
        assert outcome.attempted == outcome.succeeded + len(outcome.failed)


class TestReasonReachesTheWire:
    """`Cause.reason` — the discriminator the desktop localises from.

    The defect this class pins: `refusals.py` promised in a comment that "the
    user-facing surfaces localise from the reason, not from this text", and no
    such field existed. `Cause` carried `category` (all eight refusals share
    one) and the English `message`, so `ProjectDiagnosticPopover` had nothing to
    key a translation on and rendered the English raw — in all 21 non-en
    locales, inside a popover whose header and count line translated correctly.
    """

    def test_stage_failure_carries_the_reason(self) -> None:
        f = stage_failure(
            source_file="p07-interview.m4a",
            reason=UnusableReason.EMPTY,
            stage="s01_ingest",
        )
        assert f.cause.reason is UnusableReason.EMPTY

    def test_reason_survives_the_json_round_trip(self) -> None:
        """It has to reach Swift as a plain string, not a Python enum repr."""
        f = stage_failure(
            source_file="p03-consent-form.pdf",
            reason=UnusableReason.UNSUPPORTED_FORMAT,
            stage="s01_ingest",
        )
        wire = json.loads(f.model_dump_json())
        assert wire["cause"]["reason"] == "unsupported_format"

    def test_message_is_still_english_on_the_wire(self) -> None:
        """`reason` is additive — it does not replace `message`.

        The English stays: the CLI prints it, the s01/s02 log lines use it, a
        desktop build older than Aug 2026 falls back to it, and a diagnostic
        pasted into a bug report should read the same whatever the reporter's
        UI language is.
        """
        f = stage_failure(
            source_file="p06.mp4", reason=UnusableReason.EMPTY, stage="s01_ingest"
        )
        assert f.cause.message == MESSAGES[UnusableReason.EMPTY]

    def test_every_reason_is_expressible_on_the_wire(self) -> None:
        """No reason can be emitted that the popover cannot then key on."""
        for reason in UnusableReason:
            f = stage_failure(
                source_file="x.mp4", reason=reason, stage="s01_ingest"
            )
            wire = json.loads(f.model_dump_json())
            assert wire["cause"]["reason"] == reason.value
            assert wire["cause"]["message"] == MESSAGES[reason]

    def test_absent_reason_still_parses(self) -> None:
        """An event from a sidecar older than the field must not fail to load.

        Same additive contract the Swift side relies on — and the reason the
        contract fixture's `run_completed_partial_refusals` deliberately leaves
        `reason` off its last entry.
        """
        cause = Cause.model_validate(
            {"category": "unusable_input", "message": "The file couldn't be read."}
        )
        assert cause.reason is None


class TestBristlenoseArtefactsAreNeverRefusals:
    """Our own state files must never appear in a researcher's failure list.

    `discover_files` already declines to descend into `bristlenose-output`, which
    covers the default layout. This covers the rest: `--output` pointing at some
    other directory inside the input folder, and artefacts moved by hand.

    Observed 27 Aug 2026 on a real project: `Partial completion — 4 files not
    analysed`, and all four were ours (`bristlenose.db`, its two WAL companions,
    `bristlenose.log`). Four of nine files, crowding out the refusals that were
    genuinely the researcher's.

    Fixtures use `.srt` because **`.txt` is not an accepted format** —
    `classify_file` takes audio, video, `.srt`, `.vtt` and `.docx`. Worth stating
    since the obvious fixture is a `.txt` and it silently discovers nothing.
    """

    def test_state_dir_is_skipped_wherever_it_sits(self, tmp_path):
        from bristlenose.stages.s01_ingest import discover_files

        # Deliberately NOT under `bristlenose-output/` — that guard already
        # existed; this is the `--output elsewhere` shape it doesn't cover.
        state = tmp_path / "analysis" / ".bristlenose"
        state.mkdir(parents=True)
        for name in ("bristlenose.db", "bristlenose.db-wal",
                     "bristlenose.db-shm", "bristlenose.log",
                     "pipeline-events.jsonl", "run.pid"):
            (state / name).write_bytes(b"x")
        (tmp_path / "interview.srt").write_text(
            "1\n00:00:01,000 --> 00:00:02,000\nhello\n", encoding="utf-8"
        )

        skipped: list = []
        files = discover_files(tmp_path, skipped)

        assert [f.path.name for f in files] == ["interview.srt"]
        assert skipped == [], f"our own artefacts were reported as refusals: {skipped}"

    def test_loose_artefacts_are_skipped_by_name(self, tmp_path):
        """Copied out of the state dir, they are still ours."""
        from bristlenose.stages.s01_ingest import discover_files

        for name in ("bristlenose.db", "bristlenose.log", "pii_summary.txt"):
            (tmp_path / name).write_text("x", encoding="utf-8")
        (tmp_path / "interview.srt").write_text(
            "1\n00:00:01,000 --> 00:00:02,000\nhello\n", encoding="utf-8"
        )

        skipped: list = []
        files = discover_files(tmp_path, skipped)

        assert [f.path.name for f in files] == ["interview.srt"]
        assert skipped == []

    def test_a_researchers_own_file_is_still_refused_normally(self, tmp_path):
        """The filter matches our exact names, not anything that resembles them.

        A researcher's `bristlenose-notes.txt` is not ours, so it takes the
        ordinary unsupported-format path and IS reported — declining to analyse
        it is correct, and silently swallowing it would not be.
        """
        from bristlenose.stages.s01_ingest import discover_files

        (tmp_path / "bristlenose-notes.txt").write_text("mine", encoding="utf-8")
        skipped: list = []
        files = discover_files(tmp_path, skipped)

        assert files == []
        assert [sf.path.name for sf in skipped] == ["bristlenose-notes.txt"]
