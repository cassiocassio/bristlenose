"""Dynamic codebook builder API — synthesise, edit, scan, and refine a tag's prompt.

The manual codebook lets a researcher group tags. This router lets them grow a
tag into a *code*: from the quotes they coded by hand, infer an inclusion /
exclusion prompt; scan the rest of the corpus for more like it; review the
candidates with reasons; and fold those reasons back into the prompt. The
researcher can also edit the prompt directly and re-scan to see the candidate
set move.

Engine: ``bristlenose.server.codebook_builder``. Storage: ``TagPrompt`` (the
learned prompt, one per tag) and ``TagPromptDecision`` (each accept/reject with
its local-only reason).
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from bristlenose.config import load_settings
from bristlenose.server import codebook_builder as cb
from bristlenose.server.models import (
    Project,
    Quote,
    QuoteTag,
    TagDefinition,
    TagPrompt,
    TagPromptDecision,
)
from bristlenose.server.routes.data import _quote_dom_id, _resolve_quote

router = APIRouter(prefix="/api")


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class PromptOut(BaseModel):
    summary: str = ""
    definition: str = ""
    apply_when: str = ""
    not_this: str = ""
    version: str = ""
    status: str = "draft"
    example_count: int = 0


class BuilderStateOut(BaseModel):
    tag_id: int
    tag_name: str
    coded_count: int
    ready_to_synthesize: bool
    min_examples: int
    prompt: PromptOut | None = None


class CandidateOut(BaseModel):
    quote_id: str  # DOM id (q-{participant}-{timecode})
    text: str
    confidence: float
    rationale: str


class CandidateScanOut(BaseModel):
    candidates: list[CandidateOut]
    scanned: int
    errors: int


class CandidatesRequest(BaseModel):
    min_confidence: float = 0.5
    limit: int = 50


class EditPromptRequest(BaseModel):
    summary: str | None = None
    definition: str | None = None
    apply_when: str | None = None
    not_this: str | None = None
    status: str | None = None  # "draft" | "active"


class DecisionIn(BaseModel):
    quote_id: str  # DOM id
    decision: str  # "accept" | "reject"
    reason: str = ""


class DecisionsRequest(BaseModel):
    decisions: list[DecisionIn]
    refine: bool = True


class DecisionsResponse(BaseModel):
    accepted: int
    rejected: int
    applied_tags: int
    prompt: PromptOut | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_db(request: Request) -> Session:
    return request.app.state.db_factory()


def _check_project(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _get_tag(db: Session, tag_id: int) -> TagDefinition:
    td = db.get(TagDefinition, tag_id)
    if not td:
        raise HTTPException(status_code=404, detail="Tag not found")
    return td


def _prompt_out(row: TagPrompt | None) -> PromptOut | None:
    if row is None:
        return None
    return PromptOut(
        summary=row.summary,
        definition=row.definition,
        apply_when=row.apply_when,
        not_this=row.not_this,
        version=row.version,
        status=row.status,
        example_count=row.example_count,
    )


def _draft_from_row(row: TagPrompt | None) -> cb.PromptDraft | None:
    if row is None:
        return None
    return cb.PromptDraft(
        summary=row.summary,
        definition=row.definition,
        apply_when=row.apply_when,
        not_this=row.not_this,
    )


def _coded_quotes(db: Session, project_id: int, tag_id: int) -> list[Quote]:
    """Quotes in this project that already carry the tag — the exemplars."""
    return (
        db.query(Quote)
        .join(QuoteTag, QuoteTag.quote_id == Quote.id)
        .filter(Quote.project_id == project_id, QuoteTag.tag_definition_id == tag_id)
        .all()
    )


def _example(q: Quote) -> cb.ExampleQuote:
    return cb.ExampleQuote(
        text=q.text,
        session_id=q.session_id,
        participant_id=q.participant_id,
        topic_label=q.topic_label or "",
        sentiment=q.sentiment or "",
    )


def _upsert_prompt(db: Session, tag_id: int, draft: cb.PromptDraft,
                   example_count: int) -> TagPrompt:
    """Create or update the TagPrompt row for a tag from a fresh draft."""
    row = db.query(TagPrompt).filter_by(tag_definition_id=tag_id).first()
    if row is None:
        row = TagPrompt(tag_definition_id=tag_id)
        db.add(row)
    row.summary = draft.summary
    row.definition = draft.definition
    row.apply_when = draft.apply_when
    row.not_this = draft.not_this
    row.version = draft.version
    row.example_count = example_count
    return row


def _load_settings_for(request: Request) -> object:
    """Load LLM settings, honouring a test override on app.state."""
    override = getattr(request.app.state, "settings", None)
    if override is not None:
        return override
    return load_settings()


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@router.get("/projects/{project_id}/codebook/tags/{tag_id}/builder")
def get_builder_state(
    project_id: int, tag_id: int, request: Request,
) -> BuilderStateOut:
    """Return the builder state for a tag: prompt, coded count, readiness."""
    db = _get_db(request)
    try:
        _check_project(db, project_id)
        td = _get_tag(db, tag_id)
        coded = len(_coded_quotes(db, project_id, tag_id))
        row = db.query(TagPrompt).filter_by(tag_definition_id=tag_id).first()
        return BuilderStateOut(
            tag_id=td.id,
            tag_name=td.name,
            coded_count=coded,
            ready_to_synthesize=coded >= cb.MIN_EXAMPLES_FOR_SYNTHESIS,
            min_examples=cb.MIN_EXAMPLES_FOR_SYNTHESIS,
            prompt=_prompt_out(row),
        )
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Synthesize — infer the prompt from coded exemplars
# ---------------------------------------------------------------------------


@router.post("/projects/{project_id}/codebook/tags/{tag_id}/builder/synthesize")
async def synthesize(
    project_id: int, tag_id: int, request: Request,
) -> PromptOut:
    """Infer an inclusion/exclusion prompt from the tag's hand-coded quotes."""
    db = _get_db(request)
    try:
        _check_project(db, project_id)
        td = _get_tag(db, tag_id)
        coded = _coded_quotes(db, project_id, tag_id)
        if len(coded) < cb.MIN_EXAMPLES_FOR_SYNTHESIS:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Need at least {cb.MIN_EXAMPLES_FOR_SYNTHESIS} coded quotes "
                    f"to synthesize a prompt (have {len(coded)})"
                ),
            )
        examples = [_example(q) for q in coded]
        tag_name = td.name
        n = len(examples)
    finally:
        db.close()

    settings = _load_settings_for(request)
    draft = await cb.synthesize_prompt(tag_name, examples, settings)  # type: ignore[arg-type]

    db = _get_db(request)
    try:
        row = _upsert_prompt(db, tag_id, draft, example_count=n)
        db.commit()
        return _prompt_out(row)  # type: ignore[return-value]
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Edit the prompt directly
# ---------------------------------------------------------------------------


