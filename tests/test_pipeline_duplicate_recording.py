"""The same interview under two names is one session — R49, 20 Oct 2026.

``P3.wav`` and ``P3 (1).wav`` (a Finder copy, a renamed download) used to be
two sessions: both transcribed and paid for, and the copy's quotes counted as
a second participant agreeing. Driven through the real ``Pipeline.run`` (the
harness in ``test_pipeline_platform_transcripts``): ingest's sessions, the
session registry, the manifest and the transcription cache are real; Whisper
and every LLM call are stubbed. Measured red against HEAD ``2530ba10`` before
the fold was written.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest

from bristlenose.events import UnusableReason
from bristlenose.models import FileType, InputFile, InputSession
from tests.test_pipeline_platform_transcripts import (
    _T0,
    TEAMS_PAIR,
    audio_session,
    run_pipeline,
    write_vtt,
)


def _copy_of(input_dir: Path, session, n: int, name: str):
    """A byte-identical copy of *session*'s recording under another name."""
    src = session.files[0].path
    dst = input_dir / name
    if not dst.exists():
        shutil.copy2(src, dst)
    return audio_session(input_dir, n, dst.stem)


def _refusals(h, run: int) -> list[tuple[str, str, str | None]]:
    summary = h.results[run].summary
    assert summary is not None and summary.ingest is not None
    return [
        (f.source_file or "", f.cause.reason or "", f.session_id)
        for f in summary.ingest.failed
    ]


class TestDuplicateRecording:
    def test_two_identical_recordings_are_transcribed_once_and_the_copy_is_stated(
        self, tmp_path: Path,
    ) -> None:
        def build(d: Path, _i: int):
            original = audio_session(d, 1, "P3")
            return [original, _copy_of(d, original, 2, "P3 (1).wav")]

        h = run_pipeline(tmp_path, build)
        assert h.transcribed == [["s1"]], "the copy was transcribed as its own session"
        assert h.quoted == [["s1"]], "the copy's quotes count as a second participant"
        assert _refusals(h, 0) == [
            ("P3 (1).wav", UnusableReason.DUPLICATE_RECORDING.value, "s1"),
        ]

    def test_a_copy_added_later_is_folded_in_and_nothing_is_transcribed_again(
        self, tmp_path: Path,
    ) -> None:
        def build(d: Path, i: int):
            original = audio_session(d, 1, "P3")
            if i == 0:
                return [original]
            return [original, _copy_of(d, original, 2, "P3 (1).wav")]

        h = run_pipeline(tmp_path, build, runs=2)
        assert h.transcribed in ([["s1"]], [["s1"], []]), "the copy re-paid Whisper"
        assert 1 not in h.quoted_by_run, "the second run paid for quotes again"
        assert _refusals(h, 1) == [
            ("P3 (1).wav", UnusableReason.DUPLICATE_RECORDING.value, "s1"),
        ]

    def test_deleting_the_kept_copy_leaves_the_session_to_the_other(
        self, tmp_path: Path,
    ) -> None:
        """The remaining copy is the same bytes, so it is the same session —
        found by content, its transcription still cached."""

        def build(d: Path, i: int):
            original = audio_session(d, 1, "P3")
            copy = _copy_of(d, original, 2, "P3 (1).wav")
            if i == 0:
                return [original, copy]
            original.files[0].path.unlink(missing_ok=True)
            return [audio_session(d, 1, "P3 (1)")]

        h = run_pipeline(tmp_path, build, runs=2)
        assert h.transcribed in ([["s1"]], [["s1"], []]), "the survivor re-paid Whisper"
        segments = h.session_segments()
        assert list(segments) == ["s1"]
        assert _refusals(h, 1) == []


def _transcript_session(input_dir: Path, n: int, name: str) -> InputSession:
    """A Teams transcript with no recording beside it. ``name`` other than
    ``transcript.vtt`` is a byte-identical copy of that file (a second
    download)."""
    original = write_vtt(input_dir, "transcript", TEAMS_PAIR)
    path = input_dir / name
    if not path.exists():
        shutil.copy2(original, path)
    vtt = InputFile(
        path=path, file_type=FileType.SUBTITLE_VTT, created_at=_T0,
        size_bytes=path.stat().st_size,
    )
    return InputSession(
        session_id=f"s{n}", session_number=n, participant_id=f"p{n}", participant_number=n,
        files=[vtt], audio_path=None, has_existing_transcript=True, session_date=_T0,
    )


