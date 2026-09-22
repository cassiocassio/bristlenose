"""`check_bundle_locales` must not require a full locale's files from a fork.

The gate blocked every desktop build on 22 Sep 2026 against a correct tree. It
required `common.json` from all 22 locale **codes**, and `zh-Hant-HK` is a thin
override fork that ships only what it overrides — an absent namespace there is
how it inherits, not a gap.

Three things make it worth a test file rather than a one-line fix:

* **It cannot fail in CI.** It reads a built PyInstaller bundle, so its only
  natural home is ~87s into a desktop build. These tests give it a home that
  runs in milliseconds against a synthetic tree, which is the difference
  between a regression caught now and one caught at the next release.
* **The loop it fixes is load-bearing.** `33c9f6ae` wrote it to catch "spec
  entry present, but PyInstaller silently dropped files". Weakening it was
  proposed twice during diagnosis and rejected twice; these tests pin what it
  still catches so the next person can see the cost of touching it.
* **The premise was invisible.** `zh-Hant-HK` was enrolled in the full-locale
  set on 30 Jun, three days before the thin-fork classification existed at all
  (`b6ae8951`, which swept the tests, the guide and `check-locales.py` — but
  not `doctor.py`). Its `common.json` carried three `help` overrides; the help
  modal was retired eleven days later, so from 10 Jul the check asserted
  nothing real about that locale and passed anyway, for ten weeks.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from bristlenose import doctor
from bristlenose.doctor import CheckStatus, check_bundle_locales
from bristlenose.i18n import FALLBACK_ONLY_LOCALES, SUPPORTED_LOCALES

_ROOT_DOC = Path(__file__).resolve().parents[1] / "docs" / "design-doctor-and-snap.md"
_FULL = sorted(set(SUPPORTED_LOCALES) - FALLBACK_ONLY_LOCALES)
_FORK = sorted(FALLBACK_ONLY_LOCALES)


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.fixture
def tree(tmp_path, monkeypatch):
    """A synthetic locales tree, healthy by default, that the check can read."""

    def _build(**edits):
        root = tmp_path / "pkg"
        for lang in _FULL:
            # Comfortably over the 100-byte floor, as a real locale is.
            _write(root / "locales" / lang / "common.json", {"pad": "x" * 200})
        for lang in _FORK:
            # A fork ships only overrides — deliberately no common.json.
            _write(root / "locales" / lang / "desktop.json", {"a": "b"})
        for rel, action in edits.items():
            target = root / "locales" / rel
            if action is None:
                target.unlink()
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(action, encoding="utf-8")
        monkeypatch.setattr(doctor, "_package_root", lambda: root)
        return root

    return _build


def test_a_fork_without_common_json_is_healthy(tree):
    """The defect, stated as the contract. This is what blocked the build."""
    tree()
    result = check_bundle_locales()
    assert result.status is CheckStatus.OK, result.detail


def test_a_full_locale_missing_common_json_still_fails(tree):
    """The loop's real job survives: a tree that arrived without its files."""
    tree(**{"es/common.json": None})
    result = check_bundle_locales()
    assert result.status is CheckStatus.FAIL
    assert "es/common.json" in result.detail


def test_a_truncated_full_locale_still_fails(tree):
    """The size floor survives where it belongs — on locales that ship prose.

    `strip` once left a file at exactly the right size with zeros inside
    (root CLAUDE.md, the SIGILL post-mortem), so "present" has never been the
    same question as "intact" in this bundle.
    """
    tree(**{"de/common.json": "{}"})
    result = check_bundle_locales()
    assert result.status is CheckStatus.FAIL
    assert "de/common.json" in result.detail


def test_an_empty_fork_directory_fails(tree):
    """A fork names no required namespace, but an empty directory is a drop.

    Without this the fix would trade one blind spot for another: `zh-Hant-HK`
    could vanish from a bundle entirely and the check would shrug.
    """
    for lang in _FORK:
        tree(**{f"{lang}/desktop.json": None})
        result = check_bundle_locales()
        assert result.status is CheckStatus.FAIL, f"{lang}: empty fork dir passed"
        assert lang in result.detail


def test_no_size_floor_on_a_fork(tree):
    """A legitimate fork can be one short override — 38 bytes, measured.

    Applying the full-locale floor here would fail a correct tree for the
    second time in this function's life, which is the specific mistake this
    file exists to prevent recurring in a new place.
    """
    for lang in _FORK:
        tiny = json.dumps({"settings": {"appearance": {"theme": "主題"}}})
        assert len(tiny.encode()) < 100, "the premise of this test"
        tree(**{f"{lang}/desktop.json": tiny})
        assert check_bundle_locales().status is CheckStatus.OK


def test_a_missing_language_directory_still_fails(tree):
    """The outer assertion is untouched: a dropped tree is still a dropped tree."""
    root = tree()
    for f in (root / "locales" / "ja").iterdir():
        f.unlink()
    (root / "locales" / "ja").rmdir()
    result = check_bundle_locales()
    assert result.status is CheckStatus.FAIL
    assert "ja" in result.detail


def test_the_real_tree_passes():
    """No fixture. The build failed against the shipped tree, so pin it."""
    result = check_bundle_locales()
    assert result.status is CheckStatus.OK, result.detail


def test_the_success_message_does_not_claim_what_it_cannot(tree):
    """The old one said "all with common.json" one line under the loop that
    asserted it — a claim that was never true of the fork by design. A gate
    whose passing message teaches the wrong architecture is how the premise
    survived three months of green builds."""
    tree()
    detail = check_bundle_locales().detail
    assert "all with common.json" not in detail
    assert str(len(_FULL)) in detail and str(len(_FORK)) in detail


def test_the_classification_has_exactly_one_home():
    """`bristlenose.i18n` owns it; the test module derives. Two copies is how
    doctor.py went on encoding the old premise after the concept existed."""
    from tests import test_pipeline_diagnostic_locale_keys as sibling

    assert tuple(sorted(FALLBACK_ONLY_LOCALES)) == sibling._FALLBACK_ONLY_LOCALES
    source = Path(sibling.__file__).read_text(encoding="utf-8")
    assert '_FALLBACK_ONLY_LOCALES = ("zh-Hant-HK",)' not in source, (
        "the sibling restated the list instead of deriving it — one copy only"
    )


def test_every_bundle_check_is_documented():
    """The design doc's table of `--self-test` checks must name all of them.

    It drifted by two — `check_bundle_admin_panel` and `check_bundle_mcp` were
    added after it was written, and the table stopped at six while the code had
    eight. That is the `_JS_FILES` disease the root CLAUDE.md names: a list kept
    in prose is a list nobody recomputes, and the same pass found the table's
    locale row asserting 21 dirs when there are 22.

    Names, not a count — a count is the brittle version and would fail on a
    reordering that changed nothing.
    """
    doc = (_ROOT_DOC).read_text(encoding="utf-8")
    source = (Path(__file__).resolve().parents[1] / "bristlenose" / "doctor.py").read_text(
        encoding="utf-8"
    )
    in_code = set(re.findall(r"^def (check_bundle_\w+)", source, re.M))
    undocumented = sorted(name for name in in_code if f"`{name}`" not in doc)
    assert not undocumented, (
        f"{undocumented} run in doctor --self-test but appear in no row of "
        f"{_ROOT_DOC.name}'s check table. Add a row in the same commit — this "
        f"table is the only place the checks are described together."
    )
