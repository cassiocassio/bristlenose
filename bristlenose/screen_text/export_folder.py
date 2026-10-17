"""The exported screens folder's manifest, and its share of removing an interview.

`bristlenose-output/screens/` holds the stills Export Screens wrote (`server/routes/screens_export.py`),
named by participant code (`p3-07.jpg`), so the pipeline's per-session prune — which matches file
names that are session ids — cannot see them. The manifest says which session each file came from,
so when an interview is removed from the project its exported screengrabs go with it (owner, 17 Oct
2026: rare — a participant who withdraws usually does so before the session — but a cleanup that
misses a folder is a hole). Files not in the manifest are the researcher's and are never touched.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

FOLDER = "screens"
MANIFEST_NAME = ".screens_manifest.json"


def plain_name(name: object) -> bool:
    """A file name that names a file in this folder and nothing else."""
    return isinstance(name, str) and bool(name) and name == Path(name).name and not name.startswith(".")


def read_manifest(folder: Path) -> tuple[list[str], dict[str, str]]:
    """(files in export order, {file: session id}); empty when there is no readable manifest."""
    try:
        data = json.loads((folder / MANIFEST_NAME).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return [], {}
    except (OSError, ValueError):
        logger.warning("Unreadable %s; earlier stills left in place", MANIFEST_NAME, exc_info=True)
        return [], {}
    files = [f for f in data.get("files", []) if plain_name(f)] if isinstance(data, dict) else []
    sessions = data.get("sessions", {}) if isinstance(data, dict) else {}
    return files, {f: s for f, s in sessions.items() if f in files and isinstance(s, str)} \
        if isinstance(sessions, dict) else {}


def write_manifest(folder: Path, files: list[str], sessions: Mapping[str, str]) -> None:
    """Replace the manifest whole, so a reader never sees half of one."""
    tmp = folder / f"{MANIFEST_NAME}.tmp"
    tmp.write_text(json.dumps({
        "exported_at": datetime.now(timezone.utc).isoformat(), "files": files,
        "sessions": {f: sessions[f] for f in files if f in sessions},
    }, indent=2, ensure_ascii=True), encoding="utf-8")
    os.replace(tmp, folder / MANIFEST_NAME)


def prune_removed_sessions(output_dir: Path, keep: Iterable[str]) -> list[Path]:
    """Remove the exported stills of sessions no longer in the project; returns what was removed.

    Only files the manifest attributes to a session outside `keep`. A manifest from before sessions
    were recorded attributes nothing, so nothing is removed from it."""
    folder = output_dir / FOLDER
    files, sessions = read_manifest(folder)
    if not sessions:
        return []
    keep_ids = set(keep)
    gone = [f for f in files if f in sessions and sessions[f] not in keep_ids]
    removed: list[Path] = []
    for name in gone:
        path = folder / name
        try:
            path.unlink(missing_ok=True)
            removed.append(path)
        except OSError:
            logger.warning("Could not remove %s of a removed interview", name, exc_info=True)
    if gone:
        left = [f for f in files if f not in gone]
        try:
            write_manifest(folder, left, sessions)
        except OSError:
            logger.warning("Could not rewrite %s", MANIFEST_NAME, exc_info=True)
    return removed