class TestDuplicateTranscript:
    """The same transcript downloaded twice, no recording — decision #97,
    21 Oct 2026. One session, the copy stated, never a second participant.
    The wire value is spelled out: it is what the Files bucket and the
    locale key are built from."""

    def test_two_identical_vtts_are_one_session_and_the_copy_is_stated(
        self, tmp_path: Path,
    ) -> None:
        def build(d: Path, _i: int):
            return [_transcript_session(d, 1, "transcript.vtt"),
                    _transcript_session(d, 2, "transcript (1).vtt")]

        h = run_pipeline(tmp_path, build)
        assert h.quoted == [["s1"]], "the copy's quotes count as a second participant"
        assert _refusals(h, 0) == [("transcript (1).vtt", "duplicate_transcript", "s1")]
        # Set aside means not read: it is stated once, as a duplicate, and is
        # not parsed and then "superseded" as well.
        assert "superseded" not in h.log()

    def test_a_transcript_copy_added_later_is_folded_in_and_nothing_runs_again(
        self, tmp_path: Path,
    ) -> None:
        def build(d: Path, i: int):
            original = _transcript_session(d, 1, "transcript.vtt")
            if i == 0:
                return [original]
            return [original, _transcript_session(d, 2, "transcript (1).vtt")]

        h = run_pipeline(tmp_path, build, runs=2)
        assert 1 not in h.quoted_by_run, "the second run paid for quotes again"
        assert _refusals(h, 1) == [("transcript (1).vtt", "duplicate_transcript", "s1")]

    def test_deleting_the_kept_transcript_leaves_the_session_to_the_other(
        self, tmp_path: Path,
    ) -> None:
        def build(d: Path, i: int):
            original = _transcript_session(d, 1, "transcript.vtt")
            copy = _transcript_session(d, 2, "transcript (1).vtt")
            if i == 0:
                return [original, copy]
            original.files[0].path.unlink(missing_ok=True)
            return [copy]

        h = run_pipeline(tmp_path, build, runs=2)
        assert list(h.session_segments()) == ["s1"]
        assert _refusals(h, 1) == []


class TestSetAsideStage:
    """A row says which stage set the file aside. The folds happen at ingest
    (the session registry, before stage 2); until 21 Oct 2026 every
    set-aside file was labelled ``s02_extract_audio``."""

    @staticmethod
    def _stages(h, run: int = 0) -> list[tuple[str, str | None]]:
        summary = h.results[run].summary
        assert summary is not None and summary.ingest is not None
        return [(f.source_file or "", f.cause.stage) for f in summary.ingest.failed]

    def test_a_folded_recording_copy_is_labelled_ingest(self, tmp_path: Path) -> None:
        def build(d: Path, _i: int):
            original = audio_session(d, 1, "P3")
            return [original, _copy_of(d, original, 2, "P3 (1).wav")]

        assert self._stages(run_pipeline(tmp_path, build)) == [("P3 (1).wav", "s01_ingest")]

    def test_a_folded_transcript_copy_is_labelled_ingest(self, tmp_path: Path) -> None:
        def build(d: Path, _i: int):
            return [_transcript_session(d, 1, "transcript.vtt"),
                    _transcript_session(d, 2, "transcript (1).vtt")]

        assert self._stages(run_pipeline(tmp_path, build)) == [
            ("transcript (1).vtt", "s01_ingest"),
        ]

    def test_a_file_stage_2_set_aside_is_still_labelled_stage_2(self, tmp_path: Path) -> None:
        """The control: stage 2 writes ``error`` and nothing else."""
        from bristlenose.config import BristlenoseSettings
        from bristlenose.pipeline import Pipeline

        session = audio_session(tmp_path, 1, "P3")
        session.files[0].error = UnusableReason.EMPTY.value
        pipeline = Pipeline(BristlenoseSettings(project_name="t"))
        pipeline._record_ingest_outcome([session], [])
        ingest = pipeline._summary.ingest
        assert ingest is not None
        assert [f.cause.stage for f in ingest.failed] == ["s02_extract_audio"]

def test_the_harness_runs_the_discussion_stage_without_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``run_pipeline`` is shared by ten suites that drive the whole pipeline
    to test other stages. The discussion stage is on by default and the
    harness once handed it a MagicMock client, so every drive from a suite
    without ``conftest.no_discussion_stage`` logged its failure, unasserted,
    and a real failure there was invisible (#109 did the same for the caches
    suite). Here, outside that fixture, on purpose: fresh, then cached.

    Read from the run's own log file: the pipeline's logging setup keeps
    these records from ``caplog``, so a caplog assertion passes on a harness
    that logs the failure every run."""
    # The file's level comes from the environment; a quieter one would hide
    # the line this looks for.
    monkeypatch.delenv("BRISTLENOSE_LOG_LEVEL", raising=False)
    h = run_pipeline(tmp_path, lambda d, _i: [audio_session(d, 1, "bare")], runs=2)

    # The failure's own words, at whatever level they are logged.
    failures = [line for line in h.log().splitlines()
                if "discussion stage failed" in line or re.search(r"discussion: s\d+ failed", line)]
    assert failures == [], failures
    assert h.discussed == [["s1"]], h.discussed  # ran once, then cached
