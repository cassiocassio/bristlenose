"""Discussion lens — the stage's record and its LLM response schemas.

Kept in this package rather than ``models.py`` / ``llm/structured.py`` while the
stage is built behind its off switch (plan §1.2; moved here 3 Oct 2026 to stay
out of files concurrent identity work is changing). They graduate when the
stage does.

The record is the "lens data contract", version 1, that the dev-gated SPA lens
already reads from a fixture (``frontend/src/islands/discussion/types.ts``) —
with one deliberate difference (plan §9.C): it carries **speaker codes, never
names**. Codes are per session (s1's m1 and s2's m1 can be different people), so
display keys on (session, code); names come per session from the session-speaker
rows (``people.load_session_speakers``, the DB in serve), which the export
anonymiser already handles — never from ``/people``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

RECORD_VERSION = 1


def _clip(v: object, cap: int) -> object:
    """An over-long label is clipped, never a validation error: one long field
    must not fail a whole session's response (silent-failure review, 3 Oct)."""
    if isinstance(v, str) and len(v) > cap:
        return v[: cap - 1].rstrip() + "…"
    return v


# ── LLM response schemas ─────────────────────────────────────────────────────


class SpineItemOut(BaseModel):
    text: str
    terse: str = ""

    @field_validator("terse", mode="before")
    @classmethod
    def _terse(cls, v: object) -> object:
        return _clip(v, 30)


class SpineSectionOut(BaseModel):
    title: str
    kind: Literal["questions", "task", "instruction"] = "questions"
    items: list[SpineItemOut] = Field(default_factory=list)


class SpineOut(BaseModel):
    sections: list[SpineSectionOut]


class TurnLabelOut(BaseModel):
    turn_id: str
    kind: Literal["planned", "adlib", "new", "instruction", "chat"]
    item_id: str = ""
    section_id: str = ""
    cluster: str = ""
    role: Literal["opening", "core", "closing"] = "core"
    terse: str = ""

    @field_validator("terse", mode="before")
    @classmethod
    def _terse(cls, v: object) -> object:
        return _clip(v, 30)


class SessionLabelsOut(BaseModel):
    labels: list[TurnLabelOut]


class TopicOut(BaseModel):
    name: str
    nav: str = ""
    heading: str = ""

    @field_validator("nav", mode="before")
    @classmethod
    def _nav(cls, v: object) -> object:
        return _clip(v, 24)

    @field_validator("heading", mode="before")
    @classmethod
    def _heading(cls, v: object) -> object:
        return _clip(v, 48)


class ConsolidatedItemOut(BaseModel):
    turn_ids: list[str]
    terse: str = ""
    where: str

    @field_validator("terse", mode="before")
    @classmethod
    def _terse(cls, v: object) -> object:
        return _clip(v, 30)


class ConsolidateOut(BaseModel):
    # topics FIRST: the model settles the lines of enquiry, then assigns
    # questions to them (measured in the spike, 3 Oct 2026)
    topics: list[TopicOut] = Field(default_factory=list)
    items: list[ConsolidatedItemOut] = Field(default_factory=list)


class RouteOut(BaseModel):
    quote_id: str
    section_id: str
    confidence: float = 0.0

    @field_validator("confidence", mode="before")
    @classmethod
    def _conf(cls, v: object) -> object:  # out of range is clamped, not a failed batch
        return min(1.0, max(0.0, float(v))) if isinstance(v, (int, float)) else 0.0


class RouteBatchOut(BaseModel):
    routes: list[RouteOut]


# ── the record (lens data contract v1) ───────────────────────────────────────


SessionState = Literal["ok", "failed", "no_moderator", "moderator_unreliable"]


class RecordSession(BaseModel):
    id: str
    number: int
    participants: list[str] = Field(default_factory=list)  # codes only; names per (session, code)
    duration: str = ""
    seconds: float = 0.0
    # Why a session contributes nothing, so absence never reads as "no
    # questions asked" (plan §9.A). "ok" sessions are in the structure.
    state: SessionState = "ok"


class RecordAsk(BaseModel):
    turn: str
    session: str
    sec: float


class RecordItem(BaseModel):
    id: str
    terse: str
    verbatim: str = ""
    source: Literal["planned", "asked", "both"] = "planned"
    placed: Literal["", "flow"] = ""
    role: Literal["opening", "core", "closing"] = "core"
    asks: list[RecordAsk] = Field(default_factory=list)


class RecordSection(BaseModel):
    id: str
    title: str
    heading: str = ""
    kind: Literal["questions", "task", "instruction"] = "questions"
    origin: Literal["planned", "emergent"] = "planned"
    items: list[RecordItem] = Field(default_factory=list)


class RecordSpineItem(BaseModel):
    id: str
    terse: str
    text: str


class RecordSpineSection(BaseModel):
    id: str
    title: str
    kind: Literal["questions", "task", "instruction"] = "questions"
    # Instruction sections keep their title only: consent, logistics and
    # welfare text is not evidence and must not ride into exports (§9.C).
    items: list[RecordSpineItem] = Field(default_factory=list)


class RecordTurn(BaseModel):
    id: str
    session: str
    sec: float
    time: str
    text: str
    kind: Literal["planned", "adlib", "new", "instruction", "chat", "unclassified"]
    item: str | None = None
    speaker: str = ""  # this turn's moderator code — a session can have m1 and m2


class RecordQuote(BaseModel):
    """A quote, keyed the way the importer keys quotes (session, participant,
    start) — never by list position (§9.F)."""

    session: str
    participant: str
    sec: float
    time: str
    text: str
    after_item: str | None = None
    section: str | None = None
    how: Literal["agree", "topic", "anchor", "unrouted"] = "unrouted"
    sentiment: str | None = None


class DiscussionRecord(BaseModel):
    version: int = RECORD_VERSION
    # complete: every session contributed; partial: some sessions failed or
    # were unreliable; failed: nothing usable. Never inferred from absence.
    status: Literal["complete", "partial", "failed"] = "complete"
    guide: bool = False
    guide_sha: str = ""          # the guide this was built from ("" = none)
    quotes_sha: str = ""         # the quotes it was built from: a stale record is refused
    sessions: list[RecordSession] = Field(default_factory=list)
    spine: list[RecordSpineSection] = Field(default_factory=list)
    sections: list[RecordSection] = Field(default_factory=list)
    standalone: list[RecordItem] = Field(default_factory=list)
    turns: list[RecordTurn] = Field(default_factory=list)
    quotes: list[RecordQuote] = Field(default_factory=list)
    # degraded-run counts the lens must surface (silent-failure review, §9.A)
    stats: dict[str, int] = Field(default_factory=dict)
