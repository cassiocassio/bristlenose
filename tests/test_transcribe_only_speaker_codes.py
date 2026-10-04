"""`bristlenose transcribe` codes its speakers the way a full run does.

Until 4 Oct 2026 ``run_transcription_only`` ran the heuristic role pass and
never assigned codes, so every segment fell through to the session's
provisional ``p<session number>``: a moderator and a participant written as one
person, and two sessions' participants under codes the registry would later
hand to someone else. The seam is ``_gather_all_segments``, as in
``test_refusals.py::TestTranscribeOnlyStatesSilenceToo``.
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from bristlenose.events import StageOutcome
from bristlenose.models import FileType, InputFile, InputSession, TranscriptSegment
from bristlenose.pipeline import Pipeline
from bristlenose.session_registry import SessionRegistry

_CODE = re.compile(r"^\[\d+:\d{2}(?::\d{2})?\]\s+\[(\w+)\]", re.MULTILINE)


def _sessions(input_dir: Path, n: int) -> list[InputSession]:
    out = []
    for i in range(1, n + 1):
        media = input_dir / f"rec{i}.wav"
        media.write_bytes(b"fake")
        out.append(InputSession(
            session_id=f"s{i}", session_number=i,
            participant_id=f"p{i}", participant_number=i,
            session_date=datetime.now(timezone.utc),
            files=[InputFile(
                path=media, file_type=FileType.AUDIO,
                created_at=datetime.now(timezone.utc), size_bytes=4,
                duration_seconds=60.0,
            )],
            audio_path=media,
        ))
    return out


def _interview() -> list[TranscriptSegment]:
    """A labelled two-speaker interview the heuristic can tell apart."""
    lines = [
        ("Mod", "Thanks for joining. Can you tell me about the last time you shopped?"),
        ("Ann", "I went to the store on Saturday and could not find the checkout at all, "
                "so I wandered around for ages before asking someone for help."),
        ("Mod", "What happened next? Could you walk me through it?"),
        ("Ann", "Someone pointed me to the back of the shop, and the queue there was long, "
                "so I left the basket and went home without buying anything."),
    ]
    return [
        TranscriptSegment(
            segment_index=i, start_time=float(i * 10), end_time=float(i * 10 + 9),
            text=text, speaker_label=label,
        )
        for i, (label, text) in enumerate(lines)
    ]


def _run(tmp_path: Path, n: int = 2) -> Path:
    settings = MagicMock()
    settings.project_name = "codes"
    settings.write_intermediate = False
    settings.color_scheme = "default"
    pipeline = Pipeline(settings)

    input_dir = tmp_path / "in"
    input_dir.mkdir()
    output_dir = tmp_path / "out"
    sessions = _sessions(input_dir, n)

    async def _fake_gather(_self, _sessions, **_kw):
        return (
            {s.session_id: _interview() for s in _sessions},
            StageOutcome(attempted=len(_sessions), succeeded=len(_sessions)),
        )

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
    return output_dir


def _codes(output_dir: Path, sid: str) -> list[str]:
    text = (output_dir / "transcripts-raw" / f"{sid}.txt").read_text(encoding="utf-8")
    return _CODE.findall(text)


def test_the_moderator_and_the_participant_are_two_speakers(tmp_path: Path) -> None:
    out = _run(tmp_path)
    assert _codes(out, "s1") == ["m1", "p1", "m1", "p1"]


def test_participants_are_numbered_across_the_study(tmp_path: Path) -> None:
    out = _run(tmp_path)
    assert set(_codes(out, "s2")) == {"m1", "p2"}


def test_the_codes_are_recorded_so_a_full_run_keeps_them(tmp_path: Path) -> None:
    out = _run(tmp_path)
    reg = SessionRegistry.load(out)
    assert reg.speakers_for("s1") == {"Mod": "m1", "Ann": "p1"}
    assert reg.speakers_for("s2") == {"Mod": "m1", "Ann": "p2"}
