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
- **pins** (version 2): per sid, speaker label → the role a person said that
  speaker is (design-people.md §J7 R3). Written by serve when a researcher
  re-analyses a session after a recode into or out of participant, honoured by
  every later run before codes are assigned. A pin carries the evidence it was
  set on — the start times of that label's turns — and a run whose label now
  covers other turns drops it and says so, rather than apply it to whoever
  holds the label now (a re-run of speaker identification can hand
  *Speaker A* to the other voice).

- **starts** (optional, 11 Oct 2026): per sid, the best start time a run has
  resolved for it and the signal it came from (``utils.session_start``). A
  later run replaces it only with a better-ranked signal, so a recording that
  iCloud evicts — its container unreadable until downloaded — cannot fall back
  to its file date, and a re-run on a Mac in another zone cannot move a start
  read from a filename's local wall clock. Additive and optional: a release
  that does not know it ignores it, and an entry this release cannot read is
  skipped, never a reason to refuse the file.

- **content keys** (version 3, 15 Oct 2026): a session is found first by its
  recording's content fingerprint (``utils.fingerprint``), stored as
  ``fp:v1:…`` beside one name key (``stem:…``, ``zoom:…``, ``stamp:…``) for the
  same sid. So renaming ``Recording 1433.mp4`` to ``p1 sarah.mp4`` keeps its
  number, its speaker codes and everything keyed by them, while editing a
  transcript file (new bytes, same name) still finds it by name. A sid has at
  most one name key: when its recording turns up under another name, the old
  name key goes, so a new recording given the old name is a new session.
  ``hints`` remembers where each fingerprint was last seen, which is how a
  cloud placeholder (no bytes, so no fingerprint) keeps its session.
  ``docs/design-project-identity.md`` §5–6.

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
import re
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bristlenose.models import InputSession

logger = logging.getLogger(__name__)

REGISTRY_VERSION = 3
#: Versions this release reads. Version 1 has no pins and version 2 no content
#: keys; each is read as such and written back as 3.
_READABLE_VERSIONS = (1, 2, 3)
#: The prefix of a content key in ``sessions``.
FP_PREFIX = "fp:"
#: The roles a pin may hold — ``SpeakerRole`` values.
PIN_ROLES = ("researcher", "participant", "observer")
REGISTRY_FILENAME = "sessions.json"
#: The label a session's placeholder participant is recorded under. Never a
#: real speaker: segments are keyed ``speaker_label or "Unknown"``.
NO_PARTICIPANT_LABEL = ""


def retired_label(code: str) -> str:
    """Where a session keeps a moderator or observer code it has retired —
    its speaker was not heard again, or was re-identified as another kind —
    so the code is never issued to someone else in that session, who would
    then wear the first speaker's name (design-people.md §J7). A label no
    speaker can have, like ``NO_PARTICIPANT_LABEL``."""
    return f"\u0000retired {code}"


def registry_path(output_dir: Path) -> Path:
    return output_dir / ".bristlenose" / REGISTRY_FILENAME


#: What a Re-analyse hands the new run: each recording's best start, keyed by
#: content. Read once by the next registry load, then folded in and deleted.
CARRIED_STARTS_FILENAME = "carried-starts.json"


def carried_starts_path(output_dir: Path) -> Path:
    return output_dir / ".bristlenose" / CARRIED_STARTS_FILENAME


#: A carried start for a session with no content key (a study analysed before
#: content keys whose recordings are still evicted) is keyed by a hash of its
#: name key: matchable on the next run, never a file name (§8).
NAME_CARRY_PREFIX = "name:"


def _name_carry_key(name_key: str) -> str:
    import hashlib

    return NAME_CARRY_PREFIX + hashlib.sha256(name_key.encode("utf-8")).hexdigest()[:32]


def starts_by_content(output_dir: Path) -> dict[str, dict[str, str]]:
    """The study's resolved starts keyed by recording content, for a Re-analyse.

    ``run --clean`` resets numbering and speakers, which is the point of it, but
    a start read from a recording's own clock or a filename may not be readable
    again: iCloud may have evicted the recording, or the researcher renamed it.
    So the starts cross the reset as a validated extract — fingerprint, UTC
    instant and source, nothing identifying, never the registry file
    (docs/design-project-identity.md §8). Empty on any problem: a carry is an
    improvement, never a reason to stop a run.
    """
    try:
        registry = SessionRegistry.load(output_dir)
    except ValueError:
        return {}
    by_sid = {
        sid: key[len(FP_PREFIX):] for key, sid in registry.sessions.items()
        if key.startswith(FP_PREFIX)
    }
    # A session with no content key yet (Fable review, 15 Oct 2026) crosses
    # under a hash of its name key instead of being dropped.
    for key, sid in registry.sessions.items():
        if sid not in by_sid and not key.startswith(FP_PREFIX):
            by_sid[sid] = _name_carry_key(key)
    return {
        by_sid[sid]: dict(entry) for sid, entry in registry.starts.items() if sid in by_sid
    }


