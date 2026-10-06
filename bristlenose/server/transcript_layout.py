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

A third kind, ``speaker``, credits one paragraph to another speaker of the same
session — the transcript picker's Paragraph scope (``design-people.md`` §K).
"""

from __future__ import annotations

import json
import logging
import re
from difflib import SequenceMatcher

from sqlalchemy.orm import Session as DbSession

from bristlenose.server.models import Session as SessionModel
from bristlenose.server.models import SessionSpeaker, TranscriptLayoutEdit, TranscriptSegment

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


def _norm(word: str) -> str:
    """A word as the alignment compares it: case and punctuation dropped."""
    return re.sub(r"[^\w']", "", word.casefold())


def text_cut(text: str, drawn: list[str], token: int) -> int:
    """Where in the paragraph's own text the drawn word ``token`` starts.

    The cut is counted in the words the page draws, which for a timed
    paragraph are Whisper's — lower-cased, unpunctuated, and not always the
    text word for word (a platform transcript's "(Speaker B)" is not among
    them; a sentence's first words can sit in the previous paragraph's word
    list). So the drawn words are aligned to the text's words, and the text is
    cut where the chosen word landed: its case, punctuation and spacing stay.
    A word that found no partner moves the cut to the next one that did; with
    none, the cut falls the same share of the way through the text.
    """
    spans = [(m.start(), m.group()) for m in re.finditer(r"\S+", text)]
    if not spans:
        return 0
    if [w for _, w in spans] == drawn:
        return spans[token][0]
    matcher = SequenceMatcher(None, [_norm(w) for w in drawn], [_norm(w) for _, w in spans],
                              autojunk=False)
    to_text: dict[int, int] = {}
    for block in matcher.get_matching_blocks():
        for k in range(block.size):
            to_text[block.a + k] = block.b + k
    for i in range(token, len(drawn)):
        if i in to_text and to_text[i] > 0:
            return spans[to_text[i]][0]
    share = round(len(spans) * token / max(len(drawn), 1))
    return spans[min(max(share, 1), len(spans) - 1)][0]


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
    # The text is cut at the same word, in the text's own spelling (text_cut):
    # rebuilding it from Whisper's words lost case and punctuation.
    at = text_cut(seg.text, drawn, token)
    left_text, right_text = seg.text[:at].rstrip(), seg.text[at:].strip()
    if not left_text or not right_text:
        raise LayoutRefusedError("a split needs words on both sides")
    if start <= seg.start_time:
        # No time to share (an untimed paragraph, or one whose first word is
        # at its start): put the second half a hair after the first, short of
        # whatever reads next, so a second split of the first half still lands
        # between the two — ties would fall through to insertion order.
        later = [s.start_time for s in segs[position + 1:] if s.start_time > seg.start_time]
        start = seg.start_time + ((later[0] - seg.start_time) / 2 if later else 0.001)
    second = TranscriptSegment(
        session_id=seg.session_id,
        speaker_code=seg.speaker_code,
        start_time=start,
        end_time=max(seg.end_time, start),
        text=right_text,
        source=seg.source,
        segment_index=seg.segment_index,
        words_json=json.dumps(right_words, separators=(",", ":")) if right_words else None,
        moved_from=seg.moved_from,
    )
    seg.text = left_text
    seg.end_time = min(seg.end_time, start) if seg.end_time > seg.start_time else seg.end_time
    seg.words_json = json.dumps(left_words, separators=(",", ":")) if left_words else None
    db.add(second)
    db.flush()


def _join(db: DbSession, segs: list[TranscriptSegment], position: int, verify: str) -> None:
    if not 0 < position < len(segs):
        raise LayoutRefusedError("no paragraph above to join")
    first, second = segs[position - 1], segs[position]
    if first.speaker_code != second.speaker_code:
        raise LayoutRefusedError("two speakers' paragraphs are not joined")
    # A moved paragraph keeps whose words it was (``moved_from``), which a join
    # would lose or spread over words that were never moved (§K).
    if first.moved_from != second.moved_from:
        raise LayoutRefusedError("a moved paragraph is not joined to one that was not")
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


#: Roles a Paragraph-scope move can create a speaker in, by their code's letter.
NEW_ROLES = {"moderator": ("m", "researcher")}


def mint_code(db: DbSession, session_pk: int, role: str, issued: list[str]) -> str:
    """The next code of ``role``'s letter in this session: above every slot it
    has and every code the pipeline ever issued it (``issued``), so a later
    re-run's own speaker never takes it."""
    letter, _ = NEW_ROLES[role]
    held = [sp.speaker_code for sp in db.query(SessionSpeaker).filter_by(session_id=session_pk)]
    numbers = [
        int(c[1:]) for c in held + issued
        if c[:1] == letter and c[1:].isdigit()
    ]
    return f"{letter}{max(numbers, default=0) + 1}"


def _speaker(db: DbSession, segs: list[TranscriptSegment], position: int, verify: str,
             code: str, creates: bool = False) -> None:
    """Credit one paragraph to another speaker of its session (§K, the
    picker's Paragraph scope). The words and timing stay; ``moved_from``
    remembers whose they were, so a quote from them leaves the evidence.

    ``creates``: the move made its speaker, a new unknown moderator (a call
    collapsed into one voice has none to move to). The importer drops a
    moderator slot nobody confirmed that the transcript no longer uses, so the
    replay makes it again — unless the pipeline's own transcript now uses the
    code, when the move is refused rather than landed on someone real."""
    if not 0 <= position < len(segs):
        raise LayoutRefusedError("no such paragraph")
    seg = segs[position]
    if join_verify(seg) != verify:
        raise LayoutRefusedError("the paragraph has changed")
    if code == seg.speaker_code:
        raise LayoutRefusedError("the paragraph is already that speaker's")
    held = {
        sp.speaker_code
        for sp in db.query(SessionSpeaker).filter_by(session_id=seg.session_id)
    }
    if creates and any(g.speaker_code == code and g.moved_from is None for g in segs):
        raise LayoutRefusedError("the new speaker's code is now someone else's")
    if code not in held:
        role = next((r for k, (letter, r) in NEW_ROLES.items() if code[:1] == letter), None)
        if not creates or role is None:
            raise LayoutRefusedError("no such speaker in this session")
        db.add(SessionSpeaker(session_id=seg.session_id, person_id=None,
                              speaker_code=code, speaker_role=role))
    origin = seg.moved_from or seg.speaker_code
    seg.speaker_code = code
    # Moved back to whoever it came from: it is theirs again.
    seg.moved_from = None if code == origin else origin
    db.flush()


def apply(db: DbSession, edit: TranscriptLayoutEdit) -> None:
    """Make one recorded edit on the session's live paragraphs."""
    segs = ordered(db, edit.session_id)
    if edit.kind == "split":
        _split(db, segs, edit.position, edit.token, edit.verify)
    elif edit.kind == "join":
        _join(db, segs, edit.position, edit.verify)
    elif edit.kind == "speaker":
        _speaker(db, segs, edit.position, edit.verify, edit.speaker_code, creates=edit.token == 1)
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
            logger.warning("%s: a paragraph %s was not re-made (%s)", session.session_id,
                        edit.kind, exc)
    return made
