"""Persist completed Signals-lens snapshots.

The models are created before Alembic runs on a fresh database, so this upgrade
is guarded for that normal path as well as for existing research projects.

Revision ID: 023
Revises: 022
Create Date: 2026-10-27
"""

import sqlalchemy as sa
from alembic import op

revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "signal_snapshots" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "signal_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("payload_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("computed_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_signal_snapshots_project_id", "signal_snapshots", ["project_id"])
    op.create_index("ix_signal_snapshots_computed_at", "signal_snapshots", ["computed_at"])


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported")
