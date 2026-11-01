"""`run` no longer accepts `--config` (N119, owner ruling 1 Nov 2026).

The flag was accepted and never read: nothing in the settings loads a `bristlenose.toml`, so a
researcher who pointed it at one got no error and no effect. A script that passes it now fails
loudly with the usual "No such option" instead of being silently ignored.
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from bristlenose.cli import app


def test_run_rejects_config_instead_of_ignoring_it(tmp_path: Path) -> None:
    folder = tmp_path / "interviews"
    folder.mkdir()
    result = CliRunner().invoke(app, ["run", str(folder), "--config", "x.toml"])
    assert result.exit_code == 2
    assert "No such option" in result.output


def test_run_help_does_not_list_config() -> None:
    out = CliRunner().invoke(app, ["run", "--help"]).output
    assert "--config" not in out


def test_the_man_page_does_not_document_a_config_flag() -> None:
    man = Path("bristlenose/data/bristlenose.1").read_text(encoding="utf-8")
    man = man.replace("\\-", "-")
    assert "--config" not in man
