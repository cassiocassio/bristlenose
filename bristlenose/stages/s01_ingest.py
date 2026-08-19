"""Stage 1: File discovery, classification, and participant numbering."""

from __future__ import annotations

import logging
import platform
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

from bristlenose.models import (
    FileType,
    InputFile,
    InputSession,
    classify_file,
)
from bristlenose.refusals import MESSAGES, UnusableReason
from bristlenose.utils.audio import probe_duration
from bristlenose.utils.fs import is_dataless, is_os_metadata

logger = logging.getLogger(__name__)


class SkippedFile(NamedTuple):
    """A file the scan declined, and why — so the decline can be *stated*.

    Discovery used to drop unrecognised files at DEBUG level, which reads as
    "there was nothing there" rather than "there was something and we ignored
    it". For a researcher that difference is a missing participant they still
    believe is in the report.

    OS metadata (``._foo.mp4``, ``.DS_Store``) is deliberately NOT collected —
    it is genuine noise the user never created and does not want listed.
    """

    path: Path
    #: Why, as a token the summary can turn into a sentence. Prose stays out of
    #: the scan so the log and the researcher-facing surfaces can word it
    #: differently without this stage knowing they exist.
    reason: UnusableReason
    #: Extra context for the log only — an errno string, say. Never reaches
    #: ``Cause.message``: ``pipeline-events.jsonl`` is a re-identification
    #: surface and an OS error can name paths.
    detail: str | None = None


def _get_creation_time(path: Path) -> datetime:
    """Get the file creation time.

    - macOS: st_birthtime (true creation time)
    - Windows: st_ctime (true creation time on NTFS)
    - Linux: st_ctime is metadata-change time, not creation; we fall back
      to st_mtime (last modification) which is the most stable proxy.
    """
    stat = path.stat()
    if platform.system() == "Darwin":
        ts = stat.st_birthtime
    elif platform.system() == "Windows":
        ts = stat.st_ctime  # true creation time on NTFS
    else:
        # Linux: st_ctime is inode change time, not creation.
        # st_mtime (last modified) is a better proxy for "when was this recorded".
        ts = stat.st_mtime
    return datetime.fromtimestamp(ts, tz=timezone.utc)


class UnsuitableInputDirError(ValueError):
    """The folder is not a plausible study folder — refuse it by name.

    Raised for filesystem and system roots. Deliberately NOT raised for a
    merely-large folder: a thousand ten-second video answers to one question is
    an ordinary unmoderated study, while ten ninety-minute interviews is five
    times the work at one percent of the file count. Volume is the wrong axis;
    what makes a drop wrong is *what it is*, not how much of it there is.
    """


# Files at most this many levels below the drop point are ingested.
#
#   project/interview.mp4              level 1  ✓
#   project/week1/interview.mp4        level 2  ✓
#   project/week1/zoom1/video.mp4      level 3  ✓
#   project/a/b/c/video.mp4            level 4  ✗
#
# Three is what real folder shapes need: a study grouped into weeks or rounds,
# each holding per-meeting folders from Zoom. It is also what stops Zoom being a
# special case — `zoom1/` is just a folder that happens to contain media, and
# `group_into_sessions` keys the Zoom rule on the *containing* directory name,
# so it works at any depth. Measured before choosing: a whole-filesystem scan at
# this depth visits ~4,000 entries and finds 5 media files, so the cap is not
# what protects against a silly drop — `_refuse_reason` is.
#: Our own output directory, which by default lives *inside* the input
#: folder. Matches `ProjectFolderWatcher.filterEligible`'s exclusion. The
#: literal is repeated in `cli.py` (six sites) — worth one shared constant,
#: but that is a separate sweep, not this one.
OUTPUT_DIR_NAME = "bristlenose-output"

_MAX_SCAN_DEPTH = 3


