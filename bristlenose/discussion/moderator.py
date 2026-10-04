"""Which of a session's turns are the moderator's — the ONE place the stage reads
speaker roles, so identity work upstream (moderator identity, a whole-transcript
speaker split) changes one function, not the stage.

Two reliability checks, from the speaker-split work (3 Oct 2026, measured on a
real project). Until 3 Oct 2026 the splitter labelled speaker changes on
Whisper-transcribed sessions only inside an opening sample window, and every
later segment inherited the last label. So the role could be OVER-attributed (a
35-minute session read as moderator for its last 29 minutes) or
UNDER-attributed (an 18-minute session with no moderator turn after 4:25).

The splitter now reads the whole transcript, so new runs no longer have that
window. Speaker results are cached per session, so a project analysed before
the change keeps its propagated labels on resume. Since 4 Oct 2026 each
session's speaker cache says which splitter wrote it: a fresh one carries a
``speaker_split`` record, an old one has no such key. The under-attribution
check runs only on a session WITHOUT that record — where it catches a real
failure — and is skipped on a whole-transcript split, where it could only
misfire on a moderator who genuinely asks nothing after the opening minutes.
Retire it when no cache from before 3 Oct 2026 can be resumed. The
over-attribution check (over half the words) is a sanity check either way.

A session that fails either check is marked ``moderator_unreliable`` and left
out of the structure, so it reads as "can't tell", never as "no questions
asked". Platform transcripts (Teams, Zoom, Meet) carry real speakers and skip
the splitter, so the checks do not apply to them.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from bristlenose.models import FullTranscript, SpeakerRole, TranscriptSegment

MIN_WORDS = 3  # shorter moderator turns ("yeah", "great") are never questions

# Over-attribution: a moderator who speaks for more than half the session's
# words is implausible in an interview.
MAX_MODERATOR_SHARE = 0.5

# Under-attribution: the sample window s05b used before 3 Oct 2026
# (min(max(300 s, 18% of duration), 480 s)) — kept for caches written then; see
# the module docstring — and the margin past it after which a session with no
# later moderator turn is not believable.
_WINDOW_FLOOR_S, _WINDOW_SHARE, _WINDOW_CEIL_S = 300.0, 0.18, 480.0
_SILENT_MARGIN_S = 120.0

_WHISPER_SOURCES = {"whisper", "mlx-whisper", "faster-whisper"}


@dataclass
class ModeratorTurns:
    turns: list[TranscriptSegment]
    code: str                  # the first moderator's code (a session can have m1, m2); "" when none
    reliable: bool
    reason: str = ""           # why not, for the record's stats and the log


def is_moderator(seg: TranscriptSegment) -> bool:
    if seg.speaker_role == SpeakerRole.RESEARCHER:
        return True
    return seg.speaker_role == SpeakerRole.UNKNOWN and seg.speaker_code.startswith("m")


def splitter_window(duration: float) -> float:
    return min(max(_WINDOW_FLOOR_S, _WINDOW_SHARE * duration), _WINDOW_CEIL_S)


def whole_transcript_split(speaker_info_dir: Path, session_ids: Iterable[str]) -> frozenset[str]:
    """The sessions whose speaker cache records a whole-transcript split.

    Absent key, a null record, or an unreadable file all mean "can't say", and
    such a session keeps the under-attribution check.
    """
    found: set[str] = set()
    for sid in session_ids:
        try:
            data = json.loads((speaker_info_dir / f"{sid}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        split = data.get("speaker_split") if isinstance(data, dict) else None
        if isinstance(split, dict) and split.get("method"):
            found.add(sid)
    return frozenset(found)


def moderator_turns(transcript: FullTranscript, *, whole_split: bool = False) -> ModeratorTurns:
    segs = transcript.segments
    mod = [s for s in segs if is_moderator(s)]
    code = next((s.speaker_code for s in mod if s.speaker_code), "")
    askable = [s for s in mod if len(s.text.split()) >= MIN_WORDS]
    if not askable:
        return ModeratorTurns([], code, False, "no_moderator")

    whisper = any(s.source in _WHISPER_SOURCES for s in segs)
    if whisper:
        words = sum(len(s.text.split()) for s in segs) or 1
        share = sum(len(s.text.split()) for s in mod) / words
        if share > MAX_MODERATOR_SHARE:
            return ModeratorTurns(askable, code, False, "moderator_over_attributed")
        duration = transcript.duration_seconds or (segs[-1].end_time if segs else 0.0)
        window = splitter_window(duration)
        last = max(s.start_time for s in mod)
        if not whole_split and last <= window and duration > window + _SILENT_MARGIN_S:
            return ModeratorTurns(askable, code, False, "moderator_under_attributed")
    return ModeratorTurns(askable, code, True)
