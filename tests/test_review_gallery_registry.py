"""The Review Gallery registry names real commits.

`desktop/Bristlenose/Bristlenose/ReviewGalleryRegistry.swift` is the list behind
Diagnostics ▸ Review Gallery in the Mac app: one entry per changed surface, each
naming the commits it reviews. "Reviewed" is stored against that commit list, so
a hash that does not resolve (a typo, a rebased-away commit) would make an entry
unreviewable without anyone noticing. The Swift suite checks the shape
(`ReviewGalleryRegistryTests`); only git can say a hash is real, so this reads
the Swift source as text and asks git.

Skipped where there is nothing to ask: no desktop tree, no `.git`, or a shallow
clone (CI's default checkout), where older commits are legitimately absent.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_REGISTRY = (
    _REPO_ROOT / "desktop" / "Bristlenose" / "Bristlenose" / "ReviewGalleryRegistry.swift"
)

_ID_RE = re.compile(r'\bid:\s*"([^"]+)"')
_COMMITS_RE = re.compile(r'\bcommits:\s*\[\s*("[^\]]*)\]')
_HASH_RE = re.compile(r'"([^"]*)"')


def _source() -> str:
    if not _REGISTRY.exists():
        pytest.skip("no desktop tree here")
    return _REGISTRY.read_text(encoding="utf-8")


def _ids(text: str) -> list[str]:
    return _ID_RE.findall(text)


def _hashes(text: str) -> list[str]:
    found: list[str] = []
    for group in _COMMITS_RE.findall(text):
        found.extend(_HASH_RE.findall(group))
    return found


def test_the_registry_parses() -> None:
    text = _source()
    ids = _ids(text)
    groups = _COMMITS_RE.findall(text)
    # One commit list per entry. A drift here means the regexes no longer see
    # the file the way the Swift compiler does — fix them before trusting the
    # tests below, which would otherwise pass on nothing.
    assert ids, "no `id:` found in ReviewGalleryRegistry.swift"
    assert len(groups) == len(ids), f"{len(ids)} ids but {len(groups)} commit lists"
    assert all(_HASH_RE.findall(g) for g in groups), "an entry names no commit"


def test_ids_are_unique() -> None:
    ids = _ids(_source())
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    assert not duplicates, f"duplicate Review Gallery ids: {duplicates}"


def test_every_commit_resolves() -> None:
    text = _source()
    if not (_REPO_ROOT / ".git").exists():
        pytest.skip("not a git checkout")
    shallow = subprocess.run(
        ["git", "-C", str(_REPO_ROOT), "rev-parse", "--is-shallow-repository"],
        capture_output=True, text=True, check=False,
    ).stdout.strip()
    if shallow == "true":
        pytest.skip("shallow clone: older commits are absent by design")

    hashes = sorted(set(_hashes(text)))
    assert hashes, "no commit hashes found"
    missing = [
        h for h in hashes
        if not re.fullmatch(r"[0-9a-f]{7,40}", h)
        or subprocess.run(
            ["git", "-C", str(_REPO_ROOT), "cat-file", "-e", f"{h}^{{commit}}"],
            capture_output=True, check=False,
        ).returncode != 0
    ]
    assert not missing, f"Review Gallery names commits git cannot find: {missing}"
