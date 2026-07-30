"""Per-project Anonymise switch for the MCP agent surface.

Adds ``projects.mcp_anonymise`` — the same choice the export surfaces offer
(CSV/XLSX, clips, Miro), per-surface sticky per the 31 Jul 2026 decision.
Default ``false`` (names ride along), matching the shipped clip-export
default: the person driving the agent is the researcher who met the
participants, so anonymisation here is onward-sharing posture, not secrecy
from themselves. When true, the MCP tools return speaker codes only.

Guarded per the Alembic discipline: ``upgrade()`` runs on a fresh DB too,
but ``_has_column`` skips the ALTER there (``create_all()`` already made
the column from the model).

Revision ID: 008
Revises: 007
Create Date: 2026-07-31
"""

import sqlalchemy as sa
from alembic import op

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    columns = sa.inspect(op.get_bind()).get_columns(table)
    return any(c["name"] == column for c in columns)


def upgrade() -> None:
    if _has_column("projects", "mcp_anonymise"):
        return
    op.add_column(
        "projects",
        sa.Column("mcp_anonymise", sa.Boolean(), nullable=False,
                  server_default=sa.false()),
    )


def downgrade() -> None:
    if _has_column("projects", "mcp_anonymise"):
        op.drop_column("projects", "mcp_anonymise")
