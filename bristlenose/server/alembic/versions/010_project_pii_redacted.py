"""Record whether the run that produced this output redacted PII.

Adds ``projects.pii_redacted``. Set at import from the presence of
``transcripts-cooked/`` — a signal that only became trustworthy on 13 Sep 2026,
when stage 7 started clearing that directory on a run that does *not* redact.
Before then it could outlive the setting, and two readers built the report from
a previous run's redacted text with newly-added sessions silently absent.

Stored rather than probed per request: one reader of that signal at import
time instead of a fresh one on every ``/info`` call, and the value then rides
into the offline export, which has no filesystem to probe.

**Not** ``mcp_anonymise`` and not the export Anonymise checkbox, however
similar they sound. Those strip participant *display names* at read/export
time, by the researcher's choice, now. This records that personal detail was
removed from the transcript *text* before analysis, by a pipeline run, and is
not changeable from any surface that reads it.

Default ``false``: redaction is opt-in (decision D1), so every project that
predates this column correctly reads as un-redacted, and the report says
nothing rather than making a claim the manifest cannot support.

Guarded per the Alembic discipline: ``upgrade()`` runs on a fresh DB too, but
``_has_column`` skips the ALTER there (``create_all()`` already made the column
from the model).

Revision ID: 010
Revises: 009
Create Date: 2026-09-13
"""

import sqlalchemy as sa
from alembic import op

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    columns = sa.inspect(op.get_bind()).get_columns(table)
    return any(c["name"] == column for c in columns)


def upgrade() -> None:
    if _has_column("projects", "pii_redacted"):
        return
    op.add_column(
        "projects",
        sa.Column("pii_redacted", sa.Boolean(), nullable=False,
                  server_default=sa.false()),
    )


def downgrade() -> None:
    if _has_column("projects", "pii_redacted"):
        op.drop_column("projects", "pii_redacted")
