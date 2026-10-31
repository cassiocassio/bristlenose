"""A Meet "Notes by Gemini" document with no transcript in it is not a transcript (ruling 9, 31 Oct 2026).

Drive's .docx export of a Meet Doc flattens its Notes tab and its Transcript tab into
one paragraph stream. When the Transcript tab is empty nothing in it is timed, so the
parser read every paragraph (Gemini's summary, an attendee's address) as speech at
00:00, the speaker stage guessed voices for it, and the summary's sentences became
quotes nobody said. It is now refused, by name, as ``notes_only``. The two documents
here are built by hand (decision #183): session 3 is to capture real ones, so the
rule is the filename's Meet date tail plus "nothing in it is timed", never the
localised tab headings.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from bristlenose.events import CauseCategoryEnum, UnusableReason
from bristlenose.models import FileType, InputFile, InputSession

_T0 = datetime(2026, 10, 20, tzinfo=timezone.utc)

_NOTES = [
    "📝 Notes",
    "Checkout call",
    "Invited participant@example.org Alex Example",
    "A summary wasn't produced for this meeting.",
    "How is the quality of these specific notes? Take a short survey.",
    "📖 Transcript",
]
_MEET_NAME = "Checkout call - 2026_10_20 14_00 GMT - Notes by Gemini.docx"


def _docx(tmp_path: Path, name: str, paragraphs: list[str]) -> Path:
    from docx import Document

    doc = Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    path = tmp_path / name
    doc.save(str(path))
    return path


def _gather(path: Path):
    from bristlenose.config import BristlenoseSettings
    from bristlenose.pipeline import Pipeline

    f = InputFile(path=path, file_type=FileType.DOCX, created_at=_T0,
                  size_bytes=path.stat().st_size)
    session = InputSession(
        session_id="s1", session_number=1, participant_id="p1", participant_number=1,
        files=[f], has_existing_transcript=True, session_date=_T0,
    )
    pipeline = Pipeline(BristlenoseSettings(skip_transcription=True))
    return asyncio.run(pipeline._gather_all_segments([session]))


def test_a_meet_notes_document_with_nothing_timed_is_refused_as_notes_only(
    tmp_path: Path,
) -> None:
    segments, outcome = _gather(_docx(tmp_path, _MEET_NAME, _NOTES))
    assert segments == {}, "Gemini's summary must never become a transcript"
    (failure,) = outcome.failed
    assert failure.cause.category == CauseCategoryEnum.UNUSABLE_INPUT
    assert failure.cause.reason == UnusableReason.NOTES_ONLY
    assert failure.source_file == _MEET_NAME
    assert failure.session_id == "s1"


def test_the_api_spelling_of_the_name_is_refused_too(tmp_path: Path) -> None:
    """Drive's API names the Doc with slashes and a colon; a hand download may keep them."""
    name = "Checkout call - 2026-10-20 14.00 GMT - Notes by Gemini.docx"
    segments, outcome = _gather(_docx(tmp_path, name, _NOTES))
    assert segments == {}
    assert [f.cause.reason for f in outcome.failed] == [UnusableReason.NOTES_ONLY]


def test_an_agency_document_with_an_ordinary_name_is_still_read(tmp_path: Path) -> None:
    """The rule is the Meet filename AND nothing timed: an untimed agency file is a transcript."""
    segments, outcome = _gather(_docx(tmp_path, "P3 interview transcript.docx", [
        "Interviewer: How did you find the checkout?",
        "Participant: I couldn't find the save button.",
    ]))
    assert outcome.failed == []
    assert list(segments) == ["s1"]


def test_a_meet_document_that_does_hold_a_timed_transcript_is_still_read(
    tmp_path: Path,
) -> None:
    segments, outcome = _gather(_docx(tmp_path, _MEET_NAME, [
        *_NOTES,
        "00:00:11",
        "Alex Example: Okay, talking, talking.",
        "Transcription ended after 00:00:39",
    ]))
    assert outcome.failed == []
    assert list(segments) == ["s1"]
    assert all("summary" not in s.text for s in segments["s1"])
