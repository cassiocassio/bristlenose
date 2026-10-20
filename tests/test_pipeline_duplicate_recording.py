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

import shutil
from pathlib import Path

from bristlenose.events import UnusableReason
from tests.test_pipeline_platform_transcripts import audio_session, run_pipeline


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
