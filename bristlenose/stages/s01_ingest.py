"""Stage 1: File discovery, classification, and participant numbering."""

from __future__ import annotations

import logging
import os
import re
import sys
import unicodedata
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

from bristlenose.discussion.guide import is_guide_folder
from bristlenose.models import (
    FileType,
    InputFile,
    InputSession,
    classify_file,
)
from bristlenose.refusals import MESSAGES, UnusableReason
from bristlenose.utils.audio import probe_media
from bristlenose.utils.fs import is_bristlenose_artefact, is_dataless, is_os_metadata
from bristlenose.utils.session_start import resolve_session_start

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
    # ``sys.platform`` rather than ``platform.system()``: mypy narrows on it,
    # and ``st_birthtime`` exists on the macOS ``stat_result`` only.
    if sys.platform == "darwin":
        ts = stat.st_birthtime
    elif sys.platform == "win32":
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
#: folder. The Mac's port of this walk (`ScanSelection.swift`) skips it too. The
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
    files: list[InputFile] = []
    for path in iter_scanned_files(input_dir, skipped):
        try:
            _try_add_file(path, files, skipped)
        except OSError as exc:  # gone or unreadable since the listing
            logger.warning("Skipping unreadable entry %s: %s", path, exc)

    # Sort by creation date, then filename as tiebreaker
    files.sort(key=lambda f: (f.created_at, f.path.name))
    return files


def iter_scanned_files(
    input_dir: Path, skipped: list[SkippedFile] | None = None
) -> Iterator[Path]:
    """Every file `run`'s scan considers, in scan order — its file selection.

    The walk alone: depth, hidden entries, OS metadata, our own artefacts and
    output, the discussion guide, links, unreadable folders. It lists and stats
    and never opens a file, so a dataless placeholder is yielded without being
    downloaded. :func:`discover_files` classifies and probes what it yields;
    the serve's never-run page asks only whether any of it is a format we read
    (decision #82), so the two cannot disagree about what a folder holds.

    Raises:
        UnsuitableInputDirError: *input_dir* is a filesystem or system root
            (on the first ``next``).
    """
    reason = _refuse_reason(input_dir)
    if reason is not None:
        raise UnsuitableInputDirError(
            f"{input_dir} can't be analysed because {reason}. "
            "Point Bristlenose at the folder holding your recordings."
        )

    seen: set[Path] = set()
    links: list[tuple[Path, int]] = []
    yield from _scan_dir(input_dir, 0, skipped, seen, links)
    # Links after the real tree, so whatever a link and its target both reach
    # keeps the target's own path, wherever the link sorts (R123).
    while links:
        link, depth = links.pop(0)
        yield from _scan_entries([link], depth, skipped, seen, links, defer_links=False)


def _resolved(path: Path) -> Path:
    try:
        return path.resolve()
    except (OSError, RuntimeError):  # a link loop (RuntimeError on 3.12), a vanished target
        return path.absolute()


def _scan_dir(
    directory: Path,
    depth: int,
    skipped: list[SkippedFile] | None,
    seen: set[Path],
    links: list[tuple[Path, int]],
) -> Iterator[Path]:
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
    yield from _scan_entries(entries, depth, skipped, seen, links, defer_links=True)


