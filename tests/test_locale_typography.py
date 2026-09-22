"""No locale quotes a name with a straight `"`.

Register row 17b. `codebook.hideTitle` was found showing straight quotes in
eight locales while eleven others used their own typographic pair — and the
row's own note was that *"the pattern is almost certainly not confined to one
key, and finding out is a measurement job before it is an editing one"*.

Measured 22 Sep 2026: **7 keys across 9 locales**, and `en` was one of them, so
this was never only a translation problem. The source strings used straight
quotes and every translation inherited them.

WHAT THE REPAIR USED, AND WHY NOT A STYLE GUIDE

Each locale's own **dominant existing pair**, counted from its own values — de
„…“ (21 occurrences), fr «…» (24), ru «…» (35), ja 「…」 (27), sv ”…” (24), and
so on. Not CLDR, and not a typography manual: `.claude/agents/i18n-review.md`
§6a records a sweep that reasoned from the JTF guide and got Japanese colons
backwards in *both* directions, against measured Apple and Microsoft corpora.
The values already in the tree came from translations that were at least partly
native-reviewed, which makes them better evidence than a rule.

WHAT IS DELIBERATELY NOT FIXED

`nl` — its values are split 13 ”…” against 11 “…”, so there is no dominant form
to repair *to*. That is a question for a Dutch reviewer, not a sweep, and it is
filed as one. Picking a side here would be inventing an answer and then pinning
it with a test, which is worse than the inconsistency.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LOCALES = REPO / "bristlenose" / "locales"

#: Values that may still carry a straight `"`, with the reason. This register
#: may shrink and may not grow without one: the polarity is deliberate, so a
#: NEW straight quote fails rather than joining a list nobody rereads.
_PENDING_REVIEW = {
    "nl": "Dutch has no dominant pair in its own values — 13 ”…” against 11 “…”. "
          "Filed for a native reviewer (row 17b); picking a side here would be "
          "inventing an answer and then pinning it with a test.",
}


def _values(locale_dir: Path):
    for f in sorted(locale_dir.glob("*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))

        def walk(node, path=""):
            for k, v in node.items():
                if k.startswith("_"):
                    continue
                p = f"{path}.{k}" if path else k
                if isinstance(v, dict):
                    yield from walk(v, p)
                elif isinstance(v, str):
                    yield f"{f.stem}.{p}", v

        yield from walk(data)


def test_no_locale_quotes_a_name_with_a_straight_double_quote() -> None:
    """A straight `"` beside eleven locales using their own pair is a defect.

    It renders as a typewriter mark in a sentence the researcher reads, next to
    a dialog title that got it right in the next language along.
    """
    offenders: list[str] = []
    for d in sorted(p for p in LOCALES.iterdir() if p.is_dir()):
        if d.name in _PENDING_REVIEW:
            continue
        for key, value in _values(d):
            if '"' in value:
                offenders.append(f"{d.name}/{key}: {value[:60]}")

    assert not offenders, (
        "straight double-quotes in locale values. Use that locale's own pair — "
        "count its existing values rather than reaching for a style guide "
        "(see this file's docstring, and i18n-review §6a):\n  "
        + "\n  ".join(offenders)
    )


def test_the_pending_register_has_not_gone_stale() -> None:
    """A locale excused here must still need excusing.

    The register's whole value is that it shrinks. An entry for a locale that
    has since been repaired is a note claiming work is outstanding when it is
    done — the same disease as a register row left open after its fix landed.
    """
    fixed = []
    for name in _PENDING_REVIEW:
        d = LOCALES / name
        if not d.exists():
            continue
        if not any('"' in v for _, v in _values(d)):
            fixed.append(name)
    assert not fixed, (
        f"{fixed} carry no straight quotes any more — remove them from "
        "_PENDING_REVIEW so it keeps meaning 'still to decide'."
    )
