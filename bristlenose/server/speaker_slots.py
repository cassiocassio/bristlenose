"""A session's speakers as slots, and the identities the slots point at.

Route C, Phase 1 (``docs/design-people.md`` §H H9). A transcript's ``m1`` is a
*slot*: "the first moderator of this session". Moderator and observer codes
restart in every session, so the slot is not a person; ``session_speakers.
person_id`` says which person it is, or ``None`` when nothing has identified it.
Each identity carries a project-wide ``code`` — ``m2`` is the second moderator
to appear in the study — and **that** is the code every route emits, so a client
that looks a name up by code can never be handed another session's moderator.
An unidentified slot reads ``m?`` / ``o?``, a code no identity has.

Participant codes were project-wide already (participant numbers are never
reused), so a participant's identity code is its slot code.

Read slots through ``project_slots`` / ``session_slots``; never join
``session_speakers`` to ``persons`` with an inner join, which drops the
unidentified slot instead of showing it.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy.orm import Session as DbSession

from bristlenose.server.models import Person, Quote, SessionSpeaker, TranscriptSegment
from bristlenose.server.models import Session as SessionModel

logger = logging.getLogger(__name__)

PROPOSED = "proposed"
CONFIRMED = "confirmed"
#: A person said "not this person": the slot holds nobody, and a re-run must not
#: propose the same name again (design-people.md §C5's sticky ``cleared``, §J8.8).
CLEARED = "cleared"
#: The evidence a person's own act leaves on a slot.
PICK = "pick"

_SLOT_RE = re.compile(r"^([a-z]+)(\d+)$")


def is_team_code(code: str) -> bool:
    """A moderator (``m``) or observer (``o``) code — the ones whose slots
    restart in every session."""
    return code[:1] in ("m", "o")


#: A slot's stored role → the prefix its code takes. The role is the slot's
#: own (``SessionSpeaker.speaker_role``), set from the transcript tag when the
#: slot is made and changed only by a person's recode (design-people.md §J7):
#: an ``m1`` tag recoded as an observer reads ``o…``.
_ROLE_PREFIX = {"researcher": "m", "observer": "o", "participant": "p"}


def kind_prefix(sp: SessionSpeaker) -> str:
    """The prefix a slot's code takes: its role's, else its tag's."""
    return _ROLE_PREFIX.get(sp.speaker_role or "", sp.speaker_code[:1])


def is_team(sp: SessionSpeaker) -> bool:
    """Whether a slot is a moderator or observer *now* — its role, not its
    tag's letter, which a recode leaves alone (design-people.md §J7)."""
    return kind_prefix(sp) in ("m", "o")


def is_recoded_out(sp: SessionSpeaker) -> bool:
    """A participant's tag whose speaker was recoded as moderator or observer
    (§J7 R2). The session's quotes are credited to that tag, and they leave
    the evidence until the session is re-analysed (``evidence_out``)."""
    return sp.speaker_code[:1] == "p" and is_team(sp)


def unidentified_code(slot_code: str, letter: str = "") -> str:
    """``m1`` → ``m?``: what an unidentified slot reads; ``mA?`` when its
    session has more than one speaker of that role (``lettered``)."""
    return f"{slot_code[:1]}{letter}?"


def lettered(slot_codes: list[str]) -> dict[str, str]:
    """The letter each of one session's moderator (or observer) slots goes by.

    One speaker of a role in a session needs no letter: ``m?``. Two or more are
    ``A``, ``B``… in slot order, so two unknowns never read as the same ``m?``
    in a transcript, whose badges show the code alone (design-people.md §J8.9).
    The letter is the slot's place among *all* that role's speakers, not among
    the unknown ones, so naming ``mA?`` leaves ``mB?`` as it was. Letters, never
    numbers, so an unknown cannot be read as ``m1`` or ``m2``.
    """
    ordered = sorted(slot_codes, key=_number)
    if len(ordered) < 2:
        return {}
    return {code: _letter(i) for i, code in enumerate(ordered)}


def _letter(i: int) -> str:
    """A, B, … Z, then AA, AB — a session with 27 moderators is not a study, but
    the label must still be distinct."""
    out = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        out = chr(ord("A") + r) + out
    return out


