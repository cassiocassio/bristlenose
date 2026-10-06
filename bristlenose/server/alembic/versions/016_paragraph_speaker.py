"""A paragraph moved to another speaker of its session.

``docs/design-people.md`` §K. The transcript picker's Paragraph scope moves one
paragraph to another speaker, recorded as a layout edit (``kind = "speaker"``)
beside split and join and replayed the same way. Two columns:

- ``transcript_layout_edits.speaker_code``: the slot the paragraph moves to.
- ``transcript_segments.moved_from``: the slot it was credited to before the
  move, so a quote from those words leaves the evidence (``speaker_slots``)
  while a quote elsewhere in the session stays.

Guarded per the Alembic discipline: ``upgrade()`` runs on a fresh DB too, after
``create_all()`` built the new shape.

Revision ID: 016
Revises: 015
Create Date: 2026-10-06
"""

import sqlalchemy as sa
from alembic import op

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if "speaker_code" not in _columns("transcript_layout_edits"):
        op.add_column(
            "transcript_layout_edits",
            sa.Column("speaker_code", sa.String(20), nullable=False, server_default=""),
        )
    if "moved_from" not in _columns("transcript_segments"):
        op.add_column(
            "transcript_segments",
            sa.Column("moved_from", sa.String(20), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("transcript_segments", "moved_from")
    op.drop_column("transcript_layout_edits", "speaker_code")
