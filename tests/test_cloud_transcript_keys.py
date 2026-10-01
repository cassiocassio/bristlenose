"""Cloud-import transcript column: a key per state, a state per key, in every locale.

The import window's Transcript column (design-cloud-import-transcripts.md §5e)
renders each `TranscriptAvailability` and `TranscriptOutcome` through a locale
key the Swift enum names in `cellKey`, and the waiting row and the footer
checkbox read two more. The Swift suite cannot check the *values* — a bare
`I18n()` there resolves a key to itself — so, like `test_cloud_fetch_failure_keys.py`,
this pins the round trip from here, in both directions:

* every key the Swift names resolves in every full locale, so a new state cannot
  ship rendering `desktop.cloudImport…` in the cell;
* every `transcript*` key in `en` is read by some Swift source, so a key cannot
  orphan (`check-locales.py` is green for a key nobody reads);
* the footer's plural key carries exactly the CLDR forms each locale already
  uses, so cs/pl/ru/uk do not fall back to `_other` on 2–4.

The Swift that reads these keys is uncompiled at the time of writing (1 Oct 2026,
a cloud session with no Xcode); this is the half of the contract that can be
proven here.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_LOCALES = _ROOT / "bristlenose" / "locales"
_APP = _ROOT / "desktop" / "Bristlenose" / "Bristlenose"
_MODEL = _APP / "GoogleMeetModel.swift"
_PREFIX = "desktop.cloudImport."

# Read by the grid and the footer directly, not through an enum.
_DIRECT_KEYS = ("columnTranscript", "statusWaitingForTranscript")
_PLURAL_BASE = "includeWaiting"
# A plural key's forms are derived from a key every locale already carries.
_PLURAL_REFERENCE = "footerRecordings"


def _enum_block(name: str) -> str:
    body = _MODEL.read_text(encoding="utf-8")
    match = re.search(rf"enum {name}\b[^{{]*\{{(.*?)\n\}}", body, re.DOTALL)
    assert match, f"{name} not found in GoogleMeetModel.swift — did it move or get renamed?"
    return match.group(1)


def _cell_keys(enum: str) -> set[str]:
    """The `cellKey` leaves an enum names — one per case, by construction."""
    block = _enum_block(enum)
    cell = re.search(r"var cellKey: String \{(.*?)\n    \}", block, re.DOTALL)
    assert cell, f"{enum} has no cellKey"
    leaves = set(re.findall(rf'"{re.escape(_PREFIX)}(\w+)"', cell.group(1)))
    assert leaves, f"{enum}.cellKey names no keys"
    return leaves


def _swift_sources() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted(_APP.rglob("*.swift")))


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
def test_every_state_resolves(locale: str) -> None:
    block = _block(locale)
    wanted = _cell_keys("TranscriptAvailability") | _cell_keys("TranscriptOutcome") | set(_DIRECT_KEYS)
    missing = sorted(k for k in wanted if not block.get(k))
    assert not missing, (
        f"{locale}: {missing} absent, so the Transcript column would render the raw "
        f"key. Seed every full locale in the same commit as the Swift case."
    )


@pytest.mark.parametrize("locale", _full_locales())
def test_include_waiting_carries_the_locales_plural_forms(locale: str) -> None:
    """The footer's "Include {{count}} waiting on transcription", per CLDR form."""
    block = _block(locale)
    reference = _forms(block, _PLURAL_REFERENCE)
    assert reference, f"{locale}: {_PLURAL_REFERENCE} has no plural forms to derive from"
    forms = _forms(block, _PLURAL_BASE)
    assert forms == reference, (
        f"{locale}: {_PLURAL_BASE} carries {sorted(forms)}, the locale's forms are "
        f"{sorted(reference)} — a missing form falls back to _other on exactly the "
        f"counts it exists for"
    )
    for form in forms:
        assert "{{count}}" in block[f"{_PLURAL_BASE}_{form}"], (
            f"{locale}: {_PLURAL_BASE}_{form} dropped its {{{{count}}}}"
        )


def test_no_orphan_transcript_keys() -> None:
    """A key with no reader is a translation nobody will ever see."""
    sources = _swift_sources()
    present = {k for k in _block("en") if k.startswith("transcript")}
    orphans = sorted(k for k in present if f'"{_PREFIX}{k}"' not in sources)
    assert not orphans, (
        f"desktop.cloudImport.{orphans} are read by no Swift source. Wire them or "
        f"delete them from all 21 locales — check-locales.py cannot see either way."
    )


def test_every_cell_key_is_in_english() -> None:
    """The Swift ↔ locale contract from the Swift side: a case that names a key
    `en` does not carry renders its key in every language at once."""
    block = _block("en")
    wanted = _cell_keys("TranscriptAvailability") | _cell_keys("TranscriptOutcome")
    missing = sorted(k for k in wanted if k not in block)
    assert not missing, f"Swift names {missing}; en/desktop.json has no such keys"


def test_direct_keys_are_read() -> None:
    sources = _swift_sources()
    unread = [k for k in _DIRECT_KEYS if f'"{_PREFIX}{k}"' not in sources]
    assert not unread, f"{unread} are seeded but read by no Swift source"
    assert f'"{_PREFIX}{_PLURAL_BASE}"' in sources, (
        f"{_PLURAL_BASE} is pluralised by no Swift call site"
    )
