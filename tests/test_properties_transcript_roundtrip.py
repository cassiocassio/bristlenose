"""Transcript .txt files are a round-trip format: whatever the writer emits, the
reader must load back.

The pipeline writes raw transcripts (``write_raw_transcripts``) and reads them
back on resume and re-analysis (``load_transcripts_from_dir``). The reader's
timecode field was ``\\d{2}`` until 22 Aug 2026, when ``format_timecode``
stopped zero-padding the hour. A segment at ``[1:00:00]`` then failed to match
and was dropped silently, and a short transcript was the only symptom. This
property generates whole transcripts, an hour-plus included, writes them with
the real writer, reads them with the real reader, and checks nothing was lost.

Not covered, deliberately: the optional speaker label. The writer prints it as
``(Speaker B)`` and the reader keeps it as part of the text, so it is not a
round-tripped field.
"""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path

from hypothesis import example, given
from hypothesis import strategies as st

from bristlenose.models import FullTranscript, TranscriptSegment
from bristlenose.pipeline import load_transcripts_from_dir
from bristlenose.stages.s06_merge_transcript import write_raw_transcripts

# parse_timecode's declared domain: hours are 1-2 digits.
MAX_TC = 99 * 3600 + 59 * 60 + 59

# Text the writer can carry on one line: no line-breaking characters
# (str.splitlines splits on the Cc ones and on U+2028/U+2029), and no edge
# whitespace, which the reader strips.
_line_text = (
    st.text(
        alphabet=st.characters(exclude_categories=("Cs", "Cc", "Zl", "Zp")),
        min_size=1,
        max_size=40,
    )
    .map(str.strip)
    .filter(bool)
)

_segment = st.builds(
    lambda start, code, text: TranscriptSegment(
        start_time=float(start), end_time=float(start), text=text, speaker_code=code
    ),
    st.integers(0, MAX_TC),
    st.sampled_from(["p1", "p2", "m1", "m2", "o1"]),
    _line_text,
)

_dates = st.datetimes(
    min_value=datetime(1990, 1, 1), max_value=datetime(2090, 1, 1), timezones=st.just(timezone.utc)
)


@given(
    segments=st.lists(_segment, min_size=1, max_size=12),
    session_n=st.integers(1, 999),
    duration=st.integers(0, MAX_TC),
    session_date=_dates,
)
@example(  # the silent drop: an hour-plus segment, unpadded hour field
    segments=[
        TranscriptSegment(start_time=59.0, end_time=59.0, text="before", speaker_code="m1"),
        TranscriptSegment(start_time=3600.0, end_time=3600.0, text="the hour", speaker_code="p1"),
    ],
    session_n=1,
    duration=3725,
    session_date=datetime(2026, 8, 22, tzinfo=timezone.utc),
)
def test_raw_transcript_reads_back_what_was_written(segments, session_n, duration, session_date):
    session_id = f"s{session_n}"
    transcript = FullTranscript(
        session_id=session_id,
        participant_id="p1",
        source_file="interview.mp4",
        session_date=session_date,
        duration_seconds=float(duration),
        segments=segments,
    )
    with tempfile.TemporaryDirectory() as tmp:
        write_raw_transcripts([transcript], Path(tmp))
        (loaded,) = load_transcripts_from_dir(Path(tmp))

    assert loaded.session_id == session_id
    assert loaded.duration_seconds == duration
    assert loaded.session_date == session_date
    # If this fails: a written segment did not come back — the reader's
    # timecode pattern and the writer's format have drifted apart.
    assert [(s.start_time, s.speaker_code, s.text) for s in loaded.segments] == [
        (s.start_time, s.speaker_code, s.text) for s in segments
    ]
