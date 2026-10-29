"""Store validated evidence assertions with cached signal narratives.

Revision ID: 024
Revises: 023
Create Date: 2026-10-28
"""

import sqlalchemy as sa
from alembic import op

revision = "024"
down_revision = "023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("elaboration_caches")}
    if "evidence_assertions" not in columns:
        op.add_column(
            "elaboration_caches",
            sa.Column("evidence_assertions", sa.Text(), nullable=False, server_default="[]"),
        )


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported")
