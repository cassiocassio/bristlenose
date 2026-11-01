"""Reproductions for N146 and the shared-tag hazards (1 Nov 2026): strict xfails that name a bug.

A tag is looked up by NAME across the whole library, and one manual tag definition serves every
project (docs/design-tag-provenance-and-clashes.md §2). Each test states the behaviour a
researcher is owed and is a strict xfail until the fix lands, so the bug is pinned by a failing
witness, not a paragraph, and the fix cannot ship without turning it green (an unexpected pass
fails the suite). Nothing here changes behaviour.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from bristlenose.server.app import create_app
from bristlenose.server.grounding import quote_dom_id
from bristlenose.server.models import (
    UNCATEGORISED_GROUP_NAME,
    CodebookGroup,
    Project,
    Quote,
    QuoteTag,
    TagDefinition,
)
from tests.conftest import AuthTestClient

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"


def _app():
    app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")
    return app, AuthTestClient(app)


def _dom_id(q: Quote) -> str:
    return quote_dom_id(q.participant_id, q.start_timecode, q.ordinal)


@pytest.mark.xfail(
    strict=True,
    reason="N146: delete_tag removes every QuoteTag of a shared definition with no project filter",
)
def test_deleting_a_tag_in_one_project_leaves_another_projects_tagging_alone() -> None:
    app, tc = _app()
    tc.get("/api/projects/1/codebook")  # creates the shared Uncategorised group
    db = app.state.db_factory()
    try:
        other = Project(name="Other", input_dir="/tmp/o", output_dir="/tmp/o/out")
        db.add(other)
        db.flush()
        theirs = Quote(
            project_id=other.id, session_id="s1", participant_id="p1", start_timecode=1.0,
            end_timecode=2.0, text="their quote", quote_type="general_context",
        )
        db.add(theirs)
        floor = db.query(CodebookGroup).filter_by(name=UNCATEGORISED_GROUP_NAME).one()
        trust = TagDefinition(name="trust", codebook_group_id=floor.id)
        db.add(trust)
        db.flush()
        mine = db.query(Quote).filter_by(project_id=1).first()
        db.add(QuoteTag(quote_id=mine.id, tag_definition_id=trust.id))
        db.add(QuoteTag(quote_id=theirs.id, tag_definition_id=trust.id))
        db.commit()
        trust_id, theirs_id = trust.id, theirs.id
    finally:
        db.close()

    tc.delete(f"/api/projects/1/codebook/tags/{trust_id}")

    db = app.state.db_factory()
    try:
        left = db.query(QuoteTag).filter_by(quote_id=theirs_id).count()
    finally:
        db.close()
    assert left == 1, "the other project's quote lost its tag when this project deleted 'trust'"


@pytest.mark.xfail(
    strict=True,
    reason="N146: a typed name resolves to the LAST same-named definition in the library, "
    "so a codebook installed later takes the researcher's own tag",
)
def test_a_typed_name_lands_on_the_researchers_own_tag_not_a_later_codebooks() -> None:
    app, tc = _app()
    tc.get("/api/projects/1/codebook")
    db = app.state.db_factory()
    try:
        floor = db.query(CodebookGroup).filter_by(name=UNCATEGORISED_GROUP_NAME).one()
        mine = TagDefinition(name="trust", codebook_group_id=floor.id)
        db.add(mine)
        db.commit()
        mine_id = mine.id
        quotes = db.query(Quote).filter_by(project_id=1).order_by(Quote.id).all()
        target_dom = _dom_id(quotes[0])
        target_id = quotes[0].id
    finally:
        db.close()

    # A codebook that has a tag called "trust" is installed AFTER the researcher made theirs.
    resp = tc.post("/api/projects/1/codebook/import-template", json={"template_id": "uxr"})
    assert resp.status_code == 200

    tc.patch("/api/projects/1/tags", json={target_dom: {"add": ["trust"]}})

    db = app.state.db_factory()
    try:
        landed = {
            td.id
            for td in db.query(TagDefinition)
            .join(QuoteTag, QuoteTag.tag_definition_id == TagDefinition.id)
            .filter(QuoteTag.quote_id == target_id)
            .all()
            if td.name.lower() == "trust"
        }
    finally:
        db.close()
    assert landed == {mine_id}, "the researcher's 'trust' was attached to the codebook's tag"
