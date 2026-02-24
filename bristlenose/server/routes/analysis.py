"""Analysis API endpoints — tag-based signal concentration analysis.

Two endpoints:

- ``GET /analysis/tags`` — flat analysis across all active groups (backward compat)
- ``GET /analysis/codebooks`` — per-codebook analysis (groups partitioned by framework)

Both compute the same concentration / agreement / intensity maths as the
pipeline's sentiment analysis, but using codebook groups as the column
dimension instead of sentiments.  A quote counts in a group column if
it has *any* tag from that group.

Quotes tagged in multiple groups count in each group column — this
inflates ``grand_total`` relative to the number of unique quotes.  The
trade-off is documented in the response and the signal maths remains
internally consistent.

Tag sources and weighting:
- **Accepted tags** (``QuoteTag`` rows): weight 1.0
- **Pending proposed tags** (``ProposedTag`` with status="pending"):
  weight = LLM confidence (0.0–1.0)
- **Denied proposed tags**: excluded entirely
- Accepted proposals already have a ``QuoteTag`` row — the endpoint
  de-duplicates to avoid double-counting.
"""

from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from bristlenose.analysis.generic_matrix import QuoteContribution, build_matrix_from_contributions
from bristlenose.analysis.generic_signals import QuoteRecord, detect_signals_generic
from bristlenose.server.models import (
    UNCATEGORISED_GROUP_NAME,
    ClusterQuote,
    CodebookGroup,
    Project,
    ProjectCodebookGroup,
    ProposedTag,
    Quote,
    QuoteTag,
    ScreenCluster,
    TagDefinition,
    ThemeGroup,
    ThemeQuote,
)

router = APIRouter(prefix="/api")

_TRADE_OFF_NOTE = (
    "Quotes tagged with codes from multiple groups count in each group column."
    " This inflates grand_total relative to the number of unique quotes."
    " Signal strengths are internally consistent within this analysis —"
    " compare them to each other, not against sentiment-based analysis."
)


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class TagSignalQuote(BaseModel):
    """One quote attached to a signal card."""

    text: str
    participant_id: str
    session_id: str
    start_seconds: float
    intensity: int
    tag_names: list[str] = []
    segment_index: int = -1


class TagSignal(BaseModel):
    """A notable concentration pattern for a codebook group."""

    location: str
    source_type: str
    group_name: str
    colour_set: str = ""
    count: int
    participants: list[str]
    n_eff: float
    mean_intensity: float
    concentration: float
    composite_signal: float
    confidence: str
    quotes: list[TagSignalQuote]
    # Elaboration fields (populated when elaborate=True)
    signal_name: str | None = None
    pattern: str | None = None
    elaboration: str | None = None


class MatrixCellOut(BaseModel):
    """A single cell in the contingency table."""

    count: int
    weighted_count: float
    participants: dict[str, int]
    intensities: list[int]


class MatrixOut(BaseModel):
    """A row × column contingency matrix serialised for the client."""

    cells: dict[str, MatrixCellOut]
    row_totals: dict[str, int]
    col_totals: dict[str, int]
    grand_total: int
    row_labels: list[str]


class SourceBreakdown(BaseModel):
    """How many tag associations come from each source."""

    accepted: int
    pending: int
    total: int


class TagAnalysisResponse(BaseModel):
    """Full tag-based analysis result (flat, all groups merged)."""

    signals: list[TagSignal]
    section_matrix: MatrixOut
    theme_matrix: MatrixOut
    total_participants: int
    columns: list[str]
    participant_ids: list[str]
    source_breakdown: SourceBreakdown
    trade_off_note: str


class CodebookAnalysisOut(BaseModel):
    """Analysis result for one codebook (framework or user-created)."""

    codebook_id: str
    codebook_name: str
    colour_set: str
    signals: list[TagSignal]
    section_matrix: MatrixOut
    theme_matrix: MatrixOut
    columns: list[str]
    participant_ids: list[str]
    source_breakdown: SourceBreakdown
    tag_colour_indices: dict[str, int]


