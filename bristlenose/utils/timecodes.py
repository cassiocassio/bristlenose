"""Timecode formatting, parsing, and arithmetic."""

from __future__ import annotations

import re
from datetime import datetime, timezone

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
    """Format an elapsed span as ``<1m`` · ``26m`` · ``1h`` · ``1h 3m``.

    **The canonical Python implementation of the ``duration_human`` shared
    render format.** Mirrored by ``formatDurationHuman`` (TypeScript) and
    ``DurationFormat.human`` (Swift); the agreed case table is
    ``tests/fixtures/shared-format-contract.json`` and the register is
    ``docs/design-shared-formats.md``. Change this and the mirrors move with
    it, in the same commit. ``server/routes/dashboard._format_duration_human``
    delegates here.

    This is an ELAPSED SPAN, not a position in a recording — positions use
    ``format_timecode``. Until 12 Sep 2026 this function was a *different*
    format (``1 h 0 min``, and ``1 min`` for a 30-second span) with one caller,
    the static report's dashboard total, which therefore disagreed with the SPA
    for the same number. One shape now.

    ``0`` renders ``0m`` — a real zero for an aggregate total. A per-row cell
    where zero means *unknown* renders an em-dash at the call site (the SPA and
    ``routes/dev.py`` do), which is the one deliberate fork in the register.
    """
    if seconds <= 0:
        return "0m"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    if h > 0:
        return f"{h}h {m}m" if m > 0 else f"{h}h"
    return f"{m}m" if m > 0 else "<1m"


def parse_header_datetime(value: str) -> datetime | None:
    """Read a transcript ``# Date:`` header value as a UTC-aware datetime.

    One reader for both the pipeline resume path and the server importer,
    which until 12 Sep 2026 disagreed: the pipeline did
    ``fromisoformat(s).replace(tzinfo=utc)``, which *overwrites* an offset
    rather than converting it, so a ``+01:00`` (BST) header was stored an hour
    late; the importer converted correctly. Same file, two instants.

    Accepts full ISO 8601 with or without an offset, and the legacy date-only
    ``YYYY-MM-DD``. Returns ``None`` for anything else — callers keep their
    own default rather than receive a guess.

    **A naive value means UTC, by decision.** The writer emits an aware
    ``isoformat()`` (which carries an offset), so a naive header only appears
    in output written before the time-of-recording fix, and that output was
    UTC. Relabelling it is correct; relabelling an *aware* value is the bug
    this function exists to remove.
    """
    text = value.strip()
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        try:
            dt = datetime.strptime(text, "%Y-%m-%d")
        except ValueError:
            return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_timecode(tc: str) -> float:
    """Parse a timecode string into seconds.

    Supports:
      - HH:MM:SS,mmm  (SRT format)
      - HH:MM:SS.mmm  (VTT format)
      - HH:MM:SS
      - MM:SS
      - MM:SS.mmm

    The whole (stripped) string must be a timecode. It used to ``match`` a
    prefix, so ``"00:01:23 extra"`` returned 83.0 with no error — a malformed
    line yielding a plausible number. Every caller passes an isolated token
    (verified 12 Sep 2026: subtitle cue fields, docx regex groups, header
    values, LLM fields that already catch ``ValueError``), so refusing the
    remainder costs nothing and says so.

    Domain: hours are one or two digits, so ``99:59:59`` parses and
    ``100:00:00`` raises. That is a declared limit (``docs/time-defects.md`` § 2)
    — a research session is a few hours, and past a single hour digit the right
    behaviour is to fail loudly. Seconds are always two digits: unpadded
    ``1:2:3`` is refused, measured against 344 real transcripts to be a shape
    no export produces (the only matches were Stephanus citations).
    """
    tc = tc.strip()

    # Try SRT/VTT format first
    m = _SRT_PATTERN.fullmatch(tc)
    if m:
        h, mi, s, ms = m.groups()
        ms_str = ms.ljust(3, "0")  # pad to 3 digits
        return int(h) * 3600 + int(mi) * 60 + int(s) + int(ms_str) / 1000

    # Try simple format
    m = _SIMPLE_PATTERN.fullmatch(tc)
    if m:
        h, mi, s, ms = m.groups()
        hours = int(h) if h else 0
        frac = int(ms.ljust(3, "0")) / 1000 if ms else 0.0
        return hours * 3600 + int(mi) * 60 + int(s) + frac

    raise ValueError(f"Cannot parse timecode: {tc!r}")


def seconds_between(start: float, end: float) -> float:
    """Return the duration between two timecodes in seconds."""
    return max(0.0, end - start)
