"""Record whether a person has said yes to a speaker's name.

Adds ``session_speakers.name_confirmed``. A name the pipeline found (a platform
transcript's label, the speaker-identification pass) is a *proposal*: the
Sessions grid draws it with a dotted ring and a grey name, and the person
picker's Enter says yes to it. A name a person typed or picked is confirmed.
This is the slot state of route C (``docs/design-people.md`` §H H9), the part
the picker needs.

Not nullable, default false: every name that predates the column is a
proposal until someone confirms it. The owner accepted that existing projects
show their names as proposed (3 Oct 2026: "existing projects — forget").

Guarded per the Alembic discipline: ``upgrade()`` runs on a fresh DB too, but
``_has_column`` skips the ALTER there (``create_all()`` already made it).

Revision ID: 012
Revises: 011
Create Date: 2026-10-04
"""

import sqlalchemy as sa
from alembic import op

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    columns = sa.inspect(op.get_bind()).get_columns(table)
    return any(c["name"] == column for c in columns)


def upgrade() -> None:
    if _has_column("session_speakers", "name_confirmed"):
        return
    op.add_column(
        "session_speakers",
        sa.Column("name_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    if _has_column("session_speakers", "name_confirmed"):
        op.drop_column("session_speakers", "name_confirmed")
