"""Persistent log file and terminal logging configuration.

Two independent knobs:

- ``-v`` / ``--verbose`` on the CLI controls **terminal** verbosity
  (stderr handler level).  Default: WARNING.
- ``BRISTLENOSE_LOG_LEVEL`` env var controls **log file** verbosity.
  Default: INFO.  The log file lives at
  ``<output_dir>/.bristlenose/bristlenose.log``.

Both are fully independent — ``-v`` doesn't affect the log file,
``BRISTLENOSE_LOG_LEVEL`` doesn't affect the terminal.
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
_NOISY_LOGGERS = ("httpx", "presidio-analyzer", "presidio_analyzer", "faster_whisper")


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
    terminal.setFormatter(logging.Formatter("%(levelname)s | %(name)s | %(message)s"))
    root.addHandler(terminal)

    # ── Log file handler ───────────────────────────────────────────
    if output_dir is not None:
        log_dir = output_dir / ".bristlenose"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / _LOG_FILENAME

        from logging.handlers import RotatingFileHandler

        file_level_str = os.environ.get("BRISTLENOSE_LOG_LEVEL", "INFO")
        file_level = _parse_log_level(file_level_str)

        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=_MAX_BYTES,
            backupCount=_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setLevel(file_level)
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        root.addHandler(file_handler)

    # ── Suppress noisy third-party loggers ─────────────────────────
    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
