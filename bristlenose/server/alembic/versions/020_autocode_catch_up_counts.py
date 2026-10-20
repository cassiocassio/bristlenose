"""AutoCode catch-up counts — a catch-up's own outcome, not the codebook's.

The on-enable catch-up chip decided "some batches failed" from the job's
cumulative ``processed_quotes < total_quotes``. Those counts keep every earlier
shortfall for good, so once any apply had come up short, every later catch-up
that worked said it had partly failed.

Adds ``catch_up_total`` and ``catch_up_processed``: the quotes the last catch-up
sent and the ones whose batch answered. A route starting a catch-up zeroes them;
the catch-up writes them when it completes.

Guarded per the Alembic discipline: ``upgrade()`` runs on a fresh DB too, where
``create_all()`` has already made the columns.

Revision ID: 020
Revises: 019
Create Date: 2026-10-20
"""

import sqlalchemy as sa
from alembic import op

revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    return column in {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    for column in ("catch_up_total", "catch_up_processed"):
        if not _has_column("autocode_jobs", column):
            op.add_column(
                "autocode_jobs",
                sa.Column(column, sa.Integer(), nullable=False, server_default="0"),
            )


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported")
