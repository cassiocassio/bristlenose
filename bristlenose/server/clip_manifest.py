"""Pure-logic layer for video clip extraction: manifest building, naming, merging.

All functions are pure (data in, data out). No DB queries, no filesystem, no subprocess.
Shared by the FFmpeg backend (CLI/serve) and the future AVFoundation backend (desktop).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from bristlenose.utils.text import safe_filename

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class ClipSpec:
    """Specification for a single clip to extract."""

    quote_id: str           # "q-p1-42"
    participant_id: str     # "p1"
    session_id: str         # "s1"
    source_path: Path       # absolute path to source media
    start: float            # seconds (with padding applied)
    end: float              # seconds (with padding applied)
    raw_start: float        # original quote start (for timecode in filename)
    speaker_name: str       # display name (or "" if anonymised)
    quote_gist: str         # first ~6 words, lowercase
    is_audio_only: bool     # True → output .m4a, False → output .mp4
    is_starred: bool
    is_hero: bool


# ---------------------------------------------------------------------------
# Gist extraction
# ---------------------------------------------------------------------------

#: Punctuation to strip from gist text.
_GIST_STRIP = re.compile(r"['\u2018\u2019\u201c\u201d\"?!.,;:()\[\]]")


def extract_gist(text: str, max_chars: int = 40) -> str:
    """Extract a filename-safe gist from quote text.

    Takes the first ~6 words, lowercases, strips punctuation.
    Returns ``"clip"`` if the input is empty or whitespace-only.
    """
    text = text.strip()
    if not text:
        return "clip"

    cleaned = _GIST_STRIP.sub("", text).lower()
    words = cleaned.split()
    if not words:
        return "clip"

    result = ""
    for word in words[:6]:
        candidate = f"{result} {word}".strip() if result else word
        if len(candidate) > max_chars:
            break
        result = candidate

    return result or "clip"


# ---------------------------------------------------------------------------
# Participant code zero-padding
# ---------------------------------------------------------------------------


def zero_pad_code(code: str, participant_count: int) -> str:
    """Zero-pad a participant code based on the number of participants.

    ``p1`` stays ``p1`` when count < 10, becomes ``p01`` when count >= 10.
    """
    if participant_count < 10:
        return code

    # Split prefix letter(s) from digits
    prefix = ""
    digits = ""
    for i, ch in enumerate(code):
        if ch.isdigit():
            prefix = code[:i]
            digits = code[i:]
            break
    else:
        return code

    if not digits:
        return code

    width = 2 if participant_count < 100 else 3
    return f"{prefix}{int(digits):0{width}d}"


# ---------------------------------------------------------------------------
# Timecode formatting
# ---------------------------------------------------------------------------


def format_clip_timecode(seconds: float, *, use_hours: bool = False) -> str:
    """Format seconds as a clip-filename timecode.

    Returns ``03m45`` (under 1 hour) or ``0h03m45`` (when *use_hours* is True).
    """
    total = int(seconds)
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    if use_hours:
        return f"{h}h{m:02d}m{s:02d}"
    return f"{m:02d}m{s:02d}"


# ---------------------------------------------------------------------------
# Clip filename
# ---------------------------------------------------------------------------


def build_clip_filename(
    spec: ClipSpec,
    participant_count: int,
    use_hours: bool,
    *,
    anonymise: bool = False,
) -> str:
    """Build a human-readable clip filename.

    Format: ``{code} {timecode} {speaker} {gist}.mp4``
    Anonymised: ``{code} {timecode} {gist}.mp4`` (no speaker name, zero-padded code)
    """
    code = zero_pad_code(spec.participant_id, participant_count)
    timecode = format_clip_timecode(spec.raw_start, use_hours=use_hours)
    ext = ".m4a" if spec.is_audio_only else ".mp4"

    if anonymise or not spec.speaker_name:
        # Zero-pad when anonymising (even if < 10 participants)
        if anonymise and participant_count < 10:
            code = zero_pad_code(spec.participant_id, 10)
        stem = f"{code} {timecode} {spec.quote_gist}"
    else:
        stem = f"{code} {timecode} {spec.speaker_name} {spec.quote_gist}"

    return safe_filename(stem) + ext


# ---------------------------------------------------------------------------
# Padding
# ---------------------------------------------------------------------------


def apply_padding(
    start: float,
    end: float,
    duration: float,
    *,
    pad_before: float = 3.0,
    pad_after: float = 2.0,
) -> tuple[float, float]:
    """Apply padding to clip boundaries, clamped to [0, duration]."""
    padded_start = max(0.0, start - pad_before)
    padded_end = min(duration, end + pad_after)
    return (padded_start, padded_end)


# ---------------------------------------------------------------------------
# Adjacent merge
# ---------------------------------------------------------------------------


def merge_adjacent_clips(
    clips: list[ClipSpec],
    threshold: float = 10.0,
) -> list[ClipSpec]:
    """Merge clips from the same session that are within *threshold* seconds.

    When two clips overlap or are close together, the merged clip keeps
    the first clip's metadata (quote_id, gist, speaker).
    """
    if len(clips) <= 1:
        return list(clips)

    # Sort by session, then start time
    sorted_clips = sorted(clips, key=lambda c: (c.session_id, c.start))

    merged: list[ClipSpec] = []
    current = sorted_clips[0]

    for clip in sorted_clips[1:]:
        if clip.session_id == current.session_id and clip.start <= current.end + threshold:
            # Merge: extend the current clip's end, keep first clip's metadata
            current = ClipSpec(
                quote_id=current.quote_id,
                participant_id=current.participant_id,
                session_id=current.session_id,
                source_path=current.source_path,
                start=current.start,
                end=max(current.end, clip.end),
                raw_start=current.raw_start,
                speaker_name=current.speaker_name,
                quote_gist=current.quote_gist,
                is_audio_only=current.is_audio_only,
                is_starred=current.is_starred or clip.is_starred,
                is_hero=current.is_hero or clip.is_hero,
            )
        else:
            merged.append(current)
            current = clip

    merged.append(current)
    return merged


# ---------------------------------------------------------------------------
# Manifest builder
# ---------------------------------------------------------------------------


@dataclass
class _QuoteLike:
    """Minimal interface expected from a quote object for manifest building."""

    quote_id: str
    participant_id: str
    session_id: str
    start_timecode: float
    end_timecode: float
    text: str
    is_starred: bool
    is_hero: bool


def build_clip_manifest(
    quotes: list[_QuoteLike],
    speaker_map: dict[tuple[str, str], str],
    session_media: dict[str, tuple[Path, bool]],
    session_durations: dict[str, float],
    *,
    anonymise: bool = False,
) -> list[ClipSpec]:
    """Build a clip manifest from a list of quotes.

    Parameters
    ----------
    quotes:
        Flat list of quote-like objects (starred and/or hero).
    speaker_map:
        ``(session_id, participant_id) → display_name``.
    session_media:
        ``session_id → (absolute_media_path, is_audio_only)``.
        Only sessions with media files should be included.
    session_durations:
        ``session_id → duration_seconds``.
    anonymise:
        When True, speaker names are omitted from filenames.

    Returns
    -------
    list[ClipSpec]
        Deduplicated, padded clip specs (not yet merged).
    """
    seen: set[str] = set()
    specs: list[ClipSpec] = []

    for q in quotes:
        if q.quote_id in seen:
            continue
        seen.add(q.quote_id)

        # Skip quotes with no media
        media_info = session_media.get(q.session_id)
        if media_info is None:
            continue

        source_path, is_audio_only = media_info
        duration = session_durations.get(q.session_id, float("inf"))

        padded_start, padded_end = apply_padding(
            q.start_timecode, q.end_timecode, duration,
        )

        speaker_name = "" if anonymise else speaker_map.get(
            (q.session_id, q.participant_id), "",
        )

        specs.append(ClipSpec(
            quote_id=q.quote_id,
            participant_id=q.participant_id,
            session_id=q.session_id,
            source_path=source_path,
            start=padded_start,
            end=padded_end,
            raw_start=q.start_timecode,
            speaker_name=speaker_name,
            quote_gist=extract_gist(q.text),
            is_audio_only=is_audio_only,
            is_starred=q.is_starred,
            is_hero=q.is_hero,
        ))

    return specs