def _number(code: str) -> int:
    m = _SLOT_RE.match(code)
    return int(m.group(2)) if m else 0


@dataclass(frozen=True)
class Slot:
    """One speaker in one session, as every route should see it."""

    session_id: str  # the session's string id ("s2")
    session_number: int
    slot_code: str  # the transcript's token ("m1")
    code: str  # the identity's code ("m2"), or "m?" when unidentified
    row: SessionSpeaker
    person: Person | None

    @property
    def role(self) -> str:
        return self.row.speaker_role

    @property
    def full_name(self) -> str:
        return self.person.full_name if self.person else ""

    @property
    def name(self) -> str:
        """The house display name: short, else full, else nothing."""
        if not self.person:
            return ""
        return self.person.short_name or self.person.full_name or ""


def _derive_codes(
    rows: list[tuple[str, int, SessionSpeaker, Person | None]],
) -> dict[int, str]:
    """Every slot's code, by the slot row's id — worked out on read.

    A participant is its slot's code (global, never reissued). A moderator or
    observer is numbered per (person, role) in the order the pair first appears
    — session order, then slot order — so Steve is ``m2`` where he moderates and
    ``o1`` where he observes, and the name joins them (design-people.md §J7,
    call 3). An unidentified one is ``m?``, lettered ``mA?``, ``mB?`` when its
    session has more than one speaker of that role (``lettered``). Nothing is
    stored: the session registry keeps sessions and tags stable, so codes only
    move when the map does — two people joined, or a recode.
    """
    ordered = sorted(rows, key=lambda r: (r[1], r[0], _slot_sort_key(r[2].speaker_code)))
    letters: dict[tuple[str, str], dict[str, str]] = {}
    for sid, _n, sp, _p in ordered:
        if is_team(sp):
            letters.setdefault((sid, kind_prefix(sp)), {})[sp.speaker_code] = ""
    for group, codes in letters.items():
        letters[group] = lettered(list(codes))
    # A speaker recoded into participant (§J7 R2) has no participant number of
    # their own: they are numbered after every number the pipeline issued, so
    # they can never read as another participant.
    numbers: dict[str, int] = {
        "p": max((_number(sp.speaker_code) for _s, _n, sp, _p in rows
                  if sp.speaker_code[:1] == "p"), default=0),
    }
    issued: dict[tuple[str, int], str] = {}
    out: dict[int, str] = {}
    for sid, _n, sp, person in ordered:
        prefix = kind_prefix(sp)
        if prefix == "p" and sp.speaker_code[:1] == "p":
            out[sp.id] = sp.speaker_code
            continue
        if person is None:
            letter = letters.get((sid, prefix), {}).get(sp.speaker_code, "")
            out[sp.id] = f"{prefix}{letter}?"
            continue
        pair = (prefix, person.id)
        if pair not in issued:
            numbers[prefix] = numbers.get(prefix, 0) + 1
            issued[pair] = f"{prefix}{numbers[prefix]}"
        out[sp.id] = issued[pair]
    return out


def display_code(sp: SessionSpeaker, person: Person | None, letter: str = "") -> str:
    """A slot's code without its project around it: its tag's, or ``m?``.
    Routes read ``Slot.code``, worked out across the project; this is for a
    caller with one row and no project to number it against."""
    if person is None and is_team(sp):
        return unidentified_code(kind_prefix(sp), letter)
    if kind_prefix(sp) != sp.speaker_code[:1]:
        return unidentified_code(kind_prefix(sp))
    return sp.speaker_code


def _slot_sort_key(code: str) -> tuple[int, int]:
    order = {"m": 0, "p": 1, "o": 2}
    return (order.get(code[:1], 3), _number(code))


def project_slots(db: DbSession, project_id: int) -> list[Slot]:
    """Every slot in the project, in session order then moderators, participants,
    observers. An outer join: an unidentified slot is a slot."""
    rows = (
        db.query(SessionModel.session_id, SessionModel.session_number, SessionSpeaker, Person)
        .join(SessionSpeaker, SessionSpeaker.session_id == SessionModel.id)
        .outerjoin(Person, SessionSpeaker.person_id == Person.id)
        .filter(SessionModel.project_id == project_id)
        .all()
    )
    codes = _derive_codes([(sid, number, sp, person) for sid, number, sp, person in rows])
    slots = [Slot(sid, number, sp.speaker_code, codes[sp.id], sp, person) for sid, number, sp, person in rows]
    slots.sort(key=lambda s: (s.session_number, s.session_id, _slot_sort_key(s.slot_code)))
    return slots


