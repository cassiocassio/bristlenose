"""The researcher's arrangements of Screens lens boards, per project.

Until now a custom arrangement lived in the browser's localStorage, which in the Mac app is an
in-memory store per serve session: quitting the app lost every arrangement. One row per version of
a screen (``models.ScreenArrangement``), the arrangement as JSON.

Guarded per the Alembic discipline: ``upgrade()`` runs on a fresh DB too, after ``create_all()``
built the table.

Revision ID: 018
Revises: 017
Create Date: 2026-10-15
"""

import sqlalchemy as sa
from alembic import op

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "screen_arrangements" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "screen_arrangements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("screen_key", sa.Text(), nullable=False),
        sa.Column("session_id", sa.String(64), nullable=False),
        sa.Column("cards", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "screen_key", "session_id", name="uq_screen_arrangement"),
    )


def downgrade() -> None:
    op.drop_table("screen_arrangements")
