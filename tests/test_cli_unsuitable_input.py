"""`run`, `transcribe` and `analyze` refuse a home folder or system root by name, first.

Until 22 Oct 2026 the refusal was raised from inside the scan, past the output
folder's creation, a `--clean` stash and the setup checks, and nothing caught
it: `bristlenose run ~` ended in a Rich traceback whose last line was the
sentence written for the researcher (RE#20, decision #110).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from bristlenose import cli


@pytest.fixture()
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    (home / "interview.mp3").write_bytes(b"\x00")
    monkeypatch.setenv("HOME", str(home))
    return home


@pytest.mark.parametrize("command", ["run", "transcribe"])
def test_home_folder_is_refused_by_name_without_a_traceback(
    home: Path, command: str
) -> None:
    result = CliRunner().invoke(cli.app, [command, str(home)])

    assert result.exit_code == 2, result.output
    assert "Traceback" not in result.output
    assert not isinstance(result.exception, ValueError), "the refusal escaped as a crash"
    flat = " ".join(result.output.split())
    assert "can't be analysed because it is your home folder" in flat
    assert "Point Bristlenose at the folder holding your recordings." in flat
    # Before the setup checks, so before anything they or the run would write.
    assert "AI provider" not in flat
    assert sorted(p.name for p in home.iterdir()) == ["interview.mp3"]



# `analyze` takes a transcripts folder and, unless --output says otherwise, puts
# the report beside it (`<parent>/bristlenose-output`) or, for a project's own
# `transcripts-raw`, in its parent. So the parent is the study: `analyze ~` ended
# in a traceback writing /Users/bristlenose-output, and `analyze ~/transcripts`
# made the home folder a study (decision #160).
@pytest.mark.parametrize(
    "argument",
    [
        ".",  # the home folder itself
        "transcripts",  # the report would land in the home folder
        "transcripts-raw",  # the report would BE the home folder
    ],
)
def test_analyze_refuses_a_home_folder_by_name_without_a_traceback(
    home: Path, tmp_path: Path, argument: str
) -> None:
    folder = (home / argument).resolve()
    folder.mkdir(exist_ok=True)
    (folder / "s1.txt").write_text("[00:00] p1: hello\n")
    before = sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*"))

    result = CliRunner().invoke(cli.app, ["analyze", str(folder)])

    assert result.exit_code == 2, result.output
    assert "Traceback" not in result.output
    assert not isinstance(result.exception, ValueError), "the refusal escaped as a crash"
    flat = " ".join(result.output.split())
    assert "can't be analysed because it is your home folder" in flat
    # The home folder is named, whichever folder was typed (Rich may wrap the path).
    assert f"{home}can't" in "".join(result.output.split())
    assert "Point Bristlenose at the folder holding your recordings." in flat
    assert "AI provider" not in flat
    assert sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*")) == before


class _PastTheRefusalError(Exception):
    pass


@pytest.mark.parametrize(
    ("argument", "explicit_output"),
    [
        ("study/transcripts", False),  # an ordinary study: the report lands in ~/study
        ("transcripts", True),  # an explicit --output: only the argument is checked
    ],
)
def test_analyze_lets_an_ordinary_transcripts_folder_through(
    home: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    argument: str,
    explicit_output: bool,
) -> None:
    transcripts = home / argument
    transcripts.mkdir(parents=True)
    extra = ["--output", str(tmp_path / "out")] if explicit_output else []

    def stop(**_kwargs: object) -> None:
        raise _PastTheRefusalError

    monkeypatch.setattr(cli, "load_settings", stop)
    result = CliRunner().invoke(cli.app, ["analyze", str(transcripts), *extra])

    assert isinstance(result.exception, _PastTheRefusalError), result.output
    assert "can't be analysed" not in " ".join(result.output.split())


def test_a_relative_argument_is_refused_by_the_folder_it_names(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`cd ~ && analyze transcripts` refuses `Path("transcripts").parent`, which is
    `.`: the sentence names the home folder, not a bare "." the user never typed."""
    (home / "transcripts").mkdir()
    monkeypatch.chdir(home)

    result = CliRunner().invoke(cli.app, ["analyze", "transcripts"])

    assert result.exit_code == 2, result.output
    assert f"{home.resolve()}can't" in "".join(result.output.split())
