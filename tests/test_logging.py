"""Tests for the two-handler logging system (terminal + log file)."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _reset_logging():
    """Reset root logger handlers after each test."""
    yield
    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)
        handler.close()
    # Restore basicConfig-like defaults so other tests aren't affected
    logging.basicConfig(level=logging.WARNING, force=True)


class TestSetupLogging:
    """Tests for setup_logging configuration."""

    def test_terminal_only_when_no_output_dir(self) -> None:
        """Without output_dir, only terminal handler is configured."""
        from bristlenose.logging import setup_logging

        setup_logging(output_dir=None, verbose=False)

        root = logging.getLogger()
        assert len(root.handlers) == 1
        handler = root.handlers[0]
        assert isinstance(handler, logging.StreamHandler)
        assert handler.level == logging.WARNING

    def test_terminal_verbose_sets_debug(self) -> None:
        """verbose=True sets terminal handler to DEBUG."""
        from bristlenose.logging import setup_logging

        setup_logging(output_dir=None, verbose=True)

        root = logging.getLogger()
        terminal = root.handlers[0]
        assert terminal.level == logging.DEBUG

    def test_file_handler_created_with_output_dir(self, tmp_path: Path) -> None:
        """Log file is created inside .bristlenose/ when output_dir provided."""
        from bristlenose.logging import setup_logging

        setup_logging(output_dir=tmp_path, verbose=False)

        root = logging.getLogger()
        # Should have terminal + file handler
        assert len(root.handlers) == 2

        log_path = tmp_path / ".bristlenose" / "bristlenose.log"
        assert log_path.parent.is_dir()

    def test_file_handler_default_level_is_info(self, tmp_path: Path) -> None:
        """Without BRISTLENOSE_LOG_LEVEL, file handler defaults to INFO."""
        from bristlenose.logging import setup_logging

        # Ensure env var is not set
        env = os.environ.pop("BRISTLENOSE_LOG_LEVEL", None)
        try:
            setup_logging(output_dir=tmp_path, verbose=False)

            root = logging.getLogger()
            file_handler = [h for h in root.handlers if hasattr(h, "baseFilename")]
            assert len(file_handler) == 1
            assert file_handler[0].level == logging.INFO
        finally:
            if env is not None:
                os.environ["BRISTLENOSE_LOG_LEVEL"] = env

    def test_file_handler_respects_env_var(self, tmp_path: Path) -> None:
        """BRISTLENOSE_LOG_LEVEL controls file handler level."""
        from bristlenose.logging import setup_logging

        old = os.environ.get("BRISTLENOSE_LOG_LEVEL")
        os.environ["BRISTLENOSE_LOG_LEVEL"] = "DEBUG"
        try:
            setup_logging(output_dir=tmp_path, verbose=False)

            root = logging.getLogger()
            file_handler = [h for h in root.handlers if hasattr(h, "baseFilename")]
            assert len(file_handler) == 1
            assert file_handler[0].level == logging.DEBUG
        finally:
            if old is not None:
                os.environ["BRISTLENOSE_LOG_LEVEL"] = old
            else:
                os.environ.pop("BRISTLENOSE_LOG_LEVEL", None)

    def test_terminal_and_file_are_independent(self, tmp_path: Path) -> None:
        """Terminal at WARNING, file at INFO — independent levels."""
        from bristlenose.logging import setup_logging

        env = os.environ.pop("BRISTLENOSE_LOG_LEVEL", None)
        try:
            setup_logging(output_dir=tmp_path, verbose=False)

            root = logging.getLogger()
            terminal = [h for h in root.handlers if not hasattr(h, "baseFilename")]
            file_h = [h for h in root.handlers if hasattr(h, "baseFilename")]
            assert terminal[0].level == logging.WARNING
            assert file_h[0].level == logging.INFO
        finally:
            if env is not None:
                os.environ["BRISTLENOSE_LOG_LEVEL"] = env

    def test_messages_written_to_log_file(self, tmp_path: Path) -> None:
        """INFO messages appear in the log file but not in terminal."""
        from bristlenose.logging import setup_logging

        env = os.environ.pop("BRISTLENOSE_LOG_LEVEL", None)
        try:
            setup_logging(output_dir=tmp_path, verbose=False)

            test_logger = logging.getLogger("bristlenose.test_module")
            test_logger.info("test info message for log file")

            log_path = tmp_path / ".bristlenose" / "bristlenose.log"
            assert log_path.exists()
            content = log_path.read_text()
            assert "test info message for log file" in content
        finally:
            if env is not None:
                os.environ["BRISTLENOSE_LOG_LEVEL"] = env

    def test_idempotent_setup(self, tmp_path: Path) -> None:
        """Calling setup_logging twice doesn't duplicate handlers."""
        from bristlenose.logging import setup_logging

        setup_logging(output_dir=tmp_path, verbose=False)
        setup_logging(output_dir=tmp_path, verbose=False)

        root = logging.getLogger()
        assert len(root.handlers) == 2  # terminal + file, not 4

    def test_noisy_loggers_suppressed(self, tmp_path: Path) -> None:
        """Third-party loggers are set to WARNING regardless of verbose."""
        from bristlenose.logging import setup_logging

        setup_logging(output_dir=tmp_path, verbose=True)

        assert logging.getLogger("httpx").level == logging.WARNING
        assert logging.getLogger("faster_whisper").level == logging.WARNING


class TestParseLogLevel:
    """Tests for _parse_log_level."""

    def test_standard_levels(self) -> None:
        from bristlenose.logging import _parse_log_level

        assert _parse_log_level("DEBUG") == logging.DEBUG
        assert _parse_log_level("INFO") == logging.INFO
        assert _parse_log_level("WARNING") == logging.WARNING
        assert _parse_log_level("ERROR") == logging.ERROR

    def test_case_insensitive(self) -> None:
        from bristlenose.logging import _parse_log_level

        assert _parse_log_level("debug") == logging.DEBUG
        assert _parse_log_level("Info") == logging.INFO

    def test_unknown_falls_back_to_info(self) -> None:
        from bristlenose.logging import _parse_log_level

        assert _parse_log_level("banana") == logging.INFO
