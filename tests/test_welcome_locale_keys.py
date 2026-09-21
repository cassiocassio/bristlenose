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


def _strip_comments(src: str) -> str:
    """Drop `//` line comments, leaving string literals alone.

    Load-bearing twice over. A naive strip eats the `//` in
    `"https://bristlenose.app/docs/"` and silently shortens the corpus. And
    without any strip the scanner reads COMMENTED-OUT call sites as live, which
    is how `WITHHELD_PREFIXES` was dead on arrival: the withheld PII slot matched
    its own commented `.init(key:)` line, so the allow-list never fired and any
    slot someone commented out was quietly exempt from the stranded-key check.
    """
    out: list[str] = []
    in_str = esc = False
    i = 0
    while i < len(src):
        c = src[i]
        if in_str:
            out.append(c)
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
            out.append(c)
        elif src[i : i + 2] == "//":
            while i < len(src) and src[i] != "\n":
                i += 1
            continue
        else:
            out.append(c)
        i += 1
    return "".join(out)


def _source() -> str:
    return _strip_comments("\n".join(p.read_text(encoding="utf-8") for p in SWIFT))


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


def _exact() -> set[str]:
    """Leaves the Swift asks for BY NAME — every one of which must exist.

    Two kinds, both whole keys rather than a slot's optional leaf: a literal
    `i18n.t("desktop.welcome.home.…")`, and a slug interpolated onto a dynamic
    prefix (`"…books." + b.line`). A miss here renders the dotted path on the
    pane, so there is nothing to be tolerant about.
    """
    src = _source()
    exact = {
        m.group(1)
        for m in re.finditer(rf'"{re.escape(PREFIX)}([\w.]+)"', src)
        if not m.group(1).endswith(".")  # the dynamic prefixes themselves
    }
    # `resolve`'s pool fallback is named at the call site, not written literally.
    exact |= set(re.findall(r'fallbackLink: "(\w+)"', src))
    exact |= set(re.findall(r'fallbackLink: String = "(\w+)"', src))
    for prefix, field in (("books", "line"), ("ingestRows", "surtitle")):
        if f'"{PREFIX}{prefix}." +' not in src:
            continue
        exact |= {f"{prefix}.{slug}" for slug in re.findall(rf'{field}: "(\w+)"', src)}
    return exact


def _slots() -> set[str]:
    """Slot keys from the pools. Each yields up to five leaves, all optional
    except `text`, which is the one every slot must carry."""
    return set(re.findall(r'\.init\(key: "([\w.]+)"', _source()))


def _requested() -> set[str]:
    """Every `welcome.home` leaf the Swift can ask for at runtime."""
    return _exact() | {f"{slot}.{leaf}" for slot in _slots() for leaf in SLOT_LEAVES}


def test_every_named_key_exists_in_english() -> None:
    """A literal key or a dynamic slug with no English entry renders its path."""
    leaves = _en_leaves()
    missing = sorted(k for k in _exact() if k not in leaves)
    assert not missing, f"named keys English does not carry: {missing}"


def test_every_slot_carries_at_least_its_text() -> None:
    """`text` is the one leaf every slot must have; title, more, link and link2
    are each legitimately absent on some slot, so this is the honest statement
    of the invariant rather than a count."""
    leaves = _en_leaves()
    dead = sorted(s for s in _slots() if f"{s}.text" not in leaves)
    assert not dead, f"call sites ask for slots English does not carry: {dead}"


def test_the_in_app_cta_keeps_its_ellipsis_in_every_locale() -> None:
    """`cta(_:)` infers intent from punctuation: a label ending in `…` opens
    something HERE and takes no arrow. The Connect-an-agent link opens Settings,
    so a translator who writes `...`, drops the ellipsis, or doubles it gets an
    arrow on an in-app control — silently, in one locale, which nothing else
    looks at."""
    for locale in sorted(p.name for p in (REPO / "bristlenose/locales").iterdir() if p.is_dir()):
        data = json.loads((REPO / f"bristlenose/locales/{locale}/desktop.json").read_text(encoding="utf-8"))
        label = data.get("welcome", {}).get("home", {}).get("tools", {}).get("agent", {}).get("link")
        if label is None:
            continue  # zh-Hant-HK inherits; absence is correct there
        assert label.endswith("\u2026"), f"{locale}: agent link must end in … — {label!r}"
        assert not label.endswith("\u2026\u2026"), f"{locale}: doubled ellipsis — {label!r}"


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


def test_every_illustration_webview_keys_its_id_on_locale() -> None:
    """A webview illustration that forgets `i18n.locale` in its `.id` goes silent.

    `IllustrationWebView.updateNSView` is empty by design — the HTML is handed
    over once at `makeNSView`, so nothing a caller changes ever reaches a webview
    that already exists. The only thing that redraws one is SwiftUI tearing it
    down, which happens when the caller's `.id` changes.

    All nine `.id`s keyed on appearance, palette and stillness and **none on
    language**, so changing the picker left every illustration in the language it
    was built in until a dark-mode toggle happened to rebuild it by accident
    (fixed 21 Sep 2026). Nothing was red, and nothing could have been: this is
    `desktop/CLAUDE.md`'s "a gate that answers confidently and wrongly" shape,
    one layer up — the contract lives in a string interpolation that no compiler
    and no locale gate can see.

    So the tenth illustration is the one this exists for.
    """
    body = (REPO / "desktop/Bristlenose/Bristlenose/WelcomeIllustrations.swift").read_text(
        encoding="utf-8"
    )
    # Each illustration is `IllustrationWebView(html: …)` followed, within its
    # modifier chain, by the `.id(...)` that owns its identity.
    call_sites = [m.start() for m in re.finditer(r"IllustrationWebView\(", body)]
    assert call_sites, "no IllustrationWebView call sites — did the type get renamed?"

    unkeyed = []
    for start in call_sites:
        # The `.id(...)` belonging to this call is the next one after it.
        ident = re.search(r'\.id\("([^"]*)"\)', body[start:])
        line_no = body.count("\n", 0, start) + 1
        if ident is None:
            unkeyed.append(f"line {line_no}: no .id at all")
        elif "i18n.locale" not in ident.group(1):
            unkeyed.append(f"line {line_no}: .id(\"{ident.group(1)}\") omits i18n.locale")

    assert not unkeyed, (
        "every IllustrationWebView's `.id` must key on `i18n.locale`, or that "
        "illustration stops following the language picker in silence — no build "
        "error, nothing red, and it self-corrects only when the user toggles "
        "dark mode:\n  " + "\n  ".join(unkeyed)
    )