class CodebookAnalysisListResponse(BaseModel):
    """All per-codebook analyses for a project."""

    codebooks: list[CodebookAnalysisOut]
    total_participants: int
    trade_off_note: str


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


def _natural_sort_pids(pids: set[str]) -> list[str]:
    """Sort participant IDs naturally: p1, p2, …, p10."""
    return sorted(pids, key=lambda p: (p[0], int(p[1:]) if p[1:].isdigit() else 0))


def _serialize_matrix(matrix: object) -> MatrixOut:
    """Convert a Matrix dataclass to the response model."""
    from bristlenose.analysis.models import Matrix

    assert isinstance(matrix, Matrix)
    cells_out: dict[str, MatrixCellOut] = {}
    for key, cell in matrix.cells.items():
        cells_out[key] = MatrixCellOut(
            count=cell.count,
            weighted_count=round(cell.weighted_count, 2),
            participants=dict(cell.participants),
            intensities=list(cell.intensities),
        )
    return MatrixOut(
        cells=cells_out,
        row_totals=dict(matrix.row_totals),
        col_totals=dict(matrix.col_totals),
        grand_total=matrix.grand_total,
        row_labels=list(matrix.row_labels),
    )


_EMPTY_BREAKDOWN = SourceBreakdown(accepted=0, pending=0, total=0)

_EMPTY_MATRIX = MatrixOut(
    cells={}, row_totals={}, col_totals={}, grand_total=0, row_labels=[],
)


def _serialize_signal(
    s: object,
    group_colour_sets: dict[str, str],
) -> TagSignal:
    """Convert a Signal dataclass to the response model."""
    from bristlenose.analysis.models import Signal

    assert isinstance(s, Signal)
    return TagSignal(
        location=s.location,
        source_type=s.source_type,
        group_name=s.sentiment,  # carries group name (historical field name)
        colour_set=group_colour_sets.get(s.sentiment, ""),
        count=s.count,
        participants=s.participants,
        n_eff=round(s.n_eff, 2),
        mean_intensity=round(s.mean_intensity, 2),
        concentration=round(s.concentration, 2),
        composite_signal=round(s.composite_signal, 4),
        confidence=s.confidence,
        quotes=[
            TagSignalQuote(
                text=q.text,
                participant_id=q.participant_id,
                session_id=q.session_id,
                start_seconds=q.start_seconds,
                intensity=q.intensity,
                tag_names=list(q.tag_names),
                segment_index=q.segment_index,
            )
            for q in s.quotes
        ],
    )


# ---------------------------------------------------------------------------
# Shared data loading
# ---------------------------------------------------------------------------


class _SharedProjectData:
    """Data shared across per-codebook computations."""

    def __init__(
        self,
        all_quotes: list[Quote],
        quote_by_id: dict[int, Quote],
        quote_section: dict[int, str],
        quote_theme: dict[int, str],
        section_row_labels: list[str],
        theme_row_labels: list[str],
        total_participants: int,
    ) -> None:
        self.all_quotes = all_quotes
        self.quote_by_id = quote_by_id
        self.quote_section = quote_section
        self.quote_theme = quote_theme
        self.section_row_labels = section_row_labels
        self.theme_row_labels = theme_row_labels
        self.total_participants = total_participants


