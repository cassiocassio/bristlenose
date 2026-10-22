"""AutoCode per-session stamps — which sessions a codebook has coded (RE#66).

One timestamp per codebook, ``AutoCodeJob.completed_at``, said which sessions it
had coded: those first imported at or before it. A pass where some batches
failed still moved it, so the sessions in those batches were never coded by
that codebook again.

Adds ``autocode_session_stamps``: one row per (job, session) whose every quote
was sent in a batch that answered. The backfill stamps what the watermark
claimed, every session first imported at or before ``completed_at`` and those
with no import time (which the watermark never selected), so an upgraded
project's next re-apply sends exactly what it would have sent before.

First, a first apply stopped on an older release is made what a Stop now
leaves (#65): not applied. Until 22 Oct 2026 the Stop set ``completed_at`` to
the Stop time, a watermark past quotes it never coded. Stamped, they would be
coded by nothing, since Apply now refuses a job with ``completed_at``; left
unstamped but applied, the next run would auto-accept the whole uncoded corpus
at the default cutoff with no review, the harm #65 refused. Such a job is told
from a stopped catch-up by its times: a first apply's ``started_at`` is its
creation, before the Stop, while starting a catch-up moves ``started_at`` past
the job's ``completed_at``. A heuristic, said so: a catch-up stopped before
20 Oct 2026, when a Stop still moved ``completed_at``, reads the same; a catch-up
had no Stop button, so none is expected. Its pending proposals stay for review.

Guarded per the Alembic discipline: ``upgrade()`` runs on a fresh DB too, where
``create_all()`` has already made the table (and there is nothing to backfill).

Revision ID: 022
Revises: 021
Create Date: 2026-10-22
"""

import sqlalchemy as sa
from alembic import op

revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


def _has_table(table: str) -> bool:
    return table in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    op.execute(sa.text(
        "UPDATE autocode_jobs SET completed_at = NULL"
        " WHERE status = 'cancelled' AND completed_at IS NOT NULL"
        " AND started_at <= completed_at"
    ))
    if not _has_table("autocode_session_stamps"):
        op.create_table(
            "autocode_session_stamps",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "job_id", sa.Integer(), sa.ForeignKey("autocode_jobs.id"), nullable=False,
            ),
            sa.Column(
                "session_id", sa.Integer(), sa.ForeignKey("sessions.id"), nullable=False,
            ),
            sa.Column(
                "coded_at", sa.DateTime(), nullable=False, server_default=sa.func.now(),
            ),
            sa.UniqueConstraint(
                "job_id", "session_id", name="uq_autocode_stamp_job_session",
            ),
        )
        op.create_index(
            "ix_autocode_session_stamps_job_id", "autocode_session_stamps", ["job_id"],
        )
        op.create_index(
            "ix_autocode_session_stamps_session_id", "autocode_session_stamps", ["session_id"],
        )
    op.execute(sa.text(
        "INSERT OR IGNORE INTO autocode_session_stamps (job_id, session_id, coded_at)"
        " SELECT j.id, s.id, j.completed_at FROM autocode_jobs j"
        " JOIN sessions s ON s.project_id = j.project_id"
        " WHERE j.completed_at IS NOT NULL"
        " AND (s.first_imported_at IS NULL OR s.first_imported_at <= j.completed_at)"
    ))


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported")
