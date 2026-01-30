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
        session_segments: Map of participant_id -> segments from any source
            (whisper, subtitle, docx).

    Returns:
        List of FullTranscript objects, one per session.
    """
    transcripts: list[FullTranscript] = []

    for session in sessions:
        segments = session_segments.get(session.participant_id, [])
        if not segments:
            logger.warning(
                "%s: No transcript segments available.",
                session.participant_id,
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
            participant_id=session.participant_id,
            source_file=source_file,
            session_date=session.session_date,
            duration_seconds=duration,
            segments=merged,
        )
        transcripts.append(transcript)
        logger.info(
            "%s: Merged %d segments, duration=%.0fs",
            session.participant_id,
            len(merged),
            duration,
        )

    return transcripts


def write_raw_transcripts(
    transcripts: list[FullTranscript],
    output_dir: Path,
) -> list[Path]:
    """Write raw transcript text files.

    Format:
        [HH:MM:SS] [ROLE] Speaker text here.

    Args:
        transcripts: Transcripts to write.
        output_dir: Directory to write to.

    Returns:
        List of written file paths.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    for transcript in transcripts:
        filename = f"{transcript.participant_id}_raw.txt"
        path = output_dir / filename

        lines: list[str] = []
        lines.append(f"# Transcript: {transcript.participant_id}")
        lines.append(f"# Source: {transcript.source_file}")
        lines.append(f"# Date: {transcript.session_date.date()}")
        lines.append(f"# Duration: {format_timecode(transcript.duration_seconds)}")
        lines.append("")

        for seg in transcript.segments:
            tc = format_timecode(seg.start_time)
            role = seg.speaker_role.value.upper()
            speaker = f" ({seg.speaker_label})" if seg.speaker_label else ""
            lines.append(f"[{tc}] [{role}]{speaker} {seg.text}")
            lines.append("")

        path.write_text("\n".join(lines), encoding="utf-8")
        paths.append(path)
        logger.info("Wrote raw transcript: %s", path)

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
