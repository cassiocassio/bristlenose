"""The tag sidebar overview's remembered state: ``tag_overview_states``.

The AutoCode overview at the top of the tag sidebar opens by itself once, after a
first run, and its open/closed and merged/split are remembered per study, on the
server (docs/design-autocode-landing-plan.md D12, Phase 6). One row per project,
made on the first write; absence means closed, merged and not yet opened by itself,
which is what every study from before this migration is.

Guarded per the Alembic discipline: ``upgrade()`` runs on a fresh DB too, where
``create_all()`` has already made the table.

Revision ID: 029
Revises: 028
Create Date: 2026-11-23
"""

import sqlalchemy as sa
from alembic import op

revision = "029"
down_revision = "028"
branch_labels = None
depends_on = None


def _has_table(table: str) -> bool:
    return table in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if _has_table("tag_overview_states"):
        return
    op.create_table(
        "tag_overview_states",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False, unique=True
        ),
        sa.Column("open", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("split", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("auto_opened", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported")
