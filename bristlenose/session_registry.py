"""Sticky session ids and sticky speaker slots — ``.bristlenose/sessions.json``.

Without this, every run numbered sessions afresh by recording date, so a
recording older than the ones already analysed renumbered every session after
it: one interview's transcript, stars and typed names moved onto another
(``docs/design-cloud-import-transcripts.md`` §2, "Adding an older recording").

The registry remembers two things across runs:

- **sessions**: the session's grouping key (``s01_ingest.session_key``) → its
  sid. A known key keeps its sid; a new key takes the next number after every
  number ever handed out, so nothing already analysed moves. An older recording
  arriving late is numbered last — the cost of never renumbering.
- **speakers**: per sid, speaker label → speaker code. A label keeps its code
  while its role is unchanged; participant numbers are global and never
  reused, so a participant's code — and the quotes, stars and names keyed by
  it — stays with them when another session is added.
- **participants_issued**: the highest participant number ever handed out.
  The speaker map alone cannot say it: a speaker re-identified as a moderator
  or observer leaves the map, and its number would be issued again, to someone
  else, wearing the name typed for the first.

A project with no file behaves exactly as before on its first run: sessions in
date order, codes from 1. Entries for sessions that disappear are kept, so their
numbers are never handed to someone else. This is the first package of
``docs/design-people.md`` §H H9 (Phase 0), which keys the per-session moderator
slot on it.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from bristlenose.models import InputSession

logger = logging.getLogger(__name__)

REGISTRY_VERSION = 1
REGISTRY_FILENAME = "sessions.json"


def registry_path(output_dir: Path) -> Path:
    return output_dir / ".bristlenose" / REGISTRY_FILENAME


@dataclass
class SessionRegistry:
    path: Path
    sessions: dict[str, str] = field(default_factory=dict)
    speakers: dict[str, dict[str, str]] = field(default_factory=dict)
    participants_issued: int = 0

    # ── persistence ──────────────────────────────────────────────────────

    @classmethod
    def load(cls, output_dir: Path) -> SessionRegistry:
        """Read the registry, or start an empty one if the project has none.

        A file this version cannot read is refused loudly rather than replaced:
        starting afresh would renumber every session, which is the corruption
        the file exists to prevent.
        """
        path = registry_path(output_dir)
        if not path.exists():
            return cls(path=path)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValueError(
                f"Cannot read {path}: {exc}. It holds this project's session "
                "numbering; move it aside to renumber the sessions from scratch."
            ) from exc
        version = data.get("version") if isinstance(data, dict) else None
        if version != REGISTRY_VERSION:
            raise ValueError(
                f"{path} has version {version!r}; this Bristlenose reads version "
                f"{REGISTRY_VERSION}. It may have been written by a newer release."
            )
        sessions = data.get("sessions") or {}
        speakers = data.get("speakers") or {}
        return cls(
            path=path,
            sessions={str(k): str(v) for k, v in sessions.items()},
            speakers={
                str(sid): {str(lbl): str(code) for lbl, code in labels.items()}
                for sid, labels in speakers.items()
            },
            participants_issued=int(data.get("participants_issued") or 0),
        )

    def save(self) -> None:
        """Write atomically: a reader never sees half a file."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": REGISTRY_VERSION,
            "sessions": dict(sorted(self.sessions.items())),
            "speakers": {sid: self.speakers[sid] for sid in sorted(self.speakers)},
            "participants_issued": self.participants_issued,
        }
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".sessions.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2, ensure_ascii=False)
                fh.write("\n")
            os.replace(tmp, self.path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    # ── sessions ─────────────────────────────────────────────────────────

    def apply(self, sessions: list[InputSession]) -> list[InputSession]:
        """Give each session its remembered sid, or the next unused one.

        ``sessions`` arrive in ingest's order (recording date); new sessions
        are numbered in that order. Returns the sessions sorted by number.
        """
        from bristlenose.stages.s01_ingest import session_key

        used = {_number(sid) for sid in self.sessions.values()}
        next_n = max(used, default=0) + 1
        seen: set[str] = set()
        for session in sessions:
            key = session_key(session.files) if session.files else f"sid:{session.session_id}"
            if key in seen:
                # Grouping makes keys unique; if that ever breaks, keep the two
                # sessions apart rather than give them one number.
                logger.warning("Two sessions share the key %r; numbering them apart", key)
                key = f"{key}#{session.session_id}"
            seen.add(key)

            sid = self.sessions.get(key)
            if sid is None:
                sid = f"s{next_n}"
                next_n += 1
                self.sessions[key] = sid
            elif sid != session.session_id:
                logger.info("Session %r keeps %s (by date it would be %s)", key,
                            sid, session.session_id)
            n = _number(sid)
            session.session_id = sid
            session.session_number = n
            session.participant_id = f"p{n}"  # provisional, as before — reassigned after 5b
            session.participant_number = n
        return sorted(sessions, key=lambda s: s.session_number)

    # ── speakers ─────────────────────────────────────────────────────────

    def speakers_for(self, sid: str) -> dict[str, str]:
        return dict(self.speakers.get(sid, {}))

    def record_speakers(self, sid: str, label_codes: dict[str, str]) -> None:
        """Remember this run's codes; labels no longer heard keep their entry."""
        before = self._highest_participant()  # counts a code this update replaces
        self.speakers.setdefault(sid, {}).update(label_codes)
        self.participants_issued = max(before, self._highest_participant())

    def next_participant_number(self) -> int:
        """One past every participant number ever handed out, in any session."""
        return self._highest_participant() + 1

    def _highest_participant(self) -> int:
        numbers = [
            _number(code)
            for labels in self.speakers.values()
            for code in labels.values()
            if code.startswith("p")
        ]
        return max(self.participants_issued, *numbers, 0)


def _number(code: str) -> int:
    try:
        return int(code[1:])
    except ValueError:
        return 0
