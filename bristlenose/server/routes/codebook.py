"""Codebook API endpoints — CRUD for codebook groups, tags, merge, and templates."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from bristlenose.server.codebook import CODEBOOK_TEMPLATES, get_template
from bristlenose.server.models import (
    _LEGACY_UNGROUPED_NAME,
    UNCATEGORISED_GROUP_NAME,
    UNCATEGORISED_GROUP_SUBTITLE,
    CodebookGroup,
    Project,
    ProjectCodebookGroup,
    QuoteTag,
    TagDefinition,
)

router = APIRouter(prefix="/api")


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class CodebookTagOut(BaseModel):
    id: int
    name: str
    count: int
    colour_index: int


class CodebookGroupOut(BaseModel):
    id: int
    name: str
    subtitle: str
    colour_set: str
    order: int
    tags: list[CodebookTagOut]
    total_quotes: int
    is_default: bool = False
    framework_id: str | None = None


class CodebookResponse(BaseModel):
    groups: list[CodebookGroupOut]
    ungrouped: list[CodebookTagOut]  # deprecated — kept for back-compat, always []
    all_tag_names: list[str]


class CreateGroupRequest(BaseModel):
    name: str
    colour_set: str = "ux"
    subtitle: str = ""


class UpdateGroupRequest(BaseModel):
    name: str | None = None
    subtitle: str | None = None
    colour_set: str | None = None
    order: int | None = None


class CreateTagRequest(BaseModel):
    name: str
    group_id: int | None = None  # defaults to Uncategorised


class UpdateTagRequest(BaseModel):
    name: str | None = None
    group_id: int | None = None


class MergeTagsRequest(BaseModel):
    source_id: int
    target_id: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_db(request: Request) -> Session:
    return request.app.state.db_factory()


def _check_project(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _tag_quote_counts(db: Session, tag_ids: list[int]) -> dict[int, int]:
    """Return {tag_definition_id: quote_count} for the given tag IDs."""
    if not tag_ids:
        return {}
    rows = (
        db.query(QuoteTag.tag_definition_id, func.count(QuoteTag.id))
        .filter(QuoteTag.tag_definition_id.in_(tag_ids))
        .group_by(QuoteTag.tag_definition_id)
        .all()
    )
    return {tid: cnt for tid, cnt in rows}


def _get_or_create_uncategorised(db: Session) -> CodebookGroup:
    """Return the default 'Uncategorised' codebook group, creating if needed.

    Also migrates the legacy 'Ungrouped' name from older databases.
    """
    group = db.query(CodebookGroup).filter_by(name=UNCATEGORISED_GROUP_NAME).first()
    if group:
        return group
    # Migrate legacy "Ungrouped" → "Uncategorised"
    legacy = db.query(CodebookGroup).filter_by(name=_LEGACY_UNGROUPED_NAME).first()
    if legacy:
        legacy.name = UNCATEGORISED_GROUP_NAME
        legacy.subtitle = UNCATEGORISED_GROUP_SUBTITLE
        db.flush()
        return legacy
    group = CodebookGroup(
        name=UNCATEGORISED_GROUP_NAME,
        subtitle=UNCATEGORISED_GROUP_SUBTITLE,
        colour_set="",
    )
    db.add(group)
    db.flush()
    return group


def _ensure_project_link(db: Session, project_id: int, group_id: int) -> None:
    """Ensure a ProjectCodebookGroup link exists for this project+group."""
    existing = (
        db.query(ProjectCodebookGroup)
        .filter_by(project_id=project_id, codebook_group_id=group_id)
        .first()
    )
    if not existing:
        max_order = (
            db.query(func.max(ProjectCodebookGroup.sort_order))
            .filter_by(project_id=project_id)
            .scalar()
        ) or 0
        db.add(ProjectCodebookGroup(
            project_id=project_id,
            codebook_group_id=group_id,
            sort_order=max_order + 1,
        ))


# ---------------------------------------------------------------------------
# GET /projects/{id}/codebook
# ---------------------------------------------------------------------------


@router.get("/projects/{project_id}/codebook")
def get_codebook(project_id: int, request: Request) -> CodebookResponse:
    """Return codebook groups, tags, and quote counts for a project."""
    db = _get_db(request)
    try:
        _check_project(db, project_id)

        # Ensure the Uncategorised default group exists and is linked
        uncategorised = _get_or_create_uncategorised(db)
        _ensure_project_link(db, project_id, uncategorised.id)
        db.commit()

        # Get all codebook groups linked to this project
        pcg_rows = (
            db.query(ProjectCodebookGroup)
            .filter_by(project_id=project_id)
            .order_by(ProjectCodebookGroup.sort_order)
            .all()
        )
        group_ids = [pcg.codebook_group_id for pcg in pcg_rows]

        # Load groups and their tags
        groups_map: dict[int, CodebookGroup] = {}
        all_tag_ids: list[int] = []
        for gid in group_ids:
            g = db.get(CodebookGroup, gid)
            if g:
                groups_map[gid] = g
                for td in g.tag_definitions:
                    all_tag_ids.append(td.id)

        # Get quote counts per tag (single query)
        counts = _tag_quote_counts(db, all_tag_ids)

        # Build response — Uncategorised is included as a regular group
        # with is_default=True, rendered last.
        group_list: list[CodebookGroupOut] = []
        all_tag_names: list[str] = []

        def _build_group(
            g: CodebookGroup, order: int, *, is_default: bool = False,
        ) -> CodebookGroupOut:
            tags_out: list[CodebookTagOut] = []
            seen_quotes: set[int] = set()
            for i, td in enumerate(g.tag_definitions):
                tag_count = counts.get(td.id, 0)
                tags_out.append(CodebookTagOut(
                    id=td.id, name=td.name, count=tag_count, colour_index=i,
                ))
                all_tag_names.append(td.name)
                qt_rows = (
                    db.query(QuoteTag.quote_id)
                    .filter_by(tag_definition_id=td.id)
                    .all()
                )
                seen_quotes.update(r[0] for r in qt_rows)
            return CodebookGroupOut(
                id=g.id,
                name=g.name,
                subtitle=g.subtitle,
                colour_set=g.colour_set,
                order=order,
                tags=tags_out,
                total_quotes=len(seen_quotes),
                is_default=is_default,
                framework_id=g.framework_id,
            )

        # User-created groups first
        for pcg in pcg_rows:
            g = groups_map.get(pcg.codebook_group_id)
            if not g or g.name == UNCATEGORISED_GROUP_NAME:
                continue
            group_list.append(_build_group(g, pcg.sort_order))

        # Uncategorised always last
        group_list.append(
            _build_group(uncategorised, 9999, is_default=True),
        )

        return CodebookResponse(
            groups=group_list,
            ungrouped=[],  # deprecated — kept for back-compat
            all_tag_names=sorted(set(all_tag_names)),
        )
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Group CRUD
# ---------------------------------------------------------------------------


@router.post("/projects/{project_id}/codebook/groups")
def create_group(
    project_id: int, request: Request, body: CreateGroupRequest,
) -> CodebookGroupOut:
    """Create a new codebook group and link it to the project."""
    db = _get_db(request)
    try:
        _check_project(db, project_id)
        max_order = (
            db.query(func.max(ProjectCodebookGroup.sort_order))
            .filter_by(project_id=project_id)
            .scalar()
        ) or 0
        group = CodebookGroup(
            name=body.name,
            subtitle=body.subtitle,
            colour_set=body.colour_set,
            sort_order=max_order + 1,
        )
        db.add(group)
        db.flush()
        db.add(ProjectCodebookGroup(
            project_id=project_id,
            codebook_group_id=group.id,
            sort_order=max_order + 1,
        ))
        db.commit()
        return CodebookGroupOut(
            id=group.id,
            name=group.name,
            subtitle=group.subtitle,
            colour_set=group.colour_set,
            order=max_order + 1,
            tags=[],
            total_quotes=0,
        )
    finally:
        db.close()


@router.patch("/projects/{project_id}/codebook/groups/{group_id}")
def update_group(
    project_id: int, group_id: int, request: Request, body: UpdateGroupRequest,
) -> dict[str, str]:
    """Update a codebook group's name, subtitle, colour_set, or order."""
    db = _get_db(request)
    try:
        _check_project(db, project_id)
        group = db.get(CodebookGroup, group_id)
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")
        # Block editing name/subtitle of the default Uncategorised group
        if group.name == UNCATEGORISED_GROUP_NAME:
            if body.name is not None or body.subtitle is not None:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot rename the Uncategorised group",
                )
        # Block editing name/subtitle of framework groups
        if group.framework_id is not None:
            if body.name is not None or body.subtitle is not None:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot rename framework codebook groups",
                )
        if body.name is not None:
            group.name = body.name
        if body.subtitle is not None:
            group.subtitle = body.subtitle
        if body.colour_set is not None:
            group.colour_set = body.colour_set
        if body.order is not None:
            pcg = (
                db.query(ProjectCodebookGroup)
                .filter_by(project_id=project_id, codebook_group_id=group_id)
                .first()
            )
            if pcg:
                pcg.sort_order = body.order
        db.commit()
        return {"status": "ok"}
    finally:
        db.close()


