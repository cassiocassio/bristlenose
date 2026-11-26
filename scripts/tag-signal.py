#!/usr/bin/env python3
"""Count AutoCode's accept/deny signal from studies you name, on this Mac.

Design: ``docs/design-tag-telemetry-debug.md``. Spec for the signal:
``docs/methodology/tag-rejections-are-great.md``.

Reads each named study's ``.bristlenose/bristlenose.db`` and counts every
AutoCode proposal on a *shipped* codebook tag by its final state and by who
decided it. Sends nothing. A closed study's folder is left exactly as it was,
to the byte; an open one's main file and ``-wal`` are too, and only SQLite's
shared-memory ``-shm`` index changes, as it does for every reader (the app's
own included). Run it with the app closed for a folder that is guaranteed
untouched.

Usage
-----
    .venv/bin/python scripts/tag-signal.py <study output folder> [...] [--csv PATH]

Why the opening is fiddly
-------------------------
SQLite's ``mode=ro`` on a cleanly closed WAL database creates empty ``-wal``
and ``-shm`` files beside it (measured 26 Nov 2026), which changes the folder
the Mac app's locate flow compares by modification time. So a database with no
WAL, or an empty one, is opened ``immutable=1`` (it creates nothing); one with
frames in its WAL (the app has it open, or crashed) is opened ``mode=ro``.
``immutable=1`` alone would be wrong there: it ignores WAL frames. A WAL with
frames but no ``-shm`` (a copied folder) is skipped, since ``mode=ro`` would
create one, and so is a database with a ``-journal`` file, whose interrupted
write a read-only connection cannot roll back (it would count half-written
rows).

Privacy
-------
Only tags whose name matches a bundled template's tag (current name or a
``renamed_from`` name, by the app's own key rule) are counted, and the name
printed is the template's. A researcher's own tag, or a framework tag they
renamed, is skipped and shown only as a count. Per-study errors, which carry
folder paths, go to stderr. Other database values printed as stored are the
job's ``llm_provider``, ``llm_model``, ``prompt_version`` and ``status`` and the
proposal's ``status`` and ``decided_by``, all written by the app; of those only
``llm_model`` is free text.
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from bristlenose.server.codebook import get_template
from bristlenose.server.codebook_sync import _key

#: ``proposed_tags.decided_by`` arrived in Alembic revision 027 (23 Nov 2026).
MIN_REVISION = 27

QUERY = """
SELECT g.framework_id, t.name, p.status, p.decided_by,
       j.prompt_version, j.llm_provider, j.llm_model, j.status
