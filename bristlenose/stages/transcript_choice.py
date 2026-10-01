"""One transcript per session — which file speaks for a meeting.

A session can arrive with several transcript files for the same recording:
Teams' ``.vtt`` and its ``.docx`` export, a cloud transcript our import wrote
beside one the researcher dropped in by hand. Reading them all gave every
turn twice (measured, 30 Sep 2026). Exactly one is used, chosen by what it
carries rather than by what it is called:

1. **Named beats unnamed.** Real speaker names are the whole reason to prefer
   a platform transcript over Whisper; a file with none has thrown that away.
2. **Coverage.** A transcript spanning the hour beats one spanning ten minutes.
   Two exports of one meeting end a few seconds apart, so spans within a
   tolerance of each other count as equal and fall through to format.
3. **Format.** Cloud VTT (our writer, trusted) > vendor VTT / SRT (timed cues)
   > DOCX (turn starts only; ends are inferred downstream).

The losers are returned so the caller can **state** the supersession — a log
line and a CLI warning naming both files. Silently using one of two files is
how a researcher comes to believe the other was read.
"""

from __future__ import annotations

from dataclasses import dataclass

from bristlenose.models import (
    CLOUD_TRANSCRIPT_SOURCE,
    FileType,
    InputFile,
    TranscriptSegment,
)
from bristlenose.people import is_generic_label

#: Spans within this fraction of the longest candidate's span are the same
#: coverage. Teams' .vtt and .docx of one meeting differ by seconds; a
#: ten-minute excerpt beside an hour's transcript differs by a lot.
COVERAGE_TOLERANCE = 0.10


@dataclass
class ParsedTranscriptFile:
    """A transcript file that parsed, with the segments it produced."""

    file: InputFile
    segments: list[TranscriptSegment]

    @property
    def is_named(self) -> bool:
        """At least one speaker label that is a name rather than a placeholder."""
        return any(
            seg.speaker_label and not is_generic_label(seg.speaker_label)
            for seg in self.segments
        )

    @property
    def span(self) -> float:
        """Seconds between the first cue's start and the last cue's end."""
        if not self.segments:
            return 0.0
        return max(s.end_time for s in self.segments) - min(s.start_time for s in self.segments)

    @property
    def format_rank(self) -> int:
        if any(seg.source == CLOUD_TRANSCRIPT_SOURCE for seg in self.segments):
            return 3
        if self.file.file_type in (FileType.SUBTITLE_VTT, FileType.SUBTITLE_SRT):
            return 2
        return 1


def choose_transcript(
    candidates: list[ParsedTranscriptFile],
) -> tuple[ParsedTranscriptFile, list[ParsedTranscriptFile]]:
    """Pick the transcript a session uses; return it and the ones it supersedes.

    Order among equals is the caller's order, so a tie is deterministic.

    Raises:
        ValueError: no candidates.
    """
    if not candidates:
        raise ValueError("choose_transcript needs at least one candidate")

    pool = [c for c in candidates if c.segments] or list(candidates)

    if any(c.is_named for c in pool):
        pool = [c for c in pool if c.is_named]

    longest = max(c.span for c in pool)
    floor = longest * (1.0 - COVERAGE_TOLERANCE)
    pool = [c for c in pool if c.span >= floor]

    best_rank = max(c.format_rank for c in pool)
    chosen = next(c for c in pool if c.format_rank == best_rank)

    superseded = [c for c in candidates if c is not chosen]
    return chosen, superseded
