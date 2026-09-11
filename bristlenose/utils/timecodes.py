"""Timecode formatting, parsing, and arithmetic."""

from __future__ import annotations

import re

# Pattern for SRT/VTT style timestamps: 00:01:23,456 or 00:01:23.456
_SRT_PATTERN = re.compile(
    r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})"
)

# Pattern for simple HH:MM:SS or MM:SS
_SIMPLE_PATTERN = re.compile(
    r"(?:(\d{1,2}):)?(\d{1,2}):(\d{2})(?:\.(\d{1,3}))?"
)


def format_timecode(seconds: float) -> str:
    """Format seconds as MM:SS or HH:MM:SS (hours only when >= 1 h)."""
    total = max(0, int(seconds))
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def format_timecode_ms(seconds: float) -> str:
    """Format seconds as HH:MM:SS.mmm."""
    total = max(0.0, seconds)
    h = int(total // 3600)
    m = int((total % 3600) // 60)
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def format_timecode_prompt(seconds: float) -> str:
    """Format seconds as zero-padded ``HH:MM:SS``, for LLM PROMPTS ONLY.

    NOT a display format and NOT a sibling of ``format_timecode``. Never render
    this to a user, never write it to disk, and never widen it into the
    cross-language register in ``docs/design-shared-formats.md`` — ``timecode``
    is Class R there (round-trip, parsed back off disk) and this is not.

    Why it exists. ``format_timecode`` omits the hour below 1 h, so a transcript
    of a sub-hour session rendered into a prompt reads ``[05:30]`` while the
    schema asks the model for ``HH:MM:SS``. `gpt-5.6-terra` resolves that
    mismatch by appending ``:00``, shifting every field up one place and making
    the value exactly 60x the truth — 63% of quotes, measured 5 Sep 2026
    (``experiments/quote-stability/FINDINGS.md`` § 3). Padding the hour removes
    the ambiguity at its source: the transcript now speaks the format the schema
    asks for, in every session, for every provider.

    Padding also makes the rendering uniform WITHIN one transcript. The old form
    was per-segment, so a session over an hour rendered its first hour as
    ``MM:SS`` and the rest as ``H:MM:SS`` — two formats in one prompt, which is
    the case the s09 range guard cannot detect.
    """
    total = max(0, int(seconds))
    return f"{total // 3600:02d}:{(total % 3600) // 60:02d}:{total % 60:02d}"


def format_duration_human(seconds: float) -> str:
    """Format seconds as a compact human-readable duration.

    Examples: ``14 min``, ``1 h 23 min``, ``2 h 0 min``.
    Seconds are dropped — this is for summary display, not precision.
    """
    total = max(0, int(seconds))
    h = total // 3600
    m = (total % 3600) // 60
    # Round up if there are leftover seconds and minutes is 0.
    leftover_s = total % 60
    if leftover_s and m == 0 and h == 0:
        m = 1  # avoid showing "0 min" for e.g. 45 seconds
    elif leftover_s and h == 0:
        pass  # keep exact minute count — "14 min" not "15 min" for 14:01
    if h:
        return f"{h} h {m} min"
    return f"{m} min"


def parse_timecode(tc: str) -> float:
    """Parse a timecode string into seconds.

    Supports:
      - HH:MM:SS,mmm  (SRT format)
      - HH:MM:SS.mmm  (VTT format)
      - HH:MM:SS
      - MM:SS
      - MM:SS.mmm
    """
    tc = tc.strip()

    # Try SRT/VTT format first
    m = _SRT_PATTERN.match(tc)
    if m:
        h, mi, s, ms = m.groups()
        ms_str = ms.ljust(3, "0")  # pad to 3 digits
        return int(h) * 3600 + int(mi) * 60 + int(s) + int(ms_str) / 1000

    # Try simple format
    m = _SIMPLE_PATTERN.match(tc)
    if m:
        h, mi, s, ms = m.groups()
        hours = int(h) if h else 0
        frac = int(ms.ljust(3, "0")) / 1000 if ms else 0.0
        return hours * 3600 + int(mi) * 60 + int(s) + frac

    raise ValueError(f"Cannot parse timecode: {tc!r}")


def seconds_between(start: float, end: float) -> float:
    """Return the duration between two timecodes in seconds."""
    return max(0.0, end - start)
