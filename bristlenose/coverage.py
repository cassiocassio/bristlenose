"""Transcript coverage calculation for research reports."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from bristlenose.models import ExtractedQuote, FullTranscript, format_timecode

# Segments with this many words or fewer are collapsed into fragment summaries
FRAGMENT_THRESHOLD = 3


@dataclass
class OmittedSegment:
    """A transcript segment that wasn't extracted as a quote."""

    speaker_code: str
    timecode: str  # formatted as MM:SS or HH:MM:SS
    timecode_seconds: int  # raw seconds for anchor linking
    text: str


@dataclass
class SessionOmitted:
    """Omitted content for one session."""

    full_segments: list[OmittedSegment] = field(default_factory=list)
    fragment_counts: list[tuple[str, int]] = field(default_factory=list)


@dataclass
class CoverageStats:
    """Transcript coverage statistics for a research project."""

    pct_in_report: int  # 0-100, whole number
    pct_moderator: int  # 0-100
    pct_omitted: int  # 0-100
    omitted_by_session: dict[str, SessionOmitted] = field(default_factory=dict)


def _word_count(text: str) -> int:
    """Count words in text."""
    return len(text.split())


def _is_moderator_code(code: str) -> bool:
    """Check if a speaker code is moderator or observer (not participant)."""
    return code.startswith("m") or code.startswith("o")


def _is_participant_code(code: str) -> bool:
    """Check if a speaker code is a participant."""
    return code.startswith("p")


def calculate_coverage(
    transcripts: list[FullTranscript],
    quotes: list[ExtractedQuote],
) -> CoverageStats:
    """Calculate transcript coverage statistics.

    Determines what percentage of the transcript made it into the report,
    how much was moderator speech, and what participant speech was omitted.

    Args:
        transcripts: All transcripts from the pipeline.
        quotes: All extracted quotes.

    Returns:
        CoverageStats with percentages and per-session omitted content.
    """
    if not transcripts:
        return CoverageStats(pct_in_report=0, pct_moderator=0, pct_omitted=0)

    # Build quote coverage lookup: session_id -> list of (start, end) ranges
    quote_ranges: dict[str, list[tuple[float, float]]] = {}
    for q in quotes:
        sid = q.session_id
        if sid not in quote_ranges:
            quote_ranges[sid] = []
        quote_ranges[sid].append((q.start_timecode, q.end_timecode))

    # Process all segments
    participant_words_total = 0
    participant_words_in_quotes = 0
    moderator_words_total = 0
    omitted_by_session: dict[str, list[tuple[str, str, str, int]]] = {}

    for transcript in transcripts:
        session_id = transcript.session_id
        ranges = quote_ranges.get(session_id, [])

        for seg in transcript.segments:
            code = seg.speaker_code or transcript.participant_id
            text = seg.text
            wc = _word_count(text)

            if _is_moderator_code(code):
                moderator_words_total += wc
            elif _is_participant_code(code) or not code:
                # Treat unknown codes as participant (backward compat)
                participant_words_total += wc

                # Check if this segment's timecode is covered by any quote
                is_covered = any(
                    start <= seg.start_time <= end for start, end in ranges
                )

                if is_covered:
                    participant_words_in_quotes += wc
                else:
                    # Track omitted segment
                    if session_id not in omitted_by_session:
                        omitted_by_session[session_id] = []
                    tc_str = format_timecode(seg.start_time)
                    tc_seconds = int(seg.start_time)
                    omitted_by_session[session_id].append((code, tc_str, tc_seconds, text, wc))

    # Calculate percentages
    total_words = participant_words_total + moderator_words_total
    if total_words > 0:
        pct_in_report = round(100 * participant_words_in_quotes / total_words)
        pct_moderator = round(100 * moderator_words_total / total_words)
        pct_omitted = round(
            100 * (participant_words_total - participant_words_in_quotes) / total_words
        )
    else:
        pct_in_report = 0
        pct_moderator = 0
        pct_omitted = 0

    # Build structured omitted data with fragment collapsing
    structured_omitted: dict[str, SessionOmitted] = {}

    for session_id in sorted(omitted_by_session.keys()):
        segments = omitted_by_session[session_id]
        full_segs: list[OmittedSegment] = []
        fragments: list[str] = []

        for code, tc_str, tc_seconds, text, wc in segments:
            if wc > FRAGMENT_THRESHOLD:
                full_segs.append(OmittedSegment(
                    speaker_code=code,
                    timecode=tc_str,
                    timecode_seconds=tc_seconds,
                    text=text,
                ))
            else:
                fragments.append(text)

        # Count fragment occurrences
        fragment_counter = Counter(fragments)
        fragment_counts = fragment_counter.most_common()

        structured_omitted[session_id] = SessionOmitted(
            full_segments=full_segs,
            fragment_counts=fragment_counts,
        )

    return CoverageStats(
        pct_in_report=pct_in_report,
        pct_moderator=pct_moderator,
        pct_omitted=pct_omitted,
        omitted_by_session=structured_omitted,
    )