@router.put("/projects/{project_id}/codebook/tags/{tag_id}/builder/prompt")
def edit_prompt(
    project_id: int, tag_id: int, request: Request, body: EditPromptRequest,
) -> PromptOut:
    """Apply a researcher's direct edits to the prompt; recompute the version."""
    db = _get_db(request)
    try:
        _check_project(db, project_id)
        _get_tag(db, tag_id)
        row = db.query(TagPrompt).filter_by(tag_definition_id=tag_id).first()
        if row is None:
            # default="" is applied at INSERT, not attribute access — set the
            # text fields explicitly so prompt_version() never sees None.
            row = TagPrompt(
                tag_definition_id=tag_id,
                summary="", definition="", apply_when="", not_this="",
            )
            db.add(row)
        if body.summary is not None:
            row.summary = body.summary
        if body.definition is not None:
            row.definition = body.definition
        if body.apply_when is not None:
            row.apply_when = body.apply_when
        if body.not_this is not None:
            row.not_this = body.not_this
        if body.status is not None:
            if body.status not in ("draft", "active"):
                raise HTTPException(status_code=400, detail="status must be draft or active")
            row.status = body.status
        row.version = cb.prompt_version(row.definition, row.apply_when, row.not_this)
        db.commit()
        return _prompt_out(row)  # type: ignore[return-value]
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Find candidates — scan uncoded quotes against the current prompt
# ---------------------------------------------------------------------------


