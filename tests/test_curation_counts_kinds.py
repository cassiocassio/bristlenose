"""Re-analyse counts all nine kinds of the researcher's work (N131, 10 Nov 2026).

It counted five: edited quotes, human tags, starred quotes, renamed speakers and
named themes. A researcher who had only hidden quotes, fixed a transcript line or
removed a badge counted zero, so the sheet stayed silent and `--clean` ran
unasked. The four added kinds are read from the tables the researcher's gestures
write, scoped to project row 1 like the rest. Proposal B of
docs/mockups/reanalyse-uncounted-curation.html: one line per kind.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from bristlenose import curation_counts

_SCHEMA = """
CREATE TABLE quotes (id INTEGER PRIMARY KEY, project_id INTEGER);
CREATE TABLE quote_states (quote_id INTEGER, is_starred INTEGER DEFAULT 0, is_hidden INTEGER DEFAULT 0);
CREATE TABLE quote_tags (quote_id INTEGER, source TEXT);
CREATE TABLE quote_edits (quote_id INTEGER);
CREATE TABLE persons (id INTEGER PRIMARY KEY, full_name TEXT, short_name TEXT);
CREATE TABLE heading_edits (project_id INTEGER);
CREATE TABLE sessions (id INTEGER PRIMARY KEY, project_id INTEGER);
CREATE TABLE transcript_layout_edits (session_id INTEGER, kind TEXT);
CREATE TABLE session_speakers (session_id INTEGER, evidence TEXT, person_id INTEGER, state TEXT);
CREATE TABLE deleted_badges (quote_id INTEGER);
"""


def _db(tmp_path: Path) -> sqlite3.Connection:
    state = tmp_path / ".bristlenose"
    state.mkdir()
    conn = sqlite3.connect(state / "bristlenose.db")
    conn.executescript(_SCHEMA)
    # Quote 1-3 are in the report's project; quote 9 is in another project's row.
    conn.executemany("INSERT INTO quotes VALUES (?, ?)", [(1, 1), (2, 1), (3, 1), (9, 2)])
    conn.executemany("INSERT INTO sessions VALUES (?, ?)", [(1, 1), (2, 1), (8, 2)])
    return conn


def test_a_study_with_only_the_four_new_kinds_is_not_empty(tmp_path: Path) -> None:
    """The case the row is about: nothing starred or tagged, so it counted zero."""
    conn = _db(tmp_path)
    conn.executemany(
        "INSERT INTO quote_states (quote_id, is_hidden) VALUES (?, 1)", [(1,), (2,), (3,)])
    conn.executemany(
        "INSERT INTO transcript_layout_edits VALUES (?, ?)", [(1, "split"), (2, "join")])
    conn.execute("INSERT INTO session_speakers (session_id, evidence) VALUES (1, 'pick')")
    conn.execute("INSERT INTO deleted_badges VALUES (1)")
    conn.commit()
    conn.close()

    counts = curation_counts.read(tmp_path)

    assert counts is not None
    assert (counts.hidden_quotes, counts.transcript_edits,
            counts.speaker_picks, counts.removed_badges) == (3, 2, 1, 1)
    assert counts.total == 7
    assert counts.lines() == [
        "3 hidden quotes", "2 edited transcript lines", "1 speaker choice", "1 removed badge",
    ]


def test_only_the_reports_project_is_counted(tmp_path: Path) -> None:
    conn = _db(tmp_path)
    conn.execute("INSERT INTO quote_states (quote_id, is_hidden) VALUES (9, 1)")
    conn.execute("INSERT INTO transcript_layout_edits VALUES (8, 'split')")
    conn.execute("INSERT INTO session_speakers (session_id, evidence) VALUES (8, 'pick')")
    conn.execute("INSERT INTO deleted_badges VALUES (9)")
    conn.commit()
    conn.close()

    counts = curation_counts.read(tmp_path)

    assert counts is not None and counts.total == 0


def test_a_speaker_the_pipeline_matched_is_not_a_choice(tmp_path: Path) -> None:
    conn = _db(tmp_path)
    conn.executemany("INSERT INTO session_speakers (session_id, evidence) VALUES (1, ?)",
                     [("platform-name",), ("heard",), ("label",), (None,), ("pick",)])
    conn.commit()
    conn.close()

    counts = curation_counts.read(tmp_path)

    assert counts is not None and counts.speaker_picks == 1


def test_a_visible_quote_is_not_a_hidden_one(tmp_path: Path) -> None:
    conn = _db(tmp_path)
    conn.executemany("INSERT INTO quote_states (quote_id, is_hidden) VALUES (?, ?)",
                     [(1, 1), (2, 0), (3, 0)])
    conn.commit()
    conn.close()

    counts = curation_counts.read(tmp_path)

    assert counts is not None and counts.hidden_quotes == 1


def test_an_older_schema_without_the_new_tables_counts_zero_for_them(tmp_path: Path) -> None:
    """Zero for a table the schema lacks, as for the original five."""
    state = tmp_path / ".bristlenose"
    state.mkdir()
    conn = sqlite3.connect(state / "bristlenose.db")
    conn.executescript(
        "CREATE TABLE quotes (id INTEGER PRIMARY KEY, project_id INTEGER);"
        "CREATE TABLE sessions (id INTEGER PRIMARY KEY, project_id INTEGER);")
    conn.commit()
    conn.close()

    counts = curation_counts.read(tmp_path)

    assert counts is not None and counts.total == 0


def test_the_queries_read_the_real_schema(tmp_path: Path) -> None:
    """The synthetic schemas above are written by hand; this one is the models',
    so a renamed column turns the read into None here, not in a researcher's
    Re-analyse."""
    from sqlalchemy import create_engine

    from bristlenose.server.models import Base

    state = tmp_path / ".bristlenose"
    state.mkdir()
    engine = create_engine(f"sqlite:///{state / 'bristlenose.db'}")
    Base.metadata.create_all(engine)
    engine.dispose()

    counts = curation_counts.read(tmp_path)

    assert counts is not None and counts.total == 0


def test_every_line_the_mac_sheet_can_draw_has_its_locale_keys() -> None:
    """`ReAnalyseConfirmSheet` builds each line from `reAnalyseLoss.<kind>`; a kind
    counted by `CurationCountsReader` with no key would draw a raw key name."""
    import json

    en = json.loads(
        (Path(__file__).parent.parent / "bristlenose" / "locales" / "en" / "desktop.json")
        .read_text(encoding="utf-8")
    )["chrome"]["reAnalyseLoss"]
    for kind in ("editedQuotes", "tags", "starred", "renamedSpeakers", "namedThemes",
                 "hiddenQuotes", "transcriptEdits", "speakerPicks", "removedBadges"):
        assert f"{kind}_one" in en and f"{kind}_other" in en, kind
    sheet = (Path(__file__).parent.parent / "desktop" / "Bristlenose" / "Bristlenose"
             / "ReAnalyseConfirmSheet.swift").read_text(encoding="utf-8")
    for kind in ("hiddenQuotes", "transcriptEdits", "speakerPicks", "removedBadges"):
        assert f'add("{kind}"' in sheet, f"the sheet never draws {kind}"


def _name(conn: sqlite3.Connection, person_id: int, name: str, *, session: int, state: str | None,
          evidence: str = "participant", short: str = "") -> None:
    conn.execute("INSERT INTO persons VALUES (?, ?, ?)", (person_id, name, short))
    conn.execute(
        "INSERT INTO session_speakers (session_id, evidence, person_id, state) VALUES (?, ?, ?, ?)",
        (session, evidence, person_id, state))


def test_a_name_the_pipeline_filled_in_is_not_the_researchers_work(tmp_path: Path) -> None:
    """N130, decision #314. A Zoom study nobody touched: four participants named by
    the platform, every slot 'proposed'. A re-run reads the same labels, so there is
    nothing to lose and the count is zero (the Mac's sheet then draws no list)."""
    conn = _db(tmp_path)
    for i, name in enumerate(("Priya Nair", "Tom Ellis", "Ada Lee", "Sam Roe"), start=1):
        _name(conn, i, name, session=1, state="proposed", evidence="platform-name")
    conn.commit()
    conn.close()

    counts = curation_counts.read(tmp_path)

    assert counts is not None
    assert counts.renamed_speakers == 0
    assert counts.total == 0


def test_a_name_a_researcher_typed_or_accepted_is_counted(tmp_path: Path) -> None:
    """The same study with one name corrected ('Pri' typed as 'Priya Nair') and one
    proposal accepted: both slots are 'confirmed', the other two stay proposed."""
    conn = _db(tmp_path)
    _name(conn, 1, "Priya Nair", session=1, state="confirmed")
    _name(conn, 2, "Tom Ellis", session=1, state="confirmed", evidence="platform-name")
    _name(conn, 3, "Ada Lee", session=1, state="proposed", evidence="platform-name")
    _name(conn, 4, "Sam Roe", session=1, state="proposed", evidence="heard")
    conn.commit()
    conn.close()

    counts = curation_counts.read(tmp_path)

    assert counts is not None and counts.renamed_speakers == 2
    assert counts.lines() == ["2 renamed speakers"]


def test_a_person_confirmed_in_several_sessions_counts_once(tmp_path: Path) -> None:
    """A moderator named once is one person across sessions: one rename, not two."""
    conn = _db(tmp_path)
    conn.execute("INSERT INTO persons VALUES (1, 'Maya Cole', '')")
    conn.executemany(
        "INSERT INTO session_speakers (session_id, evidence, person_id, state) VALUES (?, 'pick', 1, 'confirmed')",
        [(1,), (2,)])
    conn.commit()
    conn.close()

    counts = curation_counts.read(tmp_path)

    assert counts is not None and counts.renamed_speakers == 1


def test_a_confirmed_empty_name_and_a_slot_nobody_named_are_not_renames(tmp_path: Path) -> None:
    conn = _db(tmp_path)
    _name(conn, 1, "", session=1, state="confirmed")
    conn.execute(
        "INSERT INTO session_speakers (session_id, evidence, person_id, state) VALUES (1, NULL, NULL, NULL)")
    conn.commit()
    conn.close()

    counts = curation_counts.read(tmp_path)

    assert counts is not None and counts.renamed_speakers == 0


def test_a_name_confirmed_only_in_another_projects_session_is_not_counted(tmp_path: Path) -> None:
    """Scoped through the slot's session to the report's project, like every kind."""
    conn = _db(tmp_path)
    _name(conn, 1, "Priya Nair", session=8, state="confirmed")
    conn.commit()
    conn.close()

    counts = curation_counts.read(tmp_path)

    assert counts is not None and counts.renamed_speakers == 0


def test_a_name_typed_into_the_short_name_box_alone_is_counted(tmp_path: Path) -> None:
    """Review finding, 12 Nov 2026. The report's rename box sends `short_name`
    alone for a participant (`speakerPicking.ts`, `SessionsTable.tsx`), so a typed
    "Priya" on a recording with no platform label leaves `full_name` empty. The
    slot is confirmed, and it is the researcher's work."""
    conn = _db(tmp_path)
    _name(conn, 1, "", short="Priya", session=1, state="confirmed")
    _name(conn, 2, "", short="Tom", session=1, state="proposed", evidence="heard")
    conn.commit()
    conn.close()

    counts = curation_counts.read(tmp_path)

    assert counts is not None and counts.renamed_speakers == 1


def test_the_two_queries_are_the_same() -> None:
    """The Mac counts with its own copy of the SQL (`CurationCountsReader.swift`);
    nothing else holds the two together, and they agree today by eye only."""
    import re

    swift = (Path(__file__).parent.parent / "desktop" / "Bristlenose" / "Bristlenose"
             / "CurationCountsReader.swift").read_text(encoding="utf-8")
    m = re.search(r'renamedSpeakers = count\(.*?"""\n(.*?)\n\s*"""\)', swift, re.S)
    assert m, "the renamedSpeakers query is not where this test looks for it"
    mac = " ".join(m.group(1).split()).replace("\\(pid)", "{pid}")
    assert mac == " ".join(curation_counts.RENAMED_SPEAKERS_SQL.split())


class TestThroughTheRealRoutes:
    """The `'confirmed'` the count looks for is written by the routes; a test that
    inserts rows by hand cannot notice the routes writing something else."""

    @staticmethod
    def _study(tmp_path: Path):
        from bristlenose.server.app import create_app
        from tests.conftest import AuthTestClient
        from tests.test_serve_per_session_moderators import _PER_SESSION, _project

        project = _project(tmp_path, session_names=_PER_SESSION)
        client = AuthTestClient(create_app(project_dir=project, dev=True))
        return client, project / "bristlenose-output"

    def test_names_the_pipeline_filled_in_count_nothing_and_a_researchers_rename_counts(
        self, tmp_path: Path,
    ) -> None:
        client, out = self._study(tmp_path)
        with client:
            # People named by the pipeline from people.yaml and the session speakers.
            counts = curation_counts.read(out)
            assert counts is not None and counts.renamed_speakers == 0

            people = client.get("/api/projects/1/people").json()
            people["p1"]["short_name"] = "Annie"
            assert client.put("/api/projects/1/people", json=people).status_code == 200
            counts = curation_counts.read(out)
            assert counts is not None and counts.renamed_speakers == 1

            # A moderator typed in one session: one more person said yes to.
            resp = client.put("/api/projects/1/sessions/s2/speakers/m1",
                              json={"short_name": "Joanna"})
            assert resp.status_code == 200
            counts = curation_counts.read(out)
            assert counts is not None and counts.renamed_speakers == 2

    def test_a_participant_named_only_by_typing_a_short_name_is_counted(
        self, tmp_path: Path,
    ) -> None:
        import yaml

        client, out = self._study(tmp_path)
        # No platform label and nothing heard: the pipeline left p1 unnamed.
        people_yaml = out / "people.yaml"
        raw = yaml.safe_load(people_yaml.read_text(encoding="utf-8"))
        raw["participants"]["p1"]["editable"].update({"full_name": "", "short_name": ""})
        people_yaml.write_text(yaml.safe_dump(raw), encoding="utf-8")
        with client:
            people = client.get("/api/projects/1/people").json()
            people["p1"].update({"full_name": "", "short_name": "Priya"})
            assert client.put("/api/projects/1/people", json=people).status_code == 200
            counts = curation_counts.read(out)

        assert counts is not None and counts.renamed_speakers == 1
