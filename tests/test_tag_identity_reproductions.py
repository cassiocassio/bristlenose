"""A reproduction for N146 (1 Nov 2026): a strict xfail that names the bug.

Inside one project's database a tag is looked up by NAME across every definition, and the last
same-named one wins (docs/design-tag-provenance-and-clashes.md §2). The test states the behaviour
a researcher is owed and is a strict xfail until the fix lands, so the bug is pinned by a failing
witness, not a paragraph, and the fix cannot ship without turning it green (an unexpected pass
fails the suite). Nothing here changes behaviour. (A first version also claimed a cross-project
delete; each project has its own database, so that case is not reachable and was withdrawn.)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from bristlenose.server.app import create_app
from bristlenose.server.grounding import quote_dom_id
from bristlenose.server.models import (
    UNCATEGORISED_GROUP_NAME,
    CodebookGroup,
    Quote,
    QuoteTag,
    TagDefinition,
)
from tests.conftest import AuthTestClient

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"


@pytest.mark.xfail(
    strict=True,
    reason="N146: a typed name resolves to the LAST same-named definition, "
    "so a codebook installed later takes the researcher's own tag",
)
def test_a_typed_name_lands_on_the_researchers_own_tag_not_a_later_codebooks() -> None:
    app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")
    tc = AuthTestClient(app)
    tc.get("/api/projects/1/codebook")
    db = app.state.db_factory()
    try:
        floor = db.query(CodebookGroup).filter_by(name=UNCATEGORISED_GROUP_NAME).one()
        mine = TagDefinition(name="trust", codebook_group_id=floor.id)
        db.add(mine)
        db.commit()
        mine_id = mine.id
        quotes = db.query(Quote).filter_by(project_id=1).order_by(Quote.id).all()
        target = quotes[0]
        target_dom = quote_dom_id(target.participant_id, target.start_timecode, target.ordinal)
        target_id = target.id
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
