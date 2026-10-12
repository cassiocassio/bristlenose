"""A transcript segment where someone spoke and nothing usable was heard.

Stage 5 marks a line Whisper made up from its own style prompt as inaudible
(``models.TranscriptSegment.inaudible``); the transcript files carry it as
``[inaudible]`` and the importer stores it as this flag with empty text, so
the report draws a gap rather than words nobody said.

Guarded per the Alembic discipline: ``upgrade()`` runs on a fresh DB too, after
``create_all()`` built the new shape.

Revision ID: 017
Revises: 016
Create Date: 2026-10-12
"""

import sqlalchemy as sa
from alembic import op

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if "inaudible" not in _columns("transcript_segments"):
        op.add_column(
            "transcript_segments",
            sa.Column("inaudible", sa.Boolean(), nullable=False, server_default=sa.false()),
        )


def downgrade() -> None:
    op.drop_column("transcript_segments", "inaudible")
