"""When did a session start? The resolver behind the Sessions grid's Start column.

``docs/design-timezones.md`` § 2·5 ranks the signals and § 5.4 sets a
precedence; this module is § 5.4 for the signals we have today. It replaces
``min(file.created_at)`` — the file's *creation* time — which for most
recorders is the moment the file was saved, i.e. the session's END, and for a
cloud download is the moment it landed on this Mac.

Precedence, highest first (a lower rung is consulted only when every higher
one is absent):

1. **cloud_import** — the stamp Bristlenose's own cloud import writes into the
   filename, exactly as ``CloudDownloadVerification.filename`` writes it:
   ``2026-09-03 1000 — Title`` with an em dash, or the bare stamp for an
   untitled meeting. The platform's recording start (or the scheduled start
   when it gave none), on the importing Mac's wall clock, read in this
   machine's zone. A hand-typed ``2026-09-03 1000 - P3`` is NOT read: a
   researcher's typed time is often the booking, and a sequence number looks
   the same.
2. **filename_zoned** — a name that states its zone: Teams
   ``…-20260719_142007UTC-Meeting Recording``, Zoom cloud ``GMT20260115-143022_…``,
   Pixel ``PXL_20260115_143022123``, a Meet recording with ``GMT±n``/``UTC``.
3. **filename_local** — a name on a local clock: the Zoom local folder,
   macOS Screen Recording, Android ``VID_``/screen recorders/Samsung, OBS and
   Windows Game Bar, a Meet recording with a named zone. Read in this
   machine's zone. The full list is ``_FILENAME_RULES`` plus the three
   dedicated patterns; design-timezones § 5.9 has the coverage table.
4. **container** — the time the recorder wrote inside the file. Survives
   copying and downloading, which birthtime does not. Moved back by the
   duration only for a writer *measured* to stamp the end (``_END_WRITERS``).
5. **birthtime** — the file's creation time; what shipped before. Never
   adjusted.

**Why the filename outranks the container — a departure from § 5.4's order,
made in review (11 Oct 2026).** A recognised filename convention *states* the
start. The container is either derived (ReplayKit: end minus a duration that a
trim shortens, so a trimmed recording came out 20 minutes late) or written by a
writer nobody has measured (Zoom's local transcode is expected to stamp the
end, so the container lost the folder's exact start on every Zoom session).
The container stays above birthtime: for a copied or downloaded file it is the
only signal that survived. § 5.4's order can return once § 5.2's writer table
is measured.

**A container time is refused** when it is before 2000 or after the file was
created plus the tolerance — a recorder cannot stamp a file after it exists, so
either is a wrong clock (a 1970 epoch, a camera set years ahead).

Disagreement is reported, not resolved silently: when two signals from rungs
1–4 are present and differ by more than ``CONFLICT_TOLERANCE``, the higher rung
wins and the pair is logged at WARNING. Birthtime is excluded — for every
download it is the download moment, so it would disagree with everything.
The conflict reaches only the log today; a marker in the UI waits on
design-timezones § 4 and § 5.6.

**Not here, deliberately:** the recording's offset is not persisted; Google
Meet names are read on media files only (the Gemini notes Doc beside a
recording is stamped when Gemini finished); WhatsApp names (a message time) are
not read; and ``author`` is read in memory to classify the writer and never
stored. What is still owed: design-timezones § 5.10.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import TYPE_CHECKING

from bristlenose.utils.timecodes import from_local

if TYPE_CHECKING:
    from bristlenose.models import InputFile

logger = logging.getLogger(__name__)

#: Past this, two signals are telling different stories. Absorbs the consent
#: delay (recording starts a few minutes into the call) and encode overhead
#: (+14 s / +32 s measured on Screen Recordings); not the four-hour case
#: measured on ``System Audio 20220308 1316.mp4`` (design-timezones § 2·5 d).
CONFLICT_TOLERANCE = timedelta(minutes=5)

#: Years a recording start may plausibly fall in. Outside them a value is a
#: wrong clock, a mistyped name, or a 1970 epoch — and a year near the ends of
#: ``datetime``'s range makes ``astimezone`` raise, which would cost the scan.
_EARLIEST = datetime(2000, 1, 1, tzinfo=timezone.utc)
_LATEST_YEAR = 2100


class StartSource(str, Enum):
    """Which signal a resolved start came from — highest rank first."""

    CLOUD_IMPORT = "cloud_import"
    FILENAME_ZONED = "filename_zoned"
    FILENAME_LOCAL = "filename_local"
    CONTAINER = "container"
    BIRTHTIME = "birthtime"


_RANK = {source: i for i, source in enumerate(StartSource)}


def source_rank(source: str) -> int | None:
    """Rank of a stored source name, best = 0; ``None`` for a name this
    release does not know (written by a newer one)."""
    try:
        return _RANK[StartSource(source)]
    except ValueError:
        return None


@dataclass(frozen=True)
class StartCandidate:
    instant: datetime  # aware, UTC
    source: StartSource
    file_name: str


@dataclass(frozen=True)
class SessionStart:
    instant: datetime  # aware, UTC
    source: StartSource
    conflict: bool


# -- The writer table (design-timezones § 5.2) --------------------------------
#
# A writer stamps its container either when it starts recording or when it
# saves. Only a MEASURED row may move the time; everything else is taken as
# written. A new writer is a new row — measured first.
#
# - macOS ReplayKit (Screen Recording, ⇧⌘5): ``author = ReplayKitRecording``.
#   Measured 12 Sep 2026: container time = birthtime = END; moving it back by
#   the duration lands +14 s and +32 s after the filename's start. Re-measured
#   11 Oct 2026 on 32 files: container − birthtime is 0 or −1 s on every one.
#
# Writers that stamp the START need no row — taken as written is right:
# - Teams recording downloads (no writer tags; ``isom``): container time within
#   1 s and 6 s of the filename's start on the two measured files (11 Oct).
# - iPhone camera (``make = Apple``, ``model = iPhone …``): capture date equals
#   ``creation_time`` on 7 files. That it is the START is INFERRED (Photos
#   files a video at the moment recording began), not measured here.
# - QuickTime Player / Photo Booth on a Mac (``model = Mac…``): the capture
#   date is the start side and is read first (``_container_time``).
_END_WRITERS: tuple[tuple[str, str], ...] = (("author", "ReplayKitRecording"),)


def _stamps_end(file: InputFile) -> bool:
    meta = file.container_meta
    if meta is None:
        return False
    return any((getattr(meta, field) or "").strip() == value for field, value in _END_WRITERS)


# -- Filename signals ---------------------------------------------------------
#
# These read the same conventions s01_ingest's matching patterns strip. Those
# exist to make a video and its transcript meet; these keep the time the
# stripping throws away. Each is anchored and digit-shaped, so an ordinary
# title that merely contains a date is not read as a start time.

# Bristlenose's own cloud import, exactly as Swift writes it — em dash, or the
# bare stamp (`CloudDownloadVerification.filename`), plus an optional " (2)"
# part suffix.
_BN_STAMP_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2}) (\d{2})(\d{2})(?: — .+| \(\d+\))?$")

# Teams with a zone. An unzoned Teams stamp is somebody's local wall clock and
# we do not know whose — Swift's `TeamsRecordingName` returns no date for it,
# and neither do we.
_TEAMS_UTC_RE = re.compile(
    r"[\s-]+(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})utc-(?:meeting recording|meeting transcript)$",
    re.IGNORECASE,
)

# Zoom local recording folder: "2026-01-15 14.30.22 Topic 987654321".
_ZOOM_LOCAL_DIR_RE = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})\s+(\d{2})\.(\d{2})\.(\d{2})\s+.+\s+\d{9,11}$",
)

# macOS Screen Recording: "Screen Recording 2026-01-27 at 23.37.37", localised
# ("Bildschirmaufnahme 2026-01-27 um 23.37.37"), 12-hour in some regions —
# "… at 11.37.37 PM", or with the meridiem first ("… 오후 11.37.37",
# "… 午後11.37.37"). The time must END the stem: a renamed file is a title.
_SCREEN_RECORDING_RE = re.compile(
    r"\b(\d{4})-(\d{2})-(\d{2})\s+(?:([^\s\d]{1,4})\s*)?(\d{1,2})\.(\d{2})\.(\d{2})(?:\s*([ap]m))?$",
    re.IGNORECASE,
)
_PREFIX_MERIDIEM = {"오전": "am", "午前": "am", "am": "am", "오후": "pm", "午後": "pm", "pm": "pm"}


# Further conventions, one row each: (label, pattern, clock, media_only).
# Every pattern names its groups y/mo/d/h/mi and optionally s; ``clock`` is
# "utc" (the name says UTC) or "local" (somebody's wall clock — this
# machine's, for files this machine's recorders named). Each is anchored on
# the shape the app writes, so a title with a date in it does not match.
# Measured or documented per row; none is a guess about a writer's clock
# beyond what its own naming states.
_FILENAME_RULES: tuple[tuple[str, re.Pattern[str], str, bool], ...] = (
    # Zoom cloud recording download: "GMT20260115-143022_Recording_1920x1080".
    # Zoom names it by the recording start in GMT — the prefix says so.
    ("zoom_cloud", re.compile(
        r"^GMT(?P<y>\d{4})(?P<mo>\d{2})(?P<d>\d{2})-(?P<h>\d{2})(?P<mi>\d{2})(?P<s>\d{2})_",
    ), "utc", False),
    # Google Pixel camera: "PXL_20260115_143022123" — the Pixel names in UTC.
    ("pixel", re.compile(
        r"^PXL_(?P<y>\d{4})(?P<mo>\d{2})(?P<d>\d{2})_(?P<h>\d{2})(?P<mi>\d{2})(?P<s>\d{2})\d{0,3}"
        r"(?:\.[A-Z_]+)?(?:~\d+)?$",
    ), "utc", False),
    # Android cameras and screen recorders, local time:
    # "VID_20260115_143022", "Screen_Recording_20260115-143022_Zoom",
    # "screen-20260115-143022", and Samsung's bare "20260115_143022".
    ("android", re.compile(
        r"^(?:VID_|Screen_Recording_|screen-|Screenrecorder-|Record_)?"
        r"(?P<y>\d{4})(?P<mo>\d{2})(?P<d>\d{2})[_-](?P<h>\d{2})(?P<mi>\d{2})(?P<s>\d{2})"
        r"(?:[_-][\w.-]{0,40})?(?:\(\d+\))?$",
        re.IGNORECASE,
    ), "local", False),
    # OBS Studio's default ("2026-01-15 14-30-22") and Windows Game Bar
    # ("Zoom Meeting 2026-01-15 14-30-22"): the start, local, hyphenated time.
    ("obs_gamebar", re.compile(
        r"(?:^|\s)(?P<y>\d{4})-(?P<mo>\d{2})-(?P<d>\d{2})[ _](?P<h>\d{2})-(?P<mi>\d{2})-(?P<s>\d{2})$",
    ), "local", False),
    # Google Meet recording: "Title - 2026/08/15 22:45 BST - Recording"
    # (Drive; a download sanitises / and : to _). MEDIA ONLY: the Gemini notes
    # Doc beside it carries the moment Gemini finished, not the start.
    ("meet", re.compile(
        r"\s[-–]\s(?P<y>\d{4})[_/.-](?P<mo>\d{2})[_/.-](?P<d>\d{2})\s+(?P<h>\d{1,2})[_:.](?P<mi>\d{2})"
        r"(?:\s+(?P<tz>[A-Za-z]{2,5})(?P<off>[+-]\d{1,2})?)?\s*[-–]\s*.{1,30}$",
    ), "meet", True),
)
_MEDIA_TYPES = ("audio", "video")


def _rule_candidate(file: InputFile, stem: str) -> list[StartCandidate]:
    out: list[StartCandidate] = []
    media = getattr(file.file_type, "value", str(file.file_type)) in _MEDIA_TYPES
    for _label, pattern, clock, media_only in _FILENAME_RULES:
        if media_only and not media:
            continue
        m = pattern.search(stem)
        if not m:
            continue
        g = m.groupdict()
        y, mo, d, h, mi = (int(g[k]) for k in ("y", "mo", "d", "h", "mi"))
        sec = int(g["s"]) if g.get("s") else 0
        zone: timezone | None = None
        if clock == "utc":
            zone = timezone.utc
        elif clock == "meet":
            tz = (g.get("tz") or "").upper()
            if tz in ("UTC", "GMT"):
                zone = timezone(timedelta(hours=int(g["off"]))) if g.get("off") else timezone.utc
            else:
                # A named zone ("BST", "CEST") is honoured only when it is this
                # machine's own zone at that moment — then the local reading is
                # right. Any other name is somebody else's clock, and the
                # abbreviations are ambiguous (IST, BST), so it is not read.
                local = _local(y, mo, d, h, mi, sec)
                if local is not None and tz and from_local(
                    datetime(y, mo, d, h, mi, sec)
                ).tzname() == tz:
                    out.append(StartCandidate(local, StartSource.FILENAME_LOCAL, file.path.name))
                continue
        if zone is not None:
            try:
                instant: datetime | None = datetime(y, mo, d, h, mi, sec, tzinfo=zone).astimezone(timezone.utc)
            except (ValueError, OverflowError):
                instant = None
            if instant is not None and _instant_ok(instant):
                out.append(StartCandidate(instant, StartSource.FILENAME_ZONED, file.path.name))
        else:
            local = _local(y, mo, d, h, mi, sec)
            if local is not None:
                out.append(StartCandidate(local, StartSource.FILENAME_LOCAL, file.path.name))
    return out


def _instant_ok(instant: datetime) -> bool:
    return _EARLIEST <= instant and instant.year <= _LATEST_YEAR


def _local(year: int, month: int, day: int, hour: int, minute: int, second: int = 0) -> datetime | None:
    """A wall-clock time on this machine, as an aware UTC instant; None if invalid.

    An autumn repeated hour takes its first (summer-time) reading, and a
    spring-forward gap time moves by the gap — only a hand-named file can carry
    either, since a real stamp comes from a real clock.
    """
    if not 2000 <= year <= _LATEST_YEAR:
        return None
    try:
        return from_local(datetime(year, month, day, hour, minute, second)).astimezone(timezone.utc)
    except (ValueError, OverflowError, OSError):
        return None


def _meridiem_hour(hour: int, meridiem: str) -> int | None:
    if not meridiem:
        return hour
    if not 1 <= hour <= 12:
        return None
    if meridiem == "pm":
        return hour if hour == 12 else hour + 12
    return 0 if hour == 12 else hour


def _filename_candidates(file: InputFile) -> list[StartCandidate]:
    stem = file.path.stem
    name = file.path.name
    out: list[StartCandidate] = []

    m = _BN_STAMP_RE.match(stem)
    if m:
        y, mo, d, h, mi = (int(g) for g in m.groups()[:5])
        instant = _local(y, mo, d, h, mi)
        if instant is not None:
            out.append(StartCandidate(instant, StartSource.CLOUD_IMPORT, name))

    m = _TEAMS_UTC_RE.search(stem)
    if m:
        y, mo, d, h, mi, s = (int(g) for g in m.groups()[:6])
        try:
            zoned: datetime | None = datetime(y, mo, d, h, mi, s, tzinfo=timezone.utc)
        except ValueError:
            zoned = None
        if zoned is not None and _instant_ok(zoned):
            out.append(StartCandidate(zoned, StartSource.FILENAME_ZONED, name))

    parent = file.path.parent.name
    m = _ZOOM_LOCAL_DIR_RE.match(parent) if parent else None
    if m:
        y, mo, d, h, mi, s = (int(g) for g in m.groups()[:6])
        instant = _local(y, mo, d, h, mi, s)
        if instant is not None:
            out.append(StartCandidate(instant, StartSource.FILENAME_LOCAL, name))

    # WhatsApp names media by when the MESSAGE was sent ("WhatsApp Video
    # 2026-01-15 at 14.30.22") — same shape as a Screen Recording, wrong meaning.
    m = None if stem.lower().startswith("whatsapp") else _SCREEN_RECORDING_RE.search(stem)
    if m:
        y, mo, d = (int(g) for g in m.groups()[:3])
        word = (m.group(4) or "").lower()
        h, mi, s = (int(g) for g in m.groups()[4:7])
        meridiem = (m.group(8) or "").lower() or _PREFIX_MERIDIEM.get(word, "")
        hour = _meridiem_hour(h, meridiem)
        instant = _local(y, mo, d, hour, mi, s) if hour is not None else None
        if instant is not None:
            out.append(StartCandidate(instant, StartSource.FILENAME_LOCAL, name))

    out.extend(_rule_candidate(file, stem))
    return out


def _container_time(file: InputFile) -> datetime | None:
    """The container's best start-side time, as an aware value.

    Apple's ``com.apple.quicktime.creationdate`` (``creation_local``) is the
    capture date and wins when present; ``creation_time`` is otherwise taken.
    On a Mac-made QuickTime file they differ — capture date 34 s before
    ``creation_time``, which equals the save moment (measured 11 Oct 2026, one
    file) — and on iPhone files they are identical, so preferring the capture
    date costs nothing there. A naive value is never trusted: ``astimezone``
    would read it as this machine's local time.
    """
    meta = file.container_meta
    if meta is None:
        return None
    for value in (meta.creation_local, meta.creation_utc):
        if value is not None and value.tzinfo is not None:
            return value
    return None


def _container_candidate(file: InputFile) -> StartCandidate | None:
    stamped = _container_time(file)
    if stamped is None:
        return None
    try:
        instant = stamped.astimezone(timezone.utc)
        if not _instant_ok(instant) or instant > file.created_at + CONFLICT_TOLERANCE:
            logger.warning(
                "session_start_container_refused | file=%s | container=%s | created=%s",
                file.path.name, instant.isoformat(), file.created_at.isoformat(),
            )
            return None
        if _stamps_end(file):
            if not file.duration_seconds:
                # Taken as written it is the END — exactly the wrong this replaces.
                return None
            instant -= timedelta(seconds=file.duration_seconds)
    except (ValueError, OverflowError):
        return None
    return StartCandidate(instant, StartSource.CONTAINER, file.path.name)


def _birthtime_candidate(file: InputFile) -> StartCandidate:
    return StartCandidate(file.created_at.astimezone(timezone.utc), StartSource.BIRTHTIME, file.path.name)


def candidates_for(file: InputFile) -> list[StartCandidate]:
    """Every start signal one file carries, best first."""
    out = _filename_candidates(file)
    container = _container_candidate(file)
    if container is not None:
        out.append(container)
    out.append(_birthtime_candidate(file))
    out.sort(key=lambda c: _RANK[c.source])
    return out


def resolve_session_start(files: list[InputFile]) -> SessionStart:
    """Resolve one session's start from all of its files.

    The highest-ranked source wins; within a rank, the earliest instant (two
    files of one session recorded a few seconds apart). A disagreement beyond
    ``CONFLICT_TOLERANCE`` between the winner and any other non-birthtime
    signal is logged, naming both files, and returned as ``conflict=True``;
    the winner stands.
    """
    if not files:
        raise ValueError("a session has at least one file")
    every = [c for f in files for c in candidates_for(f)]
    best_rank = min(_RANK[c.source] for c in every)
    winner = min((c for c in every if _RANK[c.source] == best_rank), key=lambda c: c.instant)

    conflict = False
    for other in every:
        if other.source is StartSource.BIRTHTIME or other is winner:
            continue
        if abs(other.instant - winner.instant) > CONFLICT_TOLERANCE:
            conflict = True
            logger.warning(
                "session_start_conflict | kept=%s %s (%s) | other=%s %s (%s)",
                winner.source.value,
                winner.instant.isoformat(),
                winner.file_name,
                other.source.value,
                other.instant.isoformat(),
                other.file_name,
            )
    return SessionStart(winner.instant, winner.source, conflict)
