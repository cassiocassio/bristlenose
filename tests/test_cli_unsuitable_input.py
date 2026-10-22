"""`run` and `transcribe` refuse a home folder or system root by name, before anything.

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

