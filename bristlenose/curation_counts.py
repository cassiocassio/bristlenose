"""What a Re-analyse would discard: the researcher's work on a study, counted.

The CLI's `run --clean` asks before it discards a report's stars, tags and
edits, as the Mac's **Re-analyse…** sheet does (R113, decision #135, 24 Oct
2026). The five counts are the Mac's own (`CurationCountsReader.swift`), so the
two surfaces name the same losses: edited quotes, human tags, starred quotes,
renamed speakers and named themes, scoped to project row 1, the one the report
shows (`SourceFilesReader.reportProjectID`).

**Unreadable is None, never zero.** A zero means "nothing to lose, go ahead",
so a count that could not be taken must not read as one; the caller asks
anyway. No database at all is a real zero, and so is a curation table an older
schema lacks. A table that is there but can't be counted (a renamed column, a
missing join table) is None, as on the Mac.

A plain read-only open, not the Mac's `immutable=1`: the CLI is not sandboxed,
so it reads the WAL like any SQLite reader and sees a commit the serve has not
checkpointed yet (the blind spot `walVouch` exists for on the Mac, #115).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from bristlenose.utils.text import count_noun

#: The one project row the report reads.
_PROJECT_ID = 1


@dataclass(frozen=True)
class CurationCounts:
    edited_quotes: int = 0
    tags: int = 0
    starred_quotes: int = 0
    renamed_speakers: int = 0
    named_themes: int = 0
    #: Interviews in the report, for "all 10 interviews again"; None if unread.
    sessions: int | None = None

    @property
    def total(self) -> int:
        return (self.edited_quotes + self.tags + self.starred_quotes
                + self.renamed_speakers + self.named_themes)

    def lines(self) -> list[str]:
        """The non-zero losses, in the Mac sheet's order."""
        pairs = (
            (self.edited_quotes, "edited quote"),
            (self.tags, "tag"),
            (self.starred_quotes, "starred quote"),
            (self.renamed_speakers, "renamed speaker"),
            (self.named_themes, "named theme"),
        )
        return [count_noun(n, noun) for n, noun in pairs if n]


def db_path(output_dir: Path) -> Path:
    return output_dir / ".bristlenose" / "bristlenose.db"


def read(output_dir: Path) -> CurationCounts | None:
    """The study's curation, or None when it could not be counted."""
    path = db_path(output_dir)
    try:
        path.stat()
    except FileNotFoundError:
        return CurationCounts(sessions=0)
    except OSError:
        return None
    try:
        # `as_uri()` percent-encodes the path. Interpolated raw, a `#` or `?` in
        # a folder name ("Round #2") cut the path short, dropped `mode=ro`, and
        # sqlite created an empty database there that counted zero: --clean
        # then discarded the curation unasked. `absolute()` because `as_uri()`
        # refuses a relative path, and `run interviews` gives one.
        conn = sqlite3.connect(path.absolute().as_uri() + "?mode=ro", uri=True)
    except sqlite3.Error:
        return None
    try:
        return _counts(conn)
    except sqlite3.Error:
        return None
    finally:
        conn.close()


def _counts(conn: sqlite3.Connection) -> CurationCounts:
    tables = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    )}
    pid = _PROJECT_ID

    def count(table: str, sql: str) -> int:
        # A table the schema lacks is an older schema: nothing of that kind to
        # lose. Anything else that fails raises, and the whole read is None.
        if table not in tables:
            return 0
        return int(conn.execute(sql).fetchone()[0])

    return CurationCounts(
        edited_quotes=count("quote_edits", (
            "SELECT COUNT(*) FROM quote_edits e JOIN quotes q ON q.id = e.quote_id "
            f"WHERE q.project_id = {pid}"
        )),
        tags=count("quote_tags", (
            "SELECT COUNT(*) FROM quote_tags t JOIN quotes q ON q.id = t.quote_id "
            f"WHERE t.source = 'human' AND q.project_id = {pid}"
        )),
        starred_quotes=count("quote_states", (
            "SELECT COUNT(*) FROM quote_states s JOIN quotes q ON q.id = s.quote_id "
            f"WHERE s.is_starred = 1 AND q.project_id = {pid}"
        )),
        # Speaker codes are p1/m1/o1, so any non-empty full name is the
        # researcher's doing. Instance-scoped by design, as on the Mac.
        renamed_speakers=count("persons", (
            "SELECT COUNT(*) FROM persons WHERE full_name IS NOT NULL AND full_name != ''"
        )),
        named_themes=count("heading_edits", (
            f"SELECT COUNT(*) FROM heading_edits WHERE project_id = {pid}"
        )),
        sessions=count("sessions", f"SELECT COUNT(*) FROM sessions WHERE project_id = {pid}"),
    )
