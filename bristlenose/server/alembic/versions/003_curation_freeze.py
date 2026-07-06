"""Curation persistence — Freeze (Phase 1).

Gives every quote the researcher touches durable identity so re-runs can never
lose their invested effort:

- ``quotes.durable_id`` — project-scoped stable id, minted on first human touch
- ``quotes.frozen_form`` — verbatim display text captured at pin time (a
  re-identification key; excluded from the export/anonymisation boundary)

Also corrects a latent mislabel: the importer used to write machine-authored
*sentiment* ``quote_tags`` with the column-default ``source="human"``.  The
Freeze pin predicate is ``source == "human"``, so those would falsely pin every
quote with a sentiment.  We relabel them to ``"pipeline"`` here (the importer
now writes them correctly going forward).

Guarded, per the project's Alembic discipline: ``init_db`` runs
``create_all()`` *before* migrations, so on fresh/recent databases the two
columns already exist by the time we get here — we add them only when absent.
``upgrade()`` still runs on a fresh DB (``run_migrations`` stamps 001 then
upgrades to head), but ``_has_column`` skips the ADD COLUMNs and the relabel /
backfill SELECTs match no rows, so it is a no-op — safety is the guards, not a
skipped upgrade().

Revision ID: 003
Revises: 002
Create Date: 2026-07-06
"""

import uuid

import sqlalchemy as sa
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    return column in {c["name"] for c in sa.inspect(bind).get_columns(table)}


def upgrade() -> None:
    if not _has_column("quotes", "durable_id"):
        op.add_column(
            "quotes", sa.Column("durable_id", sa.String(length=32), nullable=True)
        )
    if not _has_column("quotes", "frozen_form"):
        op.add_column("quotes", sa.Column("frozen_form", sa.Text(), nullable=True))

    bind = op.get_bind()

    # Relabel machine sentiment tags mislabelled as human so the pin predicate
    # (source == "human") is honest.  Fresh DBs have no such rows → no-op.
    bind.execute(
        sa.text(
            """
            UPDATE quote_tags SET source = 'pipeline'
            WHERE source = 'human' AND tag_definition_id IN (
                SELECT td.id FROM tag_definitions td
                JOIN codebook_groups cg ON td.codebook_group_id = cg.id
                WHERE cg.framework_id = 'sentiment'
            )
            """
        )
    )

    # Backfill: freeze quotes that already carry human work (star / edit /
    # human non-sentiment tag) but have no durable_id yet.
    pinned = bind.execute(
        sa.text(
            """
            SELECT q.id FROM quotes q
            WHERE q.durable_id IS NULL AND (
              EXISTS (SELECT 1 FROM quote_states s
                      WHERE s.quote_id = q.id AND s.is_starred = 1)
              OR EXISTS (SELECT 1 FROM quote_edits e WHERE e.quote_id = q.id)
              OR EXISTS (
                SELECT 1 FROM quote_tags t
                JOIN tag_definitions td ON t.tag_definition_id = td.id
                JOIN codebook_groups cg ON td.codebook_group_id = cg.id
                WHERE t.quote_id = q.id AND t.source = 'human'
                  AND (cg.framework_id IS NULL OR cg.framework_id != 'sentiment')
              )
            )
            """
        )
    ).fetchall()

    for (qid,) in pinned:
        edit = bind.execute(
            sa.text(
                "SELECT edited_text FROM quote_edits WHERE quote_id = :qid "
                "ORDER BY edited_at DESC LIMIT 1"
            ),
            {"qid": qid},
        ).fetchone()
        if edit is not None:
            frozen = edit[0]
        else:
            frozen = bind.execute(
                sa.text("SELECT text FROM quotes WHERE id = :qid"), {"qid": qid}
            ).scalar()
        bind.execute(
            sa.text(
                "UPDATE quotes SET durable_id = :did, frozen_form = :ff "
                "WHERE id = :qid"
            ),
            {"did": uuid.uuid4().hex, "ff": frozen, "qid": qid},
        )


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported")
