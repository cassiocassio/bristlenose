"""The project codebook groups that are active for analysis.

Framework enablement is semantic, not visual: a disabled framework must be
absent from both signal calculation and AutoCode maintenance.  Keeping that
rule here prevents the two paths from drifting apart.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.orm import Session

from bristlenose.server.models import (
    UNCATEGORISED_GROUP_NAME,
    CodebookGroup,
    ProjectCodebookGroup,
    ProjectFrameworkState,
)


def active_project_groups(
    db: Session,
    project_id: int,
    *,
    group_ids: Sequence[int] | None = None,
) -> list[CodebookGroup]:
    """Return installed, enabled, non-uncategorised groups in project order.

    ``group_ids`` narrows the installed set without providing an escape hatch
    around framework disablement.  Custom groups have no framework id and stay
    active unless their project link is removed.
    """
    links = (
        db.query(ProjectCodebookGroup)
        .filter_by(project_id=project_id)
        .order_by(ProjectCodebookGroup.sort_order)
        .all()
    )
    linked_ids = [link.codebook_group_id for link in links]
    if group_ids is not None:
        wanted = set(group_ids)
        linked_ids = [group_id for group_id in linked_ids if group_id in wanted]
    if not linked_ids:
        return []

    disabled_frameworks = {
        framework_id
        for (framework_id,) in (
            db.query(ProjectFrameworkState.framework_id)
            .filter_by(project_id=project_id, enabled=False)
            .all()
        )
    }
    groups_by_id = {
        group.id: group
        for group in db.query(CodebookGroup)
        .filter(CodebookGroup.id.in_(linked_ids))
        .filter(CodebookGroup.name != UNCATEGORISED_GROUP_NAME)
        .all()
    }
    return [
        group
        for group_id in linked_ids
        if (group := groups_by_id.get(group_id)) is not None
        and group.framework_id not in disabled_frameworks
    ]


def maintained_framework_ids(db: Session, project_id: int) -> set[str]:
    """Framework ids which remain installed and enabled for AutoCode upkeep."""
    return {
        group.framework_id
        for group in active_project_groups(db, project_id)
        if group.framework_id is not None
    }
