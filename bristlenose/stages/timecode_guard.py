"""Range guard for LLM-returned timecodes, shared by s08 and s09.

# ---------------------------------------------------------------------------
# The defect
# ---------------------------------------------------------------------------
#
# `full_text()` USED TO render each segment as MM:SS while a session ran under an
# hour (`format_timecode` omits hours below 1 h) while the schemas asked the model
# for HH:MM:SS. A model resolves that mismatch by appending `:00`, shifting every
# field up one place: MM becomes HH, SS becomes MM. The arithmetic is exact --
# `M*3600 + S*60 == 60 * (M*60 + S)` -- so an affected value is exactly 60x the
# truth AND is always a whole number of minutes. `parse_timecode` was correct
# throughout; the model was wrong.
#
# THE SOURCE IS FIXED as of 11 Sep 2026: `full_text()` and s09's `boundaries_text`
# render `format_timecode_prompt` (zero-padded HH:MM:SS), so there is no mismatch
# left for a model to resolve. This guard is kept as defence in depth -- the fix
# removes the *reason* a model guesses the format, not its *ability* to -- and
# because it is the only thing that would report a future model getting it wrong
# for some other reason. It should now fire on nothing.
#
# It is NOT one model's quirk. Three families have done it:
# `gpt-5.6-terra` on s09 (239 of 380 quotes, 63%), `claude-sonnet-4` on s08
# (38 of 133 cached boundaries), and `gemini-3.8-flash` on an unpadded s08
# prompt (5 of 95). `experiments/quote-stability/FINDINGS.md` §§ 3, 3b.
#
# The scaling repair fires only on the whole measured signature: out of range, a
# whole number of minutes (the appended `:00`), and back in range once divided by
# 60. A repair is a WARNING, never silent -- same rule as `_validate_repairing` in
# `llm/client.py`: the repair buys the researcher their run, and the log line is
# what says the run needed buying.
#
# KNOWN BLIND SPOT: a range check cannot see an affected timecode that lands
# INSIDE the session. The old per-segment rendering produced exactly that case (a
# session over an hour rendered its first hour MM:SS and the rest H:MM:SS, two
# formats in one prompt); padding removes it, since every segment now renders the
# same way. The blind spot itself remains, because a model can still return an
# in-range wrong value for reasons nothing here models. Closing it needs the
# returned text checked against the segment at its timecode, which this does not
# do.
"""

from __future__ import annotations

import logging
from typing import Literal

from bristlenose.models import PiiCleanTranscript

logger = logging.getLogger(__name__)

# Absolute allowance for a model naming a position a beat past the last segment.
# Irrelevant to the 60x case, which overshoots by minutes or hours.
TIMECODE_GRACE_S = 2.0

RepairOutcome = Literal["scaled", "clamped", "dropped"]


def timecode_ceiling(transcript: PiiCleanTranscript) -> float | None:
    """Latest time a value from this transcript could legitimately carry.

    ``None`` when the transcript has no usable time axis — no segments, or every
    segment starting at 0.0 (a non-timecoded transcript, the same case
    ``_resolve_segment_index`` refuses to match on). Range-checking those would be
    measuring against a clock that isn't running.

    A split chunk keeps the whole session's ``duration_seconds``
    (``_split_transcript`` only replaces ``segments``), so this is the SESSION
    ceiling on both of s09's paths — a quote from the right-hand chunk is
    legitimately at a high absolute time.
    """
    segments = transcript.segments
    if not segments or all(s.start_time == 0.0 for s in segments):
        return None
    ceiling = max([transcript.duration_seconds, *(s.end_time for s in segments)])
    return ceiling if ceiling > 0 else None


def repair_timecode(
    value: float,
    ceiling: float | None,
    *,
    session_id: str,
    field: str,
    raw: str,
    kind: str,
    out_of_range: Literal["clamp", "drop"],
) -> tuple[float, RepairOutcome | None]:
    """Range-check one parsed timecode against the session duration.

    ``kind`` prefixes the log keys (``quote`` -> ``quote_timecode_repair``), so a
    stage's lines stay greppable on their own.

    ``out_of_range`` is what to do with a value that is out of range WITHOUT the
    60x signature — a different fault, which is never divided on spec because
    that would invent a position.

      ``clamp`` (s09) bounds the value into the session. A quote's timecode is
        *shown* — a deep link, a clip-export boundary — so a bounded value is
        better than one past the end of the media.
      ``drop`` (s08) discards it. Clamping a topic boundary would manufacture a
        transition at the session end AND push it back inside
        ``_boundaries_in_range``, turning a detectably-bad boundary into an
        undetectably-wrong one. s09's downstream filter already drops these
        silently; this makes that visible.

    Returns ``(value, outcome)``. On ``"dropped"`` the value is meaningless and
    the caller must discard the item.
    """
    if ceiling is None or value <= ceiling + TIMECODE_GRACE_S:
        return value, None

    scaled = value / 60.0
    if value % 60 == 0 and scaled <= ceiling + TIMECODE_GRACE_S:
        logger.warning(
            "%s_timecode_repair | session=%s | field=%s | raw=%r | was=%.1f | "
            "now=%.1f | ceiling=%.1f | signature=minutes-as-hours",
            kind, session_id, field, raw, value, scaled, ceiling,
        )
        return scaled, "scaled"

    if out_of_range == "drop":
        logger.warning(
            "%s_timecode_out_of_range | session=%s | field=%s | raw=%r | was=%.1f | "
            "ceiling=%.1f | action=dropped",
            kind, session_id, field, raw, value, ceiling,
        )
        return value, "dropped"

    clamped = max(0.0, min(value, ceiling))
    logger.warning(
        "%s_timecode_out_of_range | session=%s | field=%s | raw=%r | was=%.1f | "
        "clamped=%.1f | ceiling=%.1f",
        kind, session_id, field, raw, value, clamped, ceiling,
    )
    return clamped, "clamped"
