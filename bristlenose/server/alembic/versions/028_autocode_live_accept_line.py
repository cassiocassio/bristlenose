"""A first apply's live accept line: ``autocode_jobs.live_accept_line``.

A first apply accepts tags batch by batch against a running estimate of its end-of-run
cut (docs/design-autocode-landing-plan.md D6). The line it accepts at never falls during
a run, so each batch needs the highest line the earlier ones used, and a run resumed
after a failure or a crash continues from it. Adds a nullable float: NULL until a
batch is saved, which is what every job from before this migration is.

Guarded per the Alembic discipline: ``upgrade()`` runs on a fresh DB too, where
``create_all()`` has already made the column.

Revision ID: 028
Revises: 027
Create Date: 2026-11-23
"""

import sqlalchemy as sa
from alembic import op

revision = "028"
down_revision = "027"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    return column in {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if _has_column("autocode_jobs", "live_accept_line"):
        return
    op.add_column("autocode_jobs", sa.Column("live_accept_line", sa.Float(), nullable=True))


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported")
