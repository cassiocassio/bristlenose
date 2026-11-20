"""The docs-terms lint and its rules file (docs/platform-terms.json).

scripts/check-docs-terms.py flags forbidden spellings of platform and vendor names in
prose. These tests prove it can fail (a forbidden spelling is caught), that it leaves
code, links and URLs alone, and that the glossary table and the JSON cannot drift apart.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "check-docs-terms.py"
RULES = ROOT / "docs" / "platform-terms.json"
GLOSSARY = ROOT / "docs" / "glossary.md"


def run_lint(tmp_path: Path, name: str, body: str) -> subprocess.CompletedProcess[str]:
    f = tmp_path / name
    f.write_text(body, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(f)], capture_output=True, text=True, check=False
    )


def terms() -> list[dict]:
    return json.loads(RULES.read_text(encoding="utf-8"))["terms"]


# --- the lint can fail ---------------------------------------------------------------


def test_flags_arm_in_prose(tmp_path: Path) -> None:
    r = run_lint(tmp_path, "a.md", "Install on an ARM computer.\n")
    assert r.returncode == 1
    assert "'ARM' should be 'Arm'" in r.stdout


def test_flags_apple_silicon_capital_s(tmp_path: Path) -> None:
    r = run_lint(tmp_path, "a.md", "Runs on Apple Silicon.\n")
    assert r.returncode == 1
    assert "Apple silicon" in r.stdout


def test_clean_prose_passes(tmp_path: Path) -> None:
    body = "On an Arm computer or Apple silicon, use macOS, FFmpeg and Homebrew.\n"
    assert run_lint(tmp_path, "a.md", body).returncode == 0


# --- and leaves non-prose alone ------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        "Run `uname` and look for `ARM` here.\n",
        "Use `ARM64` here.\n",
        "```\nuname -m  # ARM\n```\n",
        "[Arm docs](https://example.com/ARM/page)\n",
        "See https://example.com/ARM for details.\n",
        "<!-- an ARM comment -->\n",
        "A quoted old name: ARM  <!-- terms:ignore -->\n",
        "ARM64 is an architecture identifier.\n",
    ],
)
def test_non_prose_is_not_flagged(tmp_path: Path, body: str) -> None:
    assert run_lint(tmp_path, "a.md", body).returncode == 0


def test_html_prose_flagged_but_code_and_script_not(tmp_path: Path) -> None:
    body = (
        "<p>An ARM laptop.</p>\n"
        "<script>\nconst x = 'ARM';\n</script>\n"
        "<pre>\nuname ARM\n</pre>\n"
        '<a href="https://example.com/ARM">fine</a>\n'
    )
    r = run_lint(tmp_path, "a.html", body)
    assert r.returncode == 1
    assert r.stdout.count("should be") == 1
    assert "a.html:1:" in r.stdout


def test_missing_path_is_a_usage_error(tmp_path: Path) -> None:
    r = subprocess.run(
        [sys.executable, str(SCRIPT), str(tmp_path / "nope.md")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 2


def test_a_directory_is_searched_and_build_is_skipped(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "build").mkdir()
    (tmp_path / "docs" / "a.md").write_text("An ARM box.\n", encoding="utf-8")
    (tmp_path / "build" / "b.md").write_text("An ARM box.\n", encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(SCRIPT), str(tmp_path)], capture_output=True, text=True, check=False
    )
    assert r.returncode == 1
    assert "docs/a.md" in r.stdout
    assert "build" not in r.stdout


# --- the rules file and the glossary cannot drift ------------------------------------


def test_every_forbidden_pattern_compiles() -> None:
    for t in terms():
        for pat in t["forbidden"]:
            re.compile(pat)


def test_a_canonical_spelling_is_never_flagged_by_any_rule() -> None:
    """A rule that bans the spelling another rule recommends is a contradiction."""
    for t in terms():
        for other in terms():
            for pat in other["forbidden"]:
                assert not re.search(pat, t["canonical"]), (t["canonical"], pat)


def test_every_canonical_is_in_the_glossary_table() -> None:
    """The JSON is the data and the glossary is the human table: one cannot move alone."""
    text = GLOSSARY.read_text(encoding="utf-8")
    section = text.split("## Platforms, vendors and architectures", 1)[1].split("\n## ", 1)[0]
    section = section.replace("\\_", "_")
    missing = [t["canonical"] for t in terms() if t["canonical"] not in section]
    assert not missing, f"in platform-terms.json but not in the glossary section: {missing}"


def test_every_forbidden_spelling_is_in_the_glossary_table() -> None:
    """The Forbidden column must list what the lint enforces (checked on the plain words)."""
    text = GLOSSARY.read_text(encoding="utf-8")
    section = text.split("## Platforms, vendors and architectures", 1)[1].split("\n## ", 1)[0]
    section = section.replace("\\_", "_")
    for t in terms():
        for pat in t["forbidden"]:
            word = pat.replace("\\b", "").replace("\\", "")
            assert word in section, f"{t['canonical']}: forbidden '{word}' not in the glossary"
