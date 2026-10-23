"""Persistent log file and terminal logging configuration.

Two independent knobs:

- ``-v`` / ``--verbose`` on the CLI controls **terminal** verbosity
  (stderr handler level).  Default: WARNING.
- ``BRISTLENOSE_LOG_LEVEL`` env var controls **log file** verbosity.
  Default: INFO.  The log file lives at
  ``<output_dir>/.bristlenose/bristlenose.log``.

Both are fully independent — ``-v`` doesn't affect the log file,
``BRISTLENOSE_LOG_LEVEL`` doesn't affect the terminal.

PII policy (see ``docs/design-logging.md`` for full rationale):

1. Never log transcript content (quote text, segment text, LLM
   prompt/response content).  Only structural metadata (field types,
   token counts, model names).
2. Log identifiers, not names — session IDs (``s1``), speaker codes
   (``p1``), quote DOM IDs (``q-p1-123``), not participant names or
   file paths containing names.
3. Input filenames at DEBUG, not INFO.  Aggregates ("Found 6 files")
   are INFO; per-file details are DEBUG.
4. Project name: log the slug or project ID, not the raw folder name.
5. The log file lives inside the project output — same trust boundary
   as the transcripts.  Diagnostic export (future) must strip PII.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

# Log file name (inside .bristlenose/)
_LOG_FILENAME = "bristlenose.log"

# Max log file size before rotation (5 MB)
_MAX_BYTES = 5 * 1024 * 1024

# Number of rotated backups to keep
_BACKUP_COUNT = 2

# Third-party loggers that are always suppressed
# mistralai (through any-llm) logs whole request bodies at DEBUG when its own
# MISTRAL_DEBUG is set; kept at WARNING so a DEBUG run log never holds a transcript.
_NOISY_LOGGERS = (
    "httpx", "presidio-analyzer", "presidio_analyzer", "faster_whisper", "mistralai",
)


# Control characters (tab aside) and Unicode line breaks, as visible escapes.
_ONE_LINE = {c: f"\\x{c:02x}" for c in [*range(0x20), *range(0x7F, 0xA0)] if c != 0x09}
_ONE_LINE |= {0x0A: "\\n", 0x0D: "\\r", 0x2028: "\\u2028", 0x2029: "\\u2029"}


class _OneLineFormatter(logging.Formatter):
    """A formatter that keeps each record's message on one line.

    A newline in a logged value (a URL path parameter, a subprocess's stderr)
    would otherwise start what reads as a second record in the log, and a
    terminal escape could rewrite the line above. The message line shows them
    as visible escapes (``\\n``, ``\\r``, ``\\x1b``) instead; a traceback or
    stack, which ``format()`` appends after the message, keeps its own lines,
    and so does an exception's own text. Backslashes are left alone so Windows
    paths stay readable, which makes the escaping one-way.
    """

    def formatMessage(self, record: logging.LogRecord) -> str:  # noqa: N802
        return super().formatMessage(record).translate(_ONE_LINE)


def _parse_log_level(level_str: str) -> int:
    """Parse a log level string into a logging constant.

    Accepts standard names (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    case-insensitively.  Falls back to INFO for unrecognised values.
    """
    numeric = getattr(logging, level_str.upper(), None)
    if isinstance(numeric, int):
        return numeric
    return logging.INFO


def setup_logging(
    *,
    output_dir: Path | None = None,
    verbose: bool = False,
) -> None:
    """Configure the two-handler logging system.

    Args:
        output_dir: Pipeline output directory.  When provided, a rotating
            log file is created at ``<output_dir>/.bristlenose/bristlenose.log``.
            When ``None`` (e.g. ``bristlenose doctor``), only the terminal
            handler is configured.
        verbose: If True, the terminal handler shows DEBUG-level messages.
            Otherwise only WARNING and above reach the terminal.
    """
    root = logging.getLogger()

    # Remove any existing handlers (e.g. from a previous basicConfig call
    # or when setup_logging is called more than once in the same process)
    for handler in root.handlers[:]:
        root.removeHandler(handler)
        handler.close()

    # The root logger must accept everything; handlers filter independently
    root.setLevel(logging.DEBUG)

    # ── Terminal handler (stderr) ──────────────────────────────────
    terminal = logging.StreamHandler()
    terminal_level = logging.DEBUG if verbose else logging.WARNING
    terminal.setLevel(terminal_level)
    terminal.setFormatter(_OneLineFormatter("%(levelname)s | %(name)s | %(message)s"))
    root.addHandler(terminal)

    # ── Log file handler ───────────────────────────────────────────
    if output_dir is not None:
        root.addHandler(_file_handler(output_dir))

    # ── Suppress noisy third-party loggers ─────────────────────────
    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)


def _file_handler(output_dir: Path) -> logging.Handler:
    """The rotating log file at ``<output_dir>/.bristlenose/bristlenose.log``."""
    from logging.handlers import RotatingFileHandler

    log_dir = output_dir / ".bristlenose"
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_dir / _LOG_FILENAME,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setLevel(_parse_log_level(os.environ.get("BRISTLENOSE_LOG_LEVEL", "INFO")))
    handler.setFormatter(
        _OneLineFormatter(
            "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    return handler


def reopen_log_file(output_dir: Path) -> bool:
    """Point the log file handler at the file on disk, if the folder moved.

    An open handler follows its file, not its path: when ``run --clean`` moves
    the output folder aside, a serve goes on writing into the moved copy, which
    the run deletes once it succeeds. The serve calls this when it reattaches to
    the output folder now on disk. True when it reopened; False when the file
    in place is the one already open, there is no log file to follow, or the
    output folder is not there (it never creates it).

    The new handler is opened before the old one is closed, so a failure to open
    it (a permission, the folder moving again) leaves logging where it was and
    raises; the next call tries again, rather than finding no handler and
    giving up for the life of the process.
    """
    root = logging.getLogger()
    handlers = [h for h in root.handlers if isinstance(h, logging.FileHandler)]
    if not handlers:
        return False
    target = output_dir / ".bristlenose" / _LOG_FILENAME
    if not target.parent.is_dir():
        # Mid-stash, or mid-restore: creating the folder here would put a new
        # output folder where the restore is about to move the old one back.
        return False
    try:
        on_disk = os.stat(target)
    except OSError:
        on_disk = None
    stale = [h for h in handlers if not _holds(h, on_disk)]
    if not stale:
        return False
    fresh = _file_handler(output_dir)
    root.addHandler(fresh)
    for handler in stale:
        root.removeHandler(handler)
        handler.close()
    return True


def _holds(handler: logging.FileHandler, on_disk: os.stat_result | None) -> bool:
    """Whether ``handler`` has the file now on disk open."""
    stream = handler.stream
    if on_disk is None or stream is None:
        return False
    try:
        held = os.fstat(stream.fileno())
    except (OSError, ValueError):
        return False
    return (held.st_dev, held.st_ino) == (on_disk.st_dev, on_disk.st_ino)


def release_log_file() -> None:
    """Close the log file so the folder holding it can be renamed.

    The root handler keeps ``<output>/.bristlenose/bristlenose.log`` open, and
    Windows refuses to rename a directory with an open file inside it. ``run``
    renames the output folder twice — aside before a ``--clean`` run, back if
    the run fails — so it releases the file first and calls ``setup_logging``
    again after. Terminal output is untouched.
    """
    root = logging.getLogger()
    for handler in root.handlers[:]:
        if isinstance(handler, logging.FileHandler):
            root.removeHandler(handler)
            handler.close()
