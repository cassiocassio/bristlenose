"""Split and join a session's transcript paragraphs (stage 1).

``design-transcript-editing.md`` §"Split and join, stage 1". The common case
(owner, 6 Oct 2026): a long paragraph that does not read as one thing, split in
two with the same speaker; and the reverse, two paragraphs joined. Text and
timing only — the speaker stays, and quotes are not split (the converged spec's
fork rule is stage 2).

Edits are recorded (``TranscriptLayoutEdit``) and applied to the live rows; the
importer rebuilds a session's paragraphs from the pipeline's transcript on every
import and replays them in order (``replay``), so a split outlives a re-run.
A split is made at a word boundary, counted in words, so it means the same thing
whether the paragraph is drawn from Whisper's words or from its text.
"""

from __future__ import annotations

import json
import logging

from sqlalchemy.orm import Session as DbSession

from bristlenose.server.models import Session as SessionModel
from bristlenose.server.models import TranscriptLayoutEdit, TranscriptSegment

logger = logging.getLogger(__name__)

#: How many words an edit remembers to check it still lands where it was made.
VERIFY_WORDS = 6


class LayoutRefusedError(ValueError):
    """The edit cannot be made here: the paragraphs have moved, a join across
    two speakers, a split at either end."""


def ordered(db: DbSession, session_pk: int) -> list[TranscriptSegment]:
    """A session's paragraphs in reading order — the order every edit counts in.

    Start time, then the pipeline's ordinal, then insertion order, so a split
    half that shares its first half's start (no timings) still reads after it.
    """
    return (
        db.query(TranscriptSegment)
        .filter_by(session_id=session_pk)
        .order_by(TranscriptSegment.start_time, TranscriptSegment.segment_index,
                  TranscriptSegment.id)
        .all()
    )


def _verify(words: list[str]) -> str:
    return " ".join(words[:VERIFY_WORDS])


def _words(seg: TranscriptSegment) -> list[dict[str, object]] | None:
    if not seg.words_json:
        return None
    try:
        data = json.loads(seg.words_json)
    except ValueError:
        return None
    return data if isinstance(data, list) else None


def tokens(seg: TranscriptSegment) -> list[str]:
    """A paragraph's words as the transcript draws them: Whisper's words where
    the paragraph has them (the page renders those, not the text), else its
    text split on spaces. Every edit counts in these."""
    words = _words(seg)
    if words:
        return [str(w.get("t", "")).strip() for w in words]
    return seg.text.split()


def split_verify(seg: TranscriptSegment, token: int) -> str:
    return _verify(tokens(seg)[token:])


def join_verify(seg: TranscriptSegment) -> str:
    return _verify(tokens(seg))


def _split(db: DbSession, segs: list[TranscriptSegment], position: int, token: int,
           verify: str) -> None:
    if not 0 <= position < len(segs):
        raise LayoutRefusedError("no such paragraph")
    seg = segs[position]
    drawn = tokens(seg)
    if not 0 < token < len(drawn):
        raise LayoutRefusedError("a split needs words on both sides")
    if split_verify(seg, token) != verify:
        raise LayoutRefusedError("the paragraph has changed")
    words = _words(seg)
    left_words = right_words = None
    if words:
        left_words, right_words = words[:token], words[token:]
    if right_words:
        start = float(right_words[0].get("s", seg.start_time))  # type: ignore[arg-type]
    elif seg.end_time > seg.start_time:
        # No word timings: share the time by how much of the text each half holds.
        share = len(" ".join(drawn[:token])) / max(len(" ".join(drawn)), 1)
        start = seg.start_time + (seg.end_time - seg.start_time) * share
    else:
        start = seg.start_time
    start = min(max(start, seg.start_time), seg.end_time)
    second = TranscriptSegment(
        session_id=seg.session_id,
        speaker_code=seg.speaker_code,
        start_time=start,
        end_time=seg.end_time,
        text=" ".join(drawn[token:]),
        source=seg.source,
        segment_index=seg.segment_index,
        words_json=json.dumps(right_words, separators=(",", ":")) if right_words else None,
    )
    seg.text = " ".join(drawn[:token])
    seg.end_time = start
    seg.words_json = json.dumps(left_words, separators=(",", ":")) if left_words else None
    db.add(second)
    db.flush()


def _join(db: DbSession, segs: list[TranscriptSegment], position: int, verify: str) -> None:
    if not 0 < position < len(segs):
        raise LayoutRefusedError("no paragraph above to join")
    first, second = segs[position - 1], segs[position]
    if first.speaker_code != second.speaker_code:
        raise LayoutRefusedError("two speakers' paragraphs are not joined")
    if join_verify(second) != verify:
        raise LayoutRefusedError("the paragraph has changed")
    a, b = _words(first), _words(second)
    first.text = f"{first.text} {second.text}".strip()
    first.end_time = max(first.end_time, second.end_time)
    first.words_json = (
        json.dumps(a + b, separators=(",", ":")) if a is not None and b is not None else None
    )
    db.delete(second)
    db.flush()


def apply(db: DbSession, edit: TranscriptLayoutEdit) -> None:
    """Make one recorded edit on the session's live paragraphs."""
    segs = ordered(db, edit.session_id)
    if edit.kind == "split":
        _split(db, segs, edit.position, edit.token, edit.verify)
    elif edit.kind == "join":
        _join(db, segs, edit.position, edit.verify)
    else:
        raise LayoutRefusedError(f"unknown edit {edit.kind!r}")


def replay(db: DbSession, session: SessionModel) -> int:
    """Re-make a session's recorded edits on freshly imported paragraphs, in
    order. An edit whose paragraph has changed under it (a re-analysis rewrote
    the transcript) is skipped and logged, never made on other words. Returns
    how many were made."""
    made = 0
    for edit in (
        db.query(TranscriptLayoutEdit).filter_by(session_id=session.id)
        .order_by(TranscriptLayoutEdit.id).all()
    ):
        try:
            apply(db, edit)
            made += 1
        except LayoutRefusedError as exc:
            logger.info("%s: a paragraph %s was not re-made (%s)", session.session_id,
                        edit.kind, exc)
    return made