@router.delete("/projects/{project_id}/codebook/groups/{group_id}")
def delete_group(
    project_id: int, group_id: int, request: Request,
) -> dict[str, str]:
    """Delete a codebook group. Moves its tags to Ungrouped."""
    db = _get_db(request)
    try:
        _check_project(db, project_id)
        group = db.get(CodebookGroup, group_id)
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")
        if group.name == UNCATEGORISED_GROUP_NAME:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete the Uncategorised group",
            )
        if group.framework_id is not None:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete framework codebook groups",
            )
        # Move tags to Uncategorised — must flush before deleting the group
        # so SQLAlchemy doesn't try to null-cascade via the relationship.
        uncategorised = _get_or_create_uncategorised(db)
        _ensure_project_link(db, project_id, uncategorised.id)
        tag_ids = [td.id for td in group.tag_definitions]
        if tag_ids:
            db.query(TagDefinition).filter(
                TagDefinition.id.in_(tag_ids),
            ).update({TagDefinition.codebook_group_id: uncategorised.id})
            db.flush()
        # Expire the relationship so delete won't try to null-cascade
        db.expire(group, ["tag_definitions"])
        # Remove project link
        db.query(ProjectCodebookGroup).filter_by(
            project_id=project_id, codebook_group_id=group_id,
        ).delete()
        # Delete the group itself
        db.delete(group)
        db.commit()
        return {"status": "ok"}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tag CRUD
