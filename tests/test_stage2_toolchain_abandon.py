"""A media toolchain that will not run stops the run with the banner, not a traceback.

``AudioToolError`` is fail-loud by design (stages/gotchas.md: a broken FFmpeg
must never read as "no audio"). Raised bare from stage 2 it reached the
terminal as a Python traceback naming the recording, as if the file were at
fault: seen on an Intel Mac whose Homebrew FFmpeg had lost a library
(28 Nov 2026, the uv install walk). The pipeline now turns it into a
``PipelineAbandonedError`` whose Cause names only the toolchain, because the
exception's text carries the recording's name, often a participant's.
"""

from __future__ import annotations

import ast
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from bristlenose.events import CauseCategoryEnum
from bristlenose.models import FileType, InputFile, InputSession
from bristlenose.pipeline import Pipeline, PipelineAbandonedError
from bristlenose.utils.audio import AudioToolError

_PIPELINE = Path(__file__).resolve().parent.parent / "bristlenose" / "pipeline.py"


def _video_session(folder: Path) -> InputSession:
    media = folder / "p2 Sarah 2026-08-16 1609.mp4"
    media.write_bytes(b"not really a video")
    now = datetime.now(timezone.utc)
    return InputSession(
        session_id="s1", session_number=1, participant_id="p1", participant_number=1,
        session_date=now,
        files=[InputFile(path=media, file_type=FileType.VIDEO, created_at=now, size_bytes=18)],
    )


def _broken_toolchain(*_a, **_k):
    raise AudioToolError(
        "ffprobe failed to probe p2 Sarah 2026-08-16 1609.mp4 (exit -6): "
        "dyld: Library not loaded: /usr/local/opt/x265/lib/libx265.176.dylib"
    )


def test_transcribe_stops_with_a_cause_that_names_no_recording(tmp_path: Path) -> None:
    settings = MagicMock()
    settings.project_name = "toolchain"
    settings.write_intermediate = False
    settings.color_scheme = "default"
    settings.no_fetch = True
    pipeline = Pipeline(settings)
    input_dir = tmp_path / "in"
    input_dir.mkdir()
    sessions = [_video_session(input_dir)]

    with (
        patch("bristlenose.stages.s01_ingest.ingest", return_value=sessions),
        patch(
            "bristlenose.stages.s02_extract_audio.extract_audio_for_sessions",
            new=_broken_toolchain,
        ),
        patch("bristlenose.preflight.whisper.preflight_whisper"),
        pytest.raises(PipelineAbandonedError) as caught,
    ):
        asyncio.run(pipeline.run_transcription_only(input_dir, tmp_path / "out"))

    cause = caught.value.cause
    assert cause.category == CauseCategoryEnum.MISSING_BINARY
    assert cause.stage == "s02_extract_audio"
    assert "doctor" in cause.message
    assert "Sarah" not in cause.message and ".mp4" not in cause.message
    assert isinstance(caught.value.__cause__, AudioToolError)


def test_every_stage2_call_in_the_pipeline_goes_through_the_guard() -> None:
    """Pin the callers, not only the helper: a new bare call would bring the
    traceback back while the test above stayed green."""
    tree = ast.parse(_PIPELINE.read_text(encoding="utf-8"))
    bare = []
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if fn.name == "_extract_audio_or_abandon":
            continue
        for node in ast.walk(fn):
            if isinstance(node, ast.Call):
                name = getattr(node.func, "id", getattr(node.func, "attr", ""))
                if name == "extract_audio_for_sessions":
                    bare.append(f"{fn.name}:{node.lineno}")
    assert bare == [], f"stage 2 called without the toolchain guard: {bare}"
    guarded = _PIPELINE.read_text(encoding="utf-8").count("self._extract_audio_or_abandon(")
    assert guarded >= 3
