"""AutoCode apply parameters — persist the cutoff + prompt version.

Adds ``autocode_jobs.applied_lower_threshold`` / ``applied_upper_threshold``
(the researcher's chosen histogram cutoff, recorded when they apply) and
``autocode_jobs.prompt_version`` (stamped when the job runs). These let a later
re-apply to newly-added quotes reuse the *same* parameters instead of prompting
again — the appliance keeps new sessions coded consistently with the earlier
ones. All additive/nullable, no backfill needed (null = "not recorded", the
pre-feature state).

Guarded per the Alembic discipline: ``upgrade()`` runs on a fresh DB too, but
``_has_column`` skips the ADD there (``create_all()`` already made the columns).

Revision ID: 006
Revises: 005
Create Date: 2026-07-18
"""

import sqlalchemy as sa
from alembic import op

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    return column in {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if not _has_column("autocode_jobs", "applied_lower_threshold"):
        op.add_column(
            "autocode_jobs",
            sa.Column("applied_lower_threshold", sa.Float(), nullable=True),
        )
    if not _has_column("autocode_jobs", "applied_upper_threshold"):
        op.add_column(
            "autocode_jobs",
            sa.Column("applied_upper_threshold", sa.Float(), nullable=True),
        )
    if not _has_column("autocode_jobs", "prompt_version"):
        op.add_column(
            "autocode_jobs",
            sa.Column(
                "prompt_version",
                sa.String(length=20),
                nullable=False,
                server_default="",
            ),
        )


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported")
