"""Migration 003 (curation Freeze) — backfill + sentiment relabel on upgrade.

The in-memory contract tests stamp head and never run ``upgrade()``.  This
exercises the real 002→003 path on a file-based DB: quotes that already carry
human work get frozen, machine sentiment tags mislabelled "human" are
corrected, and a sentiment-only quote is *not* frozen.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import text

from bristlenose.server.db import (
    create_session_factory,
    get_engine,
    init_db,
    run_migrations,
)
from bristlenose.server.models import (
    CodebookGroup,
    Project,
    Quote,
    QuoteEdit,
    QuoteState,
    QuoteTag,
    TagDefinition,
)


def _quote(project_id: int, tc: float, text_: str) -> Quote:
    return Quote(
        project_id=project_id,
        session_id="s1",
        participant_id="p1",
        start_timecode=tc,
        end_timecode=tc + 5.0,
        text=text_,
        quote_type="screen_specific",
    )


def test_upgrade_backfills_pins_and_relabels_sentiment(tmp_path: Path) -> None:
    db_path = tmp_path / "bristlenose.db"
    engine = get_engine(f"sqlite:///{db_path}")
    init_db(engine)  # create_all() adds the columns, then stamps head
    factory = create_session_factory(engine)

    db = factory()
    project = Project(name="M", slug="m", input_dir="/x", output_dir="/x/o")
    db.add(project)
    db.flush()

    starred = _quote(project.id, 10.0, "Star me")
    edited = _quote(project.id, 20.0, "Original text")
    sentimental = _quote(project.id, 30.0, "Sentiment only")
    ux_tagged = _quote(project.id, 40.0, "UX tagged")
    db.add_all([starred, edited, sentimental, ux_tagged])
    db.flush()

    db.add(QuoteState(quote_id=starred.id, is_starred=True))
    db.add(QuoteEdit(quote_id=edited.id, edited_text="Edited words"))

    sentiment_group = CodebookGroup(
        name="Sentiment", colour_set="ux", framework_id="sentiment"
    )
    ux_group = CodebookGroup(name="UX", colour_set="ux")  # framework_id is NULL
    db.add_all([sentiment_group, ux_group])
    db.flush()
    conf = TagDefinition(codebook_group_id=sentiment_group.id, name="confusion")
    usability = TagDefinition(codebook_group_id=ux_group.id, name="Usability")
    db.add_all([conf, usability])
    db.flush()
    # A machine sentiment tag mislabelled "human" (the pre-fix importer bug),
    # and a genuine human tag in a NULL-framework group.
    db.add(QuoteTag(quote_id=sentimental.id, tag_definition_id=conf.id, source="human"))
    db.add(
        QuoteTag(quote_id=ux_tagged.id, tag_definition_id=usability.id, source="human")
    )
    db.commit()

    ids = {
        "starred": starred.id,
        "edited": edited.id,
        "sentimental": sentimental.id,
        "ux_tagged": ux_tagged.id,
    }
    db.close()

    # Pretend the DB predates 003, then upgrade for real.
    with engine.begin() as conn:
        conn.execute(text("UPDATE alembic_version SET version_num = '002'"))
    run_migrations(engine)

    db = factory()
    try:
        s = db.get(Quote, ids["starred"])
        e = db.get(Quote, ids["edited"])
        m = db.get(Quote, ids["sentimental"])
        u = db.get(Quote, ids["ux_tagged"])

        # Human work → frozen with its words.
        assert s.durable_id is not None
        assert s.frozen_form == "Star me"
        assert e.durable_id is not None
        assert e.frozen_form == "Edited words"  # edit wins over pipeline text
        # Human tag in a NULL-framework group → frozen (guards the OR IS NULL).
        assert u.durable_id is not None
        assert u.frozen_form == "UX tagged"

        # Sentiment-only quote is machine work → NOT frozen.
        assert m.durable_id is None

        # The mislabelled sentiment tag is corrected; the real human tag is not.
        sent_tag = db.query(QuoteTag).filter_by(quote_id=ids["sentimental"]).one()
        assert sent_tag.source == "pipeline"
        ux_tag = db.query(QuoteTag).filter_by(quote_id=ids["ux_tagged"]).one()
        assert ux_tag.source == "human"
    finally:
        db.close()