def _load_shared_data(db: Session, project_id: int) -> _SharedProjectData | None:
    """Load quotes, section/theme mappings — shared across codebook partitions."""
    all_quotes = db.query(Quote).filter_by(project_id=project_id).all()
    if not all_quotes:
        return None

    quote_by_id: dict[int, Quote] = {q.id: q for q in all_quotes}

    clusters = (
        db.query(ScreenCluster)
        .filter_by(project_id=project_id)
        .order_by(ScreenCluster.display_order)
        .all()
    )
    cluster_id_to_label = {c.id: c.screen_label for c in clusters}
    section_row_labels = [c.screen_label for c in clusters]

    cqs = db.query(ClusterQuote).filter(
        ClusterQuote.cluster_id.in_(cluster_id_to_label.keys())
    ).all() if cluster_id_to_label else []
    quote_section: dict[int, str] = {
        cq.quote_id: cluster_id_to_label[cq.cluster_id] for cq in cqs
    }

    themes = db.query(ThemeGroup).filter_by(project_id=project_id).all()
    theme_id_to_label = {t.id: t.theme_label for t in themes}
    theme_row_labels = [t.theme_label for t in themes]

    tqs = db.query(ThemeQuote).filter(
        ThemeQuote.theme_id.in_(theme_id_to_label.keys())
    ).all() if theme_id_to_label else []
    quote_theme: dict[int, str] = {
        tq.quote_id: theme_id_to_label[tq.theme_id] for tq in tqs
    }

    all_pids: set[str] = set()
    for q in all_quotes:
        if q.participant_id.startswith("p"):
            all_pids.add(q.participant_id)

    return _SharedProjectData(
        all_quotes=all_quotes,
        quote_by_id=quote_by_id,
        quote_section=quote_section,
        quote_theme=quote_theme,
        section_row_labels=section_row_labels,
        theme_row_labels=theme_row_labels,
        total_participants=len(all_pids),
    )


# ---------------------------------------------------------------------------
# Core analysis logic (used by both endpoints)
# ---------------------------------------------------------------------------