def write_carried_starts(output_dir: Path, starts: dict[str, dict[str, str]]) -> None:
    if not starts:
        return
    path = carried_starts_path(output_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"version": 1, "starts": starts}, indent=2), encoding="utf-8")


@dataclass
class RolePin:
    """A person's word on what one session's speaker is (§J7 R3)."""

    role: str  # a ``PIN_ROLES`` value
    #: The label's turn start times when the pin was set, seconds to 0.01.
    starts: list[float]
    #: The code the speaker had when pinned — the slot serve held the
    #: researcher's pick on, which the importer moves to the new code.
    from_code: str = ""
    #: The person serve's slot pointed at (a uuid), carried to the new code.
    person: str = ""

    def to_json(self) -> dict[str, Any]:
        return {"role": self.role, "starts": self.starts, "from_code": self.from_code,
                "person": self.person}


def pin_starts(starts: list[float]) -> list[float]:
    """Start times as a pin records and compares them."""
    return sorted(round(float(t), 2) for t in starts)


@dataclass
class SessionRegistry:
    path: Path
    sessions: dict[str, str] = field(default_factory=dict)
    speakers: dict[str, dict[str, str]] = field(default_factory=dict)
    participants_issued: int = 0
    pins: dict[str, dict[str, RolePin]] = field(default_factory=dict)
    starts: dict[str, dict[str, str]] = field(default_factory=dict)
    #: Content key (``fp:v1:…``) → the recording's last known place, relative
    #: to the interview folder.
    hints: dict[str, str] = field(default_factory=dict)
    #: Starts a Re-analyse carried over, by fingerprint; used for a session the
    #: new run would otherwise start worse, and dropped once the registry saves.
    carried: dict[str, dict[str, str]] = field(default_factory=dict)

    # ── persistence ──────────────────────────────────────────────────────

    @classmethod
    def load(cls, output_dir: Path) -> SessionRegistry:
        """Read the registry, or start an empty one if the project has none.

        A file this version cannot read is refused loudly rather than replaced:
        starting afresh would renumber every session, which is the corruption
        the file exists to prevent.
        """
        path = registry_path(output_dir)
        carried = _read_carried(output_dir)
        if not path.exists():
            return cls(path=path, carried=carried)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValueError(
                f"Cannot read {path}: {exc}. It holds this project's session "
                "numbering; move it aside to renumber the sessions from scratch."
            ) from exc
        version = data.get("version") if isinstance(data, dict) else None
        if version not in _READABLE_VERSIONS:
            raise ValueError(
                f"{path} has version {version!r}; this Bristlenose reads versions "
                f"{', '.join(map(str, _READABLE_VERSIONS))}. It may have been written by a "
                "newer release."
            )
        problem = _problem(data)
        if problem:
            raise ValueError(
                f"Cannot read {path}: {problem}. It holds this project's session "
                "numbering; move it aside to renumber the sessions from scratch."
            )
        return cls(
            path=path,
            sessions=dict(data.get("sessions") or {}),
            speakers={sid: dict(labels) for sid, labels in (data.get("speakers") or {}).items()},
            participants_issued=data.get("participants_issued") or 0,
            pins={
                sid: {
                    label: RolePin(
                        role=pin["role"], starts=pin_starts(pin["starts"]),
                        from_code=pin.get("from_code", ""), person=pin.get("person", ""),
                    )
                    for label, pin in labels.items()
                }
                for sid, labels in (data.get("pins") or {}).items()
            },
            starts=_readable_starts(data.get("starts")),
            hints=_readable_hints(data.get("hints")),
            carried=carried,
        )

    def save(self) -> None:
        """Write atomically: a reader never sees half a file."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": REGISTRY_VERSION,
            "sessions": dict(sorted(self.sessions.items())),
            "speakers": {sid: self.speakers[sid] for sid in sorted(self.speakers)},
            "participants_issued": self.participants_issued,
            "pins": {
                sid: {label: pin.to_json() for label, pin in sorted(self.pins[sid].items())}
                for sid in sorted(self.pins) if self.pins[sid]
            },
            "starts": {sid: self.starts[sid] for sid in sorted(self.starts)},
            "hints": dict(sorted(self.hints.items())),
        }
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".sessions.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2, ensure_ascii=False)
                fh.write("\n")
                # On disk before the rename: otherwise a power cut can leave
                # an empty file, whose remedy renumbers the study.
                fh.flush()
                os.fsync(fh.fileno())
            from bristlenose.utils.fs import replace_retrying

            replace_retrying(tmp, self.path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
        if self.carried:
            # Folded into ``starts`` by settle_starts; its job is done.
            carried_starts_path(self.path.parent.parent).unlink(missing_ok=True)
            self.carried = {}

    # ── sessions ─────────────────────────────────────────────────────────

    def apply(
        self, sessions: list[InputSession], input_dir: Path | None = None,
        *, fetch: bool = False,
    ) -> list[InputSession]:
        """Give each session its remembered sid, or the next unused one.

        ``sessions`` arrive in ingest's order (recording date); new sessions
        are numbered in that order. Returns the sessions sorted by number.

        A session is found by its recording's content first, then by its
        place (a cloud placeholder's last known path), then by its name, and a
        sid already claimed in this run is never handed to a second session by
        a weaker key. ``input_dir`` lets the registry remember places relative
        to the interview folder; without it nothing is remembered.
        """
        from bristlenose.stages.s01_ingest import (
            fold_duplicate_recording,
            fold_duplicate_transcript,
            session_key,
        )

        used = {_number(sid) for sid in self.sessions.values()}
        next_n = max(used, default=0) + 1
        keys = [
            session_key(s.files, root=input_dir) if s.files else f"sid:{s.session_id}"
            for s in sessions
        ]
        # The same stem in two subfolders is two sessions (ingest keeps them
        # apart); their keys collide, so those — and only those — carry the
        # folder name. The plain key stays what every other project has.
        collisions = {k for k in keys if keys.count(k) > 1}
        seen: set[str] = set()
        named: list[str] = []
        for session, key in zip(sessions, keys, strict=True):
            if key in collisions and session.files:
                key = session_key(session.files, qualified=True, root=input_dir)
            if key in seen:
                # Grouping makes keys unique; if that ever breaks, keep the two
                # sessions apart rather than give them one number.
                logger.warning("Two sessions share the key %r; numbering them apart", key)
                key = f"{key}#{session.session_id}"
            seen.add(key)
            named.append(key)

        primaries = [
            self._held_primary(s, key, input_dir) for s, key in zip(sessions, named, strict=True)
        ]
        fps = [_fingerprint(f) for f in primaries]
        places = [_place(f, input_dir) for f in primaries]
        # Two copies of one recording in a study are kept as two sessions, as
        # ingest finds them; only one is keyed by content. The copy that owns
        # the key keeps it: its name still maps to the key's sid, or else it
        # carries a new name (renamed); a copy whose name belongs to another
        # session is that session. Name order breaks a fresh tie. Not ingest
        # order: ingest orders by date, which cloud sync rewrites (Fable
        # reviews, 15 Oct 2026).
        content_keyed = {v for k, v in self.sessions.items() if k.startswith(FP_PREFIX)}

        def owner_rank(j: int) -> tuple[int, str]:
            fp = fps[j]
            holder = self.sessions.get(FP_PREFIX + fp) if fp is not None else None
            mine = self.sessions.get(named[j])
            if holder is not None and mine == holder:
                return (0, named[j])
            # A name whose session holds bytes of its own (a re-export under
            # it) says nothing about these bytes: only a name owned by an
            # unkeyed duplicate is that duplicate's (Fable review).
            if mine is None or mine in content_keyed:
                return (1, named[j])
            return (2, named[j])

        first_with_fp: dict[str, int] = {}
        for i in sorted(range(len(fps)), key=owner_rank):
            fp_i = fps[i]
            if fp_i is not None:
                first_with_fp.setdefault(fp_i, i)

        # Identical bytes under two names are one recording (§5): the copy
        # that does not own the content key is folded into the one that does
        # — `first_with_fp`, by `owner_rank` — so the interview is transcribed
        # once, paid for once and counted once (R49, 20 Oct 2026). Until then
        # both were sessions, the second keyed by name, and the copy's quotes
        # read as a second participant agreeing. The set-aside copy is stated
        # on the run's summary, never dropped silently (register row 15).
        folded: set[int] = set()

        # A session with no recording, by the fingerprints of all its files:
        # taken before any fold moves files between sessions.
        transcript_fps: dict[int, frozenset[str]] = {}
        for i, s in enumerate(sessions):
            if s.files and not _is_media(primaries[i]):
                file_fps = [_fingerprint(f.path) for f in s.files]
                if all(fp is not None for fp in file_fps):
                    transcript_fps[i] = frozenset(fp for fp in file_fps if fp is not None)

        def fold(i: int, owner: int) -> None:
            copy, kept = primaries[i], primaries[owner]
            if _is_media(copy) and _is_media(kept):
                fold_duplicate_recording(sessions[owner], sessions[i])
            elif not _is_media(copy) and not _is_media(kept) and copy is not None:
                # The same transcript file twice with no recording — a Teams
                # .vtt or .docx downloaded twice — is one session too
                # (decision #97, 21 Oct 2026): owner, retire and statement
                # as for a recording, under its own reason. Every file of the
                # copy whose bytes the owner holds is set aside, not only the
                # one that matched (the .docx of a pair is not read twice).
                # (A file whose bytes are not here proves nothing either way.)
                held = {_fingerprint(f.path) for f in sessions[owner].files} - {None}
                fold_duplicate_transcript(sessions[owner], sessions[i], {
                    f.path for f in sessions[i].files
                    if f.path == copy or _fingerprint(f.path) in held
                })
            else:
                # A recording and a transcript file with one fingerprint are
                # not two copies of one thing: kept apart, and said.
                logger.warning(
                    "%r and %r hold the same bytes but one is a recording; kept apart",
                    named[i], named[owner],
                )
                return
            folded.add(i)
            # A study analysed before 20 Oct 2026 keyed the copy by name as
            # its own session. That session is retired — its key goes, so
            # the copy can never be found by it again (deleting the kept
            # copy would otherwise hand the survivor the copy's old number)
            # — and its number stays reserved, as every vanished session's
            # does; its speakers, pins and starts are left where they are.
            stale = self.sessions.get(named[i])
            if stale is not None and stale not in content_keyed:
                del self.sessions[named[i]]
                self.sessions.setdefault(f"retired:{stale}", stale)
                logger.warning(
                    "%s was the copy's own session; retired, its number kept", stale,
                )

        for i, fp in enumerate(fps):
            if fp is not None and first_with_fp[fp] != i:
                fold(i, first_with_fp[fp])
        # A Teams pair downloaded twice: a session's first file is its key,
        # and the two downloads can land their .vtt and .docx in a different
        # order, so the keys differ while every file is the same. Sessions
        # with no recording holding the same set of files are one session.
        same_files: dict[frozenset[str], list[int]] = {}
        for i, tfps in transcript_fps.items():
            if i not in folded and len(tfps) > 1:
                same_files.setdefault(tfps, []).append(i)
        for group in same_files.values():
            kept_i = min(group, key=owner_rank)
            for i in group:
                if i != kept_i:
                    fold(i, kept_i)

        claimed: set[str] = set()
        resolved: list[str | None] = [None] * len(sessions)

        def claim(i: int, sid: str | None) -> bool:
            if sid is None or sid in claimed:
                return False
            claimed.add(sid)
            resolved[i] = sid
            return True

        # Content, then place, then name — each pass only takes what is free.
        for i, fp in enumerate(fps):
            # A copy whose name belongs to another session is that session,
            # even when the keyed copy is gone (Fable review, 15 Oct 2026).
            if (fp is not None and first_with_fp[fp] == i and owner_rank(i)[0] != 2
                    and i not in folded):
                claim(i, self.sessions.get(FP_PREFIX + fp))
        for i, fp in enumerate(fps):
            if resolved[i] is None and fp is None and places[i] is not None:
                hinted = next((k for k, h in self.hints.items() if h == places[i]), None)
                if hinted is not None:
                    claim(i, self.sessions.get(hinted))
        content_owned = {sid for k, sid in self.sessions.items() if k.startswith(FP_PREFIX)}
        # A known recording is missing and a placeholder nobody has seen has
        # appeared: most likely the same recording, renamed while evicted to
        # the cloud. It would be a new session, and a new session is
        # downloaded to be transcribed in this run anyway, so download it now
        # and let its bytes decide, before anything is paid for twice (Fable
        # review, 15 Oct 2026). Only then: a first analysis downloads at
        # transcription, as before.
        # Only where the run will need the bytes anyway (``fetch``: run and
        # transcribe, never serve's re-render), and never for a recording with
        # a transcript beside it, which Whisper will not read.
        missing = content_owned - claimed if fetch else set()
        for i in range(len(sessions)):
            if not missing:
                break
            if (resolved[i] is not None or fps[i] is not None
                    or named[i] in self.sessions or not _is_media(primaries[i])
                    or sessions[i].has_existing_transcript
                    or not _is_dataless(primaries[i])):
                continue
            fp = _fingerprint_after_download(primaries[i])
            if fp is None:
                continue
            sid = self.sessions.get(FP_PREFIX + fp)
            owner = first_with_fp.get(fp)
            if owner is None and sid is not None and sid in claimed:
                owner = resolved.index(sid)
            if owner is not None:
                # A copy of a recording that is here — resident, or held by
                # its place while evicted: one recording, as above.
                fps[i] = fp
                fold(i, owner)
                continue
            fps[i] = fp
            first_with_fp[fp] = i
            if sid in missing and claim(i, sid):
                missing.discard(sid)
        for i in range(len(sessions)):
            if resolved[i] is None and i not in folded:
                sid = self.sessions.get(named[i])
                # A recording whose bytes are known and differ from the ones
                # this sid was keyed by is a different recording (§5): a
                # deleted interview's name reused, or a re-export. It must not
                # inherit the session, its codes and its typed names. A
                # transcript file is the exception: editing one is ordinary.
                # So is a recording arriving for a session analysed from its
                # transcript alone: its key holds the transcript's bytes, and
                # the recording joins it (Fable review, 15 Oct 2026).
                if (sid in content_owned and fps[i] is not None
                        and _is_media(primaries[i]) and self._keyed_by_media(sid)):
                    logger.warning(
                        "%r has new content under a name %s held: a new session. "
                        "A re-exported or trimmed recording is a different recording; "
                        "%s keeps its curation while its recording is missing.",
                        named[i], sid, sid,
                    )
                    continue
                claim(i, sid)

        for i, session in enumerate(sessions):
            if i in folded:
                continue
            sid = resolved[i]
            if sid is None:
                sid = f"s{next_n}"
                next_n += 1
                claimed.add(sid)
            elif sid != session.session_id:
                logger.info("Session %r keeps %s (by date it would be %s)", named[i],
                            sid, session.session_id)
            fp_i = fps[i] if first_with_fp.get(fps[i] or "") == i else None
            # A content key belongs to the session that holds it; it is never
            # handed to another (a duplicate, a copy named for another session),
            # or its owner is orphaned the next time it is renamed.
            if fp_i is not None and self.sessions.get(FP_PREFIX + fp_i, sid) != sid:
                fp_i = None
            # A recording's key outlives a run where only the transcript is
            # there: a transcript's bytes never replace it, or a different
            # recording under the old name could later inherit the session.
            if (fp_i is not None and not _is_media(primaries[i])
                    and self._holds_media_key(sid)):
                fp_i = None
            self._remember(sid, named[i], fp_i, places[i])
            n = _number(sid)
            session.session_id = sid
            session.session_number = n
            session.participant_id = f"p{n}"  # provisional, as before — reassigned after 5b
            session.participant_number = n
        kept = [s for i, s in enumerate(sessions) if i not in folded]
        return sorted(kept, key=lambda s: s.session_number)

    def _held_primary(
        self, session: InputSession, name_key: str, input_dir: Path | None = None,
    ) -> Path | None:
        """The file that names ``session`` (``_primary_file``), unless the
        session its name holds is keyed by the content of another recording
        here: then that recording, still.

        A video dropped beside an analysed audio file, or a second video
        added to an analysed Zoom folder that sorts first, would otherwise
        displace the recording the session was keyed by, and the session
        would be found by nothing and analysed again as a new one, its
        curation left behind on the old number (RE#129, 23 Oct 2026). Only
        the content key the session's own name holds counts, so a copy of
        another session's recording is never taken for this one's. A recording
        evicted to the cloud is known by the fingerprint last seen at its place.
        """
        default = _primary_file(session)
        sid = self.sessions.get(name_key)
        if sid is None or not _is_media(default):
            return default
        held = {
            key[len(FP_PREFIX):] for key, owner in self.sessions.items()
            if owner == sid and key.startswith(FP_PREFIX)
        }
        def fp(path: Path | None) -> str | None:
            if path is None:
                return None
            return _fingerprint(path) or self.last_known_fingerprint(path, input_dir)

        if not held or fp(default) in held:
            return default
        for f in session.files:
            if f.path != default and _is_media(f.path) and fp(f.path) in held:
                return f.path
        return default

    def _holds_media_key(self, sid: str) -> bool:
        """Whether ``sid`` holds a content key taken from a recording."""
        # No place known counts as a recording, as in `_keyed_by_media`: the
        # two must lean the same way, or an unchanged recording whose key had
        # no hint loses its session after a transcript-only run.
        return any(
            owner == sid and key.startswith(FP_PREFIX)
            and (key not in self.hints or _is_media(Path(self.hints[key])))
            for key, owner in self.sessions.items()
        )

    def _keyed_by_media(self, sid: str) -> bool:
        """Whether ``sid``'s content key was taken from a recording. Read from
        the place the key was taken at; with no place known, assume it was
        (the stricter answer: a new session rather than a wrong one)."""
        for key, owner in self.sessions.items():
            if owner == sid and key.startswith(FP_PREFIX):
                place = self.hints.get(key)
                return True if place is None else _is_media(Path(place))
        return True

    def last_known_fingerprint(self, path: Path, input_dir: Path | None) -> str | None:
        """The fingerprint last seen at ``path``'s place, for a file whose
        bytes are not on disk now (a cloud placeholder). ``None`` if unknown."""
        place = _place(path, input_dir)
        if place is None:
            return None
        key = next((k for k, h in self.hints.items() if h == place), None)
        return key[len(FP_PREFIX):] if key is not None else None

    def _remember(self, sid: str, name_key: str, fp: str | None, place: str | None) -> None:
        """Key ``sid`` by this run's name and, when known, its content.

        A sid keeps one name key: its old name goes when the recording turns up
        under another, so a new recording given the old name is a new session.
        """
        for k in [k for k, v in self.sessions.items()
                  if v == sid and not k.startswith(FP_PREFIX) and k != name_key]:
            del self.sessions[k]
        self.sessions[name_key] = sid
        if fp is not None:
            fp_key = FP_PREFIX + fp
            # One content key per sid, as with names: an edited transcript's
            # old bytes are gone, and two keys on one sid make the file
            # unreadable to the next run.
            for k in [k for k, v in self.sessions.items()
                      if v == sid and k.startswith(FP_PREFIX) and k != fp_key]:
                del self.sessions[k]
                self.hints.pop(k, None)
            self.sessions[fp_key] = sid
            if place is not None:
                # One recording per place: a deleted recording's place reused
                # by another must not answer for the newcomer when it is evicted.
                for k in [k for k, h in self.hints.items() if h == place and k != fp_key]:
                    del self.hints[k]
                self.hints[fp_key] = place

    # ── starts ───────────────────────────────────────────────────────────

    def settle_starts(
        self, sessions: list[InputSession], input_dir: Path | None = None,
    ) -> None:
        """Keep each session's best start: this run's, unless a stored one ranks
        at least as well. Mutates ``session_date`` / ``session_start_source``.
        ``input_dir`` keys a session as `apply` did.

        Ties keep the stored value on purpose — the same signal read again on
        a machine in another zone, or with a file that has since moved, should
        not move a start the researcher has already seen.
        """
        from bristlenose.utils.session_start import source_rank

        for session in sessions:
            new_rank = source_rank(session.session_start_source or "")
            stored = self.starts.get(session.session_id)
            carried = False
            if stored is None and self.carried:
                fp = _fingerprint(_primary_file(session))
                stored = self.carried.get(fp) if fp is not None else None
                if stored is None and session.files:
                    from bristlenose.stages.s01_ingest import session_key

                    for qualified in (False, True):
                        stored = self.carried.get(
                            _name_carry_key(session_key(
                                session.files, qualified=qualified, root=input_dir)))
                        if stored is not None:
                            break
                carried = stored is not None
            stored_rank = source_rank(stored["source"]) if stored else None
            if stored and stored_rank is not None and (
                new_rank is None or stored_rank <= new_rank
            ):
                at = parse_iso_utc(stored["utc"])
                if at is not None:
                    if at != session.session_date:
                        logger.info(
                            "%s keeps its start %s (%s) over this run's %s (%s)",
                            session.session_id, stored["utc"], stored["source"],
                            session.session_date.isoformat(), session.session_start_source,
                        )
                    session.session_date = at
                    session.session_start_source = stored["source"]
                    if carried:
                        self.starts[session.session_id] = dict(stored)
                    continue
            if new_rank is not None:
                self.starts[session.session_id] = {
                    "utc": session.session_date.astimezone(timezone.utc).isoformat(),
                    "source": session.session_start_source or "",
                }

    # ── speakers ─────────────────────────────────────────────────────────

    def speakers_for(self, sid: str) -> dict[str, str]:
        return dict(self.speakers.get(sid, {}))

    def record_speakers(self, sid: str, label_codes: dict[str, str]) -> None:
        """Remember this run's codes; labels no longer heard keep their entry.

        A label whose moderator or observer code changes (a role flip) would
        drop the old code from the map, and with it the only record that it
        was issued; it is kept under ``retired_label`` instead.
        """
        before = self._highest_participant()  # counts a code this update replaces
        current = self.speakers.setdefault(sid, {})
        for label, code in label_codes.items():
            old = current.get(label)
            if old and old != code and old[:1] in ("m", "o"):
                current[retired_label(old)] = old
        current.update(label_codes)
        self.participants_issued = max(before, self._highest_participant())

    # ── role pins (§J7 R3) ───────────────────────────────────────────────

    def label_for(self, sid: str, code: str) -> str | None:
        """The label holding ``code`` in a session now, or None."""
        for label, held in self.speakers.get(sid, {}).items():
            if held == code and not label.startswith("\u0000") and label != NO_PARTICIPANT_LABEL:
                return label
        return None

    def pin(self, sid: str, label: str, pin: RolePin) -> None:
        self.pins.setdefault(sid, {})[label] = pin

    def placeholder_participant(self, sid: str) -> str:
        """A participant code for a session that heard no participant this run.

        The session's earlier participant if it ever had one; otherwise a new
        number, recorded under ``NO_PARTICIPANT_LABEL`` so it stays this
        session's on later runs and is never issued to anyone else.
        """
        for code in self.speakers.get(sid, {}).values():
            if code.startswith("p"):
                return code
        code = f"p{self.next_participant_number()}"
        self.record_speakers(sid, {NO_PARTICIPANT_LABEL: code})
        return code

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


_SID = re.compile(r"s[1-9]\d*")
_CODE = re.compile(r"[pmo][1-9]\d*")


def _problem(data: dict[str, Any]) -> str:
    """What is wrong with a registry file's contents, or ``""``.

    Checked because every value here is used as an identity: a code that does
    not parse stops the run, ``p01`` is a different participant from ``p1``,
    and two keys on one sid merge two sessions.
    """
    sessions = data.get("sessions", {})
    speakers = data.get("speakers", {})
    if not isinstance(sessions, dict) or not isinstance(speakers, dict):
        return "sessions and speakers must be objects"
    sids = list(sessions.values())
    if not all(isinstance(sid, str) and _SID.fullmatch(sid) for sid in sids):
        return "a session id is not of the form s<n>"
    # Version 3 keys a session twice, by content and by name; within each kind
    # a sid appears once.
    for content in (True, False):
        kind = [sid for k, sid in sessions.items() if k.startswith(FP_PREFIX) == content]
        if len(set(kind)) != len(kind):
            return "two sessions share one session id"
    owner: dict[str, str] = {}
    for sid, labels in speakers.items():
        if not isinstance(labels, dict):
            return f"the speakers of {sid} are not an object"
        for code in labels.values():
            if not isinstance(code, str) or not _CODE.fullmatch(code):
                return f"{sid} holds a speaker code {code!r} that is not of the form p<n>, m<n> or o<n>"
            if code.startswith("p") and owner.setdefault(code, sid) != sid:
                return f"participant {code} is in both {owner[code]} and {sid}"
    issued = data.get("participants_issued", 0)
    if isinstance(issued, bool) or not isinstance(issued, int) or issued < 0:
        return f"participants_issued is {issued!r}, not a whole number"
    pins = data.get("pins", {})
    if not isinstance(pins, dict):
        return "pins must be an object"
    for sid, labels in pins.items():
        if not isinstance(labels, dict):
            return f"the pins of {sid} are not an object"
        for label, pin in labels.items():
            if not isinstance(pin, dict) or pin.get("role") not in PIN_ROLES:
                return f"{sid}'s pin on {label!r} has no role this release knows"
            starts = pin.get("starts")
            if not isinstance(starts, list) or not starts or not all(
                isinstance(t, (int, float)) and not isinstance(t, bool) for t in starts
            ):
                return f"{sid}'s pin on {label!r} carries no start times"
    return ""


def parse_iso_utc(value: str) -> datetime | None:
    try:
        at = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    return at.astimezone(timezone.utc) if at.tzinfo else None


def _readable_starts(raw: Any) -> dict[str, dict[str, str]]:
    """The ``starts`` entries this release can use; anything else is skipped
    with a log line, never a refusal — the file's job is numbering."""
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, str]] = {}
    for sid, entry in raw.items():
        if (
            isinstance(sid, str) and _SID.fullmatch(sid) and isinstance(entry, dict)
            and isinstance(entry.get("utc"), str) and isinstance(entry.get("source"), str)
            and parse_iso_utc(entry["utc"]) is not None
        ):
            out[sid] = {"utc": entry["utc"], "source": entry["source"]}
        else:
            logger.warning("sessions.json: ignoring an unreadable start for %r", sid)
    return out


