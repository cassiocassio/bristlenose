"""Reconcile a framework's database rows with its YAML after a wording revision.

A framework codebook (``norman``, ``nielsen`` …) is imported once into
instance-scoped ``CodebookGroup`` / ``TagDefinition`` rows, and from then on
the **YAML** is what AutoCode sends to the model while the **rows** are what
its answers are resolved against (``autocode.build_tag_name_map`` keeps only
names present in both). So renaming a tag in the YAML without touching the
rows makes every proposal for that tag resolve to ``None`` and vanish with a
log warning — on every project that already had the framework installed.

``sync_framework_rows`` closes that gap. For each group and tag in the
template it finds the row by current name, else by any ``renamed_from`` name,
and renames it **in place** so applied ``QuoteTag`` rows and ``ProposedTag``
rows keep their ids; anything the template has and the rows lack is created;
a row the template no longer names is left alone (it may carry the
researcher's tags) unless nothing references it, in which case it is removed.
Researcher-authored groups (``framework_id`` NULL) are never touched.

Called before AutoCode builds its name map, on serve startup for every
installed framework, and on the relink path of ``import_template``.
Idempotent; a second call on synced rows changes nothing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy.orm import Session as SASession

from bristlenose.server.codebook import CodebookTemplate, TemplateGroup, get_template
from bristlenose.server.models import CodebookGroup, ProposedTag, QuoteTag, TagDefinition

logger = logging.getLogger(__name__)


@dataclass
class SyncReport:
    """What one sync did — for logs and tests, never for the UI."""

    framework_id: str
    groups_renamed: list[tuple[str, str]] = field(default_factory=list)
    groups_created: list[str] = field(default_factory=list)
    tags_renamed: list[tuple[str, str]] = field(default_factory=list)
    tags_created: list[str] = field(default_factory=list)
    tags_removed: list[str] = field(default_factory=list)
    tags_retired_kept: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(
            self.groups_renamed or self.groups_created or self.tags_renamed
            or self.tags_created or self.tags_removed
        )


def _key(name: str) -> str:
    return name.lower().strip()


def sync_framework_rows(db: SASession, template: CodebookTemplate) -> SyncReport:
    """Bring the instance's rows for ``template.id`` up to the template. Flushes,
    does not commit — the caller owns the transaction.

    Three passes, in this order, because a rename may cross groups (v1
    ``confirmation`` under Feedback became v2.3 ``safeguard`` under Slips and
    mistakes): every group is resolved first, then every tag is resolved
    against the whole framework's rows, and only then is anything retired.
    Retiring per group as we went would delete ``confirmation`` as unwanted
    by Feedback before Slips and mistakes could claim it.
    """
    report = SyncReport(framework_id=template.id)
    groups = db.query(CodebookGroup).filter_by(framework_id=template.id).all()
    if not groups:
        return report  # never installed on this instance; nothing to reconcile

    # Pass 1 — groups.
    group_by_name: dict[str, CodebookGroup] = {_key(g.name): g for g in groups}
    resolved: list[tuple[CodebookGroup, TemplateGroup]] = []
    for tg in template.groups:
        group = group_by_name.get(_key(tg.name))
        if group is None:
            for old in tg.renamed_from:
                group = group_by_name.get(_key(old))
                if group is not None:
                    report.groups_renamed.append((group.name, tg.name))
                    group.name = tg.name
                    break
        if group is None:
            group = CodebookGroup(
                name=tg.name,
                subtitle=tg.subtitle,
                colour_set=tg.colour_set,
                sort_order=max((g.sort_order for g in groups), default=0) + 1,
                framework_id=template.id,
            )
            db.add(group)
            db.flush()
            groups.append(group)
            report.groups_created.append(tg.name)
        group_by_name[_key(tg.name)] = group
        group.subtitle = tg.subtitle  # subtitle and colour are wording too
        group.colour_set = tg.colour_set
        resolved.append((group, tg))

    # Pass 2 — tags, resolved against every row of the framework.
    rows = (
        db.query(TagDefinition)
        .filter(TagDefinition.codebook_group_id.in_([g.id for g in groups]))
        .all()
    )
    tag_by_name: dict[str, TagDefinition] = {_key(r.name): r for r in rows}
    wanted_ids: set[int] = set()
    for group, tg in resolved:
        for tt in tg.tags:
            row = tag_by_name.get(_key(tt.name))
            if row is None:
                for old in tt.renamed_from:
                    row = tag_by_name.get(_key(old))
                    if row is not None:
                        report.tags_renamed.append((row.name, tt.name))
                        del tag_by_name[_key(old)]
                        row.name = tt.name
                        break
            if row is None:
                row = TagDefinition(name=tt.name, codebook_group_id=group.id)
                db.add(row)
                db.flush()
                report.tags_created.append(tt.name)
            elif row.codebook_group_id != group.id:
                row.codebook_group_id = group.id  # a rename that crossed groups
            tag_by_name[_key(tt.name)] = row
            wanted_ids.add(row.id)

    # Pass 3 — retire what the template no longer names.
    for row in rows:
        if row.id in wanted_ids:
            continue
        referenced = (
            db.query(QuoteTag).filter_by(tag_definition_id=row.id).first() is not None
            or db.query(ProposedTag).filter_by(tag_definition_id=row.id).first() is not None
        )
        if referenced:
            report.tags_retired_kept.append(row.name)
        else:
            db.delete(row)
            report.tags_removed.append(row.name)

    db.flush()
    if report.changed:
        logger.info(
            "codebook %s synced: %d group(s) renamed, %d created; %d tag(s) renamed, "
            "%d created, %d removed, %d retired but kept",
            template.id, len(report.groups_renamed), len(report.groups_created),
            len(report.tags_renamed), len(report.tags_created), len(report.tags_removed),
            len(report.tags_retired_kept),
        )
    return report


def sync_installed_frameworks(db: SASession) -> list[SyncReport]:
    """Sync every framework that has rows on this instance. Used at serve
    startup so a wording revision shows in the UI before any AutoCode run."""
    ids = [
        fid for (fid,) in db.query(CodebookGroup.framework_id)
        .filter(CodebookGroup.framework_id.isnot(None)).distinct().all()
    ]
    reports: list[SyncReport] = []
    for fid in ids:
        template = get_template(fid)
        if template is None:
            continue  # a framework this build no longer ships; leave its rows
        reports.append(sync_framework_rows(db, template))
    db.commit()
    return reports
