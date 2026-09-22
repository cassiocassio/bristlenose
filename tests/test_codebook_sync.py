"""codebook_sync — a reworded framework YAML must reach rows that were imported
under the old wording, without losing what the researcher applied.

The hazard this pins (see the module docstring): AutoCode sends the YAML's tag
names to the model and resolves the answers against the project's
``TagDefinition`` rows, keeping only names present in both. A rename in the
YAML with untouched rows makes every proposal for that tag resolve to ``None``
and vanish with a log warning, on every instance that already had the
framework installed. norman 2.3 renamed six tags and two groups; 2.4 and 2.5
retired four more, which the sync removes when unreferenced and keeps when a
researcher has used them.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as SASession
from sqlalchemy.orm import sessionmaker

from bristlenose.server.autocode import build_tag_name_map
from bristlenose.server.codebook import (
    CodebookTemplate,
    TemplateGroup,
    TemplateTag,
    get_template,
)
from bristlenose.server.codebook_sync import sync_framework_rows, sync_installed_frameworks
from bristlenose.server.models import (
    AutoCodeJob,
    Base,
    CodebookGroup,
    Project,
    ProjectCodebookGroup,
    ProposedTag,
    Quote,
    QuoteTag,
    TagDefinition,
)

V1_GROUPS: dict[str, list[str]] = {
    # the 20 Feb 2026 norman.yaml, exactly as an instance that imported it holds it
    "Discoverability": ["visible action", "hidden feature", "exploration", "first-time use"],
    "Feedback": ["system response", "delayed feedback", "ambiguous feedback", "confirmation"],
    "Conceptual model": ["user mental model", "system model", "model mismatch", "learned behaviour"],
    "Signifiers": ["affordance", "perceived affordance", "false signifier", "missing signifier"],
    "Mapping": ["natural mapping", "arbitrary mapping", "spatial correspondence", "logical layout"],
    "Constraints": ["physical constraint", "cultural constraint", "semantic constraint", "logical constraint"],
    "Slips vs Mistakes": ["action slip", "memory lapse", "rule-based mistake", "knowledge-based mistake"],
}


@pytest.fixture()
def db() -> SASession:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _install_v1_norman(db: SASession) -> tuple[int, dict[str, int]]:
    """Import v1 rows the way import_template did, return (project_id, name→tag id)."""
    project = Project(name="P", slug="p", input_dir="/tmp/in", output_dir="/tmp/out")
    db.add(project)
    db.flush()
    ids: dict[str, int] = {}
    for i, (gname, tags) in enumerate(V1_GROUPS.items()):
        g = CodebookGroup(name=gname, subtitle="", colour_set="ux", sort_order=i, framework_id="norman")
        db.add(g)
        db.flush()
        db.add(ProjectCodebookGroup(project_id=project.id, codebook_group_id=g.id, sort_order=i))
        for t in tags:
            td = TagDefinition(name=t, codebook_group_id=g.id)
            db.add(td)
            db.flush()
            ids[t] = td.id
    db.commit()
    return project.id, ids


def _quote(db: SASession, project_id: int, n: int) -> Quote:
    q = Quote(
        project_id=project_id, session_id="s1", participant_id="p1",
        start_timecode=float(n), end_timecode=float(n + 1), text=f"q{n}",
        quote_type="screen_specific",
    )
    db.add(q)
    db.flush()
    return q


class TestRenameInPlace:
    def test_v1_rows_become_v23_names_keeping_ids(self, db: SASession) -> None:
        _, ids = _install_v1_norman(db)
        template = get_template("norman")
        assert template is not None

        report = sync_framework_rows(db, template)
        db.commit()

        renamed = dict(report.tags_renamed)
        assert renamed == {
            "system response": "clear feedback",
            "ambiguous feedback": "uninformative feedback",
            "system model": "system image",
            "false signifier": "misleading signifier",
            "confirmation": "safeguard",
        }
        # ids survive: the renamed row IS the old row
        for old, new in renamed.items():
            row = db.get(TagDefinition, ids[old])
            assert row is not None and row.name == new
        assert dict(report.groups_renamed) == {
            "Signifiers": "Affordances and signifiers",
            "Slips vs Mistakes": "Slips and mistakes",
        }

    def test_confirmation_moves_group_with_its_id(self, db: SASession) -> None:
        """v1 'confirmation' sat under Feedback; v2.3 'safeguard' is in Slips and
        mistakes. The rename crosses groups and must carry the row, not copy it."""
        _, ids = _install_v1_norman(db)
        template = get_template("norman")
        assert template is not None
        sync_framework_rows(db, template)
        db.commit()
        row = db.get(TagDefinition, ids["confirmation"])
        assert row is not None and row.name == "safeguard"
        group = db.get(CodebookGroup, row.codebook_group_id)
        assert group is not None and group.name == "Slips and mistakes"

    def test_new_tags_created_and_template_names_all_resolvable(self, db: SASession) -> None:
        _install_v1_norman(db)
        template = get_template("norman")
        assert template is not None
        report = sync_framework_rows(db, template)
        db.commit()
        assert set(report.tags_created) == {
            "knowledge in the world", "no feedback", "excessive feedback",
            "clear signifier", "mode error",
        }
        # The property AutoCode needs: every YAML tag has a row.
        groups = db.query(CodebookGroup).filter_by(framework_id="norman").all()
        rows = db.query(TagDefinition).filter(
            TagDefinition.codebook_group_id.in_([g.id for g in groups])
        ).all()
        lookup = {r.name.lower(): r.id for r in rows}
        tag_map = build_tag_name_map(template, lookup)
        wanted = {t.name.lower() for g in template.groups for t in g.tags}
        assert set(tag_map) == wanted

    def test_retired_tag_removed_when_unreferenced_kept_when_referenced(self, db: SASession) -> None:
        project_id, ids = _install_v1_norman(db)
        q = _quote(db, project_id, 1)
        db.add(QuoteTag(quote_id=q.id, tag_definition_id=ids["perceived affordance"]))
        db.commit()
        template = get_template("norman")
        assert template is not None
        report = sync_framework_rows(db, template)
        db.commit()
        assert report.tags_retired_kept == ["perceived affordance"]
        assert db.get(TagDefinition, ids["perceived affordance"]) is not None

    def test_retired_tag_removed_when_nothing_references_it(self, db: SASession) -> None:
        _, ids = _install_v1_norman(db)
        template = get_template("norman")
        assert template is not None
        report = sync_framework_rows(db, template)
        db.commit()
        assert set(report.tags_removed) == {
            "exploration", "first-time use", "perceived affordance", "learned behaviour", "logical layout",
        }
        assert db.get(TagDefinition, ids["perceived affordance"]) is None

    def test_proposals_survive_a_rename(self, db: SASession) -> None:
        """The whole point: a pending proposal for 'system response' is still a
        proposal for the same row after it becomes 'clear feedback'."""
        project_id, ids = _install_v1_norman(db)
        q = _quote(db, project_id, 2)
        job = AutoCodeJob(project_id=project_id, framework_id="norman", status="completed")
        db.add(job)
        db.flush()
        db.add(ProposedTag(job_id=job.id, quote_id=q.id, tag_definition_id=ids["system response"],
                           confidence=0.8, status="pending"))
        db.commit()
        template = get_template("norman")
        assert template is not None
        sync_framework_rows(db, template)
        db.commit()
        pt = db.query(ProposedTag).one()
        assert db.get(TagDefinition, pt.tag_definition_id).name == "clear feedback"

    def test_idempotent(self, db: SASession) -> None:
        _install_v1_norman(db)
        template = get_template("norman")
        assert template is not None
        sync_framework_rows(db, template)
        db.commit()
        second = sync_framework_rows(db, template)
        assert not second.changed

    def test_not_installed_is_a_no_op(self, db: SASession) -> None:
        template = get_template("norman")
        assert template is not None
        report = sync_framework_rows(db, template)
        assert not report.changed
        assert db.query(CodebookGroup).count() == 0

    def test_researcher_groups_untouched(self, db: SASession) -> None:
        _install_v1_norman(db)
        own = CodebookGroup(name="Signifiers", subtitle="mine", colour_set="ux", framework_id=None)
        db.add(own)
        db.flush()
        db.add(TagDefinition(name="system response", codebook_group_id=own.id))
        db.commit()
        template = get_template("norman")
        assert template is not None
        sync_framework_rows(db, template)
        db.commit()
        db.refresh(own)
        assert own.name == "Signifiers"
        assert db.query(TagDefinition).filter_by(codebook_group_id=own.id).one().name == "system response"


class TestRenamedFromParsing:
    def test_string_and_list_forms(self) -> None:
        tpl = CodebookTemplate(
            id="x", title="x", author="", description="", author_bio="", author_links=[],
            groups=[TemplateGroup(name="G", subtitle="", colour_set="ux", renamed_from=("Old G",),
                                  tags=[TemplateTag(name="a", renamed_from=("b", "c"))])],
        )
        assert tpl.groups[0].renamed_from == ("Old G",)
        assert tpl.groups[0].tags[0].renamed_from == ("b", "c")

    def test_shipped_norman_declares_its_renames(self) -> None:
        template = get_template("norman")
        assert template is not None
        assert template.version == "2.5"
        declared = {t.name: t.renamed_from for g in template.groups for t in g.tags if t.renamed_from}
        assert declared["clear feedback"] == ("system response",)
        assert declared["safeguard"] == ("confirmation",)


class TestStartupSweep:
    def test_sync_installed_frameworks_reaches_every_installed_one(self, db: SASession) -> None:
        _install_v1_norman(db)
        reports = sync_installed_frameworks(db)
        assert [r.framework_id for r in reports] == ["norman"]
        assert reports[0].changed
        # committed by the sweep
        db.expire_all()
        names = {r.name for r in db.query(TagDefinition).all()}
        assert "clear feedback" in names and "system response" not in names
