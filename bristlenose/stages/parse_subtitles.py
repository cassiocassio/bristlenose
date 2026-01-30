"""Stage 3: Parse .srt and .vtt subtitle files into TranscriptSegments."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from bristlenose.models import FileType, InputFile, TranscriptSegment
from bristlenose.utils.timecodes import parse_timecode

logger = logging.getLogger(__name__)

# Speaker label pattern in VTT: <v Speaker Name>text</v>
_VTT_SPEAKER_PATTERN = re.compile(r"<v\s+([^>]+)>(.+?)(?:</v>)?$", re.DOTALL)

# Speaker label at start of line: "Speaker Name: text"
_COLON_SPEAKER_PATTERN = re.compile(r"^([A-Za-z][A-Za-z\s.'-]{1,40}):\s*(.+)$")


def parse_subtitle_file(input_file: InputFile) -> list[TranscriptSegment]:
    """Parse a subtitle file into transcript segments.

    Supports .srt and .vtt formats.
    """
    if input_file.file_type == FileType.SUBTITLE_SRT:
        return _parse_srt(input_file.path)
    elif input_file.file_type == FileType.SUBTITLE_VTT:
        return _parse_vtt(input_file.path)
    else:
        raise ValueError(f"Not a subtitle file: {input_file.file_type}")


def _parse_srt(path: Path) -> list[TranscriptSegment]:
    """Parse an SRT file."""
    import pysrt

    subs = pysrt.open(str(path), encoding="utf-8")
    segments: list[TranscriptSegment] = []

    for sub in subs:
        start = (
            sub.start.hours * 3600
            + sub.start.minutes * 60
            + sub.start.seconds
            + sub.start.milliseconds / 1000
        )
        end = (
            sub.end.hours * 3600
            + sub.end.minutes * 60
            + sub.end.seconds
            + sub.end.milliseconds / 1000
        )
        text = _clean_subtitle_text(sub.text)
        speaker = _extract_speaker(text)
        if speaker:
            text = _remove_speaker_prefix(text, speaker)

        if text.strip():
            segments.append(
                TranscriptSegment(
                    start_time=start,
                    end_time=end,
                    text=text.strip(),
                    speaker_label=speaker,
                    source="srt",
                )
            )

    return _merge_adjacent_segments(segments)


def _parse_vtt(path: Path) -> list[TranscriptSegment]:
    """Parse a WebVTT file."""
    import webvtt

    segments: list[TranscriptSegment] = []

    for caption in webvtt.read(str(path)):
        start = _vtt_timestamp_to_seconds(caption.start)
        end = _vtt_timestamp_to_seconds(caption.end)
        text = caption.text
        speaker: str | None = None

        # Check for VTT voice spans: <v Speaker>text</v>
        voice_match = _VTT_SPEAKER_PATTERN.search(caption.raw_text or text)
        if voice_match:
            speaker = voice_match.group(1).strip()
            text = voice_match.group(2).strip()

        text = _clean_subtitle_text(text)

        if not speaker:
            speaker = _extract_speaker(text)
            if speaker:
                text = _remove_speaker_prefix(text, speaker)

        if text.strip():
            segments.append(
                TranscriptSegment(
                    start_time=start,
                    end_time=end,
                    text=text.strip(),
                    speaker_label=speaker,
                    source="vtt",
                )
            )

    return _merge_adjacent_segments(segments)


def _vtt_timestamp_to_seconds(ts: str) -> float:
    """Convert a VTT timestamp string to seconds."""
    return parse_timecode(ts)


def _clean_subtitle_text(text: str) -> str:
    """Remove HTML tags and common subtitle artefacts."""
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Remove position/alignment cues
    text = re.sub(r"\{\\an?\d+\}", "", text)
    # Normalise whitespace
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_speaker(text: str) -> str | None:
    """Try to extract a speaker label from the text."""
    match = _COLON_SPEAKER_PATTERN.match(text)
    if match:
        return match.group(1).strip()
    return None


def _remove_speaker_prefix(text: str, speaker: str) -> str:
    """Remove the speaker prefix from text."""
    pattern = re.escape(speaker) + r"\s*:\s*"
    return re.sub(f"^{pattern}", "", text, count=1)


def _merge_adjacent_segments(
    segments: list[TranscriptSegment],
    max_gap: float = 2.0,
) -> list[TranscriptSegment]:
    """Merge consecutive segments from the same speaker that are close together.

    Args:
        segments: Sorted list of segments.
        max_gap: Maximum gap in seconds to merge across.
    """
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
            # Merge: extend the previous segment
            prev.end_time = seg.end_time
            prev.text = f"{prev.text} {seg.text}"
            prev.words.extend(seg.words)
        else:
            merged.append(seg.model_copy())

    return merged