def _scan_entries(
    entries: list[Path],
    depth: int,
    skipped: list[SkippedFile] | None,
    seen: set[Path],
    links: list[tuple[Path, int]],
    *,
    defer_links: bool,
) -> Iterator[Path]:
    """Classify *entries* (one folder's, or one deferred link) at *depth*."""
    for entry in entries:
        # Hidden entries — dot-files and dot-directories alike — are tool
        # state (`.claude/`, `.git/`, AppleDouble `._*`, `.DS_Store`), not
        # study material: Finder doesn't show them, so the researcher didn't
        # put them here in any meaningful sense. Skip silently rather than
        # refuse — a refusal names a file the researcher can't see, and one
        # `.claude/settings.local.json` demoted every otherwise-clean run to
        # "Partial completion" that way (29 Aug 2026). Matches
        # the Mac's `ScanSelection`, so the two scanners agree on what a folder
        # holds (`tests/fixtures/scan-selection-contract.json`).
        # `is_os_metadata` adds Office's `~$`
        # owner files, which are not dot-prefixed (R120).
        if entry.name.startswith(".") or is_os_metadata(entry):
            continue
        # Our own artefacts, wherever they sit. The `OUTPUT_DIR_NAME` guard
        # below covers the default layout; this covers `--output` pointing
        # elsewhere inside the input folder, and anything copied about by hand.
        # Noise the researcher did not create and cannot act on — and it crowds
        # out the refusals that are genuinely theirs.
        if is_bristlenose_artefact(entry):
            continue
        if defer_links and entry.is_symlink():
            links.append((entry, depth))
            continue
        # Each folder and file once, however many links reach it: a symlinked
        # folder inside the interview folder duplicated every session in it
        # (R123).
        real = _resolved(entry)
        if real in seen:
            logger.debug("Skipping %s: already scanned as %s", entry, real)
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
                # already makes. The Mac's folder watcher had excluded this
                # name since it was written; discovery had not, which is the
                # scanner-parity gap `tests/fixtures/scan-selection-contract.json`
                # now pins from both sides.
                if entry.name == OUTPUT_DIR_NAME:
                    continue
                # The researcher's discussion guide, beside the recordings — a
                # document *about* the study, never a session of it. A .docx
                # in there would otherwise be ingested as a transcript.
                if depth == 0 and is_guide_folder(entry):
                    continue
                if depth + 1 < _MAX_SCAN_DEPTH:
                    # Marked only once walked: a folder too deep to walk here
                    # can still be reached by a shallower link.
                    seen.add(real)
                    yield from _scan_dir(entry, depth + 1, skipped, seen, links)
            elif entry.is_file():
                seen.add(real)
                yield entry
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
    container_meta = None
    if file_type in (FileType.AUDIO, FileType.VIDEO) and not is_dataless(path):
        # One ffprobe: duration plus the container's own timestamp, zone and
        # writer identity (docs/design-timezones.md § 5.1). `group_into_sessions`
        # reads it through `utils.session_start` to place the session's start.
        duration, container_meta = probe_media(path)

    files.append(
        InputFile(
            path=path,
            file_type=file_type,
            created_at=created_at,
            size_bytes=size_bytes,
            duration_seconds=duration,
            container_meta=container_meta,
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

# Zoom web portal download: "GMT20250417-062516_Recording_1920x1200" beside
# "GMT20250417-062516_Recording.transcript" (observed, devforum.zoom.us thread
# 132034, 29 Apr 2025). The stamp is the recording's start in GMT, so it stays:
# it is what keeps two meetings apart. The resolution varies (640x360 in Stony
# Brook IT's guide). Names Zoom gives extra video layouts are not observed yet,
# so they are not matched.
_ZOOM_PORTAL_RE = re.compile(
    r"^(gmt\d{8}-\d{6})_recording(?:_\d{2,5}x\d{2,5})?(?:\.transcript)?$",
)

# Zoom local folder, as the desktop client writes it. Two observed shapes:
#
#   2021-06-14 11.44.02 <Host>'s Zoom Meeting 95138721600   (2021 client)
#   2026-10-22 09.51.39 <Host>'s Zoom Meeting               (22 Oct 2026)
#
# Today's client drops the meeting ID, so the rule required one and missed
# every new folder: video, mixed audio and each participant's track became a
# session apiece. The dotted time after the date is what marks Zoom's folder;
# the ID, when there is one, is just the end of the title.
_ZOOM_LOCAL_DIR_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}\s+\d{2}\.\d{2}\.\d{2}\s+.+$",
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

# The same prefix, keeping the stamp. `group_into_sessions` uses it to tell a
# weekly meeting's recordings apart: the stamp is stripped for *matching* (so
# a hand-fetched transcript can meet its video) but kept for *grouping* (so
# five Tuesdays are five sessions, not one). See `_stamp_and_title`.
_BN_DOWNLOAD_STAMP_RE = re.compile(
    r"^(?P<stamp>\d{4}-\d{2}-\d{2}\s+\d{4})\s*[—–-]\s*(?P<title>.+)$",
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
    stem = _ZOOM_PORTAL_RE.sub(r"\1", stem)

    # 5. Google Meet: the dated tail first — it needs the trailing kind in order
    #    to match, and `_GMEET_TRANSCRIPT_SUFFIX_RE` would otherwise eat it.
    stem = _GMEET_TAIL_RE.sub("", stem)
    stem = _GMEET_TRANSCRIPT_SUFFIX_RE.sub("", stem)
    stem = _GMEET_PAREN_RE.sub("", stem)

    return stem.strip()


def _is_zoom_local_dir(dir_name: str) -> bool:
    """Return True if *dir_name* matches the Zoom local recording folder pattern."""
    return bool(_ZOOM_LOCAL_DIR_RE.match(dir_name))


def _zoom_local_dir_of(path: Path, root: Path | None = None) -> str | None:
    """The Zoom local folder *path* belongs to, or None.

    A file in a subfolder of one belongs to it too: with "Record separate
    participant audio files" on, the client puts one track per person in
    ``Audio Record/`` (observed 2021 and 22 Oct 2026). Matched by place, not
    by that folder's name, which the client may localise.

    That claim stops at *root*, the input folder: a meeting folder above it is
    not part of the study, so pointing Bristlenose at ``Audio Record/`` itself
    gives a session per track. ``None`` leaves the claim unbounded.
    """
    if path.parent.name and _is_zoom_local_dir(path.parent.name):
        return path.parent.name
    folder = path.parent.parent
    if folder.name and _is_zoom_local_dir(folder.name) and _within(folder, root):
        return folder.name
    return None


def _within(folder: Path, root: Path | None) -> bool:
    """Whether *folder* is *root* or inside it; always, with no root.

    Resolved, so ``/tmp`` and ``/private/tmp`` agree; or as written, so a
    meeting folder linked into the study (discovery keeps the link's path)
    still counts.
    """
    if root is None:
        return True

    def lexical(p: Path) -> Path:
        return Path(os.path.normpath(p.absolute()))

    try:
        if folder.resolve().is_relative_to(root.resolve()):
            return True
    except (OSError, RuntimeError):  # a link loop, a vanished target
        pass
    return lexical(folder).is_relative_to(lexical(root))


def _stem_of(path: Path) -> str:
    """The lowercased, NFC-composed stem every grouping key starts from.

    macOS keeps a name as the tool wrote it, composed (``é``) or decomposed
    (``e`` + combining acute), so a recording and its transcript can look the
    same and differ byte for byte; until 20 Oct 2026 they became two sessions
    and the recording was transcribed beside its own transcript (R123).
    """
    return unicodedata.normalize("NFC", path.stem).lower()


def _stamp_and_title(stem: str) -> tuple[str | None, str]:
    """Split a lowercased stem into Bristlenose's download stamp and its key.

    Returns ``(stamp, key)`` — ``stamp`` is ``"2026-09-03 1000"`` for a file
    our import named and ``None`` for everything else; ``key`` is the
    normalised stem both kinds of file match on.
    """
    m = _BN_DOWNLOAD_STAMP_RE.match(stem)
    stamp = m.group("stamp") if m else None
    return stamp, _normalise_stem(stem)


def _group_by_stem(files: list[InputFile]) -> list[list[InputFile]]:
    """Group files whose normalised stems match, keeping recurring meetings apart.

    A file carrying our download stamp is grouped by (stamp, key), so two
    Tuesdays of "Weekly research sync" are two sessions. An unstamped file is
    grouped by key alone, and then joins a stamped group only when **exactly
    one** stamped group carries its key — the hand-fetched transcript beside
    the one imported video it belongs to. With two candidate days there is no
    way to know which one it is, and guessing would hand one interview's words
    to another; it stays its own session, which the pipeline then states as a
    transcript without a recording rather than merging it silently.
    """
    stamped: dict[tuple[str, str], list[InputFile]] = {}
    unstamped: dict[str, list[InputFile]] = {}
    for f in files:
        stamp, key = _stamp_and_title(_stem_of(f.path))
        if stamp is not None:
            stamped.setdefault((stamp, key), []).append(f)
        else:
            unstamped.setdefault(key, []).append(f)

    groups: list[list[InputFile]] = list(stamped.values())
    for key, group_files in unstamped.items():
        candidates = [g for (_stamp, k), g in stamped.items() if k == key]
        if len(candidates) == 1:
            candidates[0].extend(group_files)
        else:
            groups.append(group_files)
    return groups


_MEDIA_TYPES = (FileType.AUDIO, FileType.VIDEO)
_TRANSCRIPT_TYPES = (FileType.SUBTITLE_SRT, FileType.SUBTITLE_VTT, FileType.DOCX)


def _split_by_folder_if_colliding(group: list[InputFile]) -> list[list[InputFile]]:
    """One session per folder when two folders both hold a recording (or both
    a transcript) under the same name.

    ``alice/interview.mp4`` and ``bob/interview.mp4`` are two participants, not
    one session with two videos — until 12 Oct 2026 they merged, only the first
    was transcribed, and the second vanished with nothing said. A recording in
    one folder and its transcript in another is still one session: the split
    happens only when a *role* is duplicated across folders.
    """
    media_parents = {f.path.parent for f in group if f.file_type in _MEDIA_TYPES}
    transcript_parents = {f.path.parent for f in group if f.file_type in _TRANSCRIPT_TYPES}
    if len(media_parents) < 2 and len(transcript_parents) < 2:
        return [group]
    by_parent: dict[Path, list[InputFile]] = {}
    for f in group:
        by_parent.setdefault(f.path.parent, []).append(f)
    logger.warning(
        "%d files named %r in %d folders — one session per folder",
        len(group), group[0].path.stem, len(by_parent),
    )
    return list(by_parent.values())


def fold_duplicate_recording(owner: InputSession, duplicate: InputSession) -> None:
    """Fold *duplicate* — a session whose recording is byte for byte *owner*'s
    — into *owner*, so the interview is transcribed once, paid for once and
    counted once.

    ``P3.mp4`` and ``P3 (1).mp4``, a Finder copy, a download renamed: one
    recording (``docs/design-project-identity.md`` §5). Until 20 Oct 2026 the
    two were two sessions, both sent through Whisper, and the copy's quotes
    read as a second participant agreeing (R49). The duplicate's recordings
    are set aside with ``DUPLICATE_RECORDING`` — the reason stage 2 gives a
    second recording inside one session — so the file is stated on the run's
    summary, never silently dropped; its transcript files join the owner, as
    they are transcripts of this recording. The owner's files stay first, so
    what is used does not change. The session registry decides which copy is
    the owner (``SessionRegistry.apply``), because only it knows which one
    the study already keys.
    """
    for f in duplicate.files:
        if f.file_type in _MEDIA_TYPES:
            f.error = UnusableReason.DUPLICATE_RECORDING.value
            f.error_stage = "s01_ingest"
        owner.files.append(f)
    owner.has_existing_transcript = (
        owner.has_existing_transcript or duplicate.has_existing_transcript
    )
    logger.warning(
        "%s is the same recording as %s — set aside; %s is used",
        duplicate.files[0].path.name, owner.files[0].path.name, owner.files[0].path.name,
    )


def fold_duplicate_transcript(
    owner: InputSession, duplicate: InputSession, copies: set[Path],
) -> None:
    """Fold *duplicate* — a session with no recording, whose transcript files
    *copies* are byte for byte files *owner* holds — into *owner*: one
    session, read once and counted once.

    ``transcript.vtt`` and ``transcript (1).vtt``, the same Teams download
    taken twice: one transcript, as identical recordings are one recording
    (decision #97, 21 Oct 2026; ``fold_duplicate_recording`` is the sibling).
    Until then the two were sessions and the copy's quotes read as a second
    participant agreeing. Each of *copies* is set aside with
    ``DUPLICATE_TRANSCRIPT``, so it is stated on the run's summary and never
    parsed; a file of the duplicate that differs joins the owner as a
    candidate transcript, as a recording copy's companions do, and one
    transcript per session is still chosen. The owner's files stay first, so
    a tie keeps what is used. The session registry decides the owner and
    which files are copies (``SessionRegistry.apply``).
    """
    for f in duplicate.files:
        if f.path in copies:
            f.error = UnusableReason.DUPLICATE_TRANSCRIPT.value
            f.error_stage = "s01_ingest"
            logger.warning(
                "%s is the same transcript as one beside %s — set aside; %s is used",
                f.path.name, owner.files[0].path.name, owner.files[0].path.name,
            )
        owner.files.append(f)
    owner.has_existing_transcript = (
        owner.has_existing_transcript or duplicate.has_existing_transcript
    )


def session_key(
    files: list[InputFile], *, qualified: bool = False, root: Path | None = None
) -> str:
    """The stable identity of a session's file group — what the grouping keys on.

    Derived from the files rather than from the sid, so the same interview gets
    the same key on every run however the sessions around it change. Mirrors
    the three grouping passes: a Zoom local folder is its own key; a group that
    holds a file carrying our download stamp is keyed by (stamp, title), since
    an unstamped file only ever joins such a group; anything else is keyed by
    its normalised stem. A later transcript joining an existing recording does
    not change the key, which is the point — the session keeps its number.

    ``qualified`` appends the folder name, for the one case where two sessions
    in a run would otherwise share a key — the same stem in two subfolders
    (``_split_by_folder_if_colliding``). Only the registry asks for it, and only
    on a collision, so every other project's keys are untouched.

    ``root`` is the input folder, bounding the Zoom claim as the grouping does
    (`_zoom_local_dir_of`).
    """
    for f in files:
        zoom_dir = _zoom_local_dir_of(f.path, root)
        if zoom_dir is not None:
            return f"zoom:{zoom_dir}"
    for f in files:
        stamp, key = _stamp_and_title(_stem_of(f.path))
        if stamp is not None:
            return f"stamp:{stamp}|{key}"
    _stamp, key = _stamp_and_title(_stem_of(files[0].path))
    if qualified:
        return f"stem:{key}@{files[0].path.parent.name}"
    return f"stem:{key}"


def group_into_sessions(
    files: list[InputFile], *, order_by_start: bool = False, root: Path | None = None
) -> list[InputSession]:
    """Group files into sessions and assign participant numbers.

    Grouping heuristic:
    1. Files in a Zoom-style subdirectory are grouped by directory.
    2. Remaining files sharing the same normalised stem are one session —
       with Bristlenose's own download stamp keeping same-titled meetings on
       different days apart (`_group_by_stem`).
    3. Otherwise, each file is its own session.

    Stems are normalised to strip platform naming conventions (Teams date/suffix,
    Zoom cloud meeting ID, Google Meet parenthetical date).

    Participant numbers (p1, p2, ...) are assigned by the creation date of the
    session's earliest file.

    ``root`` is the input folder: a Zoom meeting folder above it claims none of
    the files (`_zoom_local_dir_of`).
    """
    # -- Pass 1: Zoom local folders (all files in the folder = one session) ------
    zoom_dir_groups: dict[str, list[InputFile]] = {}
    remaining: list[InputFile] = []
    for f in files:
        zoom_dir = _zoom_local_dir_of(f.path, root)
        if zoom_dir is not None:
            zoom_dir_groups.setdefault(zoom_dir, []).append(f)
        else:
            remaining.append(f)
    # The meeting folder's own files first: stage 2 transcribes the first
    # audio file, which must be the mixed track, not one participant's.
    for zoom_dir, group in zoom_dir_groups.items():
        group.sort(key=lambda f: f.path.parent.name != zoom_dir)

    # -- Pass 2: normalised stem matching on remaining files ---------------------
    stem_groups = [
        split for group in _group_by_stem(remaining)
        for split in _split_by_folder_if_colliding(group)
    ]

    # -- Merge both grouping passes into raw sessions --------------------------
    # Each session's start comes from `utils.session_start` (when it started,
    # not when its file was saved — design-timezones § 5.4).
    #
    # The ORDER is a separate question, because it numbers the sessions. With
    # `order_by_start` they are numbered by that start, which is what a new
    # project wants. Without it they keep the order they always had — earliest
    # file creation time — because a project analysed before the session
    # registry existed (3 Oct 2026) has no `sessions.json`, is numbered by this
    # order on its next run, and moving the key would carry one interview's
    # stars and names onto another. The pipeline decides (`_may_order_by_start`).
    raw_sessions: list[tuple[datetime, list[InputFile]]] = []
    for _dir, group_files in zoom_dir_groups.items():
        raw_sessions.append((min(f.created_at for f in group_files), group_files))
    for group_files in stem_groups:
        raw_sessions.append((min(f.created_at for f in group_files), group_files))

    starts = [resolve_session_start(group_files) for _key, group_files in raw_sessions]
    order = sorted(
        range(len(raw_sessions)),
        key=lambda n: (
            starts[n].instant if order_by_start else raw_sessions[n][0],
            raw_sessions[n][1][0].path.name,
        ),
    )

    # Assign session and provisional participant numbers
    sessions: list[InputSession] = []
    for i, n in enumerate(order, start=1):
        group_files = raw_sessions[n][1]
        start = starts[n]
        session_date = start.instant
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
            session_start_source=start.source.value,
        )
        sessions.append(session)
        logger.info(
            "Session %s: %d files, start=%s, start_source=%s, has_transcript=%s",
            session_id,
            len(group_files),
            session_date.astimezone().isoformat(timespec="minutes"),
            start.source.value,
            has_transcript,
        )

    return sessions


def ingest(
    input_dir: Path,
    skipped: list[SkippedFile] | None = None,
    *,
    order_by_start: bool = False,
) -> list[InputSession]:
    """Full ingestion pipeline: discover files, group into sessions.

    Args:
        input_dir: Directory containing input files.
        skipped: Optional list to collect what was declined, so the caller can
            put it on the run's terminus summary. Omit it and the behaviour is
            unchanged — the refusals are still logged, they just reach no
            surface but the log. Mirrors ``discover_files``.
        order_by_start: Number sessions by their resolved start rather than
            by file creation time. Only for a project whose numbering cannot
            move — see ``group_into_sessions``.

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
    sessions = group_into_sessions(files, order_by_start=order_by_start, root=input_dir)
    logger.info("Grouped into %d sessions", len(sessions))

    return sessions
