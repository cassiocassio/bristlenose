"""The participant a slot held before a recode out of participant.

``docs/design-people.md`` §J7 R2. When a participant's tag turns out to be the
moderator, the slot is pointed at the moderator; the participant's own record
is kept, hidden, and ``session_speakers.participant_person_id`` remembers it,
so the recode's undo points the slot back at exactly that person — names,
persona and notes — without ``/sessions`` ever carrying a participant's uuid.

A plain integer, not a foreign key: a second key to ``persons`` would make the
slot's ``person`` relationship ambiguous.

Guarded per the Alembic discipline: ``upgrade()`` runs on a fresh DB too, after
``create_all()`` built the new shape.

Revision ID: 014
Revises: 013
Create Date: 2026-10-06
"""

import sqlalchemy as sa
from alembic import op

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("session_speakers")}
    if "participant_person_id" not in columns:
        op.add_column(
            "session_speakers",
            sa.Column("participant_person_id", sa.Integer(), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("session_speakers", "participant_person_id")
