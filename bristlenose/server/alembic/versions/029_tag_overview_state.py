"""The tag sidebar overview's remembered state: ``tag_overview_states``.

The AutoCode overview at the top of the tag sidebar opens by itself once, after a
first run, and its open/closed and merged/split are remembered per study, on the
server (docs/design-autocode-landing-plan.md D12, Phase 6). One row per project,
made on the first write; absence means closed, merged and not yet opened by itself,
which is what every study from before this migration is.

A study that already has a finished run (a non-Sentiment AutoCode job no longer coding,
with proposals) is seeded as already opened by itself: the overview opens itself once
after a *first* run, and on an upgrade that run is long past, so no existing study pops
the overview open (D29).

Guarded per the Alembic discipline: ``upgrade()`` runs on a fresh DB too, and
``init_db`` runs ``create_all()`` before the migrations, so the table may already be
there, empty, on an upgraded study: the create is skipped then, the seed never is. The
seed adds rows only for projects that have none.

Revision ID: 029
Revises: 028
Create Date: 2026-11-23
"""

import sqlalchemy as sa
from alembic import op

revision = "029"
down_revision = "028"
branch_labels = None
depends_on = None


def _has_table(table: str) -> bool:
    return table in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if not _has_table("tag_overview_states"):
        _create()
    op.execute(
        sa.text(
            """
            INSERT INTO tag_overview_states (project_id, open, split, auto_opened, updated_at)
            SELECT DISTINCT j.project_id, 0, 0, 1, CURRENT_TIMESTAMP
            FROM autocode_jobs j
            WHERE j.framework_id != 'sentiment'
              AND j.status NOT IN ('pending', 'running')
              AND EXISTS (SELECT 1 FROM proposed_tags p WHERE p.job_id = j.id)
              AND NOT EXISTS (
                SELECT 1 FROM tag_overview_states s WHERE s.project_id = j.project_id
              )
            """
        )
    )


def _create() -> None:
    op.create_table(
        "tag_overview_states",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False, unique=True
        ),
        sa.Column("open", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("split", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("auto_opened", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported")
