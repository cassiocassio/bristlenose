"""Files in a format we never offered are left alone; files in one we offer can fail (6 Nov 2026).

Talismanic read "Partial completion" because ~30 scripts, logs and data files each counted as a
refusal. The rule now: a format we say we read (audio, video, .srt, .vtt, .docx) fails with a
reason when we open it and it is unusable; any other extension was never attempted (by `run`; `analyze` does offer `.txt`), so it is
counted as "left alone" on the run summary and named only in the log.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from bristlenose.events import UnusableReason
from bristlenose.models import FileType, InputFile, InputSession
from bristlenose.stages.s01_ingest import SkippedFile, discover_files, split_left_alone

_T0 = datetime(2026, 11, 5, tzinfo=timezone.utc)


def test_split_left_alone_keeps_every_other_reason_stated() -> None:
    declined = [
        SkippedFile(Path("a.py"), UnusableReason.UNSUPPORTED_FORMAT, ".py"),
        SkippedFile(Path("b.txt"), UnusableReason.UNSUPPORTED_FORMAT, ".txt"),
        SkippedFile(Path("locked"), UnusableReason.UNREADABLE_FOLDER, "denied"),
    ]
    stated, left_alone = split_left_alone(declined)

    assert [s.path.name for s in stated] == ["locked"]
    assert left_alone == 2


def test_a_folder_of_strays_beside_one_recording_has_nothing_to_state(tmp_path: Path) -> None:
    (tmp_path / "p1.mp4").write_bytes(b"x")
    for name in ("build.py", "notes.txt", "labels.xlsx", "guide.md", "tape.opus"):
        (tmp_path / name).write_bytes(b"x")
    declined: list[SkippedFile] = []

    found = discover_files(tmp_path, declined)
    stated, left_alone = split_left_alone(declined)

    assert [f.path.name for f in found] == ["p1.mp4"]
    assert stated == []
    assert left_alone == 5


def test_the_left_alone_count_reaches_the_summary_and_not_the_failures() -> None:
    from bristlenose.config import BristlenoseSettings
    from bristlenose.events import PipelineSummary
    from bristlenose.pipeline import Pipeline

    pipeline = Pipeline(BristlenoseSettings(skip_transcription=True))
    pipeline._summary = PipelineSummary()
    f = InputFile(path=Path("p1.mp4"), file_type=FileType.VIDEO, created_at=_T0, size_bytes=1)
    session = InputSession(
        session_id="s1", session_number=1, participant_id="p1", participant_number=1,
        files=[f], session_date=_T0,
    )

    pipeline._record_ingest_outcome([session], [], left_alone=30)

    assert pipeline._summary.ingest is not None
    assert pipeline._summary.ingest.left_alone == 30
    assert pipeline._summary.ingest.failed == []
    assert pipeline._summary.ingest.attempted == 1  # strays were never attempted


def test_a_discussion_guide_docx_is_refused_as_no_transcript(tmp_path: Path) -> None:
    from docx import Document

    from bristlenose.config import BristlenoseSettings
    from bristlenose.pipeline import Pipeline

    doc = Document()
    for line in ("Project Ikea Discussion Guide", "Warm-up: last furniture purchase.", "Probe on checkout."):
        doc.add_paragraph(line)
    path = tmp_path / "Discussion guide.docx"
    doc.save(str(path))
    f = InputFile(path=path, file_type=FileType.DOCX, created_at=_T0,
                  size_bytes=path.stat().st_size)
    session = InputSession(
        session_id="s1", session_number=1, participant_id="p1", participant_number=1,
        files=[f], has_existing_transcript=True, session_date=_T0,
    )
    pipeline = Pipeline(BristlenoseSettings(skip_transcription=True))

    segments, outcome = asyncio.run(pipeline._gather_all_segments([session]))

    assert segments == {}
    (failure,) = outcome.failed
    assert failure.cause.reason == UnusableReason.NO_TRANSCRIPT
    assert failure.source_file == "Discussion guide.docx"