def _compute_group_analysis(
    active_groups: list[CodebookGroup],
    shared: _SharedProjectData,
    db: Session,
    top_n: int,
) -> tuple[
    list[object],  # Signal list
    object,  # section_matrix
    object,  # theme_matrix
    list[str],  # col_labels
    SourceBreakdown,
    dict[str, str],  # group_name -> colour_set
    dict[int, dict[str, list[str]]],  # quote_id -> {group_name: [tag_names]}
] | None:
    """Run signal analysis for a set of codebook groups.

    Returns None if no tag data available.
    """
    group_id_to_name = {g.id: g.name for g in active_groups}
    group_name_to_colour_set = {g.name: g.colour_set for g in active_groups}
    col_labels = [g.name for g in active_groups]

    # Load tag definitions
    tag_defs = (
        db.query(TagDefinition)
        .filter(TagDefinition.codebook_group_id.in_(group_id_to_name.keys()))
        .all()
    )
    tag_def_to_group: dict[int, str] = {
        td.id: group_id_to_name[td.codebook_group_id] for td in tag_defs
    }
    tag_def_to_name: dict[int, str] = {td.id: td.name for td in tag_defs}

    if not tag_def_to_group:
        return None

    # Accepted tags (QuoteTag) — weight 1.0
    accepted_tags = (
        db.query(QuoteTag)
        .filter(QuoteTag.tag_definition_id.in_(tag_def_to_group.keys()))
        .all()
    )

    # quote_id -> {group_name: weight} — highest weight wins per group
    quote_group_weights: dict[int, dict[str, float]] = {}
    # quote_id -> {group_name: [tag_name, ...]}
    quote_tag_names: dict[int, dict[str, list[str]]] = {}
    accepted_count = 0
    for qt in accepted_tags:
        gname = tag_def_to_group.get(qt.tag_definition_id)
        tname = tag_def_to_name.get(qt.tag_definition_id, "")
        if gname:
            weights = quote_group_weights.setdefault(qt.quote_id, {})
            weights[gname] = max(weights.get(gname, 0.0), 1.0)
            names = quote_tag_names.setdefault(qt.quote_id, {}).setdefault(gname, [])
            if tname and tname not in names:
                names.append(tname)
            accepted_count += 1

    # Pending proposed tags — weight = confidence
    accepted_pairs: set[tuple[int, int]] = {
        (qt.quote_id, qt.tag_definition_id) for qt in accepted_tags
    }

    pending_proposals = (
        db.query(ProposedTag)
        .filter(
            ProposedTag.tag_definition_id.in_(tag_def_to_group.keys()),
            ProposedTag.status == "pending",
        )
        .all()
    )

    pending_count = 0
    for pt in pending_proposals:
        if (pt.quote_id, pt.tag_definition_id) in accepted_pairs:
            continue
        gname = tag_def_to_group.get(pt.tag_definition_id)
        tname = tag_def_to_name.get(pt.tag_definition_id, "")
        if gname and pt.confidence > 0:
            weights = quote_group_weights.setdefault(pt.quote_id, {})
            weights[gname] = max(weights.get(gname, 0.0), pt.confidence)
            names = quote_tag_names.setdefault(pt.quote_id, {}).setdefault(gname, [])
            if tname and tname not in names:
                names.append(tname)
            pending_count += 1

    if not quote_group_weights:
        return None

    source_breakdown = SourceBreakdown(
        accepted=accepted_count,
        pending=pending_count,
        total=accepted_count + pending_count,
    )

    # Build contributions and quote lookups
    section_contributions: list[QuoteContribution] = []
    theme_contributions: list[QuoteContribution] = []
    section_quote_lookup: dict[str, list[QuoteRecord]] = {}
    theme_quote_lookup: dict[str, list[QuoteRecord]] = {}

    for qid, group_weights in quote_group_weights.items():
        q = shared.quote_by_id.get(qid)
        if q is None:
            continue

        section_label = shared.quote_section.get(qid)
        theme_label = shared.quote_theme.get(qid)

        for gname, weight in group_weights.items():
            tag_names_for_quote = quote_tag_names.get(qid, {}).get(gname, [])
            qr = QuoteRecord(
                text=q.text,
                participant_id=q.participant_id,
                session_id=q.session_id,
                start_seconds=q.start_timecode,
                intensity=q.intensity,
                tag_names=tag_names_for_quote,
            )

            if section_label:
                section_contributions.append(
                    QuoteContribution(
                        row_label=section_label,
                        col_label=gname,
                        participant_id=q.participant_id,
                        intensity=q.intensity,
                        weight=weight,
                    )
                )
                section_quote_lookup.setdefault(
                    f"{section_label}|{gname}", [],
                ).append(qr)

            if theme_label:
                theme_contributions.append(
                    QuoteContribution(
                        row_label=theme_label,
                        col_label=gname,
                        participant_id=q.participant_id,
                        intensity=q.intensity,
                        weight=weight,
                    )
                )
                theme_quote_lookup.setdefault(
                    f"{theme_label}|{gname}", [],
                ).append(qr)

    # Build matrices
    section_matrix = build_matrix_from_contributions(
        section_contributions, shared.section_row_labels, col_labels,
    )
    theme_matrix = build_matrix_from_contributions(
        theme_contributions, shared.theme_row_labels, col_labels,
    )

    # Detect signals
    signals, section_matrix, theme_matrix = detect_signals_generic(
        section_matrix,
        theme_matrix,
        col_labels,
        shared.total_participants,
        section_quote_lookup,
        theme_quote_lookup,
        top_n=top_n,
    )

    return (
        signals,
        section_matrix,
        theme_matrix,
        col_labels,
        source_breakdown,
        group_name_to_colour_set,
        quote_tag_names,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/projects/{project_id}/analysis/tags",
    response_model=TagAnalysisResponse,
)
def get_tag_analysis(
    project_id: int,
    request: Request,
    groups: str | None = Query(
        default=None, description="Comma-separated group IDs to include",
    ),
    top_n: int = Query(default=12, ge=1, le=100),
) -> TagAnalysisResponse:
    """Compute tag-based signal analysis for a project (flat, all groups merged).

    Backward-compatible endpoint — merges all codebook groups into one analysis.
    """
    db = _get_db(request)
    try:
        _check_project(db, project_id)
        active_groups = _resolve_active_groups(db, project_id, groups)
        if not active_groups:
            return _empty_tag_response()

        shared = _load_shared_data(db, project_id)
        if shared is None:
            return _empty_tag_response()

        result = _compute_group_analysis(active_groups, shared, db, top_n)
        if result is None:
            return _empty_tag_response()

        signals, section_matrix, theme_matrix, col_labels, breakdown, colour_sets, _ = result

        signal_pids: set[str] = set()
        for s in signals:
            signal_pids.update(s.participants)  # type: ignore[attr-defined]

        return TagAnalysisResponse(
            signals=[_serialize_signal(s, colour_sets) for s in signals],
            section_matrix=_serialize_matrix(section_matrix),
            theme_matrix=_serialize_matrix(theme_matrix),
            total_participants=shared.total_participants,
            columns=col_labels,
            participant_ids=_natural_sort_pids(signal_pids),
            source_breakdown=breakdown,
            trade_off_note=_TRADE_OFF_NOTE,
        )
    finally:
        db.close()


