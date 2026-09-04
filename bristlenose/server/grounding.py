"""Shared grounding core for assistant surfaces over a project's corpus.

This module is the canonical seam named by ``docs/design-chat-lens.md`` §7:
both the in-app chat lens and the MCP-server workstream ground their answers
in the same corpus assembly, the same quote-id validation, and the same
model-facing invariants. Whichever workstream needs more generality extends
*this* module — do not grow a parallel sibling.

Public API::

    assemble_corpus_context(db, project_id, max_chars=…)  → CorpusContext
    resolve_quote_ids(quote_ids, corpus)                  → (resolved, rejected)
    load_signals(db, project_id, lens, top_n=…)           → SignalsResult
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

import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

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
    "Never compare raw counts across studies of different sizes; any "
    "cross-study comparison needs each study's denominators (participant "
    "and quote counts) stated alongside it.",
    "If the corpus does not answer a question, say so plainly instead of "
    "filling the gap from general knowledge — an uncited research claim "
    "presented next to real findings is worse than no claim.",
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
    """A project's corpus formatted for an LLM prompt, plus its id universe.

    ``quotes_by_index`` is the generator-facing citation space (§5a
    Correction 2): quotes carry server-constructed ``[1]``, ``[2]``…
    markers in the prompt, so the model cites integers and a fabricated
    citation degrades to an out-of-range int caught by arithmetic.
    ``quotes_by_id`` keys the same quotes by their report DOM id — the
    stable identifier every downstream surface (rendering, deep links,
    the MCP workstream) speaks.
    """

    text: str
    quotes_by_id: dict[str, CorpusQuote]
    quotes_by_index: dict[int, CorpusQuote]
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


def _quote_line(index: int, cq: CorpusQuote) -> str:
    """One corpus line: server-constructed citation index, speaker,
    metadata, then the quote text.

    The bracketed integer — not the DOM id — is the only citation token
    the model is given (§5a Correction 2, the LlamaIndex numbered-marker
    discipline). Ids stay server-side.
    """
    meta: list[str] = [cq.participant_id]
    if cq.sentiment:
        meta.append(cq.sentiment)
    if cq.tags:
        meta.append("tags: " + ", ".join(cq.tags))
    if cq.starred:
        meta.append("starred")
    return f'- [{index}] ({"; ".join(meta)}) "{cq.text}"'


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
    quotes_by_index: dict[int, CorpusQuote] = {}
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
            line = _quote_line(included + 1, cq)
            if char_count + len(line) + 1 > max_chars:
                truncated = True
                break
            lines.append(line)
            char_count += len(line) + 1
            quotes_by_id[cq.dom_id] = cq
            included += 1
            quotes_by_index[included] = cq
        lines.append("")

    if truncated:
        lines.append(
            f"[corpus truncated: {included} of {total_visible} quotes included]"
        )

    text = "\n".join(lines).strip() + "\n"
    return CorpusContext(
        text=text,
        quotes_by_id=quotes_by_id,
        quotes_by_index=quotes_by_index,
        quote_count=included,
        total_quotes=total_visible,
        hidden_excluded=len(hidden_pks),
        truncated=truncated,
        char_count=len(text),
    )


# ---------------------------------------------------------------------------
# Citation validation
# ---------------------------------------------------------------------------


def resolve_quote_indices(
    quote_indices: list[int],
    corpus: CorpusContext,
) -> tuple[list[CorpusQuote], list[int]]:
    """Split cited indices into (resolved corpus quotes, rejected ints).

    The generator-facing citation space is server-constructed (§5a
    Correction 2): the model only ever saw ``[1]``…``[n]`` markers, so a
    fabricated citation is an out-of-range integer and validation is
    arithmetic, not string matching. Anything not in
    ``corpus.quotes_by_index`` — zero, negative, past-the-end, or a
    non-integer that pydantic let through — lands in ``rejected``.

    Order is preserved; duplicate indices are dropped after their first
    appearance.
    """
    resolved: list[CorpusQuote] = []
    rejected: list[int] = []
    seen: set[int] = set()
    for raw in quote_indices:
        try:
            index = int(raw)
        except (TypeError, ValueError):
            continue
        if index in seen:
            continue
        seen.add(index)
        quote = corpus.quotes_by_index.get(index)
        if quote is not None:
            resolved.append(quote)
        else:
            rejected.append(index)
    return resolved, rejected


def resolve_quote_ids(
    quote_ids: list[str],
    corpus: CorpusContext,
) -> tuple[list[CorpusQuote], list[str]]:
    """Split cited ids into (resolved corpus quotes, rejected id strings).

    The stable-id sibling of ``resolve_quote_indices``, for surfaces that
    speak report DOM ids (the MCP workstream's tool responses resolve ids
    this way). The check is corpus membership, deliberately stricter than
    DB presence: a model can only honestly cite what was in the context
    it was shown. An invented id, a malformed id, an id from another
    project, or an id for a hidden/truncated-out quote all land in
    ``rejected`` — without this check the citations are theatre.

    Order is preserved; duplicate ids are dropped after their first
    appearance. Any surface that presents citations must surface the
    ``rejected`` count too — silently dropping refused citations makes the
    validation invisible exactly when it fired.
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


