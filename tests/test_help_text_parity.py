"""The hidden ``bristlenose help`` pages name only commands the CLI has.

``help``, ``help commands`` and ``help workflows`` are hand-written, so they
drift from the command list: until 20 Oct 2026 they still listed ``render``
(removed, now a hidden tombstone that errors) in the command overview, as a
``help commands`` entry and as workflow 3, and said ``-o`` defaulted to
``output``. ``bristlenose --help`` is the truth; this compares the two,
reading the real command list rather than a copy of it.
"""

from __future__ import annotations

import re
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from bristlenose.cli import app

_PAGES = ([], ["commands"], ["workflows"])


@pytest.fixture(scope="module")
def group() -> Any:
    command = typer.main.get_command(app)
    assert command.commands, "the CLI has no commands — did get_command change?"
    return command


@pytest.fixture(scope="module")
def visible(group: Any) -> set[str]:
    return {name for name, cmd in group.commands.items() if not cmd.hidden}


def _page(args: list[str]) -> str:
    result = CliRunner().invoke(app, ["help", *args])
    assert result.exit_code == 0, result.output
    return result.output


@pytest.mark.parametrize("args", _PAGES, ids=["overview", "commands", "workflows"])
def test_every_command_a_help_page_names_is_a_listed_command(
    args: list[str], visible: set[str],
) -> None:
    text = _page(args)
    named = set(re.findall(r"\bbristlenose ([a-z][a-z-]*)\b", text))
    assert named, f"no commands found on `help {' '.join(args)}` — did the format change?"
    assert named <= visible, (
        f"`help {' '.join(args)}` names {sorted(named - visible)}, "
        f"which `bristlenose --help` does not list"
    )


def test_the_overview_command_table_lists_only_listed_commands(visible: set[str]) -> None:
    text = _page([])
    table = text.split("Commands\n", 1)[1].split("\n\n", 1)[0]
    names = {line.split()[0] for line in table.splitlines() if line.strip()}
    assert names, "the overview's Commands table is empty — did the format change?"
    assert names <= visible, (
        f"the overview lists {sorted(names - visible)}, "
        f"which `bristlenose --help` does not list"
    )


def test_the_output_default_matches_the_option(group: Any) -> None:
    """`help commands` said `-o` defaulted to `output`; the option's own help
    says bristlenose-output inside the input folder."""
    run = group.commands["run"]
    output = next(p for p in run.params if p.name == "output_dir")
    assert "bristlenose-output" in (getattr(output, "help", "") or "")
    text = _page(["commands"])
    run_section = text.split("bristlenose run", 1)[1].split("\n\n", 1)[0]
    flat = " ".join(run_section.split())
    match = re.search(r"--output DIR Output directory \(default: ([^)]*)\)", flat)
    assert match, run_section
    assert "bristlenose-output" in match.group(1)
