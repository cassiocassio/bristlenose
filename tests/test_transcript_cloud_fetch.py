"""A transcript file that is a cloud placeholder is fetched with a bound, then read (R63, line 492).

``.vtt``, ``.srt`` and ``.docx`` files were opened with an unbounded read. A transcript
sitting offloaded in iCloud Drive or OneDrive made the read block with no limit under
the sandbox's dataless policy, and the run hung (docs/design-cloud-files.md: a dataless
file is read with a bound, never skipped and never narrated). The bound is
``fs.ensure_materialised``; a file that does not arrive in time is the same retryable
``cloud_fetch`` failure a recording gets, with the same sentence.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import pytest

from bristlenose.events import CauseCategoryEnum
from bristlenose.models import FileType, InputFile, InputSession
from bristlenose.refusals import CLOUD_FETCH_MESSAGE
from bristlenose.utils.fs import CloudFetchTimeoutError

_T0 = datetime(2026, 10, 31, tzinfo=timezone.utc)
_VTT = "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\n<v Anna>Hello there\n"


def _gather(path: Path, kind: FileType = FileType.SUBTITLE_VTT):
    from bristlenose.config import BristlenoseSettings
    from bristlenose.pipeline import Pipeline

    f = InputFile(path=path, file_type=kind, created_at=_T0, size_bytes=path.stat().st_size)
    session = InputSession(
        session_id="s1", session_number=1, participant_id="p1", participant_number=1,
        files=[f], has_existing_transcript=True, session_date=_T0,
    )
    pipeline = Pipeline(BristlenoseSettings(skip_transcription=True))
    return asyncio.run(pipeline._gather_all_segments([session]))


def test_a_transcript_that_does_not_download_in_time_is_a_retryable_cloud_fetch_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "interview.vtt"
    path.write_text(_VTT, encoding="utf-8")
    read: list[str] = []

    def never_arrives(p: Path, *a, **k):
        raise CloudFetchTimeoutError("did not arrive")

    monkeypatch.setattr("bristlenose.utils.fs.ensure_materialised", never_arrives)
    monkeypatch.setattr(
        "bristlenose.stages.s03_parse_subtitles.read_text_any_encoding",
        lambda p: read.append(p.name) or _VTT,
    )
    segments, outcome = _gather(path)
    assert segments == {}
    (failure,) = outcome.failed
    assert failure.cause.category == CauseCategoryEnum.CLOUD_FETCH
    assert failure.cause.message == CLOUD_FETCH_MESSAGE
    assert failure.source_file == "interview.vtt"
    assert failure.session_id == "s1"
    assert read == [], "the file must not be read once it did not arrive"


def test_a_transcript_is_fetched_before_it_is_read_and_then_parsed_as_usual(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "interview.vtt"
    path.write_text(_VTT, encoding="utf-8")
    asked: list[str] = []
    monkeypatch.setattr(
        "bristlenose.utils.fs.ensure_materialised",
        lambda p, *a, **k: asked.append(Path(p).name) or False,
    )
    segments, outcome = _gather(path)
    assert asked == ["interview.vtt"]
    assert outcome.failed == []
    assert [s.text for s in segments["s1"]] == ["Hello there"]


def test_a_docx_transcript_is_bounded_the_same_way(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from docx import Document

    doc = Document()
    doc.add_paragraph("Participant: hello")
    path = tmp_path / "interview.docx"
    doc.save(str(path))

    def never_arrives(p: Path, *a, **k):
        raise CloudFetchTimeoutError("did not arrive")

    monkeypatch.setattr("bristlenose.utils.fs.ensure_materialised", never_arrives)
    segments, outcome = _gather(path, FileType.DOCX)
    assert segments == {}
    assert [f.cause.category for f in outcome.failed] == [CauseCategoryEnum.CLOUD_FETCH]
