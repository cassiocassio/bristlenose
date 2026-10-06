"""Split and join of transcript paragraphs, replayed on every import.

``design-transcript-editing.md`` §"Split and join, stage 1". A new table: the
researcher's split or join of a session's paragraphs, which the importer
replays after it rebuilds the paragraphs from the pipeline's transcript.

Guarded per the Alembic discipline: ``upgrade()`` runs on a fresh DB too, after
``create_all()`` built the table.

Revision ID: 015
Revises: 014
Create Date: 2026-10-06
"""

import sqlalchemy as sa
from alembic import op

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "transcript_layout_edits" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "transcript_layout_edits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("token", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("verify", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_transcript_layout_edits_session_id", "transcript_layout_edits", ["session_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_transcript_layout_edits_session_id", "transcript_layout_edits")
    op.drop_table("transcript_layout_edits")
