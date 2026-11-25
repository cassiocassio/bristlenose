"""A malformed subtitle timing skips its cue and says so (R124).

pysrt read an unparseable time component as 0 (`00:00:aa,000` is 0:00), so
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
    "00:00:aa,000 --> 00:00:04,000",   # pysrt read: 0:00
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


# Our own reader replaced pysrt (GPL-3.0) on 25 Nov 2026. It reads a block as
# pysrt 1.1.2 did, quirks included, so the same bytes give the same segments
# and SUBTITLE_PARSER_VERSION did not move (a bump re-parses, and re-analyses,
# every platform-transcript session). These pin the quirks a cache depends on;
# the equivalence itself was shown by a differential run against pysrt on
# 200,000 generated blocks before it was removed.
@pytest.mark.parametrize(("block", "expected"), [
    (["1", "00:00:03,000 --> 00:00:04,500", "Anna: one", "two"],
     (3.0, 4.5, "Anna: one\ntwo")),
    (["00:00:03,000 --> 00:00:04,000", "no index"], (3.0, 4.0, "no index")),
    # Milliseconds are the digits as written: ",5" is 5 ms, not 500.
    (["0:0:3,5 --> 0:0:4,50", "short"], (3.005, 4.05, "short")),
    # Components past their range carry, as a total: 75 minutes is 1:15:00.
    (["0:75:00,000 --> 1:15:01,000", "t"], (4500.0, 4501.0, "t")),
    # Position text after the end time is ignored up to its first space...
    (["00:00:03,000 --> 00:00:04,000 X1:0 X2:0", "p"], (3.0, 4.0, "p")),
    # A component with trailing junk reads its leading digits (the gate lets a
    # tab-separated position through, and it folds into the end time)...
    (["00:00:03,000 --> 00:00:04,000\tfoo", "p"], (3.0, 4.0, "p")),
    # ...unless the junk adds a component, which spoils the end time.
    (["00:00:03,000 --> 00:00:04,000\tX1:0 X2:0", "p"], None),
    # A timing alone is not a cue (it counts as skipped)...
    (["00:00:03,000 --> 00:00:04,000"], None),
    # ...but an index and a timing is, with no text: dropped later, unwarned.
    (["1", "00:00:03,000 --> 00:00:04,000"], (3.0, 4.0, "")),
    # An index then text, with no timing.
    (["1", "just words"], None),
    # A second arrow on the timing line.
    (["00:00:03,000 --> 00:00:04,000 --> 1", "x"], None),
])
def test_a_cue_reads_as_pysrt_read_it(
    block: list[str], expected: tuple[float, float, str] | None,
) -> None:
    from bristlenose.stages.s03_parse_subtitles import _srt_cue

    cue = _srt_cue(block)
    assert (None if cue is None else (cue.start, cue.end, cue.text)) == expected
