"""caplog sees what is logged after ``create_app``.

``create_app(project_dir=…)`` calls ``setup_logging``, which removes every
handler on the root logger, pytest's capture handler with them, so a test
asserting a server warning through caplog failed while the line was plainly on
stderr. Several tests grew their own handler on a named logger to work round
it. ``conftest.no_run_log_handlers_left_behind`` now puts pytest's handlers
back after each ``setup_logging`` in a test that asks for caplog; product
logging is unchanged.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest


def test_caplog_sees_a_warning_logged_after_create_app(
    tmp_path: Path, caplog: pytest.LogCaptureFixture,
) -> None:
    from bristlenose.server.app import create_app

    create_app(project_dir=tmp_path, db_url="sqlite://")
    logging.getLogger("bristlenose.server.app").warning("seen by caplog")
    assert "seen by caplog" in caplog.text


def test_setup_logging_still_replaces_its_own_handlers(
    tmp_path: Path, caplog: pytest.LogCaptureFixture,
) -> None:
    """Only pytest's handlers are kept: a second call still leaves one
    terminal handler and one log file, not two of each."""
    from bristlenose.logging import setup_logging

    setup_logging(output_dir=tmp_path)
    setup_logging(output_dir=tmp_path)
    ours = [
        h for h in logging.getLogger().handlers
        if type(h) in (logging.StreamHandler, RotatingFileHandler)
    ]
    assert len(ours) == 2, ours
    assert caplog.handler in logging.getLogger().handlers
