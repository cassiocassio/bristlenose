"""One CLDR plural rule, two implementations, one committed table.

`I18n.swift`'s `pluralCategory` came first and serves the Mac menus; this
module's Python twin was transcribed from it on 22 Sep 2026 so the Miro board —
rendered server-side, in whatever language the researcher works in — could pick
`2 cytaty` over `5 cytatów`. A transcription is exactly the kind of thing that
is right in the cases you check and wrong in the ones you don't, so neither side
owns the answer: `tests/fixtures/cldr-plural-contract.json` does, and
`PluralCategoryContractTests.swift` asserts the same file.

The counts in the fixture are chosen, not sampled. Polish and Russian agree on
2–4 and disagree at 21 (`many` vs `one`); Czech's `many` is decimals-only so it
must never appear for an integer; French puts 0 with 1. A range of 1–10 would
pass against a rule that is wrong everywhere it matters.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bristlenose.i18n import SUPPORTED_LOCALES, plural_category

_FIXTURE = Path(__file__).parent / "fixtures" / "cldr-plural-contract.json"
_CONTRACT = json.loads(_FIXTURE.read_text(encoding="utf-8"))
_COUNTS: list[int] = _CONTRACT["counts"]


@pytest.mark.parametrize("locale", sorted(_CONTRACT["categories"]))
def test_python_matches_the_contract(locale: str) -> None:
    expected = _CONTRACT["categories"][locale]
    actual = [plural_category(n, locale) for n in _COUNTS]
    assert actual == expected, (
        f"{locale}: "
        + ", ".join(
            f"{n} → {a} (contract says {e})"
            for n, a, e in zip(_COUNTS, actual, expected)
            if a != e
        )
    )


def test_every_supported_locale_is_in_the_contract() -> None:
    """A new language must state its plural shape, not inherit one silently."""
    missing = sorted(set(SUPPORTED_LOCALES) - set(_CONTRACT["categories"]))
    assert not missing, (
        f"{missing} are in SUPPORTED_LOCALES but absent from the plural contract. "
        f"Add a row (and mirror it in the Swift suite) — a locale that falls "
        f"through to the one/other default should say so on purpose."
    )


def test_czech_never_returns_many_for_an_integer() -> None:
    """The cs/pl divergence, pinned on its own because copying is the failure.

    `many` is Czech's *decimals-only* category. `I18n.swift` carries the warning
    in a comment; this is the version that fails.
    """
    assert "many" not in {plural_category(n, "cs") for n in range(0, 200)}
    assert "many" in {plural_category(n, "pl") for n in range(0, 200)}


def test_the_teens_exception_is_real() -> None:
    """21 is `one` in ru/uk and `many` in pl — the single most-copied mistake."""
    assert plural_category(21, "ru") == "one"
    assert plural_category(21, "uk") == "one"
    assert plural_category(21, "pl") == "many"
    # …and 11 is not `one` anywhere in the family, which is what the mod-100
    # guard is for. Without it, "11 цитата" — the shape a naive mod-10 gives.
    assert plural_category(11, "ru") == "many"
