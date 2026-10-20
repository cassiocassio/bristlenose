"""A malformed subtitle timing skips its cue and says so (R124).

pysrt reads an unparseable time component as 0 (`00:00:aa,000` is 0:00), so
the cue jumped to the start of the session, and because it now sat before its
neighbour the merge pass folded the speaker's next cue into it. A timing line
it could not split at all dropped the cue with nothing said. Both are now
skipped, with one warning naming the file.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import pytest

from bristlenose.models import FileType, InputFile
from bristlenose.stages.s03_parse_subtitles import parse_subtitle_file


def _srt(tmp_path: Path, bad_timing: str) -> InputFile:
    path = tmp_path / "s.srt"
    path.write_text(
        "1\n00:00:01,000 --> 00:00:02,000\nAnna: Hello one\n\n"
        f"2\n{bad_timing}\nBob: Bad stamp\n\n"
        "3\n00:00:05,000 --> 00:00:06,000\nBob: Third line\n\n"
        "4\n00:00:30,000 --> 00:00:31,000\nAnna: Fourth\n",
        encoding="utf-8",
    )
    return InputFile(
        path=path, file_type=FileType.SUBTITLE_SRT,
        created_at=datetime(2026, 10, 20, tzinfo=timezone.utc),
        size_bytes=path.stat().st_size,
    )


@pytest.mark.parametrize("bad", [
    "00:00:aa,000 --> 00:00:04,000",   # pysrt: 0:00
    "00:00:03,000 -> 00:00:04,000",    # pysrt: dropped silently
    "00:00:03 --> 00:00:04",           # no milliseconds: dropped silently
    "00:00:03,000 --> ",               # no end
])
def test_a_malformed_cue_is_skipped_and_said(
    tmp_path: Path, bad: str, caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger="bristlenose.stages.s03_parse_subtitles"):
        segs = parse_subtitle_file(_srt(tmp_path, bad))
    assert [(s.start_time, s.text) for s in segs] == [
        (1.0, "Hello one"), (5.0, "Third line"), (30.0, "Fourth"),
    ]
    assert any("s.srt" in r.getMessage() for r in caplog.records)


@pytest.mark.parametrize("good", [
    "00:00:03,000 --> 00:00:04,000",
    "00:00:03.000 --> 00:00:04.000",
    "0:0:3,0 --> 0:0:4,0",
    "00:00:03,000-->00:00:04,000",
    "00:00:03,000 --> 00:00:04,000 X1:0 X2:0 Y1:0 Y2:0",
])
def test_a_well_formed_cue_is_kept_without_a_warning(
    tmp_path: Path, good: str, caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger="bristlenose.stages.s03_parse_subtitles"):
        segs = parse_subtitle_file(_srt(tmp_path, good))
    # Bob's next cue is a second later, so the two merge, as they should.
    assert (3.0, "Bad stamp Third line") in [(s.start_time, s.text) for s in segs]
    assert not caplog.records
