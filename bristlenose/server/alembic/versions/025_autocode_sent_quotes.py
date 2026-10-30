"""AutoCode sent-quote register — which quotes a codebook has sent (ruling 4).

Migration 022 recorded one row per (codebook, session) whose quotes were sent. A
session counted as done whatever it held, so a quote added to it afterwards (N89),
and a quote that was hidden when the codebook was applied and unhidden later
(N175), were never sent, and nothing said why.

Adds ``autocode_sent_quotes``: one row per (job, quote) that went to the model in
a batch that answered. A quote that counts and has no row is owed. Drops
``autocode_session_stamps``, which this replaces.

Backfill, from what the database can still say:

- every proposal is a quote that was sent (its job, its quote);
- every quote of a stamped session was sent, EXCEPT the ones that do not count
  right now: a hidden quote, and a quote of a participant tag recoded as a
  moderator or observer. Since 25 Oct 2026 (N175) AutoCode has not sent those, so a
  stamped session did not hold them. They are left off the register, which is what lets
  unhiding or undoing the recode find them owed.

A quote the model declined to tag in a stamped session is on the register (the
stamp covered it): marking it owed would pay for every coded session again.

Two residuals, said so. A quote has no first-import time, so one added to a
stamped session before this upgrade cannot be told from one that was sent, and is
backfilled as sent: N89 is closed from here on, not for what it already did. A
quote moved off its participant one paragraph at a time
(``speaker_slots._moved_quotes``) is not recoverable in SQL and is backfilled as
sent, which it was before the move.

Guarded per the Alembic discipline: ``upgrade()`` runs on a fresh DB too, where
``create_all()`` has already made the new table and never made the old one.

Revision ID: 025
Revises: 024
Create Date: 2026-10-30
"""

import sqlalchemy as sa
from alembic import op

revision = "025"
down_revision = "024"
branch_labels = None
depends_on = None


def _has_table(table: str) -> bool:
    return table in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if not _has_table("autocode_sent_quotes"):
        op.create_table(
            "autocode_sent_quotes",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "job_id", sa.Integer(), sa.ForeignKey("autocode_jobs.id"), nullable=False,
            ),
            sa.Column(
                "quote_id", sa.Integer(), sa.ForeignKey("quotes.id"), nullable=False,
            ),
            sa.Column(
                "sent_at", sa.DateTime(), nullable=False, server_default=sa.func.now(),
            ),
            sa.UniqueConstraint("job_id", "quote_id", name="uq_autocode_sent_job_quote"),
        )
        op.create_index(
            "ix_autocode_sent_quotes_job_id", "autocode_sent_quotes", ["job_id"],
        )
        op.create_index(
            "ix_autocode_sent_quotes_quote_id", "autocode_sent_quotes", ["quote_id"],
        )

    # A proposal is a quote that was sent: its job's register, whatever happened
    # to the quote since (a proposal on a hidden quote was paid for).
    op.execute(sa.text(
        "INSERT OR IGNORE INTO autocode_sent_quotes (job_id, quote_id, sent_at)"
        " SELECT p.job_id, p.quote_id, COALESCE(p.reviewed_at, j.started_at, CURRENT_TIMESTAMP)"
        " FROM proposed_tags p JOIN autocode_jobs j ON j.id = p.job_id"
    ))

    if _has_table("autocode_session_stamps"):
        # The quotes of a stamped session that count today. ``quote_states`` has a
        # row only for a quote a person touched; no row is not hidden.
        op.execute(sa.text(
            "INSERT OR IGNORE INTO autocode_sent_quotes (job_id, quote_id, sent_at)"
            " SELECT st.job_id, q.id, st.coded_at FROM autocode_session_stamps st"
            " JOIN sessions s ON s.id = st.session_id"
            " JOIN quotes q ON q.project_id = s.project_id AND q.session_id = s.session_id"
            " WHERE NOT EXISTS ("
            "   SELECT 1 FROM quote_states qs WHERE qs.quote_id = q.id AND qs.is_hidden = 1)"
            " AND NOT EXISTS ("
            "   SELECT 1 FROM session_speakers sp WHERE sp.session_id = s.id"
            "   AND sp.speaker_code = q.participant_id AND sp.speaker_code LIKE 'p%'"
            "   AND sp.speaker_role IN ('researcher', 'observer'))"
        ))
        op.drop_table("autocode_session_stamps")


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported")