def _refuse_reason(input_dir: Path) -> str | None:
    """Return why *input_dir* cannot be a study folder, or None if it can.

    Structural, not numeric, and it runs before anything touches the disk hard.
    Only the roots themselves are refused — `~/Documents` and `~/Desktop` are
    entirely reasonable places to keep a study, so refusing them would be wrong.
    """
    resolved = input_dir.resolve()
    home = Path.home().resolve()

    if resolved == Path(resolved.anchor):
        return "it is the root of the filesystem"
    if resolved == home:
        return "it is your home folder"
    system_roots = {
        Path("/Applications"), Path("/System"), Path("/Library"), Path("/Volumes"),
        Path("/private"), Path("/usr"), Path("/bin"), Path("/sbin"), Path("/etc"),
        Path("/var"), Path("/opt"), Path("/cores"), home / "Library",
    }
    if resolved in system_roots:
        return "it is a system folder"
    return None


def discover_files(
    input_dir: Path, skipped: list[SkippedFile] | None = None
) -> list[InputFile]:
    """Scan an input directory for supported files.

    Args:
        input_dir: Directory to scan.
        skipped: Optional list to collect files that were declined. Pass one to
            report them to the user; omit it and the behaviour is unchanged.

    Returns a list of InputFile objects sorted by creation date.

    Raises:
        UnsuitableInputDirError: *input_dir* is a filesystem or system root.
    """
    reason = _refuse_reason(input_dir)
    if reason is not None:
        raise UnsuitableInputDirError(
            f"{input_dir} can't be analysed because {reason}. "
            "Point Bristlenose at the folder holding your recordings."
        )

    files: list[InputFile] = []
    _scan_dir(input_dir, 0, files, skipped)

    # Sort by creation date, then filename as tiebreaker
    files.sort(key=lambda f: (f.created_at, f.path.name))
    return files


def _scan_dir(
    directory: Path,
    depth: int,
    files: list[InputFile],
    skipped: list[SkippedFile] | None,
) -> None:
    """Walk *directory*, descending while files stay within _MAX_SCAN_DEPTH.

    An unreadable directory is recorded and stepped over, never fatal. Dropping
    a folder containing one protected directory — `~/.Trash` is the everyday
    case — used to raise PermissionError out of `iterdir` and destroy the whole
    scan, which is the same one-bad-entry-kills-everything shape as the
    zero-byte file that aborted a 42-session run.
    """
    try:
        entries = sorted(directory.iterdir())
    except PermissionError:
        if skipped is not None:
            skipped.append(
                SkippedFile(
                    directory, UnusableReason.UNREADABLE_FOLDER, "permission denied"
                )
            )
        logger.warning("Skipping unreadable directory: %s", directory)
        return
    except OSError as exc:
        if skipped is not None:
            skipped.append(
                SkippedFile(directory, UnusableReason.UNREADABLE_FOLDER, exc.strerror)
            )
        logger.warning("Skipping unreadable directory %s: %s", directory, exc)
        return

    for entry in entries:
        if is_os_metadata(entry):
            continue
        try:
            if entry.is_dir():
                # Never descend into our own output, and never report what is
                # in there as declined. The default output directory lives
                # *inside* the input folder, so a re-run scans the last run's
                # artefacts: with refusals now surfaced by name, the first thing
                # a researcher saw was "bristlenose.db — not a format
                # Bristlenose reads", which is noise they did not create and
                # cannot act on. Same argument the OS-metadata filter above
                # already makes. `ProjectFolderWatcher.filterEligible` has
                # excluded this name since it was written; discovery had not,
                # which is the same scanner-parity gap
                # `tests/test_accepted_extension_parity.py` exists to catch.
                if entry.name == OUTPUT_DIR_NAME:
                    continue
                if depth + 1 < _MAX_SCAN_DEPTH:
                    _scan_dir(entry, depth + 1, files, skipped)
            elif entry.is_file():
                _try_add_file(entry, files, skipped)
        except OSError as exc:  # a single unstatable entry must not end the walk
            logger.warning("Skipping unreadable entry %s: %s", entry, exc)


