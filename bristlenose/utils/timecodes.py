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
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def format_timecode_ms(seconds: float) -> str:
    """Format seconds as HH:MM:SS.mmm."""
    total = max(0.0, seconds)
    h = int(total // 3600)
    m = int((total % 3600) // 60)
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


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