# ---------------------------------------------------------------------------
# Curated signal detection (the report view)
# ---------------------------------------------------------------------------

def _mcp_anonymise_active(project: object) -> bool:
    """Which Anonymise switch governs this process?

    ``BRISTLENOSE_MCP_ANONYMISE`` present → the desktop's GLOBAL switch
    (Settings ▸ MCP Agents, off by default) — it wins BOTH ways and the
    per-project DB flag is ignored entirely: v1 deliberately has one
    switch, not a per-project matrix (decided 1 Aug 2026; the per-project
    UI was retired as over-build). Absent (the CLI, tests) → the
    per-project ``projects.mcp_anonymise`` flag, unchanged.
    """
    override = os.environ.get("BRISTLENOSE_MCP_ANONYMISE")
    if override is not None:
        return override.strip().lower() in {"1", "true", "yes", "on"}
    return bool(getattr(project, "mcp_anonymise", False))


def resolve_speaker_names(db: SASession, project_id: int) -> dict[str, str]:
    """Speaker code → display name, honouring the Anonymise switch.

    Returns {} when anonymise is active (see ``_mcp_anonymise_active`` for
    which switch governs) — the ONLY gate through which assistant surfaces
    may reach the persons table. Display-name policy mirrors the
    quotes/sessions routes (short name, else full name). The desktop's
    global switch rides the serve env (applied on the prefs-changed
    restart, like every other Settings preference); the CLI/DB flag is
    read at call time as before.
    """
    from bristlenose.server.models import Person, Project, SessionSpeaker
    from bristlenose.server.models import Session as SessionModel

    project = db.get(Project, project_id)
    if project is None or _mcp_anonymise_active(project):
        return {}
    session_ids = [
        s.id for s in db.query(SessionModel).filter_by(project_id=project_id)
    ]
    if not session_ids:
        return {}
    names: dict[str, str] = {}
    rows = (
        db.query(SessionSpeaker, Person)
        .join(Person, SessionSpeaker.person_id == Person.id)
        .filter(SessionSpeaker.session_id.in_(session_ids))
    )
    for sp, person in rows:
        display = person.short_name or person.full_name or ""
        if display:
            names.setdefault(sp.speaker_code, display)
    return names


#: Lenses ``load_signals`` accepts.
SIGNAL_LENSES: tuple[str, ...] = ("sentiment", "tags")


@dataclass
class SignalsResult:
    """Signals computed over the curated corpus, plus their context."""

    signals: list[Any]  # list[bristlenose.analysis.models.Signal]
    total_participants: int
    group_colour_sets: dict[str, str]  # tags lens only; empty for sentiment


