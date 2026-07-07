"""Curation persistence — the "New" material flag (Phase 3, 3c).

Adds ``sessions.first_imported_at``, set once when a session is first imported
and never updated.  Drives the "New" badge: a section/theme is New when enough
of its quotes come from a session added more recently than the rest.

Backfill: existing sessions all get the *same* timestamp, so none is falsely
"newer than the rest" — nothing shows New on the first post-upgrade run; a
section/theme lights up only once a genuinely new interview is added on a later
import (that session gets a later ``first_imported_at``).

Guarded per the Alembic discipline: ``upgrade()`` runs on a fresh DB too, but
``_has_column`` skips the ADD and the backfill matches no rows there.

Revision ID: 005
Revises: 004
Create Date: 2026-07-07
"""

import sqlalchemy as sa
from alembic import op

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    return column in {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if not _has_column("sessions", "first_imported_at"):
        op.add_column(
            "sessions", sa.Column("first_imported_at", sa.DateTime(), nullable=True)
        )
    # One shared timestamp for all pre-existing sessions → none is "newer",
    # so nothing is flagged New until a genuinely new interview is added.
    op.get_bind().execute(
        sa.text(
            "UPDATE sessions SET first_imported_at = CURRENT_TIMESTAMP "
            "WHERE first_imported_at IS NULL"
        )
    )


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported")
