"""The active-codebook rule is shared by Signals and AutoCode."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from bristlenose.server.active_codebooks import active_project_groups, maintained_framework_ids
from bristlenose.server.db import Base
from bristlenose.server.models import (
    CodebookGroup,
    Project,
    ProjectCodebookGroup,
    ProjectFrameworkState,
)


def test_disabled_framework_is_absent_but_custom_group_remains() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        project = Project(name="P", slug="p", input_dir="/in", output_dir="/out")
        garrett = CodebookGroup(name="Feedback", colour_set="ux", framework_id="garrett")
        custom = CodebookGroup(name="Researcher notes", colour_set="custom", framework_id=None)
        db.add_all([project, garrett, custom])
        db.flush()
        db.add_all([
            ProjectCodebookGroup(project_id=project.id, codebook_group_id=garrett.id, sort_order=0),
            ProjectCodebookGroup(project_id=project.id, codebook_group_id=custom.id, sort_order=1),
            ProjectFrameworkState(project_id=project.id, framework_id="garrett", enabled=False),
        ])
        db.commit()

        assert [group.name for group in active_project_groups(db, project.id)] == ["Researcher notes"]
        assert maintained_framework_ids(db, project.id) == set()
    finally:
        db.close()


def test_group_filter_cannot_reenable_a_disabled_framework() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        project = Project(name="P", slug="p", input_dir="/in", output_dir="/out")
        group = CodebookGroup(name="Feedback", colour_set="ux", framework_id="garrett")
        db.add_all([project, group])
        db.flush()
        db.add_all([
            ProjectCodebookGroup(project_id=project.id, codebook_group_id=group.id),
            ProjectFrameworkState(project_id=project.id, framework_id="garrett", enabled=False),
        ])
        db.commit()

        assert active_project_groups(db, project.id, group_ids=[group.id]) == []
    finally:
        db.close()
