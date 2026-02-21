"""Analysis API endpoint — tag-based signal concentration analysis.

Computes the same concentration / agreement / intensity maths as the
pipeline's sentiment analysis, but using codebook groups as the column
dimension instead of sentiments.  A quote counts in a group column if
it has *any* tag from that group.

Quotes tagged in multiple groups count in each group column — this
inflates ``grand_total`` relative to the number of unique quotes.  The
trade-off is documented in the response and the signal maths remains
internally consistent.
"""

from __future__ import annotations

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


class TagSignal(BaseModel):
    """A notable concentration pattern for a codebook group."""

    location: str
    source_type: str
    group_name: str
    count: int
    participants: list[str]
    n_eff: float
    mean_intensity: float
    concentration: float
    composite_signal: float
    confidence: str
    quotes: list[TagSignalQuote]


class MatrixCellOut(BaseModel):
    """A single cell in the contingency table."""

    count: int
    participants: dict[str, int]
    intensities: list[int]


class MatrixOut(BaseModel):
    """A row × column contingency matrix serialised for the client."""

    cells: dict[str, MatrixCellOut]
    row_totals: dict[str, int]
    col_totals: dict[str, int]
    grand_total: int
    row_labels: list[str]


class TagAnalysisResponse(BaseModel):
    """Full tag-based analysis result."""

    signals: list[TagSignal]
    section_matrix: MatrixOut
    theme_matrix: MatrixOut
    total_participants: int
    columns: list[str]
    participant_ids: list[str]
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


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.get(
    "/projects/{project_id}/analysis/tags",
    response_model=TagAnalysisResponse,
)
def get_tag_analysis(
    project_id: int,
    request: Request,
    groups: str | None = Query(default=None, description="Comma-separated group IDs to include"),
    top_n: int = Query(default=12, ge=1, le=100),
) -> TagAnalysisResponse:
    """Compute tag-based signal analysis for a project.

    Builds section × group and theme × group contingency matrices, then
    runs signal detection using the same maths as sentiment analysis.
    """
    db = _get_db(request)
    try:
        _check_project(db, project_id)

        # 1. Resolve active codebook groups ----------------------------------
        if groups:
            try:
                group_ids = [int(g.strip()) for g in groups.split(",") if g.strip()]
            except ValueError:
                raise HTTPException(status_code=400, detail="groups must be comma-separated integers")
            active_groups = (
                db.query(CodebookGroup)
                .filter(CodebookGroup.id.in_(group_ids))
                .all()
            )
        else:
            # All active groups for the project, excluding Uncategorised
            pcg_rows = (
                db.query(ProjectCodebookGroup)
                .filter_by(project_id=project_id)
                .order_by(ProjectCodebookGroup.sort_order)
                .all()
            )
            active_group_ids = [r.codebook_group_id for r in pcg_rows]
            active_groups = (
                db.query(CodebookGroup)
                .filter(
                    CodebookGroup.id.in_(active_group_ids),
                    CodebookGroup.name != UNCATEGORISED_GROUP_NAME,
                )
                .all()
            ) if active_group_ids else []

        if not active_groups:
            return _empty_response()

        group_id_to_name = {g.id: g.name for g in active_groups}
        col_labels = [g.name for g in active_groups]

        # 2. Load all quotes for the project ---------------------------------
        all_quotes = db.query(Quote).filter_by(project_id=project_id).all()
        if not all_quotes:
            return _empty_response()

        quote_by_id: dict[int, Quote] = {q.id: q for q in all_quotes}

        # 3. Build quote → group-names map -----------------------------------
        tag_defs = (
            db.query(TagDefinition)
            .filter(TagDefinition.codebook_group_id.in_(group_id_to_name.keys()))
            .all()
        )
        tag_def_to_group: dict[int, str] = {
            td.id: group_id_to_name[td.codebook_group_id] for td in tag_defs
        }

        quote_tags = (
            db.query(QuoteTag)
            .filter(QuoteTag.tag_definition_id.in_(tag_def_to_group.keys()))
            .all()
        ) if tag_def_to_group else []

        # quote_id -> set of group names
        quote_groups: dict[int, set[str]] = {}
        for qt in quote_tags:
            gname = tag_def_to_group.get(qt.tag_definition_id)
            if gname:
                quote_groups.setdefault(qt.quote_id, set()).add(gname)

        if not quote_groups:
            return _empty_response()

        # 4. Build quote → section and quote → theme maps --------------------
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

        themes = (
            db.query(ThemeGroup)
            .filter_by(project_id=project_id)
            .all()
        )
        theme_id_to_label = {t.id: t.theme_label for t in themes}
        theme_row_labels = [t.theme_label for t in themes]

        tqs = db.query(ThemeQuote).filter(
            ThemeQuote.theme_id.in_(theme_id_to_label.keys())
        ).all() if theme_id_to_label else []
        quote_theme: dict[int, str] = {
            tq.quote_id: theme_id_to_label[tq.theme_id] for tq in tqs
        }

        # 5. Build contributions and quote lookups ---------------------------
        section_contributions: list[QuoteContribution] = []
        theme_contributions: list[QuoteContribution] = []
        section_quote_lookup: dict[str, list[QuoteRecord]] = {}
        theme_quote_lookup: dict[str, list[QuoteRecord]] = {}

        for qid, group_names in quote_groups.items():
            q = quote_by_id.get(qid)
            if q is None:
                continue

            qr = QuoteRecord(
                text=q.text,
                participant_id=q.participant_id,
                session_id=q.session_id,
                start_seconds=q.start_timecode,
                intensity=q.intensity,
            )

            section_label = quote_section.get(qid)
            theme_label = quote_theme.get(qid)

            for gname in group_names:
                if section_label:
                    section_contributions.append(
                        QuoteContribution(
                            row_label=section_label,
                            col_label=gname,
                            participant_id=q.participant_id,
                            intensity=q.intensity,
                        )
                    )
                    section_quote_lookup.setdefault(f"{section_label}|{gname}", []).append(qr)

                if theme_label:
                    theme_contributions.append(
                        QuoteContribution(
                            row_label=theme_label,
                            col_label=gname,
                            participant_id=q.participant_id,
                            intensity=q.intensity,
                        )
                    )
                    theme_quote_lookup.setdefault(f"{theme_label}|{gname}", []).append(qr)

        # 6. Build matrices --------------------------------------------------
        section_matrix = build_matrix_from_contributions(
            section_contributions, section_row_labels, col_labels,
        )
        theme_matrix = build_matrix_from_contributions(
            theme_contributions, theme_row_labels, col_labels,
        )

        # 7. Count unique participants ---------------------------------------
        all_pids: set[str] = set()
        for q in all_quotes:
            if q.participant_id.startswith("p"):
                all_pids.add(q.participant_id)
        total_participants = len(all_pids)

        # 8. Detect signals --------------------------------------------------
        signals, section_matrix, theme_matrix = detect_signals_generic(
            section_matrix,
            theme_matrix,
            col_labels,
            total_participants,
            section_quote_lookup,
            theme_quote_lookup,
            top_n=top_n,
        )

        # 9. Collect participant IDs that appear in signals ------------------
        signal_pids: set[str] = set()
        for s in signals:
            signal_pids.update(s.participants)

        # 10. Build response -------------------------------------------------
        return TagAnalysisResponse(
            signals=[
                TagSignal(
                    location=s.location,
                    source_type=s.source_type,
                    group_name=s.sentiment,  # carries group name
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
                        )
                        for q in s.quotes
                    ],
                )
                for s in signals
            ],
            section_matrix=_serialize_matrix(section_matrix),
            theme_matrix=_serialize_matrix(theme_matrix),
            total_participants=total_participants,
            columns=col_labels,
            participant_ids=_natural_sort_pids(signal_pids),
            trade_off_note=_TRADE_OFF_NOTE,
        )
    finally:
        db.close()


def _empty_response() -> TagAnalysisResponse:
    """Return an empty analysis result (no tags, no groups, or no quotes)."""
    return TagAnalysisResponse(
        signals=[],
        section_matrix=MatrixOut(
            cells={}, row_totals={}, col_totals={}, grand_total=0, row_labels=[],
        ),
        theme_matrix=MatrixOut(
            cells={}, row_totals={}, col_totals={}, grand_total=0, row_labels=[],
        ),
        total_participants=0,
        columns=[],
        participant_ids=[],
        trade_off_note=_TRADE_OFF_NOTE,
    )
