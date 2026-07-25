"""Per-project framework enable/disable state.

Adds ``project_framework_states`` — a per-project, per-framework flag driving the
codebook enable/disable switch. A row exists only when the researcher has an
explicit opinion; absence means enabled (the default). Per
design-codebook-library.md Decision A this is view-only (fold + report-wide badge
hide) and does NOT gate re-apply.

Guarded per the Alembic discipline: ``upgrade()`` runs on a fresh DB too, but
``_has_table`` skips the CREATE there (``create_all()`` already made the table).

Revision ID: 007
Revises: 006
Create Date: 2026-07-25
"""

import sqlalchemy as sa
from alembic import op

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def _has_table(table: str) -> bool:
    return table in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if not _has_table("project_framework_states"):
        op.create_table(
            "project_framework_states",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "project_id",
                sa.Integer(),
                sa.ForeignKey("projects.id"),
                nullable=False,
            ),
            sa.Column("framework_id", sa.String(length=50), nullable=False),
            sa.Column(
                "enabled", sa.Boolean(), nullable=False, server_default=sa.true()
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.UniqueConstraint(
                "project_id", "framework_id", name="uq_project_framework_state"
            ),
        )


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported")
