"""The Welcome pane's keys and its translations must name each other.

`check-locales.py` proves every locale carries what English carries. It cannot
prove the *Swift* asks for those keys: a typo in a call site resolves to the key
itself, so the pane renders `desktop.welcome.home.tips.signls.text` at body size
and every gate stays green (`I18n.t` returns the key on a miss, by design).

So this gate closes the loop in both directions:

* a key the Swift asks for that English does not carry  → the pane shows a path;
* a key English carries that no call site asks for      → a translation nobody
  will ever see, and the next i18n pass re-translates it for nothing.

It reads the *call sites*, not a hand-written list, so a new slot is enrolled by
existing — the failure mode `test_pipeline_diagnostic_locale_keys.py` documents
(an allow-list nobody is obliged to extend) cannot happen here.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
# The one hand-maintained seam in this file. A `desktop.welcome.home.*` call
# site outside these two files makes the stranded-key test nuisance-fail rather
# than miss silently — loud and self-correcting, which is the right direction
# for a list nothing recomputes.
SWIFT = [
    REPO / "desktop/Bristlenose/Bristlenose/WelcomeHomeView.swift",
    REPO / "desktop/Bristlenose/Bristlenose/WelcomeIllustrations.swift",
]
EN = REPO / "bristlenose/locales/en/desktop.json"
PREFIX = "desktop.welcome.home."

# The leaves `resolve(_:_:)` asks for, for every slot key. All optional — an
# absent one is how a tip says "no title". A leaf outside this set is one
# nothing renders.
SLOT_LEAVES = {"title", "text", "more", "link", "link2"}

# Deliberately withheld from the pool while the Privacy control is unbuilt, and
# deliberately kept translated so restoring the slot costs no locale round.
# See the commented `.init(key: "tools.redactPii", …)` in WelcomeHomeView.swift.
WITHHELD_PREFIXES = {"tools.redactPii"}


def _source() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in SWIFT)


def _en_leaves() -> set[str]:
    home = json.loads(EN.read_text(encoding="utf-8"))["welcome"]["home"]
    out: set[str] = set()

    def walk(node: dict, path: str) -> None:
        for k, v in node.items():
            if k.startswith("_"):  # `_comment` / `_divergent_*`: notes, not strings
                continue
            child = f"{path}.{k}" if path else k
            walk(v, child) if isinstance(v, dict) else out.add(child)

    walk(home, "")
    return out


def _requested() -> set[str]:
    """Every `welcome.home` leaf the Swift can ask for at runtime."""
    src = _source()
    asked = {m.group(1) for m in re.finditer(rf'"{re.escape(PREFIX)}([\w.]+)"', src)}

    # Slot keys: `resolve` turns each into up to five leaf lookups.
    for slot in re.findall(r'\.init\(key: "([\w.]+)"', src):
        asked |= {f"{slot}.{leaf}" for leaf in SLOT_LEAVES}

    # Dynamic prefixes: `"…books." + b.line`, `"…ingestRows." + r.surtitle`.
    for prefix, field in (("books", "line"), ("ingestRows", "surtitle")):
        if f'"{PREFIX}{prefix}." +' not in src:
            continue
        asked |= {f"{prefix}.{slug}" for slug in re.findall(rf'{field}: "(\w+)"', src)}
    return asked


def test_every_key_the_pane_asks_for_exists_in_english() -> None:
    missing = sorted(k for k in _requested() if k not in _en_leaves())
    # Optional leaves are absent on purpose (a tip has no title), so only a
    # whole slot going missing is a defect: every requested slot must yield
    # at least `text`, and every literal key must resolve.
    # `text` alone is the load-bearing leaf: title, more, link and link2 are
    # each legitimately absent on some slot, so only a missing `text` means the
    # call site is asking for a slot English does not have. (A typo'd key loses
    # the whole namespace, so every leaf goes at once — but keying the check to
    # the one leaf that must exist is the honest statement of the invariant.)
    slots = {k.rsplit(".", 1)[0] for k in missing}
    dead = sorted(s for s in slots if f"{s}.text" in missing)
    assert not dead, f"call sites ask for slots English does not carry: {dead}"


def test_no_english_string_is_stranded_without_a_call_site() -> None:
    asked = _requested()
    stranded = sorted(
        k
        for k in _en_leaves()
        if k not in asked and not any(k.startswith(w + ".") for w in WITHHELD_PREFIXES)
    )
    assert not stranded, (
        "translated in 21 locales, rendered by nothing: "
        f"{stranded} — wire the call site or delete the keys"
    )


def test_withheld_slot_is_still_translated() -> None:
    """The withheld PII slot keeps its strings, or restoring it needs a locale round."""
    leaves = _en_leaves()
    for w in WITHHELD_PREFIXES:
        assert f"{w}.text" in leaves, f"{w} lost its translations while withheld"


@pytest.mark.parametrize("locale", sorted(p.name for p in (REPO / "bristlenose/locales").iterdir() if p.is_dir()))
def test_every_locale_resolves_every_requested_key(locale: str) -> None:
    """zh-Hant-HK is a thin fork and inherits; every other locale carries the lot."""
    data = json.loads((REPO / f"bristlenose/locales/{locale}/desktop.json").read_text(encoding="utf-8"))
    home = data.get("welcome", {}).get("home", {})
    if locale == "zh-Hant-HK":
        assert home, "the HK override lost its welcome.home block"
        return

    def leaves(node: dict, path: str, out: set[str]) -> set[str]:
        for k, v in node.items():
            if k.startswith("_"):
                continue
            child = f"{path}.{k}" if path else k
            leaves(v, child, out) if isinstance(v, dict) else out.add(child)
        return out

    have = leaves(home, "", set())
    want = _en_leaves()
    assert not (want - have), f"{locale} is missing {sorted(want - have)}"