def _read_carried(output_dir: Path) -> dict[str, dict[str, str]]:
    """A Re-analyse's carried starts, validated; anything else is ignored."""
    from bristlenose.utils.fingerprint import is_fingerprint

    path = carried_starts_path(output_dir)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        logger.warning("ignoring an unreadable %s", path)
        return {}
    raw = data.get("starts") if isinstance(data, dict) and data.get("version") == 1 else None
    if not isinstance(raw, dict):
        return {}
    from bristlenose.utils.session_start import source_rank

    return {
        fp: {"utc": e["utc"], "source": e["source"]} for fp, e in raw.items()
        if (is_fingerprint(fp) or _is_name_carry_key(fp)) and isinstance(e, dict)
        and isinstance(e.get("utc"), str) and parse_iso_utc(e["utc"]) is not None
        and isinstance(e.get("source"), str) and source_rank(e["source"]) is not None
    }


def _is_name_carry_key(key: object) -> bool:
    if not isinstance(key, str) or not key.startswith(NAME_CARRY_PREFIX):
        return False
    body = key[len(NAME_CARRY_PREFIX):]
    return len(body) == 32 and all(c in "0123456789abcdef" for c in body)


def _primary_file(session: InputSession) -> Path | None:
    """The file that IS the session: its video, else its audio, else the first
    file (a transcript). Grouping decides what sits together; this decides
    which bytes name it."""
    from bristlenose.models import FileType

    for kind in (FileType.VIDEO, FileType.AUDIO):
        for f in session.files:
            if f.file_type == kind:
                return f.path
    return session.files[0].path if session.files else None


