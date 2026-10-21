"""A quote's rank within its second — two quotes with one start are two rows.

Stage 9 can cut two quotes from one paragraph with the same start, and the
importer matched on the start alone, so the second overwrote the first (85
extracted, 83 rows; R86). ``quotes.ordinal`` is the quote's rank among the
same speaker's quotes that start in the same whole second, by
``(start, end, verbatim_excerpt)``, 0 for the first — so every id and key an
existing project holds reads unchanged, and the stable key
``(project, session, participant, start, ordinal)`` becomes unique.

The backfill ranks the rows already here with a copy of
``importer.rank_quote_ordinals``: a migration must not import code that can
change under it. ``tests/test_migration_021_quote_ordinal.py`` holds the two
to the same answers.

Guarded per the Alembic discipline: ``upgrade()`` runs on a fresh DB too,
where ``create_all()`` has already made the column and the unique index.

Revision ID: 021
Revises: 020
Create Date: 2026-10-21
"""

from collections.abc import Iterable

import sqlalchemy as sa
from alembic import op

revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None

_OLD_INDEX = "ix_quote_stable_key"
_NEW_INDEX = "uq_quote_stable_key"

QuoteRankKey = tuple[str, str, float, float, str, int]


def _rank_quote_ordinals(keys: Iterable[QuoteRankKey]) -> dict[QuoteRankKey, int]:
    """Copy of ``bristlenose.server.importer.rank_quote_ordinals`` — keep identical."""
    groups: dict[tuple[str, str, int], set[QuoteRankKey]] = {}
    for key in keys:
        groups.setdefault((key[0], key[1], int(key[2])), set()).add(key)
    ranks: dict[QuoteRankKey, int] = {}
    for members in groups.values():
        for i, key in enumerate(sorted(members, key=lambda k: (k[2], k[3], k[4], k[5]))):
            ranks[key] = i
    return ranks


def _has_column(table: str, column: str) -> bool:
    return column in {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _index_names(table: str) -> set[str]:
    return {str(i["name"]) for i in sa.inspect(op.get_bind()).get_indexes(table) if i["name"]}


def _rank_key_from_row(sid: object, code: object, start: object, end: object,
                       verbatim: object, text: object, qid: object) -> QuoteRankKey:
    """Copy of the importer's ``_rank_key``, from a row's columns — the nulls and the text
    fallback read alike. The row id is the tiebreak: two identical rows (a race before the
    unique index) must take two ordinals, or the index refuses to build."""
    return (str(sid or ""), str(code or ""), float(start or 0.0), float(end or 0.0),  # type: ignore[arg-type]
            str(verbatim or text or ""), int(qid))  # type: ignore[call-overload]


def _backfill() -> None:
    bind = op.get_bind()
    rows = bind.execute(sa.text(
        "SELECT id, project_id, session_id, participant_id, start_timecode, end_timecode,"
        " verbatim_excerpt, text FROM quotes"
    )).all()
    by_project: dict[int, list[tuple[int, QuoteRankKey]]] = {}
    for qid, pid, sid, code, start, end, verbatim, text in rows:
        key = _rank_key_from_row(sid, code, start, end, verbatim, text, qid)
        by_project.setdefault(int(pid), []).append((int(qid), key))
    for members in by_project.values():
        ranks = _rank_quote_ordinals(key for _, key in members)
        for qid, key in members:
            if ranks[key]:
                bind.execute(sa.text("UPDATE quotes SET ordinal = :o WHERE id = :id"),
                             {"o": ranks[key], "id": qid})


def upgrade() -> None:
    if not _has_column("quotes", "ordinal"):
        op.add_column(
            "quotes", sa.Column("ordinal", sa.Integer(), nullable=False, server_default="0"),
        )
        _backfill()
    names = _index_names("quotes")
    if _OLD_INDEX in names:
        op.drop_index(_OLD_INDEX, table_name="quotes")
    if _NEW_INDEX not in names:
        op.create_index(
            _NEW_INDEX, "quotes",
            ["project_id", "session_id", "participant_id", "start_timecode", "ordinal"],
            unique=True,
        )


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported")
