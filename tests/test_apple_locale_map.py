"""The Apple locale map is derived and gated, not remembered.

An i18n pass cross-checks our wording against Apple's own translations in the
system ``.loctable`` corpus.  That needs our code -> Apple's code, and the map
used to live in prose in two CLAUDE.md files.  ``pt-BR`` -> ``pt`` was written
down and was wrong, and it could not fail: bare ``pt`` is a real Apple code
(legacy Brazilian) so the lookup succeeded, returned nothing for the key, and
"Apple ships no translation here" is indistinguishable from a clean audit.

These tests gate the two things that made it survive:

1. A new language cannot silently skip the cross-check -- adding a locale
   without resolving it fails here, on any platform.
2. Resolution is by measured COVERAGE, never by existence.  ``nb``,
   ``zh-Hant`` and ``pt-PT`` all exist verbatim as Apple codes carrying ~75
   keys against ~211,000 for the correct alias, so an existence check blesses
   the decoy and keeps missing everything.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest

from bristlenose.i18n import SUPPORTED_LOCALES

REPO = pathlib.Path(__file__).resolve().parent.parent
MAP_PATH = REPO / "scripts" / "apple-locale-map.json"
SCRIPT = REPO / "scripts" / "apple-locale-map.py"
LOCTABLE_ROOT = pathlib.Path("/System/Library/Frameworks")

needs_macos = pytest.mark.skipif(
    not LOCTABLE_ROOT.is_dir(),
    reason="Apple .loctable corpus only exists on macOS; the checked-in map is "
    "the artefact everywhere else, and the parity tests above still bite.",
)


@pytest.fixture(scope="module")
def amap() -> dict:
    assert MAP_PATH.exists(), (
        f"{MAP_PATH.relative_to(REPO)} is missing. Regenerate it on a Mac with "
        "scripts/apple-locale-map.py --write"
    )
    return json.loads(MAP_PATH.read_text())


def test_every_locale_we_ship_resolves_to_an_apple_code(amap: dict) -> None:
    """Adding a language must not silently skip the Apple cross-check.

    This is the parity gate and it runs on Linux too, so a new locale directory
    fails CI rather than quietly losing the one check that would have found
    Apple's own wording for it.
    """
    missing = [loc for loc in SUPPORTED_LOCALES if loc not in amap["map"]]
    assert not missing, (
        f"locales absent from the Apple map: {missing}. Adding a language is a "
        "registration site here too -- run scripts/apple-locale-map.py --write "
        "on a Mac and commit the result."
    )

    unresolved = [loc for loc in SUPPORTED_LOCALES if amap["map"].get(loc) is None]
    assert not unresolved, (
        f"locales with no Apple code: {unresolved}. Resolve them or record, in "
        "the map and in a comment here, why Apple genuinely ships nothing."
    )


def test_map_holds_no_locale_we_have_stopped_shipping(amap: dict) -> None:
    """The map is not allowed to accumulate codes we no longer ship."""
    stale = [loc for loc in amap["map"] if loc not in SUPPORTED_LOCALES]
    assert not stale, f"map carries retired locales: {stale}"


def test_english_is_marked_never_lifted(amap: dict) -> None:
    """We ship British spellings; Apple ships American ones.

    ``en`` resolves (so the corpus is fully classified) but must stay flagged,
    or a future sweep will happily "correct" our colour to color.
    """
    assert "en" in amap["never_lift"]


def test_the_known_decoys_were_rejected_on_coverage(amap: dict) -> None:
    """The three traps must be visibly rejected, with the evidence recorded.

    This is the regression that matters.  Each of these is a real Apple code
    holding a near-empty table, so any resolver that asks "does it exist?"
    instead of "does it carry the corpus?" picks the decoy and every subsequent
    lookup returns nothing -- which reads as a completed audit.
    """
    for ours, decoy, correct in (
        ("nb", "nb", "no"),
        ("zh-Hant", "zh-Hant", "zh_TW"),
        ("pt-PT", "pt-PT", "pt_PT"),
    ):
        ev = amap["evidence"][ours]
        assert ev["apple"] == correct, f"{ours} must resolve to {correct}, got {ev['apple']}"
        rejected = {r["code"]: r for r in ev["rejected"]}
        assert decoy in rejected, (
            f"{ours}: {decoy!r} exists as an Apple code and must be tried and "
            "rejected, so the evidence records why it is not the answer"
        )
        assert rejected[decoy]["share"] < amap["coverage_floor"]


def test_pt_br_does_not_resolve_to_bare_pt(amap: dict) -> None:
    """The original defect, pinned.

    Bare ``pt`` is Brazilian Portuguese in Apple's legacy spelling -- measured
    from content, not assumed: across its 454 tables it says ``arquivo`` 926
    times and ``ficheiro`` never, ``usuario`` 143 times and ``utilizador``
    never, ``tela`` 343 times and ``ecra`` never.  So it is the right language
    in the wrong, minority table, and because ``pt`` and ``pt_BR`` never
    co-occur in one file, a table carrying ``pt_BR`` yields nothing under
    ``pt``.  Right language, total miss.
    """
    assert amap["map"]["pt-BR"] == "pt_BR"
    assert amap["map"]["pt-PT"] == "pt_PT"


@needs_macos
def test_checked_in_map_still_matches_the_corpus() -> None:
    """The map is derived; prove it still agrees with the machine it came from."""
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--check"],
        capture_output=True,
        text=True,
        cwd=REPO,
    )
    assert r.returncode == 0, f"{r.stdout}\n{r.stderr}"
