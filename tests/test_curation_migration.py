"""Curation migrations (003 Freeze, 004 Section identity) — data transforms.

The in-memory contract tests stamp head and never run ``upgrade()``.  These
exercise the real file-based upgrade paths: 003 freezes already-marked quotes
and relabels mislabelled sentiment tags; 004 re-keys HeadingEdit rows from the
label slug to the durable id and drops the now-wrong label-unique constraints.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import inspect, text

from bristlenose.server.db import (
    create_session_factory,
    get_engine,
    init_db,
    run_migrations,
)
from bristlenose.server.models import (
    CodebookGroup,
    HeadingEdit,
    Project,
    Quote,
    QuoteEdit,
    QuoteState,
    QuoteTag,
    ScreenCluster,
    TagDefinition,
    ThemeGroup,
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


def test_004_rekeys_heading_edits_from_slug_to_durable_id(tmp_path: Path) -> None:
    db_path = tmp_path / "bristlenose.db"
    engine = get_engine(f"sqlite:///{db_path}")
    init_db(engine)
    factory = create_session_factory(engine)

    db = factory()
    project = Project(name="M", slug="m", input_dir="/x", output_dir="/x/o")
    db.add(project)
    db.flush()
    cluster = ScreenCluster(
        project_id=project.id, screen_label="Dashboard", created_by="pipeline"
    )
    theme = ThemeGroup(
        project_id=project.id, theme_label="Trust", created_by="pipeline"
    )
    db.add_all([cluster, theme])
    db.flush()
    cid, tid, pid = cluster.id, theme.id, project.id
    db.add_all([
        HeadingEdit(project_id=pid, heading_key="section-dashboard:title",
                    edited_text="Home"),
        HeadingEdit(project_id=pid, heading_key="theme-trust:desc",
                    edited_text="A note"),
        # No cluster/theme has this slug → unreconstructable, left as-is.
        HeadingEdit(project_id=pid, heading_key="section-gone:title",
                    edited_text="Orphan"),
    ])
    db.commit()
    db.close()

    with engine.begin() as conn:
        conn.execute(text("UPDATE alembic_version SET version_num = '003'"))
    run_migrations(engine)

    db = factory()
    try:
        keys = {he.heading_key: he.edited_text for he in db.query(HeadingEdit).all()}
        # Reconstructable slugs re-keyed to the durable id.
        assert keys.get(f"section-cluster-{cid}:title") == "Home"
        assert keys.get(f"theme-group-{tid}:desc") == "A note"
        assert "section-dashboard:title" not in keys
        assert "theme-trust:desc" not in keys
        # Unreconstructable slug left untouched (documented one-time loss).
        assert keys.get("section-gone:title") == "Orphan"
    finally:
        db.close()


def test_004_drops_label_unique_constraint_and_permits_collision(
    tmp_path: Path,
) -> None:
    """The migration's flagged risk: dropping the label-unique constraint on a
    *legacy* DB that actually carries it (models.py no longer declares it, so a
    fresh DB never has it).  Simulate the legacy schema, upgrade, and assert the
    constraint is gone and a label collision is now permitted."""
    db_path = tmp_path / "bristlenose.db"
    engine = get_engine(f"sqlite:///{db_path}")
    init_db(engine)

    # Rebuild screen_clusters WITH the old constraint to mimic a pre-Phase-2 DB.
    cols = inspect(engine).get_columns("screen_clusters")
    coldefs = [
        f'"{c["name"]}" {c["type"]}'
        f'{" PRIMARY KEY" if c.get("primary_key") else ""}'
        f'{"" if c["nullable"] else " NOT NULL"}'
        for c in cols
    ]
    coldefs.append(
        "CONSTRAINT uq_cluster_project_label UNIQUE (project_id, screen_label)"
    )
    collist = ", ".join(f'"{c["name"]}"' for c in cols)
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE screen_clusters RENAME TO sc_old"))
        conn.execute(text(f"CREATE TABLE screen_clusters ({', '.join(coldefs)})"))
        conn.execute(
            text(f"INSERT INTO screen_clusters ({collist}) "
                 f"SELECT {collist} FROM sc_old")
        )
        conn.execute(text("DROP TABLE sc_old"))
        conn.execute(text("UPDATE alembic_version SET version_num = '003'"))

    assert "uq_cluster_project_label" in {
        u["name"] for u in inspect(engine).get_unique_constraints("screen_clusters")
    }
    run_migrations(engine)  # 004 drops it
    assert "uq_cluster_project_label" not in {
        u["name"] for u in inspect(engine).get_unique_constraints("screen_clusters")
    }

    # A new section reusing a retiring section's label must now be insertable.
    factory = create_session_factory(engine)
    db = factory()
    try:
        p = Project(name="M", slug="m", input_dir="/x", output_dir="/x/o")
        db.add(p)
        db.flush()
        db.add_all([
            ScreenCluster(project_id=p.id, screen_label="Dup", created_by="pipeline"),
            ScreenCluster(project_id=p.id, screen_label="Dup", created_by="pipeline"),
        ])
        db.commit()  # must not raise
    finally:
        db.close()