def slot_map(db: DbSession, project_id: int) -> dict[tuple[str, str], Slot]:
    """(session id, slot code) → slot: how a transcript token is translated."""
    return {(s.session_id, s.slot_code): s for s in project_slots(db, project_id)}


def session_slots(db: DbSession, project_id: int, session_id: str) -> list[Slot]:
    return [s for s in project_slots(db, project_id) if s.session_id == session_id]


def code_for(db: DbSession, session_pk: int, slot_code: str) -> str:
    """One slot's identity code, by the session row's primary key — for a
    route that translates a single transcript token (a per-quote call)."""
    session = db.get(SessionModel, session_pk)
    if session is None:
        return slot_code
    slot = slot_map(db, session.project_id).get((session.session_id, slot_code))
    return slot.code if slot is not None else slot_code


def identities(db: DbSession, project_id: int) -> dict[str, Person]:
    """Identity code → person, for every identity a slot in the project uses."""
    result: dict[str, Person] = {}
    for slot in project_slots(db, project_id):
        if slot.person is not None:
            result.setdefault(slot.code, slot.person)
    return result


def renumber(db: DbSession, project_id: int) -> None:
    """Recompute every identity's code from the slot map.

    A participant is its slot's code. Moderators and observers are numbered in
    the order they first appear — session order, then slot order — so the
    session registry's stable numbering keeps them stable, and a code moves
    only when the map does (two identities joined, one released). The code is
    derived, not stored identity (``design-people.md`` §C2).
    """
    db.flush()
    seen: set[int] = set()
    for slot in project_slots(db, project_id):
        person = slot.person
        if person is None or person.id in seen:
            continue
        seen.add(person.id)
        # The person's first code. A record only: the routes read Slot.code,
        # worked out per (person, role) on every read (_derive_codes).
        person.code = slot.code


def release(db: DbSession, person_ids: set[int | None]) -> None:
    """Let go of identities no slot points at any more — and keep them.

    A person with no session is hidden, not deleted: ``identities`` and the
    routes derive everything from slots, so nothing lists them, while the
    record survives for an undo to point back at and for a later type-ahead
    to offer again (owner, 6 Oct 2026; ``design-people.md`` §J8.10). Deleting
    a person is the People lens's act. All this does is flush, so the slots'
    new pointers are visible to the renumber that follows.
    """
    del person_ids
    db.flush()


def label_taken(
    db: DbSession, project_id: int, names: list[str | None], *, but: Person | None,
) -> str | None:
    """The name another moderator or observer already goes by, if any.

    Two people may share a name in the world, but not in one study's picker:
    a second "Martin" is either a real second Martin, who needs telling apart
    ("Martin S"), or a researcher making someone new instead of picking the
    Martin in the list. Either way the write is refused (owner, 6 Oct 2026;
    ``design-people.md`` §J8.11). Case-insensitive; only the people a slot
    points at, so a hidden person never blocks a name.
    """
    wanted = {n.strip().casefold() for n in names if n and n.strip()}
    if not wanted:
        return None
    for code, person in identities(db, project_id).items():
        if person is but or not is_team_code(code):
            continue
        for held in (person.full_name, person.short_name):
            if held and held.strip().casefold() in wanted:
                return held
    return None


def is_participant(db: DbSession, person: Person, *, but: SessionSpeaker | None = None) -> bool:
    """Whether a person is a participant in some session, other than in the
    slot ``but`` — never a moderator or observer's to pick: that would join two
    participants' identities, which a recode does not do (§J7)."""
    if person.id is None:
        return False
    return any(
        not is_team(sp)
        for sp in db.query(SessionSpeaker).filter_by(person_id=person.id)
        if sp is not but
    )