@router.get(
    "/projects/{project_id}/analysis/codebooks",
    response_model=CodebookAnalysisListResponse,
)
async def get_codebook_analysis(
    project_id: int,
    request: Request,
    top_n: int = Query(default=12, ge=1, le=100),
    elaborate: bool = Query(default=False),
) -> CodebookAnalysisListResponse:
    """Compute per-codebook signal analysis for a project.

    Groups are partitioned by framework — each framework becomes a separate
    codebook entry. User-created groups (framework_id=None) are collected
    into a single "Custom" codebook.
    """
    db = _get_db(request)
    try:
        _check_project(db, project_id)
        active_groups = _resolve_active_groups(db, project_id, groups=None)
        if not active_groups:
            return CodebookAnalysisListResponse(
                codebooks=[], total_participants=0, trade_off_note=_TRADE_OFF_NOTE,
            )

        shared = _load_shared_data(db, project_id)
        if shared is None:
            return CodebookAnalysisListResponse(
                codebooks=[], total_participants=0, trade_off_note=_TRADE_OFF_NOTE,
            )

        # Partition groups by codebook identity
        partitions: dict[str, list[CodebookGroup]] = defaultdict(list)
        for g in active_groups:
            key = g.framework_id or "custom"
            partitions[key].append(g)

        codebooks: list[CodebookAnalysisOut] = []
        for codebook_id, cb_groups in partitions.items():
            result = _compute_group_analysis(cb_groups, shared, db, top_n)
            if result is None:
                continue

            (
                signals, section_matrix, theme_matrix,
                col_labels, breakdown, colour_sets, quote_tag_names,
            ) = result

            signal_pids: set[str] = set()
            for s in signals:
                signal_pids.update(s.participants)  # type: ignore[attr-defined]

            # Resolve codebook name and representative colour_set
            codebook_name, codebook_colour = _resolve_codebook_identity(
                codebook_id, cb_groups,
            )

            # Build tag_colour_indices: tag_name -> slot index within its group
            tag_colour_indices = _build_tag_colour_indices(cb_groups, db)

            codebooks.append(CodebookAnalysisOut(
                codebook_id=codebook_id,
                codebook_name=codebook_name,
                colour_set=codebook_colour,
                signals=[_serialize_signal(s, colour_sets) for s in signals],
                section_matrix=_serialize_matrix(section_matrix),
                theme_matrix=_serialize_matrix(theme_matrix),
                columns=col_labels,
                participant_ids=_natural_sort_pids(signal_pids),
                source_breakdown=breakdown,
                tag_colour_indices=tag_colour_indices,
            ))

        # Generate elaborations for top N framework signals
        if elaborate and codebooks:
            await _elaborate_top_signals(codebooks, db, project_id)

        return CodebookAnalysisListResponse(
            codebooks=codebooks,
            total_participants=shared.total_participants,
            trade_off_note=_TRADE_OFF_NOTE,
        )
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _resolve_active_groups(
    db: Session, project_id: int, groups: str | None,
) -> list[CodebookGroup]:
    """Resolve which codebook groups to include."""
    if groups:
        try:
            group_ids = [int(g.strip()) for g in groups.split(",") if g.strip()]
        except ValueError:
            raise HTTPException(
                status_code=400, detail="groups must be comma-separated integers",
            )
        return (
            db.query(CodebookGroup)
            .filter(CodebookGroup.id.in_(group_ids))
            .all()
        )

    pcg_rows = (
        db.query(ProjectCodebookGroup)
        .filter_by(project_id=project_id)
        .order_by(ProjectCodebookGroup.sort_order)
        .all()
    )
    active_group_ids = [r.codebook_group_id for r in pcg_rows]
    if not active_group_ids:
        return []
    return (
        db.query(CodebookGroup)
        .filter(
            CodebookGroup.id.in_(active_group_ids),
            CodebookGroup.name != UNCATEGORISED_GROUP_NAME,
        )
        .all()
    )


