"""The study id a project row is: the one its output folder's marker carries.

A study's database lives inside its folder, so it travels with every move,
rename and copy; ``projects.study_id`` records which study the row is, read from
``<output>/.bristlenose/study.json`` at import (``docs/design-project-identity.md``
§3–4). Nullable: a row that predates it gets its id at the next import.

Guarded per the Alembic discipline: ``upgrade()`` runs on a fresh DB too, after
``create_all()`` built the column.

Revision ID: 019
Revises: 018
Create Date: 2026-10-15
"""

import sqlalchemy as sa
from alembic import op

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if "study_id" not in _columns("projects"):
        op.add_column("projects", sa.Column("study_id", sa.String(36), nullable=True))


def downgrade() -> None:
    op.drop_column("projects", "study_id")