FROM proposed_tags AS p
JOIN autocode_jobs AS j ON j.id = p.job_id
JOIN tag_definitions AS t ON t.id = p.tag_definition_id
JOIN codebook_groups AS g ON g.id = t.codebook_group_id
"""

CUSTOM = "(own codebook)"
UNKNOWN = "(codebook not bundled)"

COLUMNS = [
    "framework",
    "tag",
    "prompt_version",
    "llm_provider",
    "llm_model",
    "job_status",
    "status",
    "decided_by",
    "count",
    "studies",
]


def _db_path(study: Path) -> Path:
    return study / ".bristlenose" / "bristlenose.db"


def _size(path: Path) -> int | None:
    """The file's size, or None if it isn't there (one stat, no race)."""
    try:
        return path.stat().st_size
    except FileNotFoundError:
        return None


def open_readonly(db: Path) -> sqlite3.Connection | str:
    """Open *db* without creating any file beside it, or say why not."""
    db = db.absolute()
    if _size(db.with_name(db.name + "-journal")) is not None:
        return "a write was interrupted (-journal present); open it in Bristlenose once first"
    wal_size = _size(db.with_name(db.name + "-wal"))
    has_frames = bool(wal_size)
    if has_frames and _size(db.with_name(db.name + "-shm")) is None:
        return "its WAL has no -shm beside it (a copied folder?); reading would create one"
    mode = "mode=ro" if has_frames else "immutable=1"
    # as_uri() percent-encodes '?', '#' and '%' in folder names.
    return sqlite3.connect(f"{db.as_uri()}?{mode}", uri=True)


def _revision(conn: sqlite3.Connection) -> int | None:
    """The Alembic revision, or None for a database that has none."""
    try:
        row = conn.execute("SELECT version_num FROM alembic_version").fetchone()
    except sqlite3.OperationalError as exc:
        if "no such table" in str(exc):
            return None
        raise
    if row is None:
        return None
    try:
        return int(str(row[0]))
    except ValueError:
        return None


def _name_index(framework_id: str) -> tuple[str, dict[str, str]] | None:
    """Return (template id, every accepted spelling -> current tag name).

    Current names are indexed first, so an old name never shadows another
    tag's current one (the app looks current names up first too).
    """
    template = get_template(framework_id)
    if template is None:
        return None
    tags = [tag for group in template.groups for tag in group.tags]
    index: dict[str, str] = {}
    for tag in tags:
        index.setdefault(_key(tag.name), tag.name)
    for tag in tags:
        for old in tag.renamed_from:
            index.setdefault(_key(old), tag.name)
    return template.id, index


def read_study(db: Path) -> list[tuple] | str:
    """Return the proposal rows for one study, or a reason it was skipped."""
    if not db.is_file():
        return "no Bristlenose database here"
    try:
        conn = open_readonly(db)
        if isinstance(conn, str):
            return conn
        try:
            revision = _revision(conn)
            if revision is None or revision < MIN_REVISION:
                return (
                    "database is older than this tool; open it in Bristlenose once to update it"
                )
            return conn.execute(QUERY).fetchall()
        finally:
            conn.close()
    except (sqlite3.Error, OSError) as exc:
        return f"could not read the database ({exc})"


def count(studies: list[Path]) -> tuple[Counter, dict, Counter, int]:
    """Count rows across *studies*.

    Returns (counts per output line, studies per output line, per-framework
    read/counted/skipped tallies, number of studies read).
    """
    counts: Counter = Counter()
    contributors: dict[tuple, set[int]] = defaultdict(set)
    tallies: Counter = Counter()
    indexes: dict[str, tuple[str, dict[str, str]] | None] = {}
    read = 0
    seen: set[Path] = set()

    for n, study in enumerate(studies):
        db = _db_path(study)
        try:
            resolved = db.resolve()
        except OSError:
            resolved = db.absolute()
        if resolved in seen:
            print(f"skipped {study}: named twice", file=sys.stderr)
            continue
        seen.add(resolved)
        result = read_study(db)
        if isinstance(result, str):
            print(f"skipped {study}: {result}", file=sys.stderr)
            continue
        read += 1
        for framework_id, name, status, decided_by, prompt_v, provider, model, job_status in result:
            if framework_id is None:
                tallies[(CUSTOM, "read")] += 1
                tallies[(CUSTOM, "skipped")] += 1
                continue
            if framework_id not in indexes:
                indexes[framework_id] = _name_index(framework_id)
            found = indexes[framework_id]
            if found is None:
                tallies[(UNKNOWN, "read")] += 1
                tallies[(UNKNOWN, "skipped")] += 1
                continue
            template_id, index = found
            tallies[(template_id, "read")] += 1
            canonical = index.get(_key(name))
            if canonical is None:
                tallies[(template_id, "skipped")] += 1
                continue
            tallies[(template_id, "counted")] += 1
            line = (
                template_id,
                canonical,
                prompt_v or "",
                provider or "",
                model or "",
                job_status or "",
                status or "",
                decided_by if decided_by is not None else "none",
            )
            counts[line] += 1
            contributors[line].add(n)

    studies_per_line = {line: len(ids) for line, ids in contributors.items()}
    return counts, studies_per_line, tallies, read


def _rows(counts: Counter, studies_per_line: dict) -> list[list[str]]:
    return [
        [*line, str(n), str(studies_per_line[line])]
        for line, n in sorted(counts.items())
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("studies", nargs="+", type=Path, help="study output folders")
    parser.add_argument("--csv", type=Path, help="write the counts to this CSV file")
    args = parser.parse_args(argv)

    counts, studies_per_line, tallies, read = count(args.studies)
    if read == 0:
        print("No study could be read.", file=sys.stderr)
        return 1

    rows = _rows(counts, studies_per_line)
    if args.csv:
        as_of = date.today().isoformat()
        with args.csv.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["as_of", *COLUMNS])
            writer.writerows([as_of, *row] for row in rows)
        print(f"Wrote {len(rows)} lines to {args.csv}")
    else:
        widths = [max(len(c), *(len(r[i]) for r in rows)) if rows else len(c)
                  for i, c in enumerate(COLUMNS)]
        print("  ".join(c.ljust(w) for c, w in zip(COLUMNS, widths, strict=True)))
        for row in rows:
            print("  ".join(v.ljust(w) for v, w in zip(row, widths, strict=True)))

    print(f"\nStudies read: {read} of {len(args.studies)}")
    for label in sorted({label for label, _ in tallies}):
        print(
            f"{label}: {tallies[(label, 'read')]} read, "
            f"{tallies[(label, 'counted')]} counted, "
            f"{tallies[(label, 'skipped')]} skipped"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