def _is_media(path: Path | None) -> bool:
    from bristlenose.models import AUDIO_EXTENSIONS, VIDEO_EXTENSIONS

    return path is not None and path.suffix.lower() in (AUDIO_EXTENSIONS | VIDEO_EXTENSIONS)


def _fingerprint(path: Path | None) -> str | None:
    if path is None:
        return None
    from bristlenose.utils.fingerprint import content_fingerprint

    return content_fingerprint(path)


def _is_dataless(path: Path | None) -> bool:
    from bristlenose.utils.fs import is_dataless

    return path is not None and is_dataless(path)


def _fingerprint_after_download(path: Path | None) -> str | None:
    """Fault a cloud placeholder in and fingerprint it; ``None`` if the
    provider refuses. Raises ``CloudFetchTimeoutError`` when the bytes are
    still on their way after the full wait."""
    if path is None:
        return None
    from bristlenose.utils.fs import CloudFetchTimeoutError, ensure_materialised

    try:
        ensure_materialised(path)
    except CloudFetchTimeoutError:
        # Still downloading after the full wait: stop with that reason rather
        # than guess. Called a new session, it would finish downloading during
        # transcription and be analysed and paid for twice (Fable review,
        # 16 Oct 2026). The next run picks it up once it is here.
        raise
    except Exception as exc:  # the provider refusing, an unreadable file
        logger.info("could not fetch %s to identify it: %s", path.name, exc)
        return None
    return _fingerprint(path)