# ---------------------------------------------------------------------------


@router.post("/projects/{project_id}/codebook/tags")
def create_tag(
    project_id: int, request: Request, body: CreateTagRequest,
) -> CodebookTagOut:
    """Create a new tag in the specified codebook group."""
    db = _get_db(request)
    try:
        _check_project(db, project_id)
        # Resolve target group — default to Uncategorised if not specified
        if body.group_id is not None:
            group = db.get(CodebookGroup, body.group_id)
            if not group:
                raise HTTPException(status_code=404, detail="Group not found")
            target_group_id = body.group_id
        else:
            uncategorised = _get_or_create_uncategorised(db)
            _ensure_project_link(db, project_id, uncategorised.id)
            group = uncategorised
            target_group_id = uncategorised.id
        # Duplicate guard (case-insensitive within this project)
        pcg_rows = (
            db.query(ProjectCodebookGroup)
            .filter_by(project_id=project_id)
            .all()
        )
        project_group_ids = [pcg.codebook_group_id for pcg in pcg_rows]
        existing = (
            db.query(TagDefinition)
            .filter(
                TagDefinition.codebook_group_id.in_(project_group_ids),
                func.lower(TagDefinition.name) == body.name.strip().lower(),
            )
            .first()
        )
        if existing:
            raise HTTPException(status_code=409, detail="Tag name already exists")
        colour_index = len(group.tag_definitions)
        td = TagDefinition(name=body.name.strip(), codebook_group_id=target_group_id)
        db.add(td)
        db.flush()
        _ensure_project_link(db, project_id, target_group_id)
        db.commit()
        return CodebookTagOut(id=td.id, name=td.name, count=0, colour_index=colour_index)
    finally:
        db.close()


