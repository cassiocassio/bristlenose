"""Cloud-import fetch failures: a case per key, a key per case, no sentences.

`FetchOutcome.failed` used to carry the English sentence and the row rendered it
verbatim, so the cloud-import window was fully localised (38 `i18n.t` sites)
while the failure rows *inside* it spoke English in all 21 locales. The
translations existed the whole time — `49ec8a50` extracted "every string in the
window" on 16 Aug 2026, and these live one layer below the window, in the
adapters — so ten keys sat with **zero readers** for five weeks and no gate
could see it: `check-locales.py` is green when a key is present, whether or not
anyone reads it (failure class 5).

This pins the round trip in both directions, which is what nothing did before:

* every `CloudFetchFailure` case resolves in every full locale — a new case
  cannot ship rendering a raw key;
* every `desktop.cloudImport.error*` key has a case — a key cannot orphan again;
* no adapter reintroduces a sentence, which is how it started.

The adapters have no `I18n` and cannot get one; the discriminator travels and the
row resolves it, exactly as `Cause.reason` and the SPA's `failure_kind` do.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_LOCALES = _ROOT / "bristlenose" / "locales"
_APP = _ROOT / "desktop" / "Bristlenose" / "Bristlenose"
_SOURCE = _APP / "CloudImportSource.swift"
_PREFIX = "error"


def _cases() -> list[str]:
    body = _SOURCE.read_text(encoding="utf-8")
    block = re.search(
        r"enum CloudFetchFailure:[^{]*\{(.*?)\n\}", body, re.DOTALL
    )
    assert block, "CloudFetchFailure not found — did the enum move or get renamed?"
    cases: list[str] = []
    for line in block.group(1).splitlines():
        m = re.match(r"\s*case\s+(.+)$", line)
        if m:
            cases += [c.strip() for c in m.group(1).split(",")]
    assert cases, "CloudFetchFailure has no cases"
    return cases


def _key_for(case: str) -> str:
    return _PREFIX + case[0].upper() + case[1:]


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


@pytest.mark.parametrize("locale", _full_locales())
def test_every_case_resolves(locale: str) -> None:
    block = _block(locale)
    missing = [_key_for(c) for c in _cases() if not block.get(_key_for(c))]
    assert not missing, (
        f"{locale}: {missing} absent, so a failed cloud-import row would render the "
        f"raw key. Seed the key in every full locale in the same commit as the case."
    )


def test_no_orphan_error_keys() -> None:
    """A key with no case is a translation nobody will ever see — how this began."""
    expected = {_key_for(c) for c in _cases()}
    present = {k for k in _block("en") if k.startswith(_PREFIX)}
    orphans = sorted(present - expected)
    assert not orphans, (
        f"desktop.cloudImport.{orphans} have no CloudFetchFailure case. Either wire "
        f"them at the producing adapter or delete them from all 21 locales — a key "
        f"read by nobody is invisible to check-locales.py from both directions."
    )


def test_adapters_carry_cases_not_sentences() -> None:
    """The regression guard: `.failed(reason: "…")` is where this started."""
    pattern = re.compile(r'\.failed\(\s*(?:\n\s*)?reason:\s*"')
    offenders = []
    for swift in sorted(_APP.rglob("*.swift")):
        body = swift.read_text(encoding="utf-8")
        for m in pattern.finditer(body):
            line_no = body.count("\n", 0, m.start()) + 1
            offenders.append(f"{swift.name}:{line_no}: {m.group(0).strip()}")
    assert not offenders, (
        "FetchOutcome.failed takes a CloudFetchFailure, not a sentence — an English "
        "literal here renders untranslated in the row:\n  " + "\n  ".join(offenders)
    )
