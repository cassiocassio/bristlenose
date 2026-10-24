"""`run --clean` asks before it discards a report's stars, tags and edits (R113).

Decision #135 (owner, 24 Oct 2026): typing --clean is a deliberate act, but a
terminal is easy to skim and the loss can't be undone. So the CLI counts what
the Mac's Re-analyse sheet counts and asks on a terminal; `--yes` skips the
question; where nobody can answer, it refuses rather than guess. A run hosted
by the Mac is not asked again, since the app's own sheet already asked.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from bristlenose import curation_counts
from bristlenose.cli import app
from bristlenose.events import PipelineSummary

_MARKER = "bristlenose-report.html"


class _Result:
    llm_model = "claude-sonnet-4-6"
    llm_input_tokens = 0
    llm_output_tokens = 0
    llm_calls = 1
    total_quotes = 3
    summary = PipelineSummary()


_SCHEMA = """
CREATE TABLE quotes (id INTEGER PRIMARY KEY, project_id INTEGER);
CREATE TABLE quote_states (quote_id INTEGER, is_starred INTEGER);
CREATE TABLE quote_tags (quote_id INTEGER, source TEXT);
CREATE TABLE quote_edits (quote_id INTEGER);
CREATE TABLE persons (full_name TEXT);
CREATE TABLE heading_edits (project_id INTEGER);
CREATE TABLE sessions (project_id INTEGER);
"""


def _seed_report(out_dir: Path, *, stars: int = 0, human_tags: int = 0,
                 autocode_tags: int = 0, sessions: int = 10) -> None:
    """A previous report whose database holds the given curation."""
    state = out_dir / ".bristlenose"
    state.mkdir(parents=True, exist_ok=True)
    (out_dir / _MARKER).write_text("old", encoding="utf-8")
    conn = sqlite3.connect(state / "bristlenose.db")
    conn.executescript(_SCHEMA)
    conn.executemany("INSERT INTO quotes (id, project_id) VALUES (?, 1)",
                     [(i,) for i in range(1, 51)])
    conn.executemany("INSERT INTO quote_states VALUES (?, 1)", [(i,) for i in range(1, stars + 1)])
    conn.executemany("INSERT INTO quote_tags VALUES (?, 'human')",
                     [(i,) for i in range(1, human_tags + 1)])
    conn.executemany("INSERT INTO quote_tags VALUES (?, 'autocode')",
                     [(i,) for i in range(1, autocode_tags + 1)])
    conn.executemany("INSERT INTO sessions VALUES (1)", [() for _ in range(sessions)])
    conn.commit()
    conn.close()


@pytest.fixture
def cli(monkeypatch):
    """Reach the pipeline (stubbed) with no keychain, preflight or provider gate."""
    monkeypatch.setattr("bristlenose.config._populate_keys_from_keychain", lambda s: s)
    monkeypatch.setattr("bristlenose.cli._maybe_guide_provider_setup", lambda s: None)
    monkeypatch.setattr("bristlenose.cli._maybe_auto_doctor", lambda s, c: True)
    monkeypatch.setattr("bristlenose.preflight.api_key.preflight_api_key", lambda **kw: None)
    ran: list[bool] = []

    async def _run(_self, _in, out, *a, **k):
        ran.append(True)
        (Path(out) / _MARKER).write_text("new", encoding="utf-8")
        return _Result()

    monkeypatch.setattr("bristlenose.pipeline.Pipeline.run", _run)
    return CliRunner(), ran


def _clean(runner: CliRunner, input_dir: Path, *extra: str, stdin: str | None = None):
    return runner.invoke(app, ["run", str(input_dir), "--clean", "--no-serve", *extra],
                         input=stdin)


def _paths(tmp_path: Path) -> tuple[Path, Path]:
    input_dir = tmp_path / "interviews"
    return input_dir, input_dir / "bristlenose-output"


class TestNobodyToAsk:
    def test_a_curated_report_is_refused_and_left_alone(self, cli, tmp_path) -> None:
        runner, ran = cli
        input_dir, out = _paths(tmp_path)
        _seed_report(out, stars=12, human_tags=31)

        result = _clean(runner, input_dir)

        assert result.exit_code == 2, result.output
        text = " ".join(result.output.split())
        assert "31 tags" in text and "12 starred quotes" in text
        assert "Add --yes to re-analyse anyway." in text
        assert not ran
        assert (out / _MARKER).read_text(encoding="utf-8") == "old"

    def test_yes_skips_the_question(self, cli, tmp_path) -> None:
        runner, ran = cli
        input_dir, out = _paths(tmp_path)
        _seed_report(out, stars=12)

        result = _clean(runner, input_dir, "--yes")

        assert result.exit_code == 0, result.output
        assert ran
        assert (out / _MARKER).read_text(encoding="utf-8") == "new"

    def test_a_run_the_mac_started_is_not_asked_again(self, cli, tmp_path, monkeypatch) -> None:
        runner, ran = cli
        input_dir, out = _paths(tmp_path)
        _seed_report(out, stars=12)
        monkeypatch.setattr("bristlenose.config.hosted_by_desktop", lambda: True)

        result = _clean(runner, input_dir)

        assert result.exit_code == 0, result.output
        assert ran

    def test_nothing_to_lose_runs_without_a_question(self, cli, tmp_path) -> None:
        """AutoCode's own proposals are not the researcher's work."""
        runner, ran = cli
        input_dir, out = _paths(tmp_path)
        _seed_report(out, autocode_tags=5)

        result = _clean(runner, input_dir)

        assert result.exit_code == 0, result.output
        assert ran

    def test_a_count_that_cannot_be_taken_is_refused_too(self, cli, tmp_path) -> None:
        runner, ran = cli
        input_dir, out = _paths(tmp_path)
        (out / ".bristlenose").mkdir(parents=True)
        (out / _MARKER).write_text("old", encoding="utf-8")
        (out / ".bristlenose" / "bristlenose.db").write_text("not a database", encoding="utf-8")

        result = _clean(runner, input_dir)

        assert result.exit_code == 2, result.output
        assert "couldn't count them" in " ".join(result.output.split())
        assert not ran


class TestOnATerminal:
    @pytest.fixture(autouse=True)
    def _terminal(self, monkeypatch):
        monkeypatch.setattr("bristlenose.cli._stdin_is_a_terminal", lambda: True)

    def test_no_keeps_the_report(self, cli, tmp_path) -> None:
        runner, ran = cli
        input_dir, out = _paths(tmp_path)
        _seed_report(out, stars=12, human_tags=31)

        result = _clean(runner, input_dir, stdin="n\n")

        assert result.exit_code == 0, result.output
        assert "Re-analyse “interviews”?" in result.output
        assert "Bristlenose will transcribe and analyse all 10 interviews again" in result.output
        assert "Your work on this study will be discarded:" in result.output
        assert "Nothing changed." in result.output
        assert not ran
        assert (out / _MARKER).read_text(encoding="utf-8") == "old"

    def test_yes_at_the_prompt_re_analyses(self, cli, tmp_path) -> None:
        runner, ran = cli
        input_dir, out = _paths(tmp_path)
        _seed_report(out, stars=1)

        result = _clean(runner, input_dir, stdin="y\n")

        assert result.exit_code == 0, result.output
        assert ran

    def test_the_default_answer_is_no(self, cli, tmp_path) -> None:
        runner, ran = cli
        input_dir, out = _paths(tmp_path)
        _seed_report(out, stars=1)

        result = _clean(runner, input_dir, stdin="\n")

        assert result.exit_code == 0, result.output
        assert "Nothing changed." in result.output
        assert not ran

    def test_a_count_that_cannot_be_taken_still_asks(self, cli, tmp_path) -> None:
        runner, ran = cli
        input_dir, out = _paths(tmp_path)
        (out / ".bristlenose").mkdir(parents=True)
        (out / _MARKER).write_text("old", encoding="utf-8")
        (out / ".bristlenose" / "bristlenose.db").write_text("not a database", encoding="utf-8")

        result = _clean(runner, input_dir, stdin="n\n")

        assert "Bristlenose couldn't count your stars, tags and edits" in result.output
        assert "Nothing changed." in result.output
        assert not ran


class TestTheCounts:
    def test_they_run_against_the_real_schema(self, tmp_path) -> None:
        """Every column the five queries name exists in the server's models; an
        empty study counts zero, not unreadable."""
        from sqlalchemy import create_engine

        from bristlenose.server.models import Base

        out = tmp_path / "bristlenose-output"
        (out / ".bristlenose").mkdir(parents=True)
        engine = create_engine(f"sqlite:///{curation_counts.db_path(out)}")
        Base.metadata.create_all(engine)
        engine.dispose()

        counts = curation_counts.read(out)

        assert counts is not None
        assert counts.total == 0
        # A table renamed in the models would read as zero for good, and the
        # zero above can't tell: the five queries' tables must all exist.
        assert {"quotes", "quote_edits", "quote_tags", "quote_states", "persons",
                "heading_edits", "sessions"} <= set(Base.metadata.tables)

    # Windows forbids "?" in a file name, so that folder cannot exist there.
    @pytest.mark.parametrize("folder", ["Round #2", "100%25 done"]
                             + ([] if sys.platform == "win32" else ["Study?v2"]))
    def test_a_folder_name_with_uri_characters_is_counted(self, tmp_path, folder) -> None:
        """A raw `file:` URI cut the path at `#` or `?`, created an empty
        database there and counted zero: --clean discarded curation unasked."""
        study = tmp_path / folder
        out = study / "bristlenose-output"
        _seed_report(out, stars=1)
        before = sorted(p.name for p in tmp_path.iterdir())

        counts = curation_counts.read(out)

        assert counts is not None and counts.starred_quotes == 1
        assert sorted(p.name for p in tmp_path.iterdir()) == before

    def test_a_relative_output_path_is_counted(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _seed_report(tmp_path / "interviews" / "bristlenose-output", stars=2)

        counts = curation_counts.read(Path("interviews") / "bristlenose-output")

        assert counts is not None and counts.starred_quotes == 2

    def test_no_database_is_nothing_to_lose(self, tmp_path) -> None:
        counts = curation_counts.read(tmp_path / "bristlenose-output")
        assert counts is not None and counts.total == 0

    def test_a_curated_study(self, tmp_path) -> None:
        out = tmp_path / "bristlenose-output"
        _seed_report(out, stars=2, human_tags=3, autocode_tags=4, sessions=1)

        counts = curation_counts.read(out)

        assert counts is not None
        assert counts.lines() == ["3 tags", "2 starred quotes"]
        assert counts.sessions == 1


def test_a_report_that_cannot_be_resumed_says_what_clean_costs(cli, tmp_path) -> None:
    runner, ran = cli
    input_dir, out = _paths(tmp_path)
    out.mkdir(parents=True)
    (out / _MARKER).write_text("old", encoding="utf-8")

    result = runner.invoke(app, ["run", str(input_dir), "--no-serve"])

    assert result.exit_code == 1, result.output
    text = " ".join(result.output.split())
    assert "holds a report Bristlenose can't resume" in text
    assert "it discards that report's stars, tags and edits" in text
    assert not ran
