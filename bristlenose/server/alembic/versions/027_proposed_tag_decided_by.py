"""How each AutoCode decision was made: ``proposed_tags.decided_by``.

A re-cut of the review dialog's lines may move only the decisions a line made, never
one a researcher made by hand (docs/design-autocode-landing-plan.md D2), and only a
researcher's exclusion counts as a rejection (D4). Adds a nullable ``decided_by``:
"threshold", "researcher" or "unknown". Every proposal decided before this migration
gets "unknown" (the database cannot say which way it was decided, so it is pinned
like a researcher's decision and never counted as a rejection); a pending one stays
NULL.

Guarded per the Alembic discipline: ``upgrade()`` runs on a fresh DB too, where
``create_all()`` has already made the column (and there are no rows to mark).

Revision ID: 027
Revises: 026
Create Date: 2026-11-23
"""

import sqlalchemy as sa
from alembic import op

revision = "027"
down_revision = "026"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    return column in {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if _has_column("proposed_tags", "decided_by"):
        return
    op.add_column("proposed_tags", sa.Column("decided_by", sa.String(20), nullable=True))
    op.execute(
        "UPDATE proposed_tags SET decided_by = 'unknown' WHERE status != 'pending'"
    )


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported")
