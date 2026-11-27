"""The transcription engine is recorded per session, and a cache never relabels it (D6).

In the store build a session may be transcribed by Apple's on-device model or by
Whisper, and which one cannot be worked out afterwards (owner, 18 Nov 2026). The
session's transcribe record in the manifest carries it. A session served from the
cache keeps the engine that transcribed it, not this run's; a record written before
the field existed stays unknown rather than being stamped with this run's engine.

Real ``Pipeline`` and real manifest; the stages around them are stubbed
(``tests/test_pipeline_command_caches._drive``).
"""

from __future__ import annotations

import json
from pathlib import Path

from tests.test_pipeline_command_caches import _drive

APPLE = ("apple-speech", None)
WHISPER = ("mlx-whisper", "large-v3-turbo")


def _manifest_path(tmp_path: Path) -> Path:
    return tmp_path / "output" / ".bristlenose" / "pipeline-manifest.json"


def _engines(tmp_path: Path) -> dict[str, tuple[str | None, str | None]]:
    from bristlenose.manifest import load_manifest

    manifest = load_manifest(tmp_path / "output")
    assert manifest is not None
    sessions = manifest.stages["transcribe"].sessions or {}
    return {
        sid: (rec.transcription_engine, rec.transcription_model)
        for sid, rec in sessions.items()
    }


def _as_written_before_the_field(tmp_path: Path, sid: str) -> None:
    """``sid``'s record as a manifest from before 26 Nov 2026 holds it: no field."""
    path = _manifest_path(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    record = data["stages"]["transcribe"]["sessions"][sid]
    record.pop("transcription_engine")
    record.pop("transcription_model")
    path.write_text(json.dumps(data), encoding="utf-8")


def test_each_session_keeps_the_engine_that_transcribed_it(tmp_path: Path) -> None:
    _drive(tmp_path, "run", 2, {}, engine_for=lambda _sid: APPLE)
    assert _engines(tmp_path) == {"s1": APPLE, "s2": APPLE}
    _as_written_before_the_field(tmp_path, "s2")

    # Whisper is on disk now, and a new recording joins: the per-session resume
    # serves s1 and s2 from the cache and transcribes only s3.
    log: dict = {}
    _drive(tmp_path, "run", 3, log, engine_for=lambda _sid: WHISPER)
    assert log["transcribed"] == [["s3"]], log
    assert _engines(tmp_path) == {"s1": APPLE, "s2": (None, None), "s3": WHISPER}

    # Nothing changed: the stage is served whole from the cache, and still says so.
    log = {}
    _drive(tmp_path, "run", 3, log, engine_for=lambda _sid: ("faster-whisper", "small"))
    assert "transcribed" not in log, log
    assert _engines(tmp_path) == {"s1": APPLE, "s2": (None, None), "s3": WHISPER}


def test_a_session_delivered_before_a_stop_keeps_its_engine(tmp_path: Path) -> None:
    """A run stopped part-way leaves the records the readable chain wrote as it
    delivered each session; the next run serves those from the cache."""
    import pytest

    def stop_at_s2(sid: str) -> tuple[str, str | None]:
        if sid == "s2":
            raise RuntimeError("stopped while s2 was transcribed")
        return APPLE

    with pytest.raises(RuntimeError, match="stopped"):
        _drive(tmp_path, "run", 2, {}, engine_for=stop_at_s2)

    log: dict = {}
    _drive(tmp_path, "run", 2, log, engine_for=lambda _sid: WHISPER)
    assert log["transcribed"] == [["s2"]], log
    assert _engines(tmp_path) == {"s1": APPLE, "s2": WHISPER}
