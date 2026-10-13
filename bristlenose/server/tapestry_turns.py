"""Speaker turns for the session tapestry, shared by the route that draws them and the
background job that takes the hover thumbnail's frames from them.

One definition, because the two must agree: the job takes a frame per participant turn, and the
route says the frames are stale when the turns it draws would select different ones (a paragraph
split, joined or moved to another speaker, a speaker recoded). See ``utils/turn_frames.py``.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session, selectinload

from bristlenose.server import speaker_slots
from bristlenose.server.models import Session as SessionModel
from bristlenose.server.models import TranscriptSegment
from bristlenose.utils.turn_frames import Frame, read_record, select_frames, selection_key

#: A turn: start, end, the transcript's slot code, and whether the speaker is on the team now.
Turn = tuple[float, float, str, bool]


def turn_spans(segments: list[TranscriptSegment], duration: float) -> list[tuple[float, float, str]]:
    """Consecutive same-speaker segments as one turn; a turn lasts until the next starts, and the
    last runs to the end of the recording."""
    turns: list[tuple[float, float, str]] = []
    for seg in sorted(segments, key=lambda s: s.start_time):
        if turns and turns[-1][2] == seg.speaker_code:
            a, b, code = turns[-1]
            turns[-1] = (a, max(b, seg.end_time), code)
        else:
            turns.append((seg.start_time, seg.end_time, seg.speaker_code))
    out = []
    for i, (a, b, code) in enumerate(turns):
        end = turns[i + 1][0] if i + 1 < len(turns) else max(b, duration)
        out.append((a, max(b, end), code))
    return out


def session_turns(sess: SessionModel, slots: dict[tuple[str, str], speaker_slots.Slot]) -> list[Turn]:
    """The session's turns, each with its speaker's role *now*: the slot's, which a recode changes
    while the token keeps its letter (design-people.md §J7)."""
    return [
        (a, b, code, speaker_slots.is_team(slots[(sess.session_id, code)].row)
         if (sess.session_id, code) in slots else speaker_slots.is_team_code(code))
        for a, b, code in turn_spans(sess.transcript_segments, sess.duration_seconds)
    ]


def participant_turns(turns: list[Turn]) -> list[tuple[float, float]]:
    return [(a, b) for a, b, _code, team in turns if not team]


def all_participant_turns(db: Session) -> dict[str, list[tuple[float, float]]]:
    """Session id → its participant turns, for every session in the database. Should a session id
    appear in two project rows (the fork ``server/CLAUDE.md`` records), the lowest project wins,
    as it does for the SPA, which reads project 1: frames taken for the other row's turns would
    never match the route's, and it would ask for a pass on every poll."""
    sessions = (db.query(SessionModel).options(selectinload(SessionModel.transcript_segments))
                .order_by(SessionModel.project_id.desc()).all())
    slots: dict[tuple[str, str], speaker_slots.Slot] = {}
    for project_id in {s.project_id for s in sessions}:
        slots.update(speaker_slots.slot_map(db, project_id))
    return {s.session_id: participant_turns(session_turns(s, slots)) for s in sessions}


def frames_dir(output_dir: Path) -> Path:
    return output_dir / ".bristlenose" / "intermediate" / "turn-frames"


def strip_changes(output_dir: Path, session_id: str) -> list[float] | None:
    """The finer scene changes from the session's strip record, or None without one (no video,
    not computed yet, or a strip from before the record carried them)."""
    from bristlenose.server.scene_strips import strips_dir

    rec = read_record(strips_dir(output_dir) / f"{session_id}.json")
    changes = rec.get("changes") if rec else None
    if not isinstance(changes, list):
        return None
    return [float(c) for c in changes if isinstance(c, (int, float))]


def wanted_frames(output_dir: Path, session_id: str,
                  turns: list[tuple[float, float]]) -> list[Frame] | None:
    """The frames the session's participant turns call for now, or None without a strip."""
    changes = strip_changes(output_dir, session_id)
    return None if changes is None else select_frames(turns, changes)


def frames_state(output_dir: Path, session_id: str,
                 turns: list[tuple[float, float]]) -> tuple[str | None, bool]:
    """(the key of the frames on disk when they are current and not empty, whether a pass is
    owed: a strip exists and its frames are missing or were taken for other turns)."""
    wanted = wanted_frames(output_dir, session_id, turns)
    if wanted is None:
        return None, False
    rec = read_record(frames_dir(output_dir) / f"{session_id}.json")
    if rec is None or rec.get("selection") != selection_key(wanted):
        return None, True
    frames = rec.get("frames")
    return (str(rec.get("key")) if isinstance(frames, list) and frames else None), False
