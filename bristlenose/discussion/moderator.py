"""Which of a session's turns are the moderator's — the ONE place the stage reads
speaker roles, so identity work upstream (moderator identity, a whole-transcript
speaker split) changes one function, not the stage.

Two reliability checks, from the speaker-split work (3 Oct 2026, measured on a
real project). On Whisper-transcribed sessions the splitter labels speaker
changes only inside an opening sample window; every later segment inherits the
last label. So the role can be OVER-attributed (a 35-minute session read as
moderator for its last 29 minutes) or UNDER-attributed (an 18-minute session
with no moderator turn after 4:25). Neither is fixed here — the split itself is
an open decision upstream. A session that fails either check is marked
``moderator_unreliable`` and left out of the structure, so it reads as "can't
tell", never as "no questions asked". Platform transcripts (Teams, Zoom, Meet)
carry real speakers and skip the splitter, so the checks do not apply to them.
"""

from __future__ import annotations

from dataclasses import dataclass

from bristlenose.models import FullTranscript, SpeakerRole, TranscriptSegment

MIN_WORDS = 3  # shorter moderator turns ("yeah", "great") are never questions

# Over-attribution: a moderator who speaks for more than half the session's
# words is implausible in an interview.
MAX_MODERATOR_SHARE = 0.5

# Under-attribution: the splitter's sample window, mirrored from s05b
# (min(max(300 s, 18% of duration), 480 s)), and the margin past it after which
# a session with no later moderator turn is not believable.
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


def moderator_turns(transcript: FullTranscript) -> ModeratorTurns:
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
        if last <= window and duration > window + _SILENT_MARGIN_S:
            return ModeratorTurns(askable, code, False, "moderator_under_attributed")
    return ModeratorTurns(askable, code, True)
