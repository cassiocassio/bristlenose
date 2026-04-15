"""Baseline — represents the v0.14.x schema with all manual migrations applied.

This is a no-op: existing databases already have the full schema from
``create_all()`` + ``_migrate_schema()``.  Fresh databases get the full
schema from ``create_all()`` alone (models.py already includes every column).

Revision ID: 001
Create Date: 2026-04-15
"""

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    raise NotImplementedError("Downgrade to pre-Alembic state is not supported")
