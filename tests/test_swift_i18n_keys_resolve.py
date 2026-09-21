"""Every literal key the Mac app asks for must exist — or it renders raw.

`I18n.t` has no error path. A key it cannot resolve comes back as *itself*, so a
typo or a rename ships as `desktop.cloudImport.signInCancelled` sitting in the
window where a sentence should be. Nothing else catches that: Swift string
literals are invisible to the compiler, `check-locales.py` compares locales to
`en` and never asks who reads them, and the i18n CI job only ran on locale-file
changes until 21 Sep 2026 — so the commit that introduces the typo does not
even trigger it.

Deliberately literal-only. Keys built at runtime
(`"desktop.menu.quotes.\\(base)"`, `"...unreachable.\\(rawValue)"`) are skipped
because the prefix alone cannot be resolved; pinning those is the job of the
per-family tests, which derive their expectations from the Swift enum that
supplies the suffix — `test_cloud_fetch_failure_keys.py` is the worked example.

Also checks the four namespaces `I18n` actually loads. It loads `common`,
`settings`, `enums` and `desktop` — four of the nine on disk — so a Swift key
naming `server.*` or `pipeline.*` can never resolve however correct it looks.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_APP = _ROOT / "desktop" / "Bristlenose" / "Bristlenose"
_LOCALES = _ROOT / "bristlenose" / "locales"

# Mirrors `I18n.namespaces`; asserted against the Swift source below so the two
# cannot drift apart silently.
LOADED_NAMESPACES = {"common", "settings", "enums", "desktop"}

# Matches a key WHEREVER it appears, not only inside `t(...)`.
#
# The first version anchored on `t\(\s*"` and was mutation-proved by typo-ing a
# key in GoogleOAuth — and passed, because every OAuth key is stored in a `key:`
# label and resolved later by the window. A gate for "keys filed as data" that
# could only see keys passed as arguments is the same blind spot, one level up.
# Anchoring on the namespace prefix instead catches both, and the prefix is
# specific enough that a false positive would have to be a string that is a
# valid key and is not one.
# The negative lookahead drops a literal that is immediately CONCATENATED onto —
# `"desktop.cloudImport.error" + rawValue...` in CloudFetchFailure.localeKey is a
# prefix, not a key, and reporting it missing is a false positive of exactly the
# kind that gets a gate switched off. Interpolated prefixes need no such guard:
# a key containing `\(` fails the character class already.
_KEY_CALL = re.compile(
    r'"((?:common|settings|enums|desktop)(?:\.[A-Za-z0-9_]+)+)"(?!\s*\+)'
)


def _literal_keys() -> dict[str, set[str]]:
    """key -> the files that ask for it."""
    keys: dict[str, set[str]] = {}
    for swift in sorted(_APP.rglob("*.swift")):
        body = swift.read_text(encoding="utf-8")
        for m in _KEY_CALL.finditer(body):
            keys.setdefault(m.group(1), set()).add(swift.name)
    return keys


# `I18n.plural(base, count:)` resolves `<base>_one` / `_few` / `_many` / `_other`,
# so a call site naming the BASE is correct and the base itself is never a key.
# Four real ones (miro.boardReady, chrome.addingInterviews, chrome.missingSubtitle,
# chrome.newProjectSaveMessage) were reported missing before this was handled —
# checked against en before being believed, which is the only reason they were
# not written up as defects.
_PLURAL = ("_zero", "_one", "_two", "_few", "_many", "_other")


def _resolves(key: str, flat: dict[str, str]) -> bool:
    return key in flat or any(key + suffix in flat for suffix in _PLURAL)


def _flat(locale: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted((_LOCALES / locale).glob("*.json")):
        def walk(node: object, prefix: str) -> None:
            if not isinstance(node, dict):
                return
            for k, v in node.items():
                if k.startswith("_comment") or k.startswith("_divergent"):
                    continue
                if isinstance(v, dict):
                    walk(v, prefix + k + ".")
                elif isinstance(v, str):
                    out[prefix + k] = v
        walk(json.loads(path.read_text(encoding="utf-8")), path.stem + ".")
    return out


def test_loaded_namespaces_match_the_swift_source() -> None:
    src = (_APP / "I18n.swift").read_text(encoding="utf-8")
    m = re.search(r"namespaces\s*=\s*\[([^\]]*)\]", src)
    assert m, "I18n.namespaces not found — did it move?"
    declared = set(re.findall(r'"([a-z]+)"', m.group(1)))
    assert declared == LOADED_NAMESPACES, (
        f"I18n loads {sorted(declared)}, this test assumes {sorted(LOADED_NAMESPACES)}. "
        f"Update both together — the list is what decides whether a key can resolve."
    )


def test_every_literal_key_is_in_a_loaded_namespace() -> None:
    """A key naming one of the five namespaces the app does NOT load can never
    resolve, however correct it looks. Scanned separately from `_literal_keys`,
    which only matches the four that can."""
    unloaded = re.compile(r'\bt\(\s*"((?:cli|doctor|pipeline|preflight|server)(?:\.[A-Za-z0-9_]+)+)"')
    bad = []
    for swift in sorted(_APP.rglob("*.swift")):
        for m in unloaded.finditer(swift.read_text(encoding="utf-8")):
            bad.append(f"{m.group(1)} (in {swift.name})")
    bad = sorted(bad)
    assert not bad, (
        "these keys name a namespace the Mac app does not load, so `t` returns the "
        "raw key and it renders on screen:\n  " + "\n  ".join(bad)
    )


def test_every_literal_key_exists_in_english() -> None:
    en = _flat("en")
    missing = sorted(
        f"{k} (in {', '.join(sorted(files))})"
        for k, files in _literal_keys().items()
        if not _resolves(k, en)
    )
    assert not missing, (
        "these keys are asked for by the Mac app and are absent from en, so they "
        "render as the dotted key itself:\n  " + "\n  ".join(missing)
    )


@pytest.mark.parametrize(
    "locale",
    sorted(
        d.name
        for d in (_ROOT / "bristlenose" / "locales").iterdir()
        # zh-Hant-HK is a thin override fork inheriting zh-Hant — absence is correct.
        if d.is_dir() and (d / "common.json").is_file() and d.name != "zh-Hant-HK"
    ),
)
def test_every_literal_key_exists_in_every_full_locale(locale: str) -> None:
    have = _flat(locale)
    missing = sorted(k for k in _literal_keys() if not _resolves(k, have))
    assert not missing, f"{locale} is missing {len(missing)} key(s) the app asks for: {missing[:8]}"
