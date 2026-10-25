"""A folder's name is text, not Rich markup, and a command we print is one the shell reads back.

Two sibling defects from the 25 Oct 2026 sweep (N149, N150), both residue of the
N107 class named in CLAUDE.md:

* a bracketed word in a study folder's name (``[draft] Acme``) was read as a style
  tag and dropped from the status header, from ``No pipeline data found in …`` and
  from the ``Run bristlenose run …`` line, and a name holding ``[/`` made
  ``bristlenose status`` crash with a MarkupError traceback;
* the retry line a stopped run prints (``run bristlenose run <folder>/ again``) named
  the folder bare, so a folder with a space pasted as two arguments
  ("Directory 'Acme' does not exist").
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path

import pytest
from typer.testing import CliRunner

from bristlenose import cli
from bristlenose.config import BristlenoseSettings
from bristlenose.events import Cause, CauseCategoryEnum

_NAMES = ["[draft] Acme", "Acme onboarding", "notes [/] x", "[bold]loud[/bold] study"]
#: A folder's own name cannot hold a "/" (the retry line names the folder, not the path).
_FOLDER_NAMES = [*_NAMES[:2], "[bold]loud study"]


def _run_command(text: str) -> list[str]:
    """The argv a shell would build from the ``bristlenose run …`` in ``text``."""
    match = re.search(r"bristlenose (?:run|analyze) .*?(?= again| to start|$)", text)
    assert match, f"no command in {text!r}"
    return shlex.split(match.group(0))


@pytest.mark.parametrize("name", _NAMES)
def test_status_names_a_folder_with_markup_in_its_name_and_prints_a_command_that_runs(
    name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / name).mkdir(parents=True)  # a "/" in a name makes a nested folder
    result = CliRunner().invoke(cli.app, ["status", name])
    assert result.exception is None or isinstance(result.exception, SystemExit), (
        f"status crashed: {result.exception!r}"
    )
    assert result.exit_code == 1
    text = " ".join(result.output.split())
    assert f"No pipeline data found in {name}." in text
    assert _run_command(text) == ["bristlenose", "run", name]


@pytest.mark.parametrize("name", _NAMES)
def test_the_status_header_names_the_project_whatever_it_is_called(
    name: str, capsys: pytest.CaptureFixture[str],
) -> None:
    from bristlenose.manifest import create_manifest
    from bristlenose.status import ProjectStatus

    manifest = create_manifest(name, "0")
    status = ProjectStatus(
        project_name=manifest.project_name,
        pipeline_version="0",
        last_run=manifest.updated_at,
        stages=[],
    )
    cli._print_project_status(status)
    assert name in capsys.readouterr().out


@pytest.mark.parametrize("name", _FOLDER_NAMES)
@pytest.mark.parametrize(
    "category",
    [
        CauseCategoryEnum.QUOTA,
        CauseCategoryEnum.OUT_OF_CREDIT,
        CauseCategoryEnum.MODEL_UNAVAILABLE,
    ],
)
def test_the_retry_line_of_a_stopped_run_survives_a_paste(
    name: str,
    category: CauseCategoryEnum,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = BristlenoseSettings(llm_provider="anthropic")
    cause = Cause(category=category, message="x", provider="anthropic", stage="quote_extraction")
    cli._print_pipeline_failure(cause, tmp_path / name, settings)
    text = " ".join(capsys.readouterr().out.split())
    assert _run_command(text) == ["bristlenose", "run", f"{name}/"]


def test_the_carry_incomplete_line_names_a_bracketed_folder(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    cli._say_carry_incomplete(tmp_path / "[draft] Acme" / "bristlenose-output")
    assert "[draft] Acme" in " ".join(capsys.readouterr().out.split())



@pytest.mark.parametrize("name", [*_FOLDER_NAMES, "a]b"])
def test_the_server_failed_fallback_names_the_error_and_the_file_whatever_the_folder_is_called(
    name: str, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Its job is to say why the server did not start and where the file is; a
    bracketed folder made it raise MarkupError instead, hiding the real error."""
    monkeypatch.chdir(tmp_path)
    report = tmp_path / name / "report.html"
    report.parent.mkdir()
    report.write_text("x", encoding="utf-8")
    cli._say_server_not_started(OSError(f"cannot bind [draft] {name}"), report)
    text = " ".join(capsys.readouterr().out.split())
    assert f"Could not start server: cannot bind [draft] {name}" in text
    assert f"Report: {name}/report.html" in text
