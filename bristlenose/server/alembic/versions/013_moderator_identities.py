"""Route C, Phase 1: one person per identity, and a per-session slot map.

``docs/design-people.md`` §H H9. Moderator and observer codes restart in every
session, so a transcript's ``m1`` is a *slot*. The slot's identity is
``session_speakers.person_id``, now nullable (``None`` renders ``m?``), with:

- ``session_speakers.state`` — ``None`` · ``proposed`` · ``confirmed``. It
  replaces 012's ``name_confirmed``: a confirmed row becomes ``confirmed``,
  every other row ``proposed`` (every existing row has a person).
- ``session_speakers.evidence`` — why the slot points where it does.
- ``persons.code`` (the identity's project-wide label, filled by the importer
  on the next start), ``persons.uuid``, ``persons.origin`` and ``persons.me``.

Existing rows keep one person per slot; the importer joins identities on the
next run that brings evidence. Owner, 3 Oct 2026: existing projects are re-run,
not migrated, so nothing here reads ``people.yaml``.

On a migrated database ``persons.uuid`` stays nullable at the SQL level (it is
backfilled here and always written by the model); a fresh one is ``NOT NULL``.

Guarded per the Alembic discipline: ``upgrade()`` runs on a fresh DB too, after
``create_all()`` built the new shape — but after 012 has added ``name_confirmed``
to it, so that column is dropped whenever present.

Revision ID: 013
Revises: 012
Create Date: 2026-10-04
"""

import uuid

import sqlalchemy as sa
from alembic import op

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()

    persons = _columns("persons")
    if "code" not in persons:
        op.add_column("persons", sa.Column("code", sa.String(20), nullable=True))
    if "origin" not in persons:
        op.add_column("persons", sa.Column("origin", sa.String(20), nullable=True))
    if "me" not in persons:
        op.add_column(
            "persons",
            sa.Column("me", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    if "uuid" not in persons:
        op.add_column("persons", sa.Column("uuid", sa.String(36), nullable=True))
    for (pid,) in bind.execute(sa.text("SELECT id FROM persons WHERE uuid IS NULL")).all():
        bind.execute(
            sa.text("UPDATE persons SET uuid = :u WHERE id = :i"),
            {"u": str(uuid.uuid4()), "i": pid},
        )

    speakers = _columns("session_speakers")
    confirmed = "name_confirmed" in speakers
    if "state" not in speakers:
        with op.batch_alter_table("session_speakers") as batch_op:
            batch_op.alter_column("person_id", existing_type=sa.Integer(), nullable=True)
            batch_op.add_column(sa.Column("state", sa.String(20), nullable=True))
            batch_op.add_column(sa.Column("evidence", sa.String(20), nullable=True))
        bind.execute(sa.text(
            "UPDATE session_speakers SET state = CASE WHEN "
            + ("name_confirmed" if confirmed else "0")
            + " THEN 'confirmed' ELSE 'proposed' END WHERE person_id IS NOT NULL"
        ))
        bind.execute(sa.text(
            "UPDATE session_speakers SET evidence = CASE"
            " WHEN substr(speaker_code, 1, 1) IN ('m', 'o') THEN 'inherited'"
            " ELSE 'participant' END WHERE person_id IS NOT NULL"
        ))
        bind.execute(sa.text(
            "UPDATE persons SET origin = (SELECT CASE"
            " WHEN substr(sp.speaker_code, 1, 1) IN ('m', 'o') THEN 'inherited'"
            " ELSE 'participant' END FROM session_speakers sp"
            " WHERE sp.person_id = persons.id LIMIT 1) WHERE origin IS NULL"
        ))
    # 012 adds this on a fresh DB too (it runs after create_all), so it is
    # dropped whenever present, not only when this revision added ``state``.
    if confirmed:
        with op.batch_alter_table("session_speakers") as batch_op:
            batch_op.drop_column("name_confirmed")


def downgrade() -> None:
    raise NotImplementedError(
        "Downgrade is not supported: an unidentified slot has no person to put back"
    )
