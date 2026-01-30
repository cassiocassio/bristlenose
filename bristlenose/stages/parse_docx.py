"""Stage 4: Parse Teams-exported .docx transcripts into TranscriptSegments."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from bristlenose.models import InputFile, TranscriptSegment
from bristlenose.utils.timecodes import parse_timecode

logger = logging.getLogger(__name__)

# Teams transcript patterns:
# "Speaker Name  00:01:23" or "Speaker Name 0:01:23"
_TEAMS_SPEAKER_LINE = re.compile(
    r"^(.+?)\s+(\d{1,2}:\d{2}(?::\d{2})?)\s*$"
)

# Teams with arrow notation: "Speaker Name  00:01:23 --> 00:01:45"
_TEAMS_SPEAKER_ARROW = re.compile(
    r"^(.+?)\s+(\d{1,2}:\d{2}:\d{2}[.,]\d{3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[.,]\d{3})\s*$"
)

# Just a timestamp line (no speaker)
_TIMESTAMP_ONLY = re.compile(
    r"^\s*(\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d{1,3})?)\s*$"
)


def parse_docx_file(input_file: InputFile) -> list[TranscriptSegment]:
    """Parse a .docx file (typically a Teams transcript export) into segments."""
    return _parse_docx(input_file.path)


def _parse_docx(path: Path) -> list[TranscriptSegment]:
    """Parse a Teams-exported .docx file."""
    from docx import Document

    doc = Document(str(path))
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]

    if not paragraphs:
        logger.warning("Empty document: %s", path.name)
        return []

    # Detect format: Teams transcript or plain text
    segments = _try_parse_teams_format(paragraphs)
    if segments:
        logger.info("Parsed %d segments from Teams format: %s", len(segments), path.name)
        return _merge_adjacent_segments(segments)

    # Fallback: treat each paragraph as a segment with no timecodes
    logger.info("Parsing as plain text (no timecodes): %s", path.name)
    return _parse_plain_paragraphs(paragraphs)


def _try_parse_teams_format(paragraphs: list[str]) -> list[TranscriptSegment] | None:
    """Try to parse paragraphs as a Teams transcript.

    Teams transcripts alternate between speaker+timestamp lines and text lines.
    Returns None if the format doesn't match.
    """
    segments: list[TranscriptSegment] = []
    current_speaker: str | None = None
    current_start: float | None = None
    current_end: float | None = None
    current_texts: list[str] = []
    matched_headers = 0

    for para in paragraphs:
        # Try matching speaker + timestamp (arrow format)
        arrow_match = _TEAMS_SPEAKER_ARROW.match(para)
        if arrow_match:
            # Flush previous segment
            if current_speaker is not None and current_texts:
                segments.append(_build_segment(
                    current_speaker, current_start, current_end, current_texts
                ))

            current_speaker = arrow_match.group(1).strip()
            current_start = parse_timecode(arrow_match.group(2))
            current_end = parse_timecode(arrow_match.group(3))
            current_texts = []
            matched_headers += 1
            continue

        # Try matching speaker + timestamp (simple format)
        speaker_match = _TEAMS_SPEAKER_LINE.match(para)
        if speaker_match:
            # Flush previous segment
            if current_speaker is not None and current_texts:
                segments.append(_build_segment(
                    current_speaker, current_start, current_end, current_texts
                ))

            current_speaker = speaker_match.group(1).strip()
            current_start = parse_timecode(speaker_match.group(2))
            current_end = None
            current_texts = []
            matched_headers += 1
            continue

        # Try timestamp-only line
        ts_match = _TIMESTAMP_ONLY.match(para)
        if ts_match:
            if current_speaker is not None and current_texts:
                segments.append(_build_segment(
                    current_speaker, current_start, current_end, current_texts
                ))
                current_texts = []
            current_start = parse_timecode(ts_match.group(1))
            current_end = None
            continue

        # Otherwise it's a text line — add to current segment
        if current_speaker is not None:
            current_texts.append(para)

    # Flush final segment
    if current_speaker is not None and current_texts:
        segments.append(_build_segment(
            current_speaker, current_start, current_end, current_texts
        ))

    # Only return if we matched a reasonable number of headers
    if matched_headers < 2:
        return None

    return segments


def _build_segment(
    speaker: str,
    start: float | None,
    end: float | None,
    texts: list[str],
) -> TranscriptSegment:
    """Build a TranscriptSegment from accumulated data."""
    text = " ".join(texts)
    return TranscriptSegment(
        start_time=start or 0.0,
        end_time=end or (start or 0.0),
        text=text,
        speaker_label=speaker,
        source="docx",
    )


def _parse_plain_paragraphs(paragraphs: list[str]) -> list[TranscriptSegment]:
    """Parse paragraphs with no timecode information.

    Each paragraph becomes a segment at time 0.0.
    """
    segments: list[TranscriptSegment] = []
    for i, para in enumerate(paragraphs):
        segments.append(
            TranscriptSegment(
                start_time=0.0,
                end_time=0.0,
                text=para,
                source="docx",
            )
        )
    return segments


def _merge_adjacent_segments(
    segments: list[TranscriptSegment],
    max_gap: float = 5.0,
) -> list[TranscriptSegment]:
    """Merge consecutive segments from the same speaker within max_gap seconds."""
    if not segments:
        return []

    merged: list[TranscriptSegment] = [segments[0].model_copy()]

    for seg in segments[1:]:
        prev = merged[-1]
        same_speaker = (
            prev.speaker_label is not None
            and prev.speaker_label == seg.speaker_label
        )
        close_enough = (seg.start_time - prev.end_time) <= max_gap

        if same_speaker and close_enough:
            prev.end_time = max(prev.end_time, seg.end_time)
            prev.text = f"{prev.text} {seg.text}"
        else:
            merged.append(seg.model_copy())

    return merged