def _try_add_file(
    path: Path, files: list[InputFile], skipped: list[SkippedFile] | None = None
) -> None:
    """Classify a file and add it to the list if supported."""
    file_type = classify_file(path)
    if file_type is None:
        suffix = path.suffix.lower() or "(no extension)"
        logger.debug("Skipping unsupported file: %s", path.name)
        if skipped is not None:
            skipped.append(
                SkippedFile(path, UnusableReason.UNSUPPORTED_FORMAT, suffix)
            )
        return

    created_at = _get_creation_time(path)
    size_bytes = path.stat().st_size

    # Probe duration for audio/video files — but never fault a cloud placeholder
    # in to do it. `probe_duration` materialises before probing, so scanning a
    # folder holding evicted recordings would download them all just to learn
    # their length. Duration at scan time is a nicety; the bytes are genuinely
    # needed at transcription, where the wait is expected and attributable.
    duration: float | None = None
    if file_type in (FileType.AUDIO, FileType.VIDEO) and not is_dataless(path):
        duration = probe_duration(path)

    files.append(
        InputFile(
            path=path,
            file_type=file_type,
            created_at=created_at,
            size_bytes=size_bytes,
            duration_seconds=duration,
        )
    )
    logger.debug("Found %s file: %s", file_type.value, path.name)


# -- Platform filename patterns --------------------------------------------------

# Teams. Two real specimens, both captured 15 Aug 2026 — note the separator is
# a HYPHEN, and the "UTC" marker appears on personal tenants only:
#
#   Meeting with Martin Storey-20260719_142007UTC-Meeting Recording.mp4   (personal)
#   Meeting with Martin Storey-20260815_200732-Meeting Recording.mp4      (business)
#
# The transcript sibling carries neither timestamp nor suffix — it is just
# "Meeting with Martin Storey.vtt" — so stripping this tail is the whole
# mechanism by which video and transcript become one session.
#
# This pattern originally required whitespace before the timestamp and no UTC
# marker, which matched neither real format and only ever matched the
# constructed fixture written alongside it. Both real files therefore ingested
# as two separate sessions, and the mp4 was re-transcribed from scratch.
_TEAMS_SUFFIX_RE = re.compile(
    r"[\s-]+\d{8}_\d{6}(utc)?-(meeting recording|meeting transcript)$",
    re.IGNORECASE,
)

# Zoom cloud: "Topic_987654321_Jan_15_2026" or "Audio Transcript_Topic_..."
# The meeting ID is 9-11 digits; the date is Month_DD_YYYY.
_ZOOM_CLOUD_TAIL_RE = re.compile(
    r"_\d{9,11}_[a-z]{3}_\d{1,2}_\d{4}$",
    re.IGNORECASE,
)
_ZOOM_CLOUD_PREFIX_RE = re.compile(
    r"^audio transcript_",
    re.IGNORECASE,
)

# Zoom local folder: "2026-01-15 14.30.22 Topic 987654321"
_ZOOM_LOCAL_DIR_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}\s+\d{2}\.\d{2}\.\d{2}\s+.+\s+\d{9,11}$",
)

# Google Meet (prep for Phase 2): "Title (2026-01-28 at 14 30 GMT-5)"
_GMEET_PAREN_RE = re.compile(
    r"\s+\(\d{4}-\d{1,2}-\d{1,2}\s+at\s+.+?\)\s*$",
    re.IGNORECASE,
)
_GMEET_TRANSCRIPT_SUFFIX_RE = re.compile(
    r"\s*[-–]\s*transcript$",
    re.IGNORECASE,
)

# Google Meet, current naming — the two patterns above match nothing Google
# emits today. Two specimens, both captured 15 Aug 2026 on a Workspace Business
# Standard tenant:
#
#   Banyalbufar discussion - 2026_08_15 23_02 - Notes by Gemini.docx   (on disk)
#   Banyalbufar discussion - 2026/08/15 22:45 BST - Recording          (Drive name)
#
# Only the first was observed on disk; the second is the Drive resource name as
# Google itself writes it in the notes document's own Attachments line. Drive's
# API `name` uses "/" and ":"; the download is sanitised to "_", so accept both.
# The timezone marker appears on the recording and not the notes Doc, so it is
# optional. `transcript` as a trailing kind is INFERRED, not observed.
#
# Three things fix the shape of this pattern:
#
# 1. **Strip the whole tail, not just the suffix.** The recording is stamped
#    with the meeting start and the Doc with the moment Gemini finished writing
#    — 22:45 vs 23:02 in the pair above. A suffix-only strip leaves two stems
#    that still differ, so the pair still becomes two sessions and the mp4 is
#    still re-transcribed from scratch. That is the whole bug.
# 2. **The trailing kind is mandatory.** It is what stops an ordinary title that
#    merely ends in a date ("Q3 planning - 2026/08/15 14:00") being truncated.
# 3. **But its content is not matched.** "Recording" and "Notes by Gemini" are
#    localised in a non-English tenant; the digits are not. Enumerating the
#    English words is the trap that made `_TEAMS_SUFFIX_RE` — and Swift's
#    `TeamsRecordingName` — match only the fixtures invented alongside them.
#    So: require " - <short run>" structurally, match any language's word for it.
_GMEET_TAIL_RE = re.compile(
    r"\s*[-–]\s*"                          # " - " before the timestamp
    r"\d{4}[_/.-]\d{2}[_/.-]\d{2}"         # 2026_08_15  /  2026/08/15
    r"\s+\d{1,2}[_:.]\d{2}"                # 23_02       /  23:02
    r"(?:\s+[a-z]{2,5}(?:[+-]\d{1,2})?)?"  # BST / UTC / GMT-5   (optional)
    r"\s*[-–]\s*"                          # " - " before the kind
    r".{1,30}$",                           # Recording / Gravació / 錄影 …
    re.IGNORECASE,
)


