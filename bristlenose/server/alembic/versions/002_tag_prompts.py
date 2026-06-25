"""Tag prompts — dynamic codebook builder.

Adds two tables for cultivating a researcher's tag into a code with operational
boundaries:

- ``tag_prompts`` — the learned inclusion/exclusion prompt (one per tag)
- ``tag_prompt_decisions`` — each accept/reject judgement with its local reason

Guarded create: ``init_db`` runs ``create_all()`` *before* this migration, so on
both fresh and recently-created databases these tables already exist by the time
we get here. We create them only when absent, which keeps the migration usable
standalone (e.g. ``alembic upgrade`` without a prior ``create_all``) while never
double-creating.

Revision ID: 002
Revises: 001
Create Date: 2026-06-25
"""

import sqlalchemy as sa
from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    return name in sa.inspect(bind).get_table_names()


def upgrade() -> None:
    if not _has_table("tag_prompts"):
        op.create_table(
            "tag_prompts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "tag_definition_id",
                sa.Integer(),
                sa.ForeignKey("tag_definitions.id"),
                nullable=False,
            ),
            sa.Column("summary", sa.Text(), nullable=False, server_default=""),
            sa.Column("definition", sa.Text(), nullable=False, server_default=""),
            sa.Column("apply_when", sa.Text(), nullable=False, server_default=""),
            sa.Column("not_this", sa.Text(), nullable=False, server_default=""),
            sa.Column("version", sa.String(length=16), nullable=False, server_default=""),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
            sa.Column("example_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        op.create_index(
            "ix_tag_prompts_tag_definition_id",
            "tag_prompts",
            ["tag_definition_id"],
            unique=True,
        )

    if not _has_table("tag_prompt_decisions"):
        op.create_table(
            "tag_prompt_decisions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "tag_definition_id",
                sa.Integer(),
                sa.ForeignKey("tag_definitions.id"),
                nullable=False,
            ),
            sa.Column(
                "quote_id",
                sa.Integer(),
                sa.ForeignKey("quotes.id"),
                nullable=False,
            ),
            sa.Column("decision", sa.String(length=10), nullable=False),
            sa.Column("reason", sa.Text(), nullable=False, server_default=""),
            sa.Column("prompt_version", sa.String(length=16), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
        op.create_index(
            "ix_tag_prompt_decisions_tag_definition_id",
            "tag_prompt_decisions",
            ["tag_definition_id"],
        )
        op.create_index(
            "ix_tag_prompt_decisions_quote_id",
            "tag_prompt_decisions",
            ["quote_id"],
        )


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported")
