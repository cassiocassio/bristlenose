"""Shared extraction layer for quote exports (CSV, XLSX, clips, future Miro).

Provides:
- ``ExportableQuote`` — flat dataclass with all 11 export columns.
- ``extract_quotes_for_export()`` — single query joining the full quote graph.
- ``pick_featured_quotes()`` — select top quotes for dashboard / clip extraction.
- ``csv_safe()`` — defence against CSV formula injection (CWE-1236).
- ``excel_sheet_name()`` — sanitise project name for Excel sheet tab.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from sqlalchemy.orm import Session as DbSession

from bristlenose.server.models import (
    ClusterQuote,
    Person,
    Quote,
    QuoteEdit,
    QuoteState,
    QuoteTag,
    ScreenCluster,
    SessionSpeaker,
    TagDefinition,
    ThemeGroup,
    ThemeQuote,
)
from bristlenose.server.models import (
    Session as SessionModel,
)
from bristlenose.server.routes.data import _parse_dom_quote_id

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

#: Characters that trigger formula interpretation in Excel / Google Sheets.
_FORMULA_TRIGGERS = frozenset("=+-@\t\r")

#: Characters illegal in Excel sheet names.
_EXCEL_SHEET_ILLEGAL = re.compile(r"[\[\]\*\?/\\]")


def csv_safe(value: str) -> str:
    """Prefix values that start with formula-trigger characters.

    Excel, LibreOffice, and Google Sheets interpret cells starting with
    ``=``, ``+``, ``-``, ``@``, tab, or carriage return as formulas.
    Prefixing with a tab character neutralises this without altering the
    visible text in most spreadsheet applications.
    """
    if value and value[0] in _FORMULA_TRIGGERS:
        return "\t" + value
    return value


def excel_sheet_name(name: str, max_length: int = 31) -> str:
    """Sanitise a project name for use as an Excel sheet tab name.

    Excel sheet names must not:
    - Contain ``[ ] * ? / \\``
    - Start or end with ``'``
    - Exceed 31 characters

    Returns ``"Quotes"`` if the input reduces to nothing.
    """
    result = _EXCEL_SHEET_ILLEGAL.sub("", name)
    result = result.strip("' ")
    if len(result) > max_length:
        result = result[:max_length].rstrip("' ")
    return result or "Quotes"


def _format_timecode(seconds: float) -> str:
    """Format seconds as ``m:ss`` or ``h:mm:ss``."""
    total = int(seconds)
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class ExportableQuote:
    """Flat representation of a quote with all 11 export columns."""

    text: str
    participant_code: str
    participant_name: str
    section: str
    theme: str
    sentiment: str
    tags: str
    starred: bool
    timecode: str
    session: str
    source_file: str


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


def extract_quotes_for_export(
    db: DbSession,
    project_id: int,
    quote_ids: list[str] | None = None,
    anonymise: bool = False,
) -> list[ExportableQuote]:
    """Extract quotes as flat export rows.

    Parameters
    ----------
    db:
        Open SQLAlchemy session (caller manages lifecycle).
    project_id:
        Project to export from.
    quote_ids:
        Optional list of DOM IDs (e.g. ``["q-p1-10", "q-p1-26"]``).
        When provided, only these quotes are exported (hidden status ignored).
        When ``None``, all non-hidden quotes are exported.
    anonymise:
        When ``True``, ``participant_name`` is set to ``""``.

    Returns
    -------
    list[ExportableQuote]
        Ordered by section display_order, then start_timecode.
    """
    # ── Resolve quote rows ─────────────────────────────────────────────
    if quote_ids is not None:
        quotes = _resolve_quote_ids(db, project_id, quote_ids)
    else:
        quotes = _load_all_visible(db, project_id)

    if not quotes:
        return []

    quote_db_ids = [q.id for q in quotes]

    # ── Bulk-load related data ─────────────────────────────────────────
    edits_map = _load_edits(db, quote_db_ids)
    state_map = _load_states(db, quote_db_ids)
    section_map = _load_sections(db, quote_db_ids)
    theme_map = _load_themes(db, quote_db_ids)
    tags_map = _load_tags(db, quote_db_ids)
    speaker_map = _load_speakers(db, project_id)

    # ── Build section ordering ─────────────────────────────────────────
    section_order = _load_section_order(db, project_id)

    # ── Assemble rows ──────────────────────────────────────────────────
    results: list[ExportableQuote] = []
    for q in quotes:
        text = edits_map.get(q.id, q.text)
        state = state_map.get(q.id)
        starred = state.is_starred if state else False

        section = section_map.get(q.id, "")
        themes = theme_map.get(q.id, [])
        theme_str = " / ".join(themes)

        tag_names = tags_map.get(q.id, [])
        tags_str = "; ".join(tag_names)

        speaker_info = speaker_map.get((q.session_id, q.participant_id))
        participant_name = ""
        source_file = ""
        if speaker_info:
            participant_name = "" if anonymise else speaker_info[0]
            source_file = os.path.basename(speaker_info[1]) if speaker_info[1] else ""

        results.append(
            ExportableQuote(
                text=text,
                participant_code=q.participant_id,
                participant_name=participant_name,
                section=section,
                theme=theme_str,
                sentiment=q.sentiment or "",
                tags=tags_str,
                starred=starred,
                timecode=_format_timecode(q.start_timecode),
                session=q.session_id,
                source_file=source_file,
            )
        )

    # ── Sort by section display order, then timecode ───────────────────
    results.sort(key=lambda eq: (section_order.get(eq.section, 999), eq.timecode))

    return results


# ---------------------------------------------------------------------------
# Internal loaders
# ---------------------------------------------------------------------------


def _resolve_quote_ids(
    db: DbSession, project_id: int, dom_ids: list[str]
) -> list[Quote]:
    """Resolve DOM IDs to Quote rows (order preserved)."""
    quotes: list[Quote] = []
    for dom_id in dom_ids:
        try:
            participant_id, timecode = _parse_dom_quote_id(dom_id)
        except ValueError:
            continue
        q = (
            db.query(Quote)
            .filter(
                Quote.project_id == project_id,
                Quote.participant_id == participant_id,
                Quote.start_timecode >= timecode,
                Quote.start_timecode < timecode + 1,
            )
            .first()
        )
        if q:
            quotes.append(q)
    return quotes


def _load_all_visible(db: DbSession, project_id: int) -> list[Quote]:
    """Load all non-hidden quotes for a project."""
    return (
        db.query(Quote)
        .outerjoin(QuoteState, QuoteState.quote_id == Quote.id)
        .filter(
            Quote.project_id == project_id,
            (QuoteState.is_hidden == False) | (QuoteState.id == None),  # noqa: E711, E712
        )
        .all()
    )


def _load_edits(db: DbSession, quote_ids: list[int]) -> dict[int, str]:
    """Map quote_id → latest edited_text."""
    rows = (
        db.query(QuoteEdit.quote_id, QuoteEdit.edited_text)
        .filter(QuoteEdit.quote_id.in_(quote_ids))
        .order_by(QuoteEdit.edited_at.desc())
        .all()
    )
    # First row per quote_id wins (latest edit)
    result: dict[int, str] = {}
    for qid, text in rows:
        if qid not in result:
            result[qid] = text
    return result


def _load_states(db: DbSession, quote_ids: list[int]) -> dict[int, QuoteState]:
    """Map quote_id → QuoteState."""
    rows = (
        db.query(QuoteState)
        .filter(QuoteState.quote_id.in_(quote_ids))
        .all()
    )
    return {s.quote_id: s for s in rows}


def _load_sections(db: DbSession, quote_ids: list[int]) -> dict[int, str]:
    """Map quote_id → section label (ScreenCluster.screen_label)."""
    rows = (
        db.query(ClusterQuote.quote_id, ScreenCluster.screen_label)
        .join(ScreenCluster, ScreenCluster.id == ClusterQuote.cluster_id)
        .filter(ClusterQuote.quote_id.in_(quote_ids))
        .all()
    )
    return {qid: label for qid, label in rows}


def _load_themes(db: DbSession, quote_ids: list[int]) -> dict[int, list[str]]:
    """Map quote_id → list of theme labels."""
    rows = (
        db.query(ThemeQuote.quote_id, ThemeGroup.theme_label)
        .join(ThemeGroup, ThemeGroup.id == ThemeQuote.theme_id)
        .filter(ThemeQuote.quote_id.in_(quote_ids))
        .all()
    )
    result: dict[int, list[str]] = {}
    for qid, label in rows:
        result.setdefault(qid, []).append(label)
    return result


def _load_tags(db: DbSession, quote_ids: list[int]) -> dict[int, list[str]]:
    """Map quote_id → list of tag names."""
    rows = (
        db.query(QuoteTag.quote_id, TagDefinition.name)
        .join(TagDefinition, TagDefinition.id == QuoteTag.tag_definition_id)
        .filter(QuoteTag.quote_id.in_(quote_ids))
        .order_by(TagDefinition.name)
        .all()
    )
    result: dict[int, list[str]] = {}
    for qid, name in rows:
        result.setdefault(qid, []).append(name)
    return result


def _load_speakers(
    db: DbSession, project_id: int
) -> dict[tuple[str, str], tuple[str, str]]:
    """Map (session_id, speaker_code) → (full_name, source_file).

    Joins Session → SessionSpeaker → Person.  Scoped to project.
    """
    rows = (
        db.query(
            SessionModel.session_id,
            SessionSpeaker.speaker_code,
            Person.full_name,
            SessionSpeaker.source_file,
        )
        .join(SessionSpeaker, SessionSpeaker.session_id == SessionModel.id)
        .join(Person, Person.id == SessionSpeaker.person_id)
        .filter(SessionModel.project_id == project_id)
        .all()
    )
    return {(sid, code): (name, sf) for sid, code, name, sf in rows}


def _load_section_order(db: DbSession, project_id: int) -> dict[str, int]:
    """Map section label → display_order for sorting."""
    rows = (
        db.query(ScreenCluster.screen_label, ScreenCluster.display_order)
        .filter(ScreenCluster.project_id == project_id)
        .all()
    )
    return {label: order for label, order in rows}


# ---------------------------------------------------------------------------
# Featured quote selection (shared by dashboard + clip export)
# ---------------------------------------------------------------------------

_NEGATIVE_SENTIMENTS = {"frustration", "confusion", "doubt"}
_POSITIVE_SENTIMENTS = {"satisfaction", "confidence", "delight"}


def pick_featured_quotes(
    all_quotes: list[Quote],
    n: int = 9,
) -> list[Quote]:
    """Select the most interesting quotes for the dashboard or clip export.

    Word-count filter → score → diversify by participant and polarity.
    """
    if not all_quotes:
        return []

    # Filter: prefer quotes between 12–33 words.
    preferred = [q for q in all_quotes if 12 <= len(q.text.split()) <= 33]
    if len(preferred) >= n:
        candidates = preferred
    else:
        longer = [
            q for q in all_quotes
            if len(q.text.split()) >= 12 and q not in preferred
        ]
        candidates = preferred + longer
    if not candidates:
        candidates = list(all_quotes)

    def _score(q: Quote) -> float:
        s = 0.0
        s += min(q.intensity, 3)
        if q.sentiment in _NEGATIVE_SENTIMENTS:
            s += 2
        elif q.sentiment == "surprise":
            s += 2
        elif q.sentiment == "delight":
            s += 2
        elif q.sentiment in _POSITIVE_SENTIMENTS:
            s += 1
        if q.researcher_context:
            s += 1
        word_count = len(q.text.split())
        if word_count > 33:
            s -= min((word_count - 33) / 10, 2.0)
        return s

    scored = sorted(
        candidates,
        key=lambda q: (-_score(q), q.start_timecode),
    )

    picked: list[Quote] = []
    used_pids: set[str] = set()
    used_polarities: set[str] = set()

    def _polarity(q: Quote) -> str:
        if q.sentiment in _POSITIVE_SENTIMENTS:
            return "positive"
        if q.sentiment in _NEGATIVE_SENTIMENTS:
            return "negative"
        if q.sentiment == "surprise":
            return "surprise"
        return "neutral"

    # Pass 1: one per participant, different polarities.
    for q in scored:
        if len(picked) >= n:
            break
        pid = q.participant_id
        pol = _polarity(q)
        if pid not in used_pids and pol not in used_polarities:
            picked.append(q)
            used_pids.add(pid)
            used_polarities.add(pol)

    # Pass 2: relax polarity, still different participants.
    if len(picked) < n:
        for q in scored:
            if len(picked) >= n:
                break
            if q in picked:
                continue
            if q.participant_id not in used_pids:
                picked.append(q)
                used_pids.add(q.participant_id)

    # Pass 3: relax all constraints.
    if len(picked) < n:
        for q in scored:
            if len(picked) >= n:
                break
            if q not in picked:
                picked.append(q)

    return picked[:n]
