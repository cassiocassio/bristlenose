"""One participant's broken upload must not destroy the other ninety-nine.

Reproduced 18 Aug 2026 against the real stages: a folder of 42 sessions
containing a single zero-byte `.mp4` aborted the entire run at stage 2 with
`AudioToolError`, discarding every healthy session with it. Three such files —
failed downloads of real research sessions from 2021-22 — were sitting in the
maintainer's Downloads folder, so this is an observed input, not a contrived one.

The fix must hold two things apart that both surface as a non-zero ffprobe exit:

  * the *tool* cannot run   → still fatal, nothing is trustworthy after that
  * the *file* is rejected  → skip it, record it, carry on

No test here shells out to ffprobe: CI installs no ffmpeg, and the logic under
test is the handling, not the probing.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import pytest

from bristlenose.models import FileType, InputFile, InputSession
from bristlenose.stages import s02_extract_audio
from bristlenose.stages.s02_extract_audio import extract_audio_for_sessions
from bristlenose.utils.audio import (
    AudioToolError,
    MediaFileDamagedError,
    _looks_like_toolchain_failure,
)


def _session(tmp_path: Path, name: str) -> InputSession:
    path = tmp_path / name
    path.write_bytes(b"")
    return InputSession(
        session_id=name, session_number=1, participant_id="p1", participant_number=1,
        session_date=datetime.now(timezone.utc),
        files=[InputFile(path=path, file_type=FileType.VIDEO,
                         created_at=datetime.now(timezone.utc), size_bytes=0)],
    )


class TestFailureAttribution:
    """Which of the two failures a given stderr represents."""

    @pytest.mark.parametrize("stderr", [
        "[mov,mp4,m4a @ 0x1] moov atom not found",
        "Invalid data found when processing input",
        "[matroska @ 0x1] File ended prematurely",
    ])
    def test_demuxer_complaints_blame_the_file(self, stderr: str) -> None:
        assert not _looks_like_toolchain_failure(stderr)

    @pytest.mark.parametrize("stderr", [
        "ffprobe: error while loading shared libraries: libblas.so.3",
        "dyld: Library not loaded: @rpath/libavcodec.dylib",
        "zsh: command not found: ffprobe",
        "Bad CPU type in executable",
        "",           # -v error always says *something* about a file it dislikes
        "   \n  ",
    ])
    def test_loader_failures_and_silence_blame_the_tool(self, stderr: str) -> None:
        assert _looks_like_toolchain_failure(stderr)

    def test_damaged_is_catchable_as_the_broader_error(self) -> None:
        """Existing fail-loud handlers must keep working unchanged."""
        assert issubclass(MediaFileDamagedError, AudioToolError)


class TestBatchSurvival:
    def test_one_damaged_file_does_not_abort_the_batch(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sessions = [_session(tmp_path, n) for n in
                    ("healthy-1.mp4", "damaged.mp4", "healthy-2.mp4")]

        def fake_probe(path: Path) -> bool:
            if path.name == "damaged.mp4":
                raise MediaFileDamagedError(
                    "ffprobe failed to probe damaged.mp4 (exit 1): moov atom not found"
                )
            return True

        monkeypatch.setattr(s02_extract_audio, "has_audio_stream", fake_probe)
        monkeypatch.setattr(s02_extract_audio, "extract_audio_from_video",
                            lambda src, out: out)

        asyncio.run(extract_audio_for_sessions(sessions, tmp_path / "work"))

        healthy = [s for s in sessions if s.session_id.startswith("healthy")]
        assert all(s.audio_path is not None for s in healthy), (
            "healthy sessions lost their audio because a sibling file was damaged"
        )
        damaged = next(s for s in sessions if s.session_id == "damaged.mp4")
        assert damaged.audio_path is None

    def test_the_damaged_file_says_so_rather_than_vanishing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Silence here is the failure mode: a participant missing from the
        report that the researcher still believes is present."""
        session = _session(tmp_path, "damaged.mp4")
        monkeypatch.setattr(s02_extract_audio, "has_audio_stream",
                            lambda p: (_ for _ in ()).throw(MediaFileDamagedError("bad")))

        asyncio.run(extract_audio_for_sessions([session], tmp_path / "work"))

        assert session.files[0].error, "the file was skipped without recording why"
        assert "damaged" in session.files[0].error

    def test_a_silent_video_is_recorded_too(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        session = _session(tmp_path, "silent.mp4")
        monkeypatch.setattr(s02_extract_audio, "has_audio_stream", lambda p: False)

        asyncio.run(extract_audio_for_sessions([session], tmp_path / "work"))

        assert session.files[0].error == "no audio track"

    def test_a_broken_toolchain_still_aborts_the_run(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The guarantee the isolation must not weaken.

        If ffprobe itself cannot run, nothing after it is trustworthy, and a
        confidently-empty report is the worst possible outcome.
        """
        sessions = [_session(tmp_path, n) for n in ("a.mp4", "b.mp4")]
        monkeypatch.setattr(
            s02_extract_audio, "has_audio_stream",
            lambda p: (_ for _ in ()).throw(AudioToolError("ffprobe binary not found")),
        )

        with pytest.raises(AudioToolError):
            asyncio.run(extract_audio_for_sessions(sessions, tmp_path / "work"))


class TestUnsupportedFilesAreStated:
    def test_discover_reports_what_it_declined(self, tmp_path: Path) -> None:
        from bristlenose.stages.s01_ingest import SkippedFile, discover_files

        (tmp_path / "interview.mp4").write_bytes(b"x")
        (tmp_path / "tape-capture.dv").write_bytes(b"x")   # real media, still declined
        (tmp_path / "._interview.mp4").write_bytes(b"x")   # AppleDouble noise

        skipped: list[SkippedFile] = []
        found = discover_files(tmp_path, skipped)

        assert [f.path.name for f in found] == ["interview.mp4"]
        assert [s.path.name for s in skipped] == ["tape-capture.dv"], (
            "OS metadata must stay silent; a real file the user created must not"
        )
        assert ".dv" in skipped[0].reason

    def test_omitting_the_collector_keeps_the_old_signature(self, tmp_path: Path) -> None:
        from bristlenose.stages.s01_ingest import discover_files

        (tmp_path / "notes.pages").write_bytes(b"x")
        assert discover_files(tmp_path) == []