def load_signals(
    db: SASession,
    project_id: int,
    lens: str = "sentiment",
    top_n: int = 12,
) -> SignalsResult:
    """Signal detection over the CURATED corpus — the researcher's report view.

    Deliberately diverges from the analysis routes (which compute over the
    raw engine view): hidden quotes are excluded, researcher-edited text
    replaces pipeline text, and unreviewed AutoCode proposals contribute
    nothing (accepted tags — ``QuoteTag`` rows — are the only tag truth).
    The computation itself is the shipped ``bristlenose/analysis`` maths,
    not a parallel implementation.
    """
    from dataclasses import dataclass as _dc
    from dataclasses import field as _field

    from bristlenose.analysis.generic_matrix import (
        QuoteContribution,
        build_matrix_from_contributions,
    )
    from bristlenose.analysis.generic_signals import QuoteRecord, detect_signals_generic
    from bristlenose.analysis.matrix import build_section_matrix, build_theme_matrix
    from bristlenose.analysis.signals import detect_signals
    from bristlenose.models import Sentiment
    from bristlenose.server.models import (
        ClusterQuote,
        CodebookGroup,
        DeletedBadge,
        ProjectCodebookGroup,
        Quote,
        QuoteEdit,
        QuoteState,
        QuoteTag,
        ScreenCluster,
        TagDefinition,
        ThemeGroup,
        ThemeQuote,
    )

    if lens not in SIGNAL_LENSES:
        msg = f"unknown lens {lens!r} — valid lenses: {list(SIGNAL_LENSES)}"
        raise ValueError(msg)

    all_quotes = db.query(Quote).filter_by(project_id=project_id).all()
    if not all_quotes:
        return SignalsResult(signals=[], total_participants=0, group_colour_sets={})
    quote_pks = [q.id for q in all_quotes]

    hidden_pks: set[int] = {
        state.quote_id
        for state in db.query(QuoteState).filter(QuoteState.quote_id.in_(quote_pks))
        if state.is_hidden
    }
    edited_text: dict[int, str] = {}
    edits = (
        db.query(QuoteEdit)
        .filter(QuoteEdit.quote_id.in_(quote_pks))
        .order_by(QuoteEdit.edited_at.asc(), QuoteEdit.id.asc())
        .all()
    )
    for edit in edits:  # ascending order: the latest edit wins
        edited_text[edit.quote_id] = edit.edited_text

    # The researcher's removed sentiment badges are curation too — a
    # de-badged quote must not drive a sentiment cell (report view).
    deleted_badges: set[tuple[int, str]] = {
        (row.quote_id, row.sentiment)
        for row in db.query(DeletedBadge).filter(DeletedBadge.quote_id.in_(quote_pks))
    }

    visible = [q for q in all_quotes if q.id not in hidden_pks]
    if not visible:
        return SignalsResult(signals=[], total_participants=0, group_colour_sets={})
    visible_pks = {q.id for q in visible}
    total_participants = len({
        q.participant_id for q in visible if q.participant_id.startswith("p")
    })

    clusters = (
        db.query(ScreenCluster)
        .filter_by(project_id=project_id)
        .order_by(ScreenCluster.display_order)
        .all()
    )
    themes = (
        db.query(ThemeGroup)
        .filter_by(project_id=project_id)
        .order_by(ThemeGroup.id)
        .all()
    )
    cluster_members: dict[int, list[int]] = {}
    for cq in db.query(ClusterQuote).filter(ClusterQuote.quote_id.in_(visible_pks)):
        cluster_members.setdefault(cq.cluster_id, []).append(cq.quote_id)
    theme_members: dict[int, list[int]] = {}
    for tq in db.query(ThemeQuote).filter(ThemeQuote.quote_id.in_(visible_pks)):
        theme_members.setdefault(tq.theme_id, []).append(tq.quote_id)
    quote_by_pk = {q.id: q for q in visible}

    if lens == "sentiment":

        @_dc
        class _QuoteAdapter:
            text: str
            participant_id: str
            session_id: str
            start_timecode: float
            sentiment: Sentiment | None
            intensity: int
            segment_index: int

        @_dc
        class _ClusterAdapter:
            screen_label: str
            display_order: int
            quotes: list[Any] = _field(default_factory=list)

        @_dc
        class _ThemeAdapter:
            theme_label: str
            quotes: list[Any] = _field(default_factory=list)

        adapters: dict[int, object] = {}
        for q in visible:
            sent: Sentiment | None = None
            if q.sentiment and (q.id, q.sentiment) not in deleted_badges:
                try:
                    sent = Sentiment(q.sentiment)
                except ValueError:
                    pass
            adapters[q.id] = _QuoteAdapter(
                text=edited_text.get(q.id, q.text),
                participant_id=q.participant_id,
                session_id=q.session_id,
                start_timecode=q.start_timecode,
                sentiment=sent,
                intensity=q.intensity,
                segment_index=q.segment_index,
            )

        cluster_adapters = []
        for c in clusters:
            ca = _ClusterAdapter(screen_label=c.screen_label, display_order=c.display_order)
            ca.quotes = [adapters[pk] for pk in cluster_members.get(c.id, [])]
            cluster_adapters.append(ca)
        theme_adapters = []
        for t in themes:
            ta = _ThemeAdapter(theme_label=t.theme_label)
            ta.quotes = [adapters[pk] for pk in theme_members.get(t.id, [])]
            theme_adapters.append(ta)

        section_matrix = build_section_matrix(cluster_adapters)  # type: ignore[arg-type]
        theme_matrix = build_theme_matrix(theme_adapters)  # type: ignore[arg-type]
        result = detect_signals(
            section_matrix,
            theme_matrix,
            cluster_adapters,  # type: ignore[arg-type]
            theme_adapters,  # type: ignore[arg-type]
            total_participants,
            top_n=top_n,
        )
        return SignalsResult(
            signals=list(result.signals),
            total_participants=total_participants,
            group_colour_sets={},
        )

    # lens == "tags" — accepted tags only, over active codebook groups.
    pcg_rows = (
        db.query(ProjectCodebookGroup)
        .filter_by(project_id=project_id)
        .order_by(ProjectCodebookGroup.sort_order)
        .all()
    )
    from bristlenose.server.models import UNCATEGORISED_GROUP_NAME

    # Mirror the analysis route's group scope: the Uncategorised holding pen
    # (where ad-hoc tags land by default) is not an analytical column.
    groups = [
        g
        for g in (db.get(CodebookGroup, r.codebook_group_id) for r in pcg_rows)
        if g and g.name != UNCATEGORISED_GROUP_NAME
    ]
    if not groups:
        return SignalsResult(
            signals=[], total_participants=total_participants, group_colour_sets={},
        )
    group_id_to_name = {g.id: g.name for g in groups}
    colour_sets = {g.name: g.colour_set for g in groups}
    col_labels = [g.name for g in groups]

    tag_defs = (
        db.query(TagDefinition)
        .filter(TagDefinition.codebook_group_id.in_(group_id_to_name.keys()))
        .all()
    )
    tag_def_to_group = {td.id: group_id_to_name[td.codebook_group_id] for td in tag_defs}
    tag_def_to_name = {td.id: td.name for td in tag_defs}
    if not tag_def_to_group:
        return SignalsResult(
            signals=[], total_participants=total_participants, group_colour_sets={},
        )

    quote_section: dict[int, str] = {}
    for c in clusters:
        for pk in cluster_members.get(c.id, []):
            quote_section[pk] = c.screen_label
    quote_theme: dict[int, str] = {}
    for t in themes:
        for pk in theme_members.get(t.id, []):
            quote_theme[pk] = t.theme_label

    accepted = (
        db.query(QuoteTag)
        .filter(
            QuoteTag.tag_definition_id.in_(tag_def_to_group.keys()),
            QuoteTag.quote_id.in_(visible_pks),
        )
        .all()
    )
    quote_groups: dict[int, dict[str, list[str]]] = {}
    for qt in accepted:
        gname = tag_def_to_group.get(qt.tag_definition_id)
        tname = tag_def_to_name.get(qt.tag_definition_id, "")
        if gname is None:
            continue
        names = quote_groups.setdefault(qt.quote_id, {}).setdefault(gname, [])
        if tname and tname not in names:
            names.append(tname)
    if not quote_groups:
        return SignalsResult(
            signals=[], total_participants=total_participants, group_colour_sets={},
        )

    section_contributions: list[QuoteContribution] = []
    theme_contributions: list[QuoteContribution] = []
    section_lookup: dict[str, list[QuoteRecord]] = {}
    theme_lookup: dict[str, list[QuoteRecord]] = {}
    for pk, per_group in quote_groups.items():
        q = quote_by_pk.get(pk)
        if q is None:
            continue
        section_label = quote_section.get(pk)
        theme_label = quote_theme.get(pk)
        for gname, tag_names in per_group.items():
            record = QuoteRecord(
                text=edited_text.get(pk, q.text),
                participant_id=q.participant_id,
                session_id=q.session_id,
                start_seconds=q.start_timecode,
                intensity=q.intensity,
                tag_names=tag_names,
                segment_index=q.segment_index,
            )
            if section_label:
                section_contributions.append(QuoteContribution(
                    row_label=section_label,
                    col_label=gname,
                    participant_id=q.participant_id,
                    intensity=q.intensity,
                    weight=1.0,
                ))
                section_lookup.setdefault(f"{section_label}|{gname}", []).append(record)
            if theme_label:
                theme_contributions.append(QuoteContribution(
                    row_label=theme_label,
                    col_label=gname,
                    participant_id=q.participant_id,
                    intensity=q.intensity,
                    weight=1.0,
                ))
                theme_lookup.setdefault(f"{theme_label}|{gname}", []).append(record)

    section_matrix = build_matrix_from_contributions(
        section_contributions, [c.screen_label for c in clusters], col_labels,
    )
    theme_matrix = build_matrix_from_contributions(
        theme_contributions, [t.theme_label for t in themes], col_labels,
    )
    signals, _, _ = detect_signals_generic(
        section_matrix,
        theme_matrix,
        col_labels,
        total_participants,
        section_lookup,
        theme_lookup,
        top_n=top_n,
    )
    return SignalsResult(
        signals=signals,
        total_participants=total_participants,
        group_colour_sets=colour_sets,
    )
