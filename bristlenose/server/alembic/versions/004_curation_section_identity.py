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

Guarded per the project's Alembic discipline.  Note ``init_db`` runs
``create_all()`` *then* ``run_migrations``, which stamps 001 and upgrades to
head — so ``upgrade()`` DOES run on a fresh DB.  It is inert there because the
guards short-circuit: ``create_all`` built the constraint-free schema (models.py
no longer declares the constraints) so ``_unique_constraint_names`` is empty and
the batch drops are skipped, and ``heading_edits`` is empty so the re-key loop
matches nothing.  Safety comes from those guards, not from a skipped upgrade().

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
    # Live (project_id, heading_key) set, to skip a re-key that would collide
    # with an existing row.  heading_edits has UNIQUE(project_id, heading_key),
    # so a colliding UPDATE would raise IntegrityError and abort the whole
    # migration; instead we leave the source row un-rekeyed (documented loss).
    live_keys = {(pid, key) for _eid, pid, key in edits}
    for eid, pid, key in edits:
        if ":" not in key:
            continue
        prefix, field = key.rsplit(":", 1)
        new_key = None
        # Consult the slug map for EVERY section-/theme- key, including ones
        # already shaped like the durable namespace.  On a rev-003 DB the
        # frontend never emitted a genuine "section-cluster-{id}" key (that key
        # form only exists post-Phase-2), so a key like "section-cluster-7"
        # present here is a *legacy* slug for a section literally labelled
        # "Cluster 7" (the pipeline's own f"Cluster {i+1}" fallback) and must be
        # re-keyed to that section's real id, not skipped.
        if prefix.startswith("section-"):
            cid = cluster_by_slug.get((pid, prefix[len("section-"):]))
            if cid is not None:
                new_key = f"section-cluster-{cid}:{field}"
        elif prefix.startswith("theme-"):
            tid = theme_by_slug.get((pid, prefix[len("theme-"):]))
            if tid is not None:
                new_key = f"theme-group-{tid}:{field}"
        if new_key is None or new_key == key:
            continue
        if (pid, new_key) in live_keys:
            logger.warning(
                "004: re-key %r -> %r collides with an existing heading_key; "
                "leaving un-rekeyed (one-time loss).", key, new_key
            )
            continue
        bind.execute(
            sa.text("UPDATE heading_edits SET heading_key = :k WHERE id = :i"),
            {"k": new_key, "i": eid},
        )
        live_keys.discard((pid, key))
        live_keys.add((pid, new_key))


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported")
