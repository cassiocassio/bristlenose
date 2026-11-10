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
CREATE TABLE persons (full_name TEXT);
CREATE TABLE heading_edits (project_id INTEGER);
CREATE TABLE sessions (id INTEGER PRIMARY KEY, project_id INTEGER);
CREATE TABLE transcript_layout_edits (session_id INTEGER, kind TEXT);
CREATE TABLE session_speakers (session_id INTEGER, evidence TEXT);
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
    conn.execute("INSERT INTO session_speakers VALUES (1, 'pick')")
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
    conn.execute("INSERT INTO session_speakers VALUES (8, 'pick')")
    conn.execute("INSERT INTO deleted_badges VALUES (9)")
    conn.commit()
    conn.close()

    counts = curation_counts.read(tmp_path)

    assert counts is not None and counts.total == 0


def test_a_speaker_the_pipeline_matched_is_not_a_choice(tmp_path: Path) -> None:
    conn = _db(tmp_path)
    conn.executemany("INSERT INTO session_speakers VALUES (1, ?)",
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
