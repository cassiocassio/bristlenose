"""A decode failure on an audio file is stated as the file's problem, not as a Whisper failure.

Found on a 0.46.0 walk (16 Nov 2026): a 2 KB random-bytes ``.mp3`` was recorded as
category ``whisper`` with ``source_file`` null and the whole ffmpeg banner as its
message, which the diagnostic popover prints raw under the session id.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from bristlenose.events import CauseCategoryEnum
from bristlenose.refusals import UnusableReason
from bristlenose.stages import s05_transcribe


def _run(monkeypatch: pytest.MonkeyPatch, audio: Path):
    from datetime import datetime

    from bristlenose.models import FileType, InputFile, InputSession

    banner = "Failed to load audio: ffmpeg version 8.0.1 Copyright (c) ... configuration: --enable-gpl ..."

    def _fake_init(_settings):
        def _t(_path, _settings, **_kw):
            raise RuntimeError(banner)

        return _t

    monkeypatch.setattr(s05_transcribe, "_init_mlx_backend", _fake_init)
    monkeypatch.setattr(s05_transcribe, "_resolve_backend", lambda _c, _h: "mlx")  # noqa: ARG005
    session = InputSession(
        session_id="s1", session_number=1,
        participant_id="p1", participant_number=1,
        files=[InputFile(
            path=audio, file_type=FileType.AUDIO,
            created_at=datetime(2026, 9, 22), size_bytes=audio.stat().st_size,
        )],
        audio_path=audio,
        session_date=datetime(2026, 9, 22),
    )
    settings = type("S", (), {
        "whisper_backend": "mlx", "whisper_model": "tiny", "whisper_language": "auto",
    })()
    _r, _l, outcome = s05_transcribe.transcribe_sessions([session], settings)
    return outcome, banner


def test_random_bytes_are_not_a_recording(monkeypatch, tmp_path) -> None:
    audio = tmp_path / "04 broken.mp3"
    audio.write_bytes(bytes(range(256)) * 8)
    outcome, banner = _run(monkeypatch, audio)
    assert len(outcome.failed) == 1
    failure = outcome.failed[0]
    cause = failure.cause
    assert cause.category == CauseCategoryEnum.UNUSABLE_INPUT, cause.category
    assert cause.reason == UnusableReason.NOT_A_RECORDING
    assert failure.source_file == "04 broken.mp3"
    assert cause.stage == "s05_transcribe" and cause.session_id == "s1"
    assert "ffmpeg" not in (cause.message or "") and banner not in (cause.message or "")


def test_a_zero_byte_audio_file_is_empty(monkeypatch, tmp_path) -> None:
    audio = tmp_path / "empty.mp3"
    audio.write_bytes(b"")
    outcome, _ = _run(monkeypatch, audio)
    assert outcome.failed[0].cause.reason == UnusableReason.EMPTY


def test_control_a_file_that_looks_like_audio_keeps_the_tool_category(monkeypatch, tmp_path) -> None:
    # A real-looking recording that still will not decode may be a broken or
    # sandboxed ffmpeg, not a bad file: it must not be blamed on the file.
    audio = tmp_path / "good.mp3"
    audio.write_bytes(b"ID3" + bytes(2000))
    outcome, _ = _run(monkeypatch, audio)
    cause = outcome.failed[0].cause
    assert cause.category == CauseCategoryEnum.WHISPER
    assert cause.reason is None