class EvidenceOut(set[tuple[str, str]]):
    """What leaves the evidence: ``(session id, tag)`` pairs, as a set, plus
    ``quotes`` — the ids of quotes whose words were moved off their participant
    one paragraph at a time (§K). A set, so a caller that reads the pairs alone
    keeps working; ``counts`` reads both."""

    def __init__(self, pairs: Iterable[tuple[str, str]] = (), quotes: Iterable[int] = ()) -> None:
        super().__init__(pairs)
        self.quotes: set[int] = set(quotes)


def _moved_quotes(db: DbSession, project_id: int) -> set[int]:
    """Quotes whose words now belong to someone else (§K, Paragraph scope).

    Only sessions where a paragraph was moved are read. A quote leaves when a
    paragraph its window overlaps was moved off its credited tag and no
    paragraph it overlaps is still that tag's — so a quote spanning a moved
    and an unmoved paragraph stays. Overlap is strict: a paragraph that only
    touches the window at its edge does not count. Untimed transcripts (every
    paragraph at 0:00) overlap nothing, so nothing leaves there.
    """
    moved = (
        db.query(TranscriptSegment, SessionModel.session_id)
        .join(SessionModel, SessionModel.id == TranscriptSegment.session_id)
        .filter(SessionModel.project_id == project_id, TranscriptSegment.moved_from.isnot(None))
        .all()
    )
    if not moved:
        return set()
    out: set[int] = set()
    for sid in {s for _, s in moved}:
        sess = db.query(SessionModel).filter_by(project_id=project_id, session_id=sid).first()
        if sess is None:
            continue
        segs = db.query(TranscriptSegment).filter_by(session_id=sess.id).all()
        for q in db.query(Quote).filter_by(project_id=project_id, session_id=sid):
            over = [
                g for g in segs
                if g.start_time < q.end_timecode and g.end_time > q.start_timecode
            ]
            if (any(g.moved_from == q.participant_id for g in over)
                    and not any(g.speaker_code == q.participant_id for g in over)):
                out.add(q.id)
    return out


def evidence_out(db: DbSession, project_id: int) -> EvidenceOut:
    """``(session id, tag)`` for every participant tag whose speaker was
    recoded as a moderator or observer (design-people.md §J7 R2, §C4).

    A session's quotes are credited to its participant's tag, so when that
    speaker turns out to be the moderator, their quotes are the moderator's
    words: they leave the Quotes lens, search, the dashboard, signals and every
    export until the session is re-analysed. Hidden, never deleted — the
    recode's undo brings them back with their stars and tags. One predicate,
    read everywhere through ``counts`` / ``evidence_quotes``.
    """
    rows = (
        db.query(SessionModel.session_id, SessionSpeaker)
        .join(SessionSpeaker, SessionSpeaker.session_id == SessionModel.id)
        .filter(
            SessionModel.project_id == project_id,
            SessionSpeaker.speaker_code.like("p%"),
            SessionSpeaker.speaker_role != "participant",
        )
        .all()
    )
    return EvidenceOut(
        {(sid, sp.speaker_code) for sid, sp in rows if is_recoded_out(sp)},
        _moved_quotes(db, project_id),
    )


def counts(quote: object, out: set[tuple[str, str]]) -> bool:
    """Whether a quote is evidence: its credited speaker is still a participant,
    and its words were not moved to someone else a paragraph at a time."""
    if (getattr(quote, "session_id", ""), getattr(quote, "participant_id", "")) in out:
        return False
    return getattr(quote, "id", None) not in getattr(out, "quotes", ())


def evidence_quotes(db: DbSession, project_id: int) -> list[Quote]:
    """The project's quotes that count as evidence (``evidence_out``)."""
    out = evidence_out(db, project_id)
    quotes = db.query(Quote).filter_by(project_id=project_id).all()
    return [q for q in quotes if counts(q, out)] if out or out.quotes else quotes


def by_uuid(db: DbSession, uuid: str) -> Person | None:
    """The person with this uuid, whether or not a slot points at them."""
    return db.query(Person).filter_by(uuid=uuid).first()


def point(
    sp: SessionSpeaker, person: Person | None, *, state: str | None, evidence: str | None,
) -> int | None:
    """Point a slot at a person (or at nobody); returns the person it left."""
    old = sp.person_id
    sp.person = person
    sp.person_id = person.id if person is not None else None
    sp.state = state if person is not None else None
    sp.evidence = evidence if person is not None else None
    return old if old != sp.person_id else None
