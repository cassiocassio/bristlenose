"""Stage 6: Merge all transcript sources into unified format and write raw files."""

from __future__ import annotations

import logging
from pathlib import Path

from bristlenose.models import (
    FullTranscript,
    InputSession,
    TranscriptSegment,
    format_timecode,
)

logger = logging.getLogger(__name__)


def merge_transcripts(
    sessions: list[InputSession],
    session_segments: dict[str, list[TranscriptSegment]],
) -> list[FullTranscript]:
    """Merge all transcript sources into unified FullTranscript objects.

    Args:
        sessions: The input sessions.
        session_segments: Map of session_id -> segments from any source
            (whisper, subtitle, docx).

    Returns:
        List of FullTranscript objects, one per session.
    """
    transcripts: list[FullTranscript] = []

    for session in sessions:
        segments = session_segments.get(session.session_id, [])
        if not segments:
            logger.warning(
                "%s: No transcript segments available.",
                session.session_id,
            )
            continue

        # Sort segments by start time
        segments.sort(key=lambda s: s.start_time)

        # Merge overlapping same-speaker segments
        merged = _merge_same_speaker(segments)

        # Compute duration
        duration = 0.0
        if merged:
            duration = merged[-1].end_time

        # Determine source file name
        source_file = session.files[0].path.name if session.files else "unknown"

        transcript = FullTranscript(
            session_id=session.session_id,
            participant_id=session.participant_id,
            source_file=source_file,
            session_date=session.session_date,
            duration_seconds=duration,
            segments=merged,
        )
        transcripts.append(transcript)
        logger.info(
            "%s: Merged %d segments, duration=%.0fs",
            session.session_id,
            len(merged),
            duration,
        )

    return transcripts


def write_raw_transcripts(
    transcripts: list[FullTranscript],
    output_dir: Path,
) -> list[Path]:
    """Write raw transcript text files.

    Format uses the markdown style template from
    :mod:`bristlenose.utils.markdown`.

    Args:
        transcripts: Transcripts to write.
        output_dir: Directory to write to.

    Returns:
        List of written file paths.
    """
    from bristlenose.utils.markdown import (
        format_raw_segment_txt,
        format_transcript_header_txt,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    for transcript in transcripts:
        # New naming: s1.txt (was s1_raw.txt — directory name now indicates raw/cooked)
        filename = f"{transcript.session_id}.txt"
        path = output_dir / filename

        header = format_transcript_header_txt(
            participant_id=transcript.session_id,
            source_file=transcript.source_file,
            session_date=str(transcript.session_date.date()),
            duration=format_timecode(transcript.duration_seconds),
        )

        lines: list[str] = [header, ""]

        for seg in transcript.segments:
            tc = format_timecode(seg.start_time)
            code = seg.speaker_code or transcript.participant_id
            lines.append(
                format_raw_segment_txt(tc, code, seg.speaker_label, seg.text)
            )
            lines.append("")

        path.write_text("\n".join(lines), encoding="utf-8")
        paths.append(path)
        logger.info("Wrote raw transcript: %s", path)

    return paths


def write_raw_transcripts_md(
    transcripts: list[FullTranscript],
    output_dir: Path,
) -> list[Path]:
    """Write raw transcript Markdown files alongside the .txt files.

    The ``.md`` version provides a more readable format with bold
    participant code labels and structured metadata.  Files are named
    ``{session_id}.md`` and placed in ``transcripts-raw/``.

    Args:
        transcripts: Transcripts to write.
        output_dir: Directory to write to.

    Returns:
        List of written file paths.
    """
    from bristlenose.utils.markdown import (
        format_raw_segment_md,
        format_transcript_header_md,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    for transcript in transcripts:
        # New naming: s1.md (was s1_raw.md)
        filename = f"{transcript.session_id}.md"
        path = output_dir / filename

        header = format_transcript_header_md(
            participant_id=transcript.session_id,
            source_file=transcript.source_file,
            session_date=str(transcript.session_date.date()),
            duration=format_timecode(transcript.duration_seconds),
        )

        lines: list[str] = [header, ""]

        for seg in transcript.segments:
            tc = format_timecode(seg.start_time)
            code = seg.speaker_code or transcript.participant_id
            lines.append(
                format_raw_segment_md(tc, code, seg.speaker_label, seg.text)
            )
            lines.append("")

        path.write_text("\n".join(lines), encoding="utf-8")
        paths.append(path)
        logger.info("Wrote raw transcript (md): %s", path)

    return paths


def _merge_same_speaker(
    segments: list[TranscriptSegment],
    max_gap: float = 2.0,
) -> list[TranscriptSegment]:
    """Merge consecutive segments from the same speaker within max_gap."""
    if not segments:
        return []

    merged: list[TranscriptSegment] = [segments[0].model_copy()]

    for seg in segments[1:]:
        prev = merged[-1]
        same_speaker = (
            prev.speaker_label is not None
            and prev.speaker_label == seg.speaker_label
        )
        close = (seg.start_time - prev.end_time) <= max_gap

        if same_speaker and close:
            prev.end_time = max(prev.end_time, seg.end_time)
            prev.text = f"{prev.text} {seg.text}"
            prev.words.extend(seg.words)
        else:
            merged.append(seg.model_copy())

    return merged
