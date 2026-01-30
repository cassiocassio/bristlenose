"""Stage 1: File discovery, classification, and participant numbering."""

from __future__ import annotations

import logging
import platform
from datetime import datetime, timezone
from pathlib import Path

from bristlenose.models import (
    FileType,
    InputFile,
    InputSession,
    classify_file,
)
from bristlenose.utils.audio import probe_duration

logger = logging.getLogger(__name__)


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


def discover_files(input_dir: Path) -> list[InputFile]:
    """Scan an input directory for supported files.

    Returns a list of InputFile objects sorted by creation date.
    """
    files: list[InputFile] = []

    for entry in sorted(input_dir.iterdir()):
        if entry.is_dir():
            # Recurse one level into subdirectories
            for sub_entry in sorted(entry.iterdir()):
                if sub_entry.is_file():
                    _try_add_file(sub_entry, files)
        elif entry.is_file():
            _try_add_file(entry, files)

    # Sort by creation date, then filename as tiebreaker
    files.sort(key=lambda f: (f.created_at, f.path.name))
    return files


def _try_add_file(path: Path, files: list[InputFile]) -> None:
    """Classify a file and add it to the list if supported."""
    file_type = classify_file(path)
    if file_type is None:
        logger.debug("Skipping unsupported file: %s", path.name)
        return

    created_at = _get_creation_time(path)
    size_bytes = path.stat().st_size

    # Probe duration for audio/video files
    duration: float | None = None
    if file_type in (FileType.AUDIO, FileType.VIDEO):
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
    logger.info("Found %s file: %s", file_type.value, path.name)


def group_into_sessions(files: list[InputFile]) -> list[InputSession]:
    """Group files into sessions and assign participant numbers.

    Grouping heuristic:
    1. Files sharing the same stem (ignoring extension) are one session.
    2. Files in the same subdirectory with only one primary file (audio/video)
       are one session.
    3. Otherwise, each file is its own session.

    Participant numbers (p1, p2, ...) are assigned by the creation date of the
    session's earliest file.
    """
    # Group by stem — e.g. "interview_01.mp4" and "interview_01.srt" share a session
    stem_groups: dict[str, list[InputFile]] = {}
    for f in files:
        stem = f.path.stem.lower()
        # Strip common suffixes like "_transcript", "_subtitles" to match base name
        for suffix in ("_transcript", "_subtitles", "_captions", "_sub", "_srt"):
            if stem.endswith(suffix):
                stem = stem[: -len(suffix)]
                break
        stem_groups.setdefault(stem, []).append(f)

    # Build sessions from groups
    raw_sessions: list[tuple[datetime, list[InputFile]]] = []
    for _stem, group_files in stem_groups.items():
        # Session date is the earliest creation date in the group
        session_date = min(f.created_at for f in group_files)
        raw_sessions.append((session_date, group_files))

    # Sort by session date, then first filename
    raw_sessions.sort(key=lambda s: (s[0], s[1][0].path.name))

    # Assign participant numbers
    sessions: list[InputSession] = []
    for i, (session_date, group_files) in enumerate(raw_sessions, start=1):
        participant_id = f"p{i}"

        # Determine if this session has an existing transcript
        has_transcript = any(
            f.file_type in (FileType.SUBTITLE_SRT, FileType.SUBTITLE_VTT, FileType.DOCX)
            for f in group_files
        )

        session = InputSession(
            participant_id=participant_id,
            participant_number=i,
            files=group_files,
            has_existing_transcript=has_transcript,
            session_date=session_date,
        )
        sessions.append(session)
        logger.info(
            "Session %s: %d files, date=%s, has_transcript=%s",
            participant_id,
            len(group_files),
            session_date.date(),
            has_transcript,
        )

    return sessions


def ingest(input_dir: Path) -> list[InputSession]:
    """Full ingestion pipeline: discover files, group into sessions.

    Args:
        input_dir: Directory containing input files.

    Returns:
        List of InputSession objects, ordered by participant number.
    """
    logger.info("Ingesting files from %s", input_dir)
    files = discover_files(input_dir)

    if not files:
        logger.warning("No supported files found in %s", input_dir)
        return []

    logger.info("Found %d supported files", len(files))
    sessions = group_into_sessions(files)
    logger.info("Grouped into %d sessions", len(sessions))

    return sessions