def _place(path: Path | None, input_dir: Path | None) -> str | None:
    if path is None or input_dir is None:
        return None
    try:
        return path.resolve().relative_to(input_dir.resolve()).as_posix()
    except (OSError, ValueError):
        pass
    # A symlink in the interview folder resolving elsewhere: its place is
    # where it sits in the folder, so the key is never left without one
    # (Fable review, 16 Oct 2026).
    def lexical(p: Path) -> Path:  # absolute and normalised, links kept
        return Path(os.path.normpath(p.absolute()))

    # The lexical folder first: a lexical path against a resolved base can
    # collapse a `link/..` into the wrong tree (Fable review, 16 Oct 2026).
    for base in (lexical(input_dir), input_dir.resolve()):
        try:
            return lexical(path).relative_to(base).as_posix()
        except (OSError, ValueError):
            continue
    return None


def _readable_hints(raw: Any) -> dict[str, str]:
    from bristlenose.utils.fingerprint import is_fingerprint

    if not isinstance(raw, dict):
        return {}
    return {
        k: v for k, v in raw.items()
        if isinstance(k, str) and k.startswith(FP_PREFIX)
        and is_fingerprint(k[len(FP_PREFIX):]) and isinstance(v, str)
    }


def _number(code: str) -> int:
    try:
        return int(code[1:])
    except ValueError:
        return 0