# Bristlenose's own cloud-import naming: "2026-08-12 1400 — P07 Interview.mp4"
# (`CloudDownloadNaming.filename`, desktop side). Date first so a Finder listing
# is chronological, title second so the researcher can see which session it is.
#
# **Why this has to be stripped, and it is not cosmetic.** We *rename on
# download*, so none of the platform patterns above can ever fire on a file we
# fetched ourselves — their whole job is to recognise the vendor's convention,
# and by the time the file is on disk it no longer wears one. Without this rule
# a cloud-imported video and a hand-fetched transcript of the same meeting
# normalise differently and become **two sessions**: the video re-transcribed by
# Whisper, and a phantom media-less session holding the transcript.
#
# That is the exact workflow it breaks. Neither Dovetail nor Marvin trusts the
# platforms' transcripts either — everyone reprocesses — but a researcher who
# fetches the Teams transcript by hand gets *accurate speaker names* out of it,
# which is a real time saver and the reason to do it at all. Splitting the pair
# threw away precisely that.
#
# The date goes for the same reason it goes on every pattern above: it is the
# one field the video and its transcript are guaranteed to share, so keeping it
# cannot help pairing, and dropping it is what lets the two meet. The known
# consequence — two same-titled meetings on different days collapsing into one
# session — is a pre-existing property of every rule here, not something this
# one introduces.
#
# The sibling ordinal (" (2)") is deliberately NOT stripped: two halves of one
# call stay two sessions, which is what happens today for platform-named files.
_BN_DOWNLOAD_PREFIX_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}\s+\d{4}\s*[—–-]\s*",
)


