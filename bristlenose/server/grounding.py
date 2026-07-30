"""Shared grounding core for assistant surfaces over a project's corpus.

This module is the canonical seam named by ``docs/design-chat-lens.md`` §7:
both the in-app chat lens and the MCP-server workstream ground their answers
in the same corpus assembly, the same quote-id validation, and the same
model-facing invariants. Whichever workstream needs more generality extends
*this* module — do not grow a parallel sibling.

Public API::

    assemble_corpus_context(db, project_id, max_chars=…)  → CorpusContext
    resolve_quote_ids(quote_ids, corpus)                  → (resolved, rejected)
    INVARIANTS                                            — statements for the model

Anonymisation boundary: the corpus identifies humans by speaker code only
(``p1``, ``m1``…). This module never reads ``Person`` rows, so real names
cannot leak into a prompt by construction.

Curation layer: hidden quotes are excluded (the researcher curated them
out), starred quotes are marked, and researcher-edited text replaces the
pipeline text — the corpus is the researcher's report, not the raw pile.

Note: ``routes/data.py`` carries an older private DOM-id resolver that
predates this module (it maps ids to ORM rows for state writes). This
module's validation is deliberately stricter: an id is valid only if it
was actually *in the assembled corpus* — a hidden or truncated-out quote
is not citable even though it exists in the DB.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session as SASession

#: Character budget for the assembled corpus (~30k tokens at 4 chars/token).
#: A real project is a few hundred curated quotes (~20k tokens), so the
#: default fits whole projects; oversized corpora truncate *visibly* (the
#: cut is stated in the corpus text and reported in CorpusContext).
DEFAULT_MAX_CHARS = 120_000

#: Model-facing statements of the data model's arithmetic. Shared vocabulary
#: with the MCP workstream (design-mcp-server.md §3/§3a) — state these to any
#: model reasoning over the corpus, on every surface.
INVARIANTS: tuple[str, ...] = (
    "Every quote appears in exactly one report section; do not sum counts "
    "across sections and themes and treat the total as the corpus size.",
    "A quote can carry tags from several codebook groups and counts once per "
    "group in tag analyses, so tag counts are only comparable within one "
    "analysis, never across analyses.",
    "Speakers are identified by code only (p1 = participant, m1 = moderator, "
    "o1 = observer). Never guess who a speaker is, and never join a speaker "
    "with any person outside this study's data.",
)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class CorpusQuote:
    """One quote as it appears in the assembled corpus."""

    dom_id: str
    participant_id: str
    session_id: str
    text: str
    sentiment: str
    tags: list[str] = field(default_factory=list)
    starred: bool = False
    where: str = ""
    start_timecode: float = 0.0


@dataclass
class CorpusContext:
    """A project's corpus formatted for an LLM prompt, plus its id universe."""

    text: str
    quotes_by_id: dict[str, CorpusQuote]
    quote_count: int
    total_quotes: int
    hidden_excluded: int
    truncated: bool
    char_count: int


# ---------------------------------------------------------------------------
# Corpus assembly
# ---------------------------------------------------------------------------


def quote_dom_id(participant_id: str, start_timecode: float) -> str:
    """Build the report's quote id (matches ``render/quote_format.py``)."""
    return f"q-{participant_id}-{int(start_timecode)}"


def _quote_line(cq: CorpusQuote) -> str:
    """One corpus line: id, speaker, metadata, then the quote text."""
    meta: list[str] = [cq.participant_id]
    if cq.sentiment:
        meta.append(cq.sentiment)
    if cq.tags:
        meta.append("tags: " + ", ".join(cq.tags))
    if cq.starred:
        meta.append("starred")
    return f'- [{cq.dom_id}] ({"; ".join(meta)}) "{cq.text}"'


