"""A researcher's own paragraph breaks in a quote.

Adds ``quote_breaks``: one row per quote whose paragraphs the researcher placed
by hand while editing it (Shift-Return, Backspace at a paragraph's start). The
breaks are presentation and are kept apart from the words, never as a newline
in the quote's text (docs/design-quote-anchor.md §3.4). No backfill: until now
a typed break was thrown away on commit.

Guarded per the Alembic discipline: ``upgrade()`` runs on a fresh DB too, where
``create_all()`` has already made the table.

Revision ID: 026
Revises: 025
Create Date: 2026-11-21
"""

import sqlalchemy as sa
from alembic import op

revision = "026"
down_revision = "025"
branch_labels = None
depends_on = None


def _has_table(table: str) -> bool:
    return table in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if _has_table("quote_breaks"):
        return
    op.create_table(
        "quote_breaks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("quote_id", sa.Integer(), sa.ForeignKey("quotes.id"), nullable=False, unique=True),
        sa.Column("breaks", sa.Text(), nullable=False),
        sa.Column("source", sa.String(16), nullable=False, server_default="researcher"),
        sa.Column("verify", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    if _has_table("quote_breaks"):
        op.drop_table("quote_breaks")