@router.patch("/projects/{project_id}/codebook/tags/{tag_id}")
def update_tag(
    project_id: int, tag_id: int, request: Request, body: UpdateTagRequest,
) -> dict[str, str]:
    """Rename a tag or move it to a different group."""
    db = _get_db(request)
    try:
        _check_project(db, project_id)
        td = db.get(TagDefinition, tag_id)
        if not td:
            raise HTTPException(status_code=404, detail="Tag not found")
        if body.name is not None:
            # Duplicate guard
            pcg_rows = (
                db.query(ProjectCodebookGroup)
                .filter_by(project_id=project_id)
                .all()
            )
            project_group_ids = [pcg.codebook_group_id for pcg in pcg_rows]
            existing = (
                db.query(TagDefinition)
                .filter(
                    TagDefinition.id != tag_id,
                    TagDefinition.codebook_group_id.in_(project_group_ids),
                    func.lower(TagDefinition.name) == body.name.strip().lower(),
                )
                .first()
            )
            if existing:
                raise HTTPException(status_code=409, detail="Tag name already exists")
            td.name = body.name.strip()
        if body.group_id is not None:
            group = db.get(CodebookGroup, body.group_id)
            if not group:
                raise HTTPException(status_code=404, detail="Target group not found")
            td.codebook_group_id = body.group_id
        db.commit()
        return {"status": "ok"}
    finally:
        db.close()


@router.delete("/projects/{project_id}/codebook/tags/{tag_id}")
def delete_tag(
    project_id: int, tag_id: int, request: Request,
) -> dict[str, str]:
    """Delete a tag and all its QuoteTag associations."""
    db = _get_db(request)
    try:
        _check_project(db, project_id)
        td = db.get(TagDefinition, tag_id)
        if not td:
            raise HTTPException(status_code=404, detail="Tag not found")
        # Remove all QuoteTag associations
        db.query(QuoteTag).filter_by(tag_definition_id=tag_id).delete()
        db.delete(td)
        db.commit()
        return {"status": "ok"}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Merge tags
# ---------------------------------------------------------------------------


@router.post("/projects/{project_id}/codebook/merge-tags")
def merge_tags(
    project_id: int, request: Request, body: MergeTagsRequest,
) -> dict[str, str]:
    """Merge source tag into target: reassign QuoteTags, delete source."""
    db = _get_db(request)
    try:
        _check_project(db, project_id)
        source = db.get(TagDefinition, body.source_id)
        target = db.get(TagDefinition, body.target_id)
        if not source:
            raise HTTPException(status_code=404, detail="Source tag not found")
        if not target:
            raise HTTPException(status_code=404, detail="Target tag not found")
        if source.id == target.id:
            raise HTTPException(status_code=400, detail="Cannot merge a tag with itself")
        # Get existing target quote IDs to avoid duplicates
        target_quote_ids = {
            row[0] for row in
            db.query(QuoteTag.quote_id).filter_by(tag_definition_id=target.id).all()
        }
        # Reassign source QuoteTags that aren't already on target
        source_qts = db.query(QuoteTag).filter_by(tag_definition_id=source.id).all()
        for qt in source_qts:
            if qt.quote_id in target_quote_ids:
                db.delete(qt)
            else:
                qt.tag_definition_id = target.id
        # Delete source tag
        db.delete(source)
        db.commit()
        return {"status": "ok"}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Codebook templates
# ---------------------------------------------------------------------------


class TemplateTagOut(BaseModel):
    name: str
    colour_set: str
    colour_index: int


class TemplateGroupOut(BaseModel):
    name: str
    subtitle: str
    colour_set: str
    tags: list[TemplateTagOut]


