"""AutoCode failure kind — say *why* a job died, not just what was thrown.

``autocode_jobs.error_message`` has always held ``str(exc)`` from a bare
``except Exception``: unclassified, unbounded, and written for a log.  Nothing
downstream could tell "out of credit" from "rate limited" — the exact confusion
``bristlenose/llm/failure_classifier.py`` exists to prevent, and which
``docs/design-pipeline-diagnostic-popover.md`` records as having told a bankrupt
account to wait.

Adds ``failure_kind``, holding an ``LLMFailureKind`` value.  Empty string means
"not classified" — every job that failed before this migration, and any failure
the classifier declines to name.

Guarded per the Alembic discipline: ``upgrade()`` runs on a fresh DB too, where
``create_all()`` has already made the column.

Revision ID: 009
Revises: 008
Create Date: 2026-08-30
"""

import sqlalchemy as sa
from alembic import op

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    return column in {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if not _has_column("autocode_jobs", "failure_kind"):
        op.add_column(
            "autocode_jobs",
            sa.Column(
                "failure_kind",
                sa.String(length=30),
                nullable=False,
                server_default="",
            ),
        )


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported")
