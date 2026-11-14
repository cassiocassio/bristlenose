"""Installing a codebook framework into a project: one path for the Import button's route and
for the house default (``autocode_house_default``)."""

from __future__ import annotations

import threading

from sqlalchemy import func
from sqlalchemy.orm import Session

from bristlenose.server.codebook import CodebookTemplate
from bristlenose.server.models import CodebookGroup, ProjectCodebookGroup, TagDefinition


def framework_linked(db: Session, project_id: int, framework_id: str) -> bool:
    """Whether the project has any group of this framework linked: installed, whether or not
    anything has been applied."""
    return (
        db.query(CodebookGroup.id)
        .join(ProjectCodebookGroup, ProjectCodebookGroup.codebook_group_id == CodebookGroup.id)
        .filter(ProjectCodebookGroup.project_id == project_id,
                CodebookGroup.framework_id == framework_id)
        .first()
    ) is not None


def link_framework(db: Session, project_id: int, tmpl: CodebookTemplate) -> None:
    """Link the framework into the project, relinking another project's groups when they exist
    (the groups are instance-scoped) and creating them otherwise. Uncommitted. The caller has
    checked it is not already linked here."""
    pcg_rows = db.query(ProjectCodebookGroup).filter_by(project_id=project_id).all()
    group_ids = {pcg.codebook_group_id for pcg in pcg_rows}
    # Groups for this framework that exist but are not linked HERE.
    #
    # This used to be the "restore path" — uninstall preserved everything and
    # re-import brought it back. D20 option A ended that, so after an
    # uninstall there is nothing of ours left to find.
    #
    # The branch still matters, for a different reason: `CodebookGroup` is
    # **instance-scoped**. If another project still has this framework, its
    # groups survive our uninstall (guarded in `remove_framework`), and
    # reinstalling here must RELINK them rather than create a second set —
    # which would give the instance two Nielsens and split every count.
    unlinked_groups = (
        db.query(CodebookGroup)
        .filter(CodebookGroup.framework_id == tmpl.id)
        .all()
    )
    orphaned = [g for g in unlinked_groups if g.id not in group_ids]

    if orphaned:
        # ── Relink path — the rows belong to another project ─────
        # They may predate a wording revision of the YAML; bring them up
        # to it before linking, so this project never sees stale names.
        from bristlenose.server.codebook_sync import sync_framework_rows

        sync_framework_rows(db, tmpl)
        max_order = (
            db.query(func.max(ProjectCodebookGroup.sort_order))
            .filter_by(project_id=project_id)
            .scalar()
        ) or 0

        for i, g in enumerate(orphaned):
            db.add(ProjectCodebookGroup(
                project_id=project_id,
                codebook_group_id=g.id,
                sort_order=max_order + 1 + i,
            ))

        # The accepted-proposal reset that used to live here is GONE, and
        # removing it fixes a latent cross-project bug rather than merely
        # tidying up. It filtered on `tag_definition_id` alone — and those
        # are instance-scoped — so re-importing here rewrote ANOTHER
        # project's accepted proposals back to pending. Since D20 option A
        # our own proposals are deleted at uninstall, there is nothing of
        # ours to reset, and the only rows it could still reach belong to
        # someone else. Same shape as A1, one table over.

        return

    # ── Fresh import path (unchanged) ───────────────────────────
    max_order = (
        db.query(func.max(ProjectCodebookGroup.sort_order))
        .filter_by(project_id=project_id)
        .scalar()
    ) or 0

    for i, tg in enumerate(tmpl.groups):
        group = CodebookGroup(
            name=tg.name,
            subtitle=tg.subtitle,
            colour_set=tg.colour_set,
            sort_order=max_order + 1 + i,
            framework_id=tmpl.id,
        )
        db.add(group)
        db.flush()
        for tt in tg.tags:
            db.add(TagDefinition(name=tt.name, codebook_group_id=group.id))
        db.add(ProjectCodebookGroup(
            project_id=project_id,
            codebook_group_id=group.id,
            sort_order=max_order + 1 + i,
        ))


#: Import is a threadpool route and the house default runs on the event loop, so "not linked yet"
#: and the link must be one step, or both pass the check and the instance holds two sets.
_INSTALL_LOCK = threading.Lock()


def link_framework_once(db: Session, project_id: int, tmpl: CodebookTemplate) -> bool:
    """Link and commit unless the framework is already linked here. True when this call did."""
    with _INSTALL_LOCK:
        if framework_linked(db, project_id, tmpl.id):
            return False
        link_framework(db, project_id, tmpl)
        db.commit()
        return True
