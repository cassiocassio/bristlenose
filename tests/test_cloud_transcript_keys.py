"""Cloud-import transcript column: the footer's plural key carries every CLDR form.

The import window's Transcript column (design-cloud-import-transcripts.md §5e)
renders each `TranscriptAvailability` / `TranscriptOutcome` through a locale key
the Swift enum names in `cellKey`. Two corpus-wide gates already pin that round
trip, so this module does not repeat them:

* `test_swift_i18n_keys_resolve.py` matches every `"desktop.…"` literal in the
  Swift tree — `cellKey` literals included — and fails if one is absent from
  `en` or from any full locale;
* `test_locale_key_readers.py` fails on a key nothing reads, so an orphaned
  `transcript*` key is caught there.

What neither can see is the one *plural* key here: `includeWaiting`, the footer's
"Include {{count}} waiting on transcription". `check-locales.py` diffs flattened
keys against `en`, whose forms are `_one`/`_other`, so a Czech or Polish file that
ships only those two is complete by its rules and falls back to `_other` on
exactly the counts `_few`/`_many` exist for. The forms a locale needs are derived
from a sibling plural the same block already carries, not from a hand-written
table — a table would be the drift this test exists to catch.

The Swift that reads these keys is uncompiled at the time of writing (1 Oct 2026,
a cloud session with no Xcode); this is the half of the contract that can be
proven here.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_LOCALES = _ROOT / "bristlenose" / "locales"

_PLURAL_BASE = "includeWaiting"
# A plural key's forms are derived from a key every locale already carries.
_PLURAL_REFERENCE = "footerRecordings"


def _full_locales() -> list[str]:
    # zh-Hant-HK is a thin override fork inheriting zh-Hant — absence is correct.
    return sorted(
        d.name
        for d in _LOCALES.iterdir()
        if d.is_dir() and (d / "desktop.json").is_file() and d.name != "zh-Hant-HK"
    )


def _block(locale: str) -> dict[str, str]:
    data = json.loads((_LOCALES / locale / "desktop.json").read_text(encoding="utf-8"))
    return data.get("cloudImport", {})


def _forms(block: dict[str, str], base: str) -> set[str]:
    return {k[len(base) + 1:] for k in block if k.startswith(base + "_")}


@pytest.mark.parametrize("locale", _full_locales())
def test_include_waiting_carries_the_locales_plural_forms(locale: str) -> None:
    block = _block(locale)
    reference = _forms(block, _PLURAL_REFERENCE)
    assert reference, f"{locale}: {_PLURAL_REFERENCE} has no plural forms to derive from"
    forms = _forms(block, _PLURAL_BASE)
    assert forms == reference, (
        f"{locale}: {_PLURAL_BASE} carries {sorted(forms)}, the locale's forms are "
        f"{sorted(reference)} — a missing form falls back to _other on exactly the "
        f"counts it exists for"
    )
    # `check-locales.py` only requires a plural form's placeholders to stay
    # within the en group's union, so a form that *dropped* `{{count}}` passes
    # it — and a footer reading "Include waiting on transcription", no number,
    # is a real defect.
    for form in forms:
        assert "{{count}}" in block[f"{_PLURAL_BASE}_{form}"], (
            f"{locale}: {_PLURAL_BASE}_{form} dropped its {{{{count}}}}"
        )
