"""Data API endpoints — researcher state (edits, tags, hidden, starred, etc.).

These endpoints mirror the localStorage keys used by the vanilla JS modules.
Each GET returns the full state map; each PUT replaces it.  The JS modules
call PUT after every localStorage write (fire-and-forget background sync).
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from bristlenose.server.models import (
    _LEGACY_UNGROUPED_NAME,
    UNCATEGORISED_GROUP_NAME,
    UNCATEGORISED_GROUP_SUBTITLE,
    CodebookGroup,
    DeletedBadge,
    HeadingEdit,
    Person,
    Project,
    Quote,
    QuoteEdit,
    QuoteState,
    QuoteTag,
    SessionSpeaker,
    TagDefinition,
)
from bristlenose.server.models import Session as SessionModel

router = APIRouter(prefix="/api")


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class PersonData(BaseModel):
    full_name: str = ""
    short_name: str = ""
    role: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_db(request: Request) -> Session:
    """Get the database session from app state."""
    return request.app.state.db_factory()


def _check_project(db: Session, project_id: int) -> Project:
    """Return the project or raise 404."""
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _parse_dom_quote_id(dom_id: str) -> tuple[str, int]:
    """Parse a DOM quote ID like 'q-p1-123' into (participant_id, timecode_int).

    Format: ``q-{participant_id}-{int(start_timecode)}``.
    participant_id is always a simple code like p1, m1, o1 (no dashes).
    """
    if not dom_id.startswith("q-"):
        raise ValueError(f"Invalid quote DOM ID: {dom_id}")
    rest = dom_id[2:]  # strip "q-"
    last_dash = rest.rfind("-")
    if last_dash < 0:
        raise ValueError(f"Invalid quote DOM ID: {dom_id}")
    participant_id = rest[:last_dash]
    try:
        timecode = int(rest[last_dash + 1 :])
    except ValueError:
        raise ValueError(f"Invalid timecode in DOM ID: {dom_id}") from None
    return participant_id, timecode


def _resolve_quote(db: Session, project_id: int, dom_id: str) -> Quote | None:
    """Resolve a DOM quote ID to a Quote row.

    The timecode in the DOM ID is ``int(start_timecode)``.  We match any
    quote whose ``start_timecode`` rounds down to that integer.
    """
    try:
        participant_id, timecode = _parse_dom_quote_id(dom_id)
    except ValueError:
        return None
    return (
        db.query(Quote)
        .filter(
            Quote.project_id == project_id,
            Quote.participant_id == participant_id,
            Quote.start_timecode >= timecode,
            Quote.start_timecode < timecode + 1,
        )
        .first()
    )


def _quote_dom_id(quote: Quote) -> str:
    """Build the DOM ID for a quote (matches render_html.py format)."""
    return f"q-{quote.participant_id}-{int(quote.start_timecode)}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _session_ids_for_project(db: Session, project_id: int) -> list[int]:
    """Return DB session IDs (not session_id strings) for a project."""
    return [
        s.id
        for s in db.query(SessionModel).filter_by(project_id=project_id).all()
    ]


def _quote_ids_for_project(db: Session, project_id: int) -> list[int]:
    """Return DB quote primary keys for a project."""
    return [q.id for q in db.query(Quote).filter_by(project_id=project_id).all()]


def _get_or_create_uncategorised(db: Session) -> CodebookGroup:
    """Return the default 'Uncategorised' codebook group, creating if needed.

    Also migrates the legacy 'Ungrouped' name from older databases.
    User-defined tags that don't belong to a codebook group are assigned here.
    """
    group = db.query(CodebookGroup).filter_by(name=UNCATEGORISED_GROUP_NAME).first()
    if group:
        return group
    # Migrate legacy "Ungrouped" → "Uncategorised"
    legacy = db.query(CodebookGroup).filter_by(name=_LEGACY_UNGROUPED_NAME).first()
    if legacy:
        legacy.name = UNCATEGORISED_GROUP_NAME
        legacy.subtitle = UNCATEGORISED_GROUP_SUBTITLE
        db.flush()
        return legacy
    group = CodebookGroup(
        name=UNCATEGORISED_GROUP_NAME,
        subtitle=UNCATEGORISED_GROUP_SUBTITLE,
        colour_set="",
    )
    db.add(group)
    db.flush()
    return group


def _write_through_people_yaml(
    output_dir_str: str,
    edits: dict[str, PersonData],
) -> None:
    """Write name edits back to ``people.yaml`` (best-effort).

    Loads the existing file, updates only the editable fields that were
    changed, and writes atomically (temp file + rename).  If the file
    doesn't exist or the write fails, logs a warning but doesn't raise —
    the DB write already succeeded, so the UI update is not lost.
    """
    import logging
    import tempfile
    from pathlib import Path

    import yaml

    logger = logging.getLogger(__name__)
    output_dir = Path(output_dir_str)
    people_path = output_dir / "people.yaml"
    if not people_path.exists():
        return

    try:
        raw = yaml.safe_load(people_path.read_text(encoding="utf-8"))
        if not raw or "participants" not in raw:
            return

        changed = False
        for speaker_code, person_data in edits.items():
            entry = raw["participants"].get(speaker_code)
            if not entry:
                continue
            ed = entry.setdefault("editable", {})
            if (
                ed.get("full_name", "") != person_data.full_name
                or ed.get("short_name", "") != person_data.short_name
                or ed.get("role", "") != person_data.role
            ):
                ed["full_name"] = person_data.full_name
                ed["short_name"] = person_data.short_name
                ed["role"] = person_data.role
                changed = True

        if not changed:
            return

        # Preserve the header comment from the original file.
        original_text = people_path.read_text(encoding="utf-8")
        header_lines: list[str] = []
        for line in original_text.splitlines(keepends=True):
            if line.startswith("#") or line.strip() == "":
                header_lines.append(line)
            else:
                break
        header = "".join(header_lines)

        yaml_content = yaml.dump(
            raw,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )

        # Atomic write: temp file + rename.
        fd, tmp_path = tempfile.mkstemp(
            dir=str(output_dir), prefix=".people-", suffix=".yaml",
        )
        try:
            with open(fd, "w", encoding="utf-8") as f:
                f.write(header + yaml_content)
            Path(tmp_path).replace(people_path)
        except Exception:
            Path(tmp_path).unlink(missing_ok=True)
            raise
    except Exception:
        logger.warning("Could not write-through to people.yaml", exc_info=True)


# ---------------------------------------------------------------------------
# People (names.js)
# ---------------------------------------------------------------------------


@router.get("/projects/{project_id}/people")
def get_people(
    project_id: int,
    request: Request,
) -> dict[str, dict[str, str]]:
    """Read people data for the project (speaker_code -> name/role)."""
    db = _get_db(request)
    try:
        _check_project(db, project_id)
        session_ids = _session_ids_for_project(db, project_id)
        speakers = (
            db.query(SessionSpeaker)
            .filter(SessionSpeaker.session_id.in_(session_ids))
            .all()
        )
        result: dict[str, dict[str, str]] = {}
        for sp in speakers:
            person = db.get(Person, sp.person_id)
            result[sp.speaker_code] = {
                "full_name": person.full_name if person else "",
                "short_name": person.short_name if person else "",
                "role": person.role_title if person else "",
            }
        return result
    finally:
        db.close()


@router.put("/projects/{project_id}/people")
def put_people(
    project_id: int,
    request: Request,
    data: dict[str, PersonData],
) -> dict[str, str]:
    """Write people edits (speaker_code -> name/role).

    Updates both the DB (immediate, for UI responsiveness) and
    ``people.yaml`` (write-through, so pipeline re-runs see edits).
    """
    db = _get_db(request)
    try:
        project = _check_project(db, project_id)
        session_ids = _session_ids_for_project(db, project_id)
        for speaker_code, person_data in data.items():
            sp = (
                db.query(SessionSpeaker)
                .filter(
                    SessionSpeaker.session_id.in_(session_ids),
                    SessionSpeaker.speaker_code == speaker_code,
                )
                .first()
            )
            if not sp:
                continue
            person = db.get(Person, sp.person_id)
            if not person:
                continue
            person.full_name = person_data.full_name
            person.short_name = person_data.short_name
            person.role_title = person_data.role
        db.commit()

        # Write-through: update people.yaml so pipeline re-runs see edits.
        _write_through_people_yaml(project.output_dir, data)

        return {"status": "ok"}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Edits (editing.js — quote text + heading text)
# ---------------------------------------------------------------------------


@router.get("/projects/{project_id}/edits")
def get_edits(
    project_id: int,
    request: Request,
) -> dict[str, str]:
    """Read all edits — quote text and heading text."""
    db = _get_db(request)
    try:
        _check_project(db, project_id)

        result: dict[str, str] = {}

        # Quote edits: resolve DB quote IDs back to DOM IDs
        quotes = db.query(Quote).filter_by(project_id=project_id).all()
        quote_by_id = {q.id: q for q in quotes}
        for qe in db.query(QuoteEdit).filter(
            QuoteEdit.quote_id.in_(quote_by_id)
        ).all():
            quote = quote_by_id.get(qe.quote_id)
            if quote:
                result[_quote_dom_id(quote)] = qe.edited_text

        # Heading edits
        for he in db.query(HeadingEdit).filter_by(project_id=project_id).all():
            result[he.heading_key] = he.edited_text

        return result
    finally:
        db.close()


@router.put("/projects/{project_id}/edits")
def put_edits(
    project_id: int,
    request: Request,
    data: dict[str, str],
) -> dict[str, str]:
    """Write all edits — quote text and heading text.

    Keys starting with ``q-`` are quote edits; others are heading edits.
    """
    db = _get_db(request)
    try:
        _check_project(db, project_id)

        # Clear existing edits for this project, then re-insert from the map
        quote_ids = _quote_ids_for_project(db, project_id)
        if quote_ids:
            db.query(QuoteEdit).filter(QuoteEdit.quote_id.in_(quote_ids)).delete(
                synchronize_session=False
            )
        db.query(HeadingEdit).filter_by(project_id=project_id).delete(
            synchronize_session=False
        )

        for key, text in data.items():
            if key.startswith("q-"):
                quote = _resolve_quote(db, project_id, key)
                if not quote:
                    continue
                db.add(QuoteEdit(quote_id=quote.id, edited_text=text, edited_at=_now()))
            else:
                db.add(
                    HeadingEdit(
                        project_id=project_id,
                        heading_key=key,
                        edited_text=text,
                        edited_at=_now(),
                    )
                )
        db.commit()
        return {"status": "ok"}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tags (tags.js — user-defined tags)
# ---------------------------------------------------------------------------


@router.get("/projects/{project_id}/tags")
def get_tags(
    project_id: int,
    request: Request,
) -> dict[str, list[str]]:
    """Read user-defined tags: {quote-dom-id: ["tag1", ...]}."""
    db = _get_db(request)
    try:
        _check_project(db, project_id)

        quotes = db.query(Quote).filter_by(project_id=project_id).all()
        quote_by_id = {q.id: q for q in quotes}

        result: dict[str, list[str]] = {}
        for qt in db.query(QuoteTag).filter(QuoteTag.quote_id.in_(quote_by_id)).all():
            quote = quote_by_id.get(qt.quote_id)
            tag_def = db.get(TagDefinition, qt.tag_definition_id)
            if quote and tag_def:
                dom_id = _quote_dom_id(quote)
                if dom_id not in result:
                    result[dom_id] = []
                result[dom_id].append(tag_def.name)

        return result
    finally:
        db.close()


@router.put("/projects/{project_id}/tags")
def put_tags(
    project_id: int,
    request: Request,
    data: dict[str, list[str]],
) -> dict[str, str]:
    """Write user-defined tags: {quote-dom-id: ["tag1", ...]}."""
    db = _get_db(request)
    try:
        _check_project(db, project_id)

        # Cache tag definitions by lowercased name -> id
        tag_defs: dict[str, int] = {}
        for td in db.query(TagDefinition).all():
            tag_defs[td.name.lower()] = td.id

        # Clear existing user tags for this project's quotes, then re-insert
        quote_ids = _quote_ids_for_project(db, project_id)
        if quote_ids:
            db.query(QuoteTag).filter(QuoteTag.quote_id.in_(quote_ids)).delete(
                synchronize_session=False
            )

        uncategorised: CodebookGroup | None = None

        for dom_id, tag_names in data.items():
            quote = _resolve_quote(db, project_id, dom_id)
            if not quote:
                continue
            seen_td_ids: set[int] = set()
            for tag_name in tag_names:
                td_id = tag_defs.get(tag_name.lower())
                if td_id is None:
                    if uncategorised is None:
                        uncategorised = _get_or_create_uncategorised(db)
                    td = TagDefinition(name=tag_name, codebook_group_id=uncategorised.id)
                    db.add(td)
                    db.flush()
                    td_id = td.id
                    tag_defs[tag_name.lower()] = td_id
                if td_id not in seen_td_ids:
                    seen_td_ids.add(td_id)
                    db.add(QuoteTag(quote_id=quote.id, tag_definition_id=td_id))

        db.commit()
        return {"status": "ok"}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Hidden (hidden.js)
# ---------------------------------------------------------------------------


@router.get("/projects/{project_id}/hidden")
def get_hidden(
    project_id: int,
    request: Request,
) -> dict[str, bool]:
    """Read hidden quote IDs: {quote-dom-id: true}."""
    db = _get_db(request)
    try:
        _check_project(db, project_id)

        quotes = db.query(Quote).filter_by(project_id=project_id).all()
        quote_by_id = {q.id: q for q in quotes}

        result: dict[str, bool] = {}
        for qs in db.query(QuoteState).filter(
            QuoteState.quote_id.in_(quote_by_id),
            QuoteState.is_hidden.is_(True),
        ).all():
            quote = quote_by_id.get(qs.quote_id)
            if quote:
                result[_quote_dom_id(quote)] = True

        return result
    finally:
        db.close()


@router.put("/projects/{project_id}/hidden")
def put_hidden(
    project_id: int,
    request: Request,
    data: dict[str, bool],
) -> dict[str, str]:
    """Write hidden quote state: {quote-dom-id: true}."""
    db = _get_db(request)
    try:
        _check_project(db, project_id)

        # Resolve which quotes should be hidden
        hidden_db_ids: set[int] = set()
        for dom_id, is_hidden in data.items():
            if not is_hidden:
                continue
            quote = _resolve_quote(db, project_id, dom_id)
            if quote:
                hidden_db_ids.add(quote.id)

        # Update or create QuoteState rows for all project quotes
        for qid in _quote_ids_for_project(db, project_id):
            qs = db.query(QuoteState).filter_by(quote_id=qid).first()
            should_hide = qid in hidden_db_ids
            if qs:
                qs.is_hidden = should_hide
                qs.hidden_at = _now() if should_hide else None
            elif should_hide:
                db.add(QuoteState(quote_id=qid, is_hidden=True, hidden_at=_now()))

        db.commit()
        return {"status": "ok"}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Starred (starred.js)
# ---------------------------------------------------------------------------


@router.get("/projects/{project_id}/starred")
def get_starred(
    project_id: int,
    request: Request,
) -> dict[str, bool]:
    """Read starred quote IDs: {quote-dom-id: true}."""
    db = _get_db(request)
    try:
        _check_project(db, project_id)

        quotes = db.query(Quote).filter_by(project_id=project_id).all()
        quote_by_id = {q.id: q for q in quotes}

        result: dict[str, bool] = {}
        for qs in db.query(QuoteState).filter(
            QuoteState.quote_id.in_(quote_by_id),
            QuoteState.is_starred.is_(True),
        ).all():
            quote = quote_by_id.get(qs.quote_id)
            if quote:
                result[_quote_dom_id(quote)] = True

        return result
    finally:
        db.close()


@router.put("/projects/{project_id}/starred")
def put_starred(
    project_id: int,
    request: Request,
    data: dict[str, bool],
) -> dict[str, str]:
    """Write starred quote state: {quote-dom-id: true}."""
    db = _get_db(request)
    try:
        _check_project(db, project_id)

        starred_db_ids: set[int] = set()
        for dom_id, is_starred in data.items():
            if not is_starred:
                continue
            quote = _resolve_quote(db, project_id, dom_id)
            if quote:
                starred_db_ids.add(quote.id)

        for qid in _quote_ids_for_project(db, project_id):
            qs = db.query(QuoteState).filter_by(quote_id=qid).first()
            should_star = qid in starred_db_ids
            if qs:
                qs.is_starred = should_star
                qs.starred_at = _now() if should_star else None
            elif should_star:
                db.add(QuoteState(quote_id=qid, is_starred=True, starred_at=_now()))

        db.commit()
        return {"status": "ok"}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Deleted badges (tags.js — AI badge deletions)
# ---------------------------------------------------------------------------


@router.get("/projects/{project_id}/deleted-badges")
def get_deleted_badges(
    project_id: int,
    request: Request,
) -> dict[str, list[str]]:
    """Read deleted AI badges: {quote-dom-id: ["sentiment", ...]}."""
    db = _get_db(request)
    try:
        _check_project(db, project_id)

        quotes = db.query(Quote).filter_by(project_id=project_id).all()
        quote_by_id = {q.id: q for q in quotes}

        result: dict[str, list[str]] = {}
        for badge in db.query(DeletedBadge).filter(
            DeletedBadge.quote_id.in_(quote_by_id),
        ).all():
            quote = quote_by_id.get(badge.quote_id)
            if quote:
                dom_id = _quote_dom_id(quote)
                if dom_id not in result:
                    result[dom_id] = []
                result[dom_id].append(badge.sentiment)

        return result
    finally:
        db.close()


@router.put("/projects/{project_id}/deleted-badges")
def put_deleted_badges(
    project_id: int,
    request: Request,
    data: dict[str, list[str]],
) -> dict[str, str]:
    """Write deleted AI badges: {quote-dom-id: ["sentiment", ...]}."""
    db = _get_db(request)
    try:
        _check_project(db, project_id)

        # Clear existing deleted badges for this project's quotes
        quote_ids = _quote_ids_for_project(db, project_id)
        if quote_ids:
            db.query(DeletedBadge).filter(
                DeletedBadge.quote_id.in_(quote_ids)
            ).delete(synchronize_session=False)

        for dom_id, sentiments in data.items():
            quote = _resolve_quote(db, project_id, dom_id)
            if not quote:
                continue
            seen_sentiments: set[str] = set()
            for sentiment in sentiments:
                if sentiment not in seen_sentiments:
                    seen_sentiments.add(sentiment)
                    db.add(
                        DeletedBadge(
                            quote_id=quote.id, sentiment=sentiment, deleted_at=_now()
                        )
                    )

        db.commit()
        return {"status": "ok"}
    finally:
        db.close()