@router.post("/projects/{project_id}/codebook/tags/{tag_id}/builder/candidates")
async def find_candidates(
    project_id: int, tag_id: int, request: Request, body: CandidatesRequest,
) -> CandidateScanOut:
    """Scan quotes that don't yet carry the tag and rank those that fit its prompt."""
    db = _get_db(request)
    try:
        _check_project(db, project_id)
        td = _get_tag(db, tag_id)
        tag_name = td.name
        row = db.query(TagPrompt).filter_by(tag_definition_id=tag_id).first()
        if row is None or not (row.definition or row.apply_when):
            raise HTTPException(
                status_code=400,
                detail="No prompt yet — synthesize or edit a prompt before scanning",
            )
        draft = _draft_from_row(row)
        # Pool: quotes in this project NOT already carrying this tag.
        coded_ids = {
            r[0]
            for r in db.query(QuoteTag.quote_id)
            .filter_by(tag_definition_id=tag_id)
            .all()
        }
        pool = [
            cb.CandidateQuote(
                db_id=q.id,
                text=q.text,
                session_id=q.session_id,
                participant_id=q.participant_id,
                topic_label=q.topic_label or "",
                sentiment=q.sentiment or "",
            )
            for q in db.query(Quote).filter_by(project_id=project_id).all()
            if q.id not in coded_ids
        ]
        # Map db_id -> DOM id for the response.
        dom_by_id = {
            q.id: _quote_dom_id(q)
            for q in db.query(Quote).filter_by(project_id=project_id).all()
        }
    finally:
        db.close()

    settings = _load_settings_for(request)
    scan = await cb.find_candidates(
        tag_name, draft, pool, settings,  # type: ignore[arg-type]
        min_confidence=body.min_confidence,
    )
    out = [
        CandidateOut(
            quote_id=dom_by_id.get(c.db_id, ""),
            text=c.text,
            confidence=round(c.confidence, 3),
            rationale=c.rationale,
        )
        for c in scan.candidates[: max(0, body.limit)]
    ]
    return CandidateScanOut(candidates=out, scanned=scan.scanned, errors=scan.errors)


# ---------------------------------------------------------------------------
# Decisions — record accept/reject with reasons, apply tags, refine
# ---------------------------------------------------------------------------


@router.post("/projects/{project_id}/codebook/tags/{tag_id}/builder/decisions")
async def submit_decisions(
    project_id: int, tag_id: int, request: Request, body: DecisionsRequest,
) -> DecisionsResponse:
    """Record review decisions, apply the tag to accepted quotes, then refine.

    Each accept also creates a ``QuoteTag`` (the tag is now on that quote, and
    becomes a future exemplar). Each decision is logged with its reason. When
    ``refine`` is set, the accept/reject reasons are folded back into the prompt
    via one LLM call and the sharper prompt is returned.
    """
    db = _get_db(request)
    accepted_fb: list[cb.DecisionFeedback] = []
    rejected_fb: list[cb.DecisionFeedback] = []
    applied = 0
    n_accept = 0
    n_reject = 0
    try:
        _check_project(db, project_id)
        td = _get_tag(db, tag_id)
        row = db.query(TagPrompt).filter_by(tag_definition_id=tag_id).first()
        version = row.version if row else ""
        now = datetime.now(timezone.utc)

        for d in body.decisions:
            if d.decision not in ("accept", "reject"):
                raise HTTPException(
                    status_code=400, detail=f"Bad decision: {d.decision!r}"
                )
            quote = _resolve_quote(db, project_id, d.quote_id)
            if quote is None:
                continue  # skip unresolved quotes rather than failing the batch
            db.add(
                TagPromptDecision(
                    tag_definition_id=tag_id,
                    quote_id=quote.id,
                    decision=d.decision,
                    reason=d.reason,
                    prompt_version=version,
                    created_at=now,
                )
            )
            if d.decision == "accept":
                n_accept += 1
                accepted_fb.append(cb.DecisionFeedback(text=quote.text, reason=d.reason))
                existing = (
                    db.query(QuoteTag)
                    .filter_by(quote_id=quote.id, tag_definition_id=tag_id)
                    .first()
                )
                if existing is None:
                    db.add(
                        QuoteTag(
                            quote_id=quote.id,
                            tag_definition_id=tag_id,
                            source="codebook-builder",
                        )
                    )
                    applied += 1
            else:
                n_reject += 1
                rejected_fb.append(cb.DecisionFeedback(text=quote.text, reason=d.reason))

        db.commit()

        if not body.refine or row is None:
            return DecisionsResponse(
                accepted=n_accept, rejected=n_reject, applied_tags=applied,
                prompt=_prompt_out(row),
            )

        # Gather exemplars + current draft for the refine call.
        coded = _coded_quotes(db, project_id, tag_id)
        examples = [_example(q) for q in coded]
        current = _draft_from_row(row)
        tag_name = td.name
        n_examples = len(examples)
    finally:
        db.close()

    settings = _load_settings_for(request)
    draft = await cb.synthesize_prompt(
        tag_name, examples, settings,  # type: ignore[arg-type]
        current=current, accepted=accepted_fb, rejected=rejected_fb,
    )

    db = _get_db(request)
    try:
        new_row = _upsert_prompt(db, tag_id, draft, example_count=n_examples)
        db.commit()
        return DecisionsResponse(
            accepted=n_accept, rejected=n_reject, applied_tags=applied,
            prompt=_prompt_out(new_row),
        )
    finally:
        db.close()