def _resolve_codebook_identity(
    codebook_id: str, groups: list[CodebookGroup],
) -> tuple[str, str]:
    """Return (display_name, representative_colour_set) for a codebook partition."""
    if codebook_id == "custom":
        colour = groups[0].colour_set if groups else "ux"
        return ("Custom", colour)

    from bristlenose.server.codebook import get_template

    template = get_template(codebook_id)
    name = template.title if template else codebook_id.title()
    colour = groups[0].colour_set if groups else "ux"
    return (name, colour)


def _build_tag_colour_indices(
    groups: list[CodebookGroup], db: Session,
) -> dict[str, int]:
    """Build tag_name -> colour slot index for all tags in the given groups."""
    indices: dict[str, int] = {}
    group_ids = [g.id for g in groups]
    if not group_ids:
        return indices

    tag_defs = (
        db.query(TagDefinition)
        .filter(TagDefinition.codebook_group_id.in_(group_ids))
        .order_by(TagDefinition.id)
        .all()
    )

    # Group tag defs by their group, assign index within each group
    group_counters: dict[int, int] = {}
    for td in tag_defs:
        idx = group_counters.get(td.codebook_group_id, 0)
        indices[td.name] = idx
        group_counters[td.codebook_group_id] = idx + 1

    return indices


def _empty_tag_response() -> TagAnalysisResponse:
    """Return an empty flat analysis result."""
    return TagAnalysisResponse(
        signals=[],
        section_matrix=_EMPTY_MATRIX,
        theme_matrix=_EMPTY_MATRIX,
        total_participants=0,
        columns=[],
        participant_ids=[],
        source_breakdown=_EMPTY_BREAKDOWN,
        trade_off_note=_TRADE_OFF_NOTE,
    )


async def _elaborate_top_signals(
    codebooks: list[CodebookAnalysisOut],
    db: Session,
    project_id: int,
) -> None:
    """Generate elaborations for the top N framework signals across codebooks.

    Modifies ``TagSignal`` objects in place — sets ``signal_name``,
    ``pattern``, and ``elaboration`` fields.
    """
    import logging

    from bristlenose.config import load_settings
    from bristlenose.server.elaboration import (
        DEFAULT_TOP_N,
        compute_signal_key,
        generate_elaborations,
    )

    logger = logging.getLogger(__name__)

    try:
        settings = load_settings()
    except Exception:
        logger.exception("Failed to load settings for elaboration")
        return

    # Collect all framework signals (skip custom codebooks)
    all_framework: list[tuple[TagSignal, str]] = []
    for cb in codebooks:
        if cb.codebook_id == "custom":
            continue
        for sig in cb.signals:
            all_framework.append((sig, cb.codebook_id))

    if not all_framework:
        return

    # Sort by composite_signal descending, take top N
    all_framework.sort(key=lambda x: x[0].composite_signal, reverse=True)
    top_signals = all_framework[:DEFAULT_TOP_N]

    # Group by codebook_id
    by_codebook: dict[str, list[TagSignal]] = {}
    for sig, cb_id in top_signals:
        by_codebook.setdefault(cb_id, []).append(sig)

    # Generate elaborations per codebook
    for cb_id, sigs in by_codebook.items():
        elaborations = await generate_elaborations(
            sigs, cb_id, settings, db, project_id,
        )
        for sig in sigs:
            key = compute_signal_key(sig.source_type, sig.location, sig.group_name)
            elab = elaborations.get(key)
            if elab:
                sig.signal_name = elab.signal_name
                sig.pattern = elab.pattern
                sig.elaboration = elab.elaboration
