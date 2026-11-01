"""A study a newer Bristlenose has opened is refused with one sentence, not a traceback (N147).

Opening a study in an older Bristlenose (an un-upgraded Homebrew or pip CLI, an older Mac
build) after a newer one had migrated its database made Alembic raise "Can't locate revision"
out of ``create_app``: a traceback, the report never opened, and the researcher thought the
study was broken. Beta behaviour, decided 1 Nov 2026: say it in one line and exit 2. What a
released version promises about this is a separate, post-v1 question
(docs/design-upgrades-and-compatibility.md).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import typer
from sqlalchemy import text

from bristlenose.server.db import StudyIsNewerError, get_engine, init_db


def _stamp_from_the_future(db_file: Path) -> None:
    engine = get_engine(f"sqlite:///{db_file}")
    init_db(engine)
    with engine.begin() as conn:
        conn.execute(text("UPDATE alembic_version SET version_num = 'zz_from_the_future'"))
    engine.dispose()


def test_a_database_a_newer_build_migrated_is_named_not_crashed_on(tmp_path: Path) -> None:
    db_file = tmp_path / "bristlenose.db"
    _stamp_from_the_future(db_file)
    engine = get_engine(f"sqlite:///{db_file}")
    with pytest.raises(StudyIsNewerError):
        init_db(engine)
    engine.dispose()


def test_an_ordinary_database_still_opens(tmp_path: Path) -> None:
    engine = get_engine(f"sqlite:///{tmp_path / 'bristlenose.db'}")
    init_db(engine)
    init_db(engine)  # safe to call repeatedly
    engine.dispose()


def test_serve_says_one_line_and_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from bristlenose.cli import _create_admitted_app

    project = tmp_path / "study"
    (project / "bristlenose-output" / ".bristlenose").mkdir(parents=True)
    _stamp_from_the_future(project / "bristlenose-output" / ".bristlenose" / "bristlenose.db")

    with pytest.raises(typer.Exit) as exit_info:
        _create_admitted_app(project, False, False)
    assert exit_info.value.exit_code == 2
    out = " ".join(capsys.readouterr().out.split())
    assert "This study was opened by a newer Bristlenose. Update to open it." in out
    assert "Traceback" not in out
