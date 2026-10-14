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
            content = log_path.read_text(encoding="utf-8")
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


@pytest.mark.skipif(os.name == "nt", reason="Windows will not move a folder holding an open log")
class TestFollowTheLogFile:
    """``run --clean`` moves the output folder aside under a live serve. The
    serve's handler kept writing into the moved copy, which the run deletes when
    it succeeds, so the serve's whole log for that run was lost (14 Oct 2026)."""

    def test_a_moved_log_is_reopened_where_the_output_is_now(self, tmp_path: Path) -> None:
        from bristlenose.logging import reopen_log_file, setup_logging

        out = tmp_path / "bristlenose-output"
        setup_logging(output_dir=out)
        log = logging.getLogger("bristlenose.test")
        log.info("before the stash")
        stash = tmp_path / ".bristlenose-output-previous"
        out.rename(stash)
        # What the run does straight after its stash: its own log, before the
        # serve notices. The serve must tell it from the one it holds open.
        (out / ".bristlenose").mkdir(parents=True)
        (out / ".bristlenose" / "bristlenose.log").write_text("the run's first line\n")

        assert reopen_log_file(out) is True
        log.info("after the stash")
        for h in logging.getLogger().handlers:
            h.flush()
        here = (out / ".bristlenose" / "bristlenose.log").read_text()
        moved = (stash / ".bristlenose" / "bristlenose.log").read_text()
        assert "after the stash" in here
        assert "the run's first line" in here, "the run's own lines were overwritten"
        assert "after the stash" not in moved
        assert "before the stash" in moved
        assert reopen_log_file(out) is False, "a second look finds the file it now holds"

    def test_a_reopen_that_fails_keeps_logging_and_is_retried(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import bristlenose.logging as bn_logging

        out = tmp_path / "bristlenose-output"
        bn_logging.setup_logging(output_dir=out)
        out.rename(tmp_path / "set-aside")
        (out / ".bristlenose").mkdir(parents=True)
        (out / ".bristlenose" / "bristlenose.log").write_text("")
        real = bn_logging._file_handler

        def refuse(_output_dir: Path) -> logging.Handler:
            raise PermissionError("no")

        monkeypatch.setattr(bn_logging, "_file_handler", refuse)
        with pytest.raises(PermissionError):
            bn_logging.reopen_log_file(out)
        files = [h for h in logging.getLogger().handlers if isinstance(h, logging.FileHandler)]
        assert len(files) == 1, "a failed reopen took the only log file away"

        monkeypatch.setattr(bn_logging, "_file_handler", real)
        assert bn_logging.reopen_log_file(out) is True

    def test_it_never_creates_the_output_folder(self, tmp_path: Path) -> None:
        """Mid-restore, a new output folder would block the old one moving back."""
        from bristlenose.logging import reopen_log_file, setup_logging

        out = tmp_path / "bristlenose-output"
        setup_logging(output_dir=out)
        out.rename(tmp_path / "set-aside")
        assert reopen_log_file(out) is False
        assert not out.exists()

    def test_a_log_still_in_place_is_left_alone(self, tmp_path: Path) -> None:
        from bristlenose.logging import reopen_log_file, setup_logging

        setup_logging(output_dir=tmp_path)
        before = [h for h in logging.getLogger().handlers if isinstance(h, logging.FileHandler)]
        assert reopen_log_file(tmp_path) is False
        after = [h for h in logging.getLogger().handlers if isinstance(h, logging.FileHandler)]
        assert after == before

    def test_no_log_file_means_nothing_to_reopen(self, tmp_path: Path) -> None:
        from bristlenose.logging import reopen_log_file, setup_logging

        setup_logging(output_dir=None)
        assert reopen_log_file(tmp_path) is False
        assert not (tmp_path / ".bristlenose").exists()


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
