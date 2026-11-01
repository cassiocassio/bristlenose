"""A tag is identified by its row, never its name (N146, option A, 1 Nov 2026).

Inside one project's database a tag used to be looked up by NAME and the last same-named
definition won, so a codebook installed after the researcher made "trust" took their tag, a
removal by name took every same-named tag on the quote, and Signals (which count a quote once per
group) silently moved the quote's contribution. Now: a typed name means the researcher's own tag
when they have one; a tag picked from a list is committed by its id; a removal can name the tag it
means; a quote's tags carry their ids. A typed name never lands on the machine-authored sentiment
tags (docs/design-tag-provenance-and-clashes.md §2a).
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
    tc = AuthTestClient(app)
    tc.get("/api/projects/1/codebook")
    return app, tc


def _first_quote(app) -> tuple[int, str]:
    db = app.state.db_factory()
    try:
        q = db.query(Quote).filter_by(project_id=1).order_by(Quote.id).first()
        return q.id, quote_dom_id(q.participant_id, q.start_timecode, q.ordinal)
    finally:
        db.close()


def _make_own_trust(app) -> int:
    db = app.state.db_factory()
    try:
        floor = db.query(CodebookGroup).filter_by(name=UNCATEGORISED_GROUP_NAME).one()
        mine = TagDefinition(name="trust", codebook_group_id=floor.id)
        db.add(mine)
        db.commit()
        return mine.id
    finally:
        db.close()


def _install_uxr_and_find_its_trust(app, tc) -> int:
    assert tc.post("/api/projects/1/codebook/import-template",
                   json={"template_id": "uxr"}).status_code == 200
    db = app.state.db_factory()
    try:
        return (
            db.query(TagDefinition.id)
            .join(CodebookGroup, CodebookGroup.id == TagDefinition.codebook_group_id)
            .filter(CodebookGroup.framework_id == "uxr", TagDefinition.name == "trust")
            .scalar()
        )
    finally:
        db.close()


def _defs_on(app, quote_id: int, name: str) -> set[int]:
    db = app.state.db_factory()
    try:
        return {
            td.id
            for td in db.query(TagDefinition)
            .join(QuoteTag, QuoteTag.tag_definition_id == TagDefinition.id)
            .filter(QuoteTag.quote_id == quote_id)
            .all()
            if td.name.lower() == name
        }
    finally:
        db.close()


def test_a_typed_name_lands_on_the_researchers_own_tag_not_a_later_codebooks() -> None:
    app, tc = _app()
    mine = _make_own_trust(app)
    _install_uxr_and_find_its_trust(app, tc)
    qid, dom = _first_quote(app)
    tc.patch("/api/projects/1/tags", json={dom: {"add": ["trust"]}})
    assert _defs_on(app, qid, "trust") == {mine}


def test_a_typed_name_only_a_codebook_has_still_means_that_codebooks_tag() -> None:
    app, tc = _app()
    theirs = _install_uxr_and_find_its_trust(app, tc)
    qid, dom = _first_quote(app)
    tc.patch("/api/projects/1/tags", json={dom: {"add": ["trust"]}})
    assert _defs_on(app, qid, "trust") == {theirs}


def test_a_typed_sentiment_name_makes_the_researchers_own_tag_not_the_machines() -> None:
    app, tc = _app()
    qid, dom = _first_quote(app)
    tc.patch("/api/projects/1/tags", json={dom: {"add": ["frustration"]}})
    db = app.state.db_factory()
    try:
        groups = {
            g.framework_id
            for g in db.query(CodebookGroup)
            .join(TagDefinition, TagDefinition.codebook_group_id == CodebookGroup.id)
            .join(QuoteTag, QuoteTag.tag_definition_id == TagDefinition.id)
            .filter(QuoteTag.quote_id == qid, TagDefinition.name == "frustration")
            .all()
        }
    finally:
        db.close()
    assert None in groups, "the typed tag should be the researcher's own"
    assert "sentiment" not in groups, "a typed name must not land on the machine's sentiment tag"


def test_a_tag_added_by_id_is_exactly_that_tag() -> None:
    app, tc = _app()
    _make_own_trust(app)
    theirs = _install_uxr_and_find_its_trust(app, tc)
    qid, dom = _first_quote(app)
    tc.patch("/api/projects/1/tags", json={dom: {"add_ids": [theirs]}})
    assert _defs_on(app, qid, "trust") == {theirs}


def test_a_tag_removed_by_id_leaves_the_same_named_other_one() -> None:
    app, tc = _app()
    mine = _make_own_trust(app)
    theirs = _install_uxr_and_find_its_trust(app, tc)
    qid, dom = _first_quote(app)
    tc.patch("/api/projects/1/tags", json={dom: {"add_ids": [mine, theirs]}})
    assert _defs_on(app, qid, "trust") == {mine, theirs}
    tc.patch("/api/projects/1/tags", json={dom: {"remove_ids": [theirs]}})
    assert _defs_on(app, qid, "trust") == {mine}


def test_an_unknown_id_refuses_the_request_and_writes_nothing() -> None:
    app, tc = _app()
    qid, dom = _first_quote(app)
    mine = _make_own_trust(app)
    # One stale id refuses the whole request, so the client takes the change back (an undo
    # after the codebook was uninstalled must not draw a tag that does not exist).
    resp = tc.patch("/api/projects/1/tags", json={dom: {"add_ids": [mine, 999999]}})
    assert resp.status_code == 404
    assert _defs_on(app, qid, "trust") == set()


def test_a_quotes_tags_carry_their_ids() -> None:
    app, tc = _app()
    mine = _make_own_trust(app)
    qid, dom = _first_quote(app)
    tc.patch("/api/projects/1/tags", json={dom: {"add_ids": [mine]}})
    quotes = tc.get("/api/projects/1/quotes").json()
    tags = [
        t
        for s in quotes["sections"] + quotes["themes"]
        for q in s["quotes"]
        for t in q["tags"]
        if t["name"] == "trust"
    ]
    assert tags and tags[0]["id"] == mine


# ---------------------------------------------------------------------------
# B: uninstalling a codebook keeps what the researcher applied by hand
# ---------------------------------------------------------------------------


def _uninstall_uxr(tc) -> None:
    assert tc.delete("/api/projects/1/codebook/remove-framework/uxr").status_code == 200


def _tags_of(app, quote_id: int) -> list[tuple[str, str | None, str]]:
    """(name, group's framework, source) of each non-sentiment tag on the quote."""
    db = app.state.db_factory()
    try:
        rows = (
            db.query(TagDefinition.name, CodebookGroup.framework_id, QuoteTag.source)
            .join(QuoteTag, QuoteTag.tag_definition_id == TagDefinition.id)
            .join(CodebookGroup, CodebookGroup.id == TagDefinition.codebook_group_id)
            .filter(QuoteTag.quote_id == quote_id)
            .all()
        )
        # The quote's own pipeline sentiment tag is not what these tests are about.
        return [(n, f, s) for n, f, s in rows if f != "sentiment"]
    finally:
        db.close()


def test_uninstalling_keeps_the_researchers_own_application_in_their_own_tag() -> None:
    app, tc = _app()
    theirs = _install_uxr_and_find_its_trust(app, tc)
    qid, dom = _first_quote(app)
    # The researcher picked the codebook's tag themselves.
    tc.patch("/api/projects/1/tags", json={dom: {"add_ids": [theirs]}})
    _uninstall_uxr(tc)
    assert _tags_of(app, qid) == [("trust", None, "human")]


def test_uninstalling_re_homes_onto_the_researchers_existing_tag_of_that_name() -> None:
    app, tc = _app()
    mine = _make_own_trust(app)
    theirs = _install_uxr_and_find_its_trust(app, tc)
    qid, dom = _first_quote(app)
    tc.patch("/api/projects/1/tags", json={dom: {"add_ids": [mine, theirs]}})
    _uninstall_uxr(tc)
    assert _defs_on(app, qid, "trust") == {mine}, "kept once, on their own tag, not duplicated"


def test_uninstalling_still_removes_the_codebooks_own_applications() -> None:
    app, tc = _app()
    theirs = _install_uxr_and_find_its_trust(app, tc)
    qid, dom = _first_quote(app)
    tc.patch("/api/projects/1/tags", json={dom: {"add_ids": [theirs], "source": "autocode"}})
    _uninstall_uxr(tc)
    assert _tags_of(app, qid) == []


def test_the_uninstall_impact_does_not_count_what_is_kept() -> None:
    app, tc = _app()
    theirs = _install_uxr_and_find_its_trust(app, tc)
    qid, dom = _first_quote(app)
    tc.patch("/api/projects/1/tags", json={dom: {"add_ids": [theirs]}})
    impact = tc.get("/api/projects/1/codebook/remove-framework/uxr/impact").json()
    assert impact["quote_count"] == 0


def test_a_put_round_trip_keeps_the_sentiment_tags_it_came_from() -> None:
    app, tc = _app()
    qid, _ = _first_quote(app)
    before = _tags_of_all(app, qid)
    assert any(f == "sentiment" for _, f, _ in before), "the fixture quote has a sentiment tag"
    snapshot = tc.get("/api/projects/1/tags").json()
    assert tc.put("/api/projects/1/tags", json=snapshot).status_code == 200
    assert _tags_of_all(app, qid) == before


def _quote_with_sentiment(app, name: str) -> tuple[int, str]:
    """A fixture quote whose pipeline sentiment tag is ``name``."""
    db = app.state.db_factory()
    try:
        q = (
            db.query(Quote)
            .join(QuoteTag, QuoteTag.quote_id == Quote.id)
            .join(TagDefinition, TagDefinition.id == QuoteTag.tag_definition_id)
            .join(CodebookGroup, CodebookGroup.id == TagDefinition.codebook_group_id)
            .filter(
                Quote.project_id == 1,
                CodebookGroup.framework_id == "sentiment",
                TagDefinition.name == name,
            )
            .order_by(Quote.id)
            .first()
        )
        assert q is not None, f"the smoke fixture has a quote with sentiment {name!r}"
        return q.id, quote_dom_id(q.participant_id, q.start_timecode, q.ordinal)
    finally:
        db.close()


def test_removing_a_typed_tag_by_name_leaves_the_machines_sentiment_tag() -> None:
    # A typed "frustration" is the researcher's own tag, beside the pipeline's sentiment
    # "frustration" on the same quote. Until the next read the typed tag has no id, so its ×
    # removes by name; that must take the typed tag only, never the machine's.
    app, tc = _app()
    qid, dom = _quote_with_sentiment(app, "frustration")
    tc.patch("/api/projects/1/tags", json={dom: {"add": ["frustration"]}})
    assert len(_defs_on(app, qid, "frustration")) == 2
    tc.patch("/api/projects/1/tags", json={dom: {"remove": ["frustration"]}})
    assert _tags_of_all(app, qid) == [("frustration", "sentiment", "pipeline")]


def test_a_put_round_trip_keeps_two_same_named_tags_on_one_quote() -> None:
    app, tc = _app()
    qid, dom = _quote_with_sentiment(app, "frustration")
    tc.patch("/api/projects/1/tags", json={dom: {"add": ["frustration"]}})
    before = _tags_of_all(app, qid)
    assert len(before) == 2
    snapshot = tc.get("/api/projects/1/tags").json()
    assert snapshot[dom].count("frustration") == 2, "the map carries both occurrences"
    assert tc.put("/api/projects/1/tags", json=snapshot).status_code == 200
    assert _tags_of_all(app, qid) == before


def _tags_of_all(app, quote_id: int) -> list[tuple[str, str | None, str]]:
    db = app.state.db_factory()
    try:
        rows = (
            db.query(TagDefinition.name, CodebookGroup.framework_id, QuoteTag.source)
            .join(QuoteTag, QuoteTag.tag_definition_id == TagDefinition.id)
            .join(CodebookGroup, CodebookGroup.id == TagDefinition.codebook_group_id)
            .filter(QuoteTag.quote_id == quote_id)
            .all()
        )
        # Two same-named rows sort on the framework, which is None for the researcher's own.
        return sorted(((n, f, s) for n, f, s in rows), key=lambda r: (r[0], r[1] or "", r[2]))
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Still open: a manual tag definition is instance-wide, and deleting it has no project filter
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason="N146: delete_tag removes every QuoteTag of a shared definition with no project filter",
)
def test_deleting_a_tag_in_one_project_leaves_another_projects_tagging_alone() -> None:
    # Restored from the reproductions file eb8e0071f deleted: the fix for A did not touch this,
    # and a strict xfail keeps the bug pinned by a failing witness rather than a paragraph.
    app, tc = _app()
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
        mine = db.query(Quote).filter_by(project_id=1).order_by(Quote.id).first()
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