class TemplateOut(BaseModel):
    id: str
    title: str
    author: str
    description: str
    author_bio: str
    author_links: list[dict[str, str]]
    groups: list[TemplateGroupOut]
    enabled: bool
    imported: bool


class TemplateListResponse(BaseModel):
    templates: list[TemplateOut]


class ImportTemplateRequest(BaseModel):
    template_id: str


def _template_to_out(
    tmpl: object, *, imported: bool,
) -> TemplateOut:
    """Convert a CodebookTemplate dataclass to a TemplateOut response."""
    from bristlenose.server.codebook import CodebookTemplate

    t: CodebookTemplate = tmpl  # type: ignore[assignment]
    groups_out: list[TemplateGroupOut] = []
    for g in t.groups:
        tags_out = [
            TemplateTagOut(name=tag.name, colour_set=g.colour_set, colour_index=i)
            for i, tag in enumerate(g.tags)
        ]
        groups_out.append(TemplateGroupOut(
            name=g.name, subtitle=g.subtitle, colour_set=g.colour_set, tags=tags_out,
        ))
    return TemplateOut(
        id=t.id,
        title=t.title,
        author=t.author,
        description=t.description,
        author_bio=t.author_bio,
        author_links=[{"label": lbl, "url": url} for lbl, url in t.author_links],
        groups=groups_out,
        enabled=t.enabled,
        imported=imported,
    )


@router.get("/projects/{project_id}/codebook/templates")
def list_templates(
    project_id: int, request: Request,
) -> TemplateListResponse:
    """Return available codebook templates with imported status."""
    db = _get_db(request)
    try:
        _check_project(db, project_id)

        # Find which framework IDs are already imported for this project
        pcg_rows = (
            db.query(ProjectCodebookGroup)
            .filter_by(project_id=project_id)
            .all()
        )
        group_ids = [pcg.codebook_group_id for pcg in pcg_rows]
        imported_ids: set[str] = set()
        if group_ids:
            fw_rows = (
                db.query(CodebookGroup.framework_id)
                .filter(
                    CodebookGroup.id.in_(group_ids),
                    CodebookGroup.framework_id.isnot(None),
                )
                .distinct()
                .all()
            )
            imported_ids = {r[0] for r in fw_rows}

        templates_out = [
            _template_to_out(t, imported=t.id in imported_ids)
            for t in CODEBOOK_TEMPLATES
        ]
        return TemplateListResponse(templates=templates_out)
    finally:
        db.close()


@router.post("/projects/{project_id}/codebook/import-template")
def import_template(
    project_id: int, request: Request, body: ImportTemplateRequest,
) -> CodebookResponse:
    """Import a codebook template into the project."""
    db = _get_db(request)
    try:
        _check_project(db, project_id)

        tmpl = get_template(body.template_id)
        if not tmpl:
            raise HTTPException(status_code=404, detail="Template not found")
        if not tmpl.enabled:
            raise HTTPException(status_code=400, detail="Template is not yet available")

        # Check if already imported
        pcg_rows = (
            db.query(ProjectCodebookGroup)
            .filter_by(project_id=project_id)
            .all()
        )
        group_ids = [pcg.codebook_group_id for pcg in pcg_rows]
        if group_ids:
            existing = (
                db.query(CodebookGroup)
                .filter(
                    CodebookGroup.id.in_(group_ids),
                    CodebookGroup.framework_id == body.template_id,
                )
                .first()
            )
            if existing:
                raise HTTPException(
                    status_code=409,
                    detail="Template already imported",
                )

        # Get max sort order for framework groups (place after researcher groups)
        max_order = (
            db.query(func.max(ProjectCodebookGroup.sort_order))
            .filter_by(project_id=project_id)
            .scalar()
        ) or 0

        # Create groups and tags
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
        db.commit()

        # Return updated codebook
        return get_codebook(project_id, request)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Remove a framework
# ---------------------------------------------------------------------------


