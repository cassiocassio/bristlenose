"""Curation persistence — Section identity (Phase 2).

Section/theme identity moves from the label to *membership* (which quotes the
group holds).  Two coordinated changes:

1. Drop the label-unique constraints on ``screen_clusters`` / ``theme_groups``.
   The label is no longer identity — it is free to drift or collide across
   re-imports — so a unique constraint on it would crash the membership upsert
   when a genuinely-new section reuses a retiring section's label.

2. Re-key ``heading_edits`` from the label slug to the durable cluster/theme id
   (``section-{slug}:title`` -> ``section-cluster-{id}:title``,
   ``theme-{slug}:title`` -> ``theme-group-{id}:title``) so a researcher's
   rename survives label drift.  A row whose slug no longer matches any current
   label can't be reconstructed and is left as-is (a one-time loss, documented
   in the plan) — it simply stops applying.

Guarded per the project's Alembic discipline: on a brand-new DB ``create_all()``
builds the constraint-free schema (models.py no longer declares the
constraints) and ``run_migrations`` stamps head *without* calling ``upgrade()``,
so this only ever runs against real pre-existing data.

Revision ID: 004
Revises: 003
Create Date: 2026-07-06
"""

import logging

import sqlalchemy as sa
from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.runtime.migration")


def _slug(label: str) -> str:
    """Match the frontend anchor slug: lowercase, spaces -> hyphens."""
    return label.lower().replace(" ", "-")


def _slug_map(rows: list) -> dict:
    """Build ``(project_id, slug) -> id``, dropping ambiguous slugs.

    Now that the label-unique constraint is gone, two groups can slugify to the
    same key; a rename on such a slug can't be attributed to one id, so we drop
    the key (the row falls into the documented "unreconstructable, left as-is"
    branch) and log it rather than re-keying to an arbitrary winner.
    """
    m: dict = {}
    collided: set = set()
    for gid, pid, label in rows:
        key = (pid, _slug(label))
        if key in m and m[key] != gid:
            collided.add(key)
        m[key] = gid
    for key in collided:
        del m[key]
        logger.warning(
            "004: slug %r is ambiguous (multiple groups); leaving any rename "
            "on it un-rekeyed (one-time loss).", key[1]
        )
    return m


def _unique_constraint_names(table: str) -> set[str]:
    insp = sa.inspect(op.get_bind())
    return {uc["name"] for uc in insp.get_unique_constraints(table)}


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Drop the label-unique constraints (identity is now membership).
    if "uq_cluster_project_label" in _unique_constraint_names("screen_clusters"):
        with op.batch_alter_table("screen_clusters") as batch_op:
            batch_op.drop_constraint("uq_cluster_project_label", type_="unique")
    if "uq_theme_project_label" in _unique_constraint_names("theme_groups"):
        with op.batch_alter_table("theme_groups") as batch_op:
            batch_op.drop_constraint("uq_theme_project_label", type_="unique")

    # 2. Re-key HeadingEdit rows: label slug -> durable id.
    clusters = bind.execute(
        sa.text("SELECT id, project_id, screen_label FROM screen_clusters")
    ).fetchall()
    themes = bind.execute(
        sa.text("SELECT id, project_id, theme_label FROM theme_groups")
    ).fetchall()
    cluster_by_slug = _slug_map(clusters)
    theme_by_slug = _slug_map(themes)

    edits = bind.execute(
        sa.text("SELECT id, project_id, heading_key FROM heading_edits")
    ).fetchall()
    for eid, pid, key in edits:
        if ":" not in key:
            continue
        prefix, field = key.rsplit(":", 1)
        new_key = None
        if prefix.startswith("section-") and not prefix.startswith("section-cluster-"):
            cid = cluster_by_slug.get((pid, prefix[len("section-"):]))
            if cid is not None:
                new_key = f"section-cluster-{cid}:{field}"
        elif prefix.startswith("theme-") and not prefix.startswith("theme-group-"):
            tid = theme_by_slug.get((pid, prefix[len("theme-"):]))
            if tid is not None:
                new_key = f"theme-group-{tid}:{field}"
        if new_key is not None and new_key != key:
            bind.execute(
                sa.text(
                    "UPDATE heading_edits SET heading_key = :k WHERE id = :i"
                ),
                {"k": new_key, "i": eid},
            )


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported")
