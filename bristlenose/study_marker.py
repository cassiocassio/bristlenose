"""The study marker: an id a study's output folder carries, minted once.

A study is what its folder carries, not where the folder is
(``docs/design-project-identity.md`` §1, §3). The database already travels
with the folder; this file gives the study a name that travels with it too,
so the server, the Mac sidebar and agent access can recognise the same study
after a move, a rename or a copy without comparing paths.

``<output>/.bristlenose/study.json``::

    {"schema": 1, "study_id": "<uuid4>", "minted_at": "...",
     "minted_by": "run" | "serve" | "app", "copied_from": null}

Rules, each a decision in the design note:

- **First toucher mints.** Whichever of ``run`` or ``serve`` reaches a study
  with no marker writes one. Nothing is written in the interview folder.
- **A Re-analyse keeps it.** ``run --clean`` reads the marker before setting
  the output aside and writes the same id into the new output: a reset of the
  analysis is not a new study.
- **The marker wins over the database.** When ``projects.study_id`` and the
  marker disagree (a copy re-minted by the app), the database follows.
- **A file this release cannot read is left alone.** Minting over it would
  give the study a second identity; ``read`` returns ``None`` and logs, and a
  caller that must have an id mints into the same path only when the file is
  absent.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

SCHEMA = 1
FILENAME = "study.json"
MINTERS = ("run", "serve", "app")


def marker_path(output_dir: Path) -> Path:
    return output_dir / ".bristlenose" / FILENAME


def _valid_id(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return str(uuid.UUID(value))
    except ValueError:
        return None


def read(output_dir: Path) -> str | None:
    """The study id the output folder carries, or ``None``.

    ``None`` for an absent file and for one this release cannot read; the
    second is logged, because it is a marker that exists and is not trusted.
    """
    path = marker_path(output_dir)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("study marker at %s is unreadable (%s); leaving it alone", path, exc)
        return None
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        logger.warning("study marker at %s has a schema this release cannot read", path)
        return None
    study_id = _valid_id(data.get("study_id"))
    if study_id is None:
        logger.warning("study marker at %s carries no valid study id", path)
    return study_id


def write(
    output_dir: Path, study_id: str, *, minted_by: str, copied_from: str | None = None,
) -> None:
    """Write the marker atomically. ``study_id`` must be a UUID."""
    valid = _valid_id(study_id)
    if valid is None:
        raise ValueError(f"not a study id: {study_id!r}")
    if minted_by not in MINTERS:
        raise ValueError(f"unknown minter: {minted_by!r}")
    path = marker_path(output_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": SCHEMA,
        "study_id": valid,
        "minted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "minted_by": minted_by,
        "copied_from": _valid_id(copied_from),
    }
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".study.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def read_or_mint(output_dir: Path, *, minted_by: str) -> str | None:
    """The study id, minting one if the folder carries none.

    Returns ``None`` only when a marker exists that this release cannot read:
    the caller then works without an id rather than give the study a second
    one.
    """
    study_id = read(output_dir)
    if study_id is not None:
        return study_id
    if marker_path(output_dir).exists():
        return None
    study_id = str(uuid.uuid4())
    write(output_dir, study_id, minted_by=minted_by)
    logger.info("study marker minted at %s by %s", marker_path(output_dir), minted_by)
    return study_id