def assemble_corpus_context(
    db: SASession,
    project_id: int,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> CorpusContext:
    """Assemble a project's quotes into a deterministic prompt corpus.

    Order mirrors the report: sections (screen clusters by display order,
    quotes by start timecode) then themes (by id, quotes by session +
    timecode). Uncategorised pinned quotes — rare orphans that lost their
    grouping — are not included. Truncation at ``max_chars`` is stated in
    the corpus text itself and reported on the returned context; nothing
    is dropped silently.
    """
    from bristlenose.server.models import (
        ClusterQuote,
        Project,
        Quote,
        QuoteEdit,
        QuoteState,
        QuoteTag,
        ScreenCluster,
        TagDefinition,
        ThemeGroup,
        ThemeQuote,
    )

    project = db.query(Project).filter_by(id=project_id).first()
    project_name = project.name if project else f"project {project_id}"

    all_quotes = db.query(Quote).filter_by(project_id=project_id).all()
    quote_by_pk: dict[int, Quote] = {q.id: q for q in all_quotes}
    quote_pks = list(quote_by_pk.keys())

    # Researcher state: starred / hidden, edited text, tag names.
    starred_pks: set[int] = set()
    hidden_pks: set[int] = set()
    if quote_pks:
        for state in db.query(QuoteState).filter(QuoteState.quote_id.in_(quote_pks)):
            if state.is_starred:
                starred_pks.add(state.quote_id)
            if state.is_hidden:
                hidden_pks.add(state.quote_id)

    edited_text: dict[int, str] = {}
    if quote_pks:
        edits = (
            db.query(QuoteEdit)
            .filter(QuoteEdit.quote_id.in_(quote_pks))
            .order_by(QuoteEdit.edited_at.asc(), QuoteEdit.id.asc())
            .all()
        )
        for edit in edits:  # ascending order: the latest edit wins
            edited_text[edit.quote_id] = edit.edited_text

    tags_by_pk: dict[int, list[str]] = {}
    if quote_pks:
        tag_rows = (
            db.query(QuoteTag.quote_id, TagDefinition.name)
            .join(TagDefinition, QuoteTag.tag_definition_id == TagDefinition.id)
            .filter(QuoteTag.quote_id.in_(quote_pks))
            .order_by(TagDefinition.name)
            .all()
        )
        for quote_pk, tag_name in tag_rows:
            tags_by_pk.setdefault(quote_pk, []).append(tag_name)

    def _corpus_quote(q: Quote, where: str) -> CorpusQuote:
        return CorpusQuote(
            dom_id=quote_dom_id(q.participant_id, q.start_timecode),
            participant_id=q.participant_id,
            session_id=q.session_id,
            text=edited_text.get(q.id, q.text),
            sentiment=q.sentiment or "",
            tags=tags_by_pk.get(q.id, []),
            starred=q.id in starred_pks,
            where=where,
            start_timecode=q.start_timecode,
        )

    # Grouping joins, mirroring routes/quotes.py.
    cluster_to_pks: dict[int, list[int]] = {}
    if quote_pks:
        for cq in db.query(ClusterQuote).filter(ClusterQuote.quote_id.in_(quote_pks)):
            cluster_to_pks.setdefault(cq.cluster_id, []).append(cq.quote_id)
    theme_to_pks: dict[int, list[int]] = {}
    if quote_pks:
        for tq in db.query(ThemeQuote).filter(ThemeQuote.quote_id.in_(quote_pks)):
            theme_to_pks.setdefault(tq.theme_id, []).append(tq.quote_id)

    # Build (heading, quotes) blocks in report order.
    blocks: list[tuple[str, str, list[CorpusQuote]]] = []  # (kind, heading, quotes)
    clusters = (
        db.query(ScreenCluster)
        .filter_by(project_id=project_id)
        .order_by(ScreenCluster.display_order)
        .all()
    )
    for cluster in clusters:
        members = [
            quote_by_pk[pk]
            for pk in cluster_to_pks.get(cluster.id, [])
            if pk in quote_by_pk and pk not in hidden_pks
        ]
        members.sort(key=lambda q: q.start_timecode)
        if members:
            blocks.append((
                "Section",
                cluster.screen_label,
                [_corpus_quote(q, cluster.screen_label) for q in members],
            ))

    themes = (
        db.query(ThemeGroup)
        .filter_by(project_id=project_id)
        .order_by(ThemeGroup.id)
        .all()
    )
    for theme in themes:
        members = [
            quote_by_pk[pk]
            for pk in theme_to_pks.get(theme.id, [])
            if pk in quote_by_pk and pk not in hidden_pks
        ]
        members.sort(key=lambda q: (q.session_id, q.start_timecode))
        if members:
            blocks.append((
                "Theme",
                theme.theme_label,
                [_corpus_quote(q, theme.theme_label) for q in members],
            ))

    # Speaker roster from codes only (anonymisation boundary).
    codes = sorted({q.participant_id for q in all_quotes if q.id not in hidden_pks})

    total_visible = len([q for q in all_quotes if q.id not in hidden_pks])

    # Render with a character budget. The cut is per whole quote line and is
    # announced in the corpus itself.
    lines: list[str] = [f"# Study: {project_name}", ""]
    if codes:
        lines.append("Speakers: " + ", ".join(codes))
        lines.append("")

    quotes_by_id: dict[str, CorpusQuote] = {}
    included = 0
    truncated = False
    char_count = sum(len(line) + 1 for line in lines)
    for kind, heading, members in blocks:
        if truncated:
            break
        header_line = f"## {kind}: {heading}"
        char_count += len(header_line) + 2
        lines.append(header_line)
        for cq in members:
            line = _quote_line(cq)
            if char_count + len(line) + 1 > max_chars:
                truncated = True
                break
            lines.append(line)
            char_count += len(line) + 1
            quotes_by_id[cq.dom_id] = cq
            included += 1
        lines.append("")

    if truncated:
        lines.append(
            f"[corpus truncated: {included} of {total_visible} quotes included]"
        )

    text = "\n".join(lines).strip() + "\n"
    return CorpusContext(
        text=text,
        quotes_by_id=quotes_by_id,
        quote_count=included,
        total_quotes=total_visible,
        hidden_excluded=len(hidden_pks),
        truncated=truncated,
        char_count=len(text),
    )


# ---------------------------------------------------------------------------
# Citation validation
# ---------------------------------------------------------------------------


def resolve_quote_ids(
    quote_ids: list[str],
    corpus: CorpusContext,
) -> tuple[list[CorpusQuote], list[str]]:
    """Split cited ids into (resolved corpus quotes, rejected id strings).

    The check is corpus membership, which is deliberately stricter than
    DB presence: a model can only honestly cite what was in the context
    it was shown. An invented id, a malformed id, an id from another
    project, or an id for a hidden/truncated-out quote all land in
    ``rejected`` — without this check the citations are theatre.

    Order is preserved; duplicate ids are dropped after their first
    appearance.
    """
    resolved: list[CorpusQuote] = []
    rejected: list[str] = []
    seen: set[str] = set()
    for raw_id in quote_ids:
        cited = str(raw_id).strip()
        if not cited or cited in seen:
            continue
        seen.add(cited)
        quote = corpus.quotes_by_id.get(cited)
        if quote is not None:
            resolved.append(quote)
        else:
            rejected.append(cited)
    return resolved, rejected
