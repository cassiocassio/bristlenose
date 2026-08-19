"""Why a file isn't in the report, and whether the run says so.

The corpus these are written against is `experiments/folder-of-horrors/` —
synthesised, because no public corpus tests folder-level ingest robustness
(see the `reference-media-test-corpora` memory). The three damaged shapes here
are the three that corpus actually contains.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from bristlenose.events import (
    STAGE_FAILED_MAX,
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