class RemoveFrameworkInfo(BaseModel):
    """Impact stats returned before/during framework removal."""

    tag_count: int
    quote_count: int


@router.delete("/projects/{project_id}/codebook/remove-framework/{framework_id}")
def remove_framework(
    project_id: int, framework_id: str, request: Request,
) -> CodebookResponse:
    """Remove all groups belonging to a framework from the project.

    Deletes framework groups, their tag definitions, and any quote-tag
    associations.  The framework can be re-imported afterwards.
    """
    db = _get_db(request)
    try:
        _check_project(db, project_id)

        # Find all groups for this framework in this project
        pcg_rows = (
            db.query(ProjectCodebookGroup)
            .filter_by(project_id=project_id)
            .all()
        )
        group_ids = [pcg.codebook_group_id for pcg in pcg_rows]
        if not group_ids:
            raise HTTPException(status_code=404, detail="Framework not found")

        fw_groups = (
            db.query(CodebookGroup)
            .filter(
                CodebookGroup.id.in_(group_ids),
                CodebookGroup.framework_id == framework_id,
            )
            .all()
        )
        if not fw_groups:
            raise HTTPException(status_code=404, detail="Framework not found")

        fw_group_ids = [g.id for g in fw_groups]

        # Collect tag definition IDs
        tag_defs = (
            db.query(TagDefinition)
            .filter(TagDefinition.codebook_group_id.in_(fw_group_ids))
            .all()
        )
        tag_def_ids = [td.id for td in tag_defs]

        # Delete quote-tag associations
        if tag_def_ids:
            db.query(QuoteTag).filter(
                QuoteTag.tag_definition_id.in_(tag_def_ids),
            ).delete(synchronize_session=False)

        # Delete tag definitions
        if tag_def_ids:
            db.query(TagDefinition).filter(
                TagDefinition.id.in_(tag_def_ids),
            ).delete(synchronize_session=False)

        # Remove project links
        db.query(ProjectCodebookGroup).filter(
            ProjectCodebookGroup.project_id == project_id,
            ProjectCodebookGroup.codebook_group_id.in_(fw_group_ids),
        ).delete(synchronize_session=False)

        # Delete groups
        db.query(CodebookGroup).filter(
            CodebookGroup.id.in_(fw_group_ids),
        ).delete(synchronize_session=False)

        db.commit()
        return get_codebook(project_id, request)
    finally:
        db.close()


@router.get(
    "/projects/{project_id}/codebook/remove-framework/{framework_id}/impact",
)
def remove_framework_impact(
    project_id: int, framework_id: str, request: Request,
) -> RemoveFrameworkInfo:
    """Return impact stats for removing a framework (tag and quote counts)."""
    db = _get_db(request)
    try:
        _check_project(db, project_id)

        pcg_rows = (
            db.query(ProjectCodebookGroup)
            .filter_by(project_id=project_id)
            .all()
        )
        group_ids = [pcg.codebook_group_id for pcg in pcg_rows]
        if not group_ids:
            return RemoveFrameworkInfo(tag_count=0, quote_count=0)

        fw_groups = (
            db.query(CodebookGroup)
            .filter(
                CodebookGroup.id.in_(group_ids),
                CodebookGroup.framework_id == framework_id,
            )
            .all()
        )
        fw_group_ids = [g.id for g in fw_groups]
        if not fw_group_ids:
            return RemoveFrameworkInfo(tag_count=0, quote_count=0)

        tag_defs = (
            db.query(TagDefinition)
            .filter(TagDefinition.codebook_group_id.in_(fw_group_ids))
            .all()
        )
        tag_def_ids = [td.id for td in tag_defs]
        tag_count = len(tag_def_ids)

        quote_count = 0
        if tag_def_ids:
            quote_count = (
                db.query(func.count(func.distinct(QuoteTag.quote_id)))
                .filter(QuoteTag.tag_definition_id.in_(tag_def_ids))
                .scalar()
            ) or 0

        return RemoveFrameworkInfo(tag_count=tag_count, quote_count=quote_count)
    finally:
        db.close()