def _normalise_stem(stem: str) -> str:
    """Normalise a filename stem for session matching.

    Strips platform-specific naming suffixes so that a video file and its
    transcript end up with the same key even when the platforms use different
    filename conventions.

    Expects *stem* to already be lowercased.
    """
    # 1. Legacy suffixes (existing behaviour)
    for suffix in ("_transcript", "_subtitles", "_captions", "_sub", "_srt"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break

    # 2. Bristlenose's own download naming, first: a file we fetched wears no
    #    vendor convention at all, so none of the platform rules below can see
    #    it. Stripping the stamp is what lets it meet a hand-fetched transcript.
    stem = _BN_DOWNLOAD_PREFIX_RE.sub("", stem)

    # 3. Teams: strip "-Meeting Recording" / "-meeting transcript" + date prefix
    stem = _TEAMS_SUFFIX_RE.sub("", stem)

    # 4. Zoom cloud: strip "Audio Transcript_" prefix and trailing "_ID_DATE"
    stem = _ZOOM_CLOUD_PREFIX_RE.sub("", stem)
    stem = _ZOOM_CLOUD_TAIL_RE.sub("", stem)

    # 5. Google Meet: the dated tail first — it needs the trailing kind in order
    #    to match, and `_GMEET_TRANSCRIPT_SUFFIX_RE` would otherwise eat it.
    stem = _GMEET_TAIL_RE.sub("", stem)
    stem = _GMEET_TRANSCRIPT_SUFFIX_RE.sub("", stem)
    stem = _GMEET_PAREN_RE.sub("", stem)

    return stem.strip()


def _is_zoom_local_dir(dir_name: str) -> bool:
    """Return True if *dir_name* matches the Zoom local recording folder pattern."""
    return bool(_ZOOM_LOCAL_DIR_RE.match(dir_name))


def group_into_sessions(files: list[InputFile]) -> list[InputSession]:
    """Group files into sessions and assign participant numbers.

    Grouping heuristic:
    1. Files in a Zoom-style subdirectory are grouped by directory.
    2. Remaining files sharing the same normalised stem are one session.
    3. Otherwise, each file is its own session.

    Stems are normalised to strip platform naming conventions (Teams date/suffix,
    Zoom cloud meeting ID, Google Meet parenthetical date).

    Participant numbers (p1, p2, ...) are assigned by the creation date of the
    session's earliest file.
    """
    # -- Pass 1: Zoom local folders (all files in the folder = one session) ------
    zoom_dir_groups: dict[str, list[InputFile]] = {}
    remaining: list[InputFile] = []
    for f in files:
        parent = f.path.parent.name
        if parent and _is_zoom_local_dir(parent):
            zoom_dir_groups.setdefault(parent, []).append(f)
        else:
            remaining.append(f)

    # -- Pass 2: normalised stem matching on remaining files ---------------------
    stem_groups: dict[str, list[InputFile]] = {}
    for f in remaining:
        stem = _normalise_stem(f.path.stem.lower())
        stem_groups.setdefault(stem, []).append(f)

    # -- Merge both grouping passes into raw sessions --------------------------
    raw_sessions: list[tuple[datetime, list[InputFile]]] = []
    for _dir, group_files in zoom_dir_groups.items():
        session_date = min(f.created_at for f in group_files)
        raw_sessions.append((session_date, group_files))
    for _stem, group_files in stem_groups.items():
        session_date = min(f.created_at for f in group_files)
        raw_sessions.append((session_date, group_files))

    # Sort by session date, then first filename
    raw_sessions.sort(key=lambda s: (s[0], s[1][0].path.name))

    # Assign session and provisional participant numbers
    sessions: list[InputSession] = []
    for i, (session_date, group_files) in enumerate(raw_sessions, start=1):
        session_id = f"s{i}"
        participant_id = f"p{i}"  # provisional — reassigned after Stage 5b

        # Determine if this session has an existing transcript
        has_transcript = any(
            f.file_type in (FileType.SUBTITLE_SRT, FileType.SUBTITLE_VTT, FileType.DOCX)
            for f in group_files
        )

        session = InputSession(
            session_id=session_id,
            session_number=i,
            participant_id=participant_id,
            participant_number=i,
            files=group_files,
            has_existing_transcript=has_transcript,
            session_date=session_date,
        )
        sessions.append(session)
        logger.info(
            "Session %s: %d files, date=%s, has_transcript=%s",
            session_id,
            len(group_files),
            session_date.date(),
            has_transcript,
        )

    return sessions


def ingest(
    input_dir: Path, skipped: list[SkippedFile] | None = None
) -> list[InputSession]:
    """Full ingestion pipeline: discover files, group into sessions.

    Args:
        input_dir: Directory containing input files.
        skipped: Optional list to collect what was declined, so the caller can
            put it on the run's terminus summary. Omit it and the behaviour is
            unchanged — the refusals are still logged, they just reach no
            surface but the log. Mirrors ``discover_files``.

    Returns:
        List of InputSession objects, ordered by participant number.
    """
    logger.info("Ingesting files from %s", input_dir)
    if skipped is None:
        skipped = []
    files = discover_files(input_dir, skipped)

    # Say what was left out, by name. A count alone does not let a researcher
    # work out which participant is missing.
    for entry in skipped:
        logger.warning(
            "Not analysed: %s — %s%s",
            entry.path.name,
            MESSAGES[entry.reason],
            f" ({entry.detail})" if entry.detail else "",
        )
    if skipped:
        logger.warning(
            "%d file(s) in %s were not analysed; see the lines above",
            len(skipped),
            input_dir,
        )

    if not files:
        logger.warning("No supported files found in %s", input_dir)
        return []

    logger.info("Found %d supported files", len(files))
    sessions = group_into_sessions(files)
    logger.info("Grouped into %d sessions", len(sessions))

    return sessions
