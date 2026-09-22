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


#: Webview builders that take no `strings:` **by decision**, with the reason.
#: Everything else must take one — an illustration whose words are literals in
#: the builder cannot follow the language picker, and nothing else would say so.
_DELIBERATELY_WORDLESS = {
    "quote": "THEIRS, and the rules' own named exception. It is not a sentence "
             "but a token array where each word is marked keep-or-trim and the "
             "spacing lives inside the tokens, so a translated sentence returns "
             "clean prose and a dead demonstration. Spanish repairs are "
             "different words in different positions (o sea, eh, bueno). This "
             "one needs a native speaker writing a native hesitation, never a "
             "seed — decided 22 Sep 2026.",
}

#: Builders whose words are still English literals awaiting the content pass.
#: Empty since 22 Sep 2026: the four that sat here were seeded into 21 locales
#: under `desktop.welcome.examples.*`, and `quote` moved to the wordless set
#: above because its exception is permanent rather than pending.
_AWAITING_CONTENT: set[str] = set()

#: Values inside a view's `strings` table that are deliberately NOT resolved
#: through `i18n`, keyed by the literal, with the reason. This is the register
#: `test_strings_tables_resolve_through_i18n` reads — a builder can take a table
#: and still pass English through it, which is how `emergentThemes` shipped ten
#: hardcoded literals while the classification gate called it done.
_DELIBERATELY_ENGLISH_VALUES = {
    "Onboarding": "GENERATED — a pipeline section name on the signal card.",
    "Search results": "GENERATED — ditto.",
    "Checkout": "GENERATED — ditto.",
    "Settings": "GENERATED — ditto.",
    "visible options": "GENERATED — an AutoCode-proposed code. The codes belong "
                       "to whichever codebook produced them, and a translated "
                       "one advertises output we do not produce.",
    "platform convention": "GENERATED — ditto.",
    "How to begin unclear": "GENERATED — a pipeline theme title. The language "
                            "the pipeline generates in is undefined "
                            "(docs/design-i18n.md §'what language sections and "
                            "themes should be generated in'), and the rules "
                            "forbid drawing the fixed version over a pipeline "
                            "that still produces the broken one.",
    "Intuitive": "GENERATED — the second theme title; same reason.",
}


def test_every_illustration_builder_is_classified() -> None:
    """A builder either takes its words from the caller, or says why it does not.

    The rules in `docs/design-i18n.md` §"Examples, mockups and illustrations"
    turn on *classifying* each fragment — ours, theirs, a framework's, another
    product's. This is the mechanical half: a new illustration cannot quietly
    hardcode English, because it will be in neither set and this fails.

    It is deliberately not "every builder takes strings". Two of them correctly
    take none, and a gate that demanded otherwise would be pressure to translate
    a depiction of somebody else's English-only software.
    """
    body = (REPO / "desktop/Bristlenose/Bristlenose/WelcomeIllustrations.swift").read_text(
        encoding="utf-8"
    )
    builders = dict(
        re.findall(r"static func (\w+)\(dark: Bool[^)]*?(strings: \[String: String\])?\)", body)
    )
    assert len(builders) >= 9, f"only found {len(builders)} builders — did the shape change?"

    takes_strings = {n for n, s in builders.items() if s}
    without = set(builders) - takes_strings

    unclassified = sorted(without - set(_DELIBERATELY_WORDLESS) - _AWAITING_CONTENT)
    assert not unclassified, (
        f"{unclassified} hardcode their words with no stated reason. Either take "
        f"a `strings:` table from the caller, or add the builder to "
        f"_DELIBERATELY_WORDLESS with the class that makes English correct."
    )

    # The other direction: a builder that gained a table should leave the
    # blocked set, so the set cannot rot into a list of things already done.
    done_but_listed = sorted(takes_strings & _AWAITING_CONTENT)
    assert not done_but_listed, (
        f"{done_but_listed} now take a strings table — remove them from "
        f"_AWAITING_CONTENT so it keeps meaning 'still to do'."
    )
    wordless_but_listed = sorted(takes_strings & set(_DELIBERATELY_WORDLESS))
    assert not wordless_but_listed, (
        f"{wordless_but_listed} are marked English-by-decision but now take "
        f"words. Read the reason in _DELIBERATELY_WORDLESS before deleting it."
    )


def _view_strings_tables() -> dict[str, list[str]]:
    """Every `let strings = [ … ]` table in an illustration view, by view name.

    Returns the raw value expressions, so the caller can ask where each one
    came from rather than what it rendered.
    """
    body = (REPO / "desktop/Bristlenose/Bristlenose/WelcomeIllustrations.swift").read_text(
        encoding="utf-8"
    )
    tables: dict[str, list[str]] = {}
    for m in re.finditer(r"^struct (\w+View): View", body, re.M):
        name = m.group(1)
        end = body.find("\nstruct ", m.end())
        chunk = body[m.end(): end if end != -1 else len(body)]
        t = re.search(r"let strings = \[(.*?)\n        \]", chunk, re.S)
        if not t:
            continue
        values = [
            v.strip()
            for v in re.findall(r'"[^"]+"\s*:\s*([^,\n]+?),?\s*\n', t.group(1) + "\n")
        ]
        tables[name] = values
    return tables


def test_strings_tables_resolve_through_i18n() -> None:
    """A builder taking a `strings:` table is not evidence its words are localised.

    The classification gate above asks *does this builder take a table?* — which
    `emergentThemes` answered yes to for months while passing ten hardcoded
    English literals through it, and `autocode` answered yes to while hardcoding
    a participant quote in its body. Plumbing is not content. This asks the
    other question: does every value in that table come from `i18n`?

    A literal is allowed only if it is registered in
    `_DELIBERATELY_ENGLISH_VALUES` with the class that makes English correct —
    the same polarity as the orphan register in
    `tests/test_locale_key_readers.py`: what is excused is listed, so anything
    unlisted is caught.
    """
    tables = _view_strings_tables()
    assert tables, "no strings tables found — did the views change shape?"

    unexplained: list[str] = []
    for view, values in sorted(tables.items()):
        for value in values:
            if "i18n.t(" in value or "i18n.plural(" in value:
                continue
            literal = re.fullmatch(r'"(.*)"', value)
            if literal and literal.group(1) in _DELIBERATELY_ENGLISH_VALUES:
                continue
            unexplained.append(f"{view}: {value}")

    assert not unexplained, (
        "these illustration strings do not resolve through i18n and are not "
        "registered as deliberately English. Either route them through a key, "
        "or add the literal to _DELIBERATELY_ENGLISH_VALUES with the class "
        "(GENERATED / FOREIGN / FRAMEWORK) that makes English correct:\n  "
        + "\n  ".join(unexplained)
    )


def test_every_seeded_example_key_has_a_reader() -> None:
    """`desktop.welcome.examples.*` is written by exactly one surface.

    Row 23's shape, scoped: ten cloud-import keys were translated into 21
    locales and read by nothing for five weeks. These keys are composed from a
    prefix in two views (`let e = "desktop.welcome.examples."`), so the
    corpus-wide orphan gate forgives the whole family by construction — it
    cannot tell which leaves a computed prefix actually reaches. This asks
    per-leaf.
    """
    import json

    en = json.loads(
        (REPO / "bristlenose/locales/en/desktop.json").read_text(encoding="utf-8")
    )
    keys = set(en["welcome"]["examples"])
    assert keys, "the examples block is empty"

    swift = (REPO / "desktop/Bristlenose/Bristlenose/WelcomeIllustrations.swift").read_text(
        encoding="utf-8"
    )
    unread = sorted(k for k in keys if k not in swift)
    assert not unread, (
        f"{unread} are translated in 21 locales and named by no call site. "
        "Delete them, or wire the illustration that was meant to read them."
    )


#: The four NATIVE illustration views, and what classifies each one's words.
#: They are outside `test_every_illustration_builder_is_classified` by
#: construction — it parses `static func …(dark: Bool…)` builders, and a
#: SwiftUI `View` struct is not one — so until 22 Sep 2026 nothing asked
#: anything of them at all, and three of the four held English content
#: including the design doc's own `anna` counter-example.
_NATIVE_ILLUSTRATIONS = {
    "SentimentFanView": "OURS — the seven sentiment names, composed onto "
                        "`enums.sentiment.` and resolved in the view.",
    "BookShelfView": "FRAMEWORK/foreign — author names never change, and a "
                     "title takes its local edition's wording only where that "
                     "edition exists. Measured 22 Sep 2026 across ten Amazon "
                     "markets: Norman has six, Braun & Clarke one (pl), "
                     "Nielsen and Lazarus none. Blocked on cover artwork, "
                     "because title and artwork move together.",
    "IngestIllustrationView": "MIXED — meeting name, person and study folder "
                              "are THEIRS and keyed; the date, separators and "
                              "extensions are structural; `Transcript` is "
                              "FOREIGN and stays English pending the per-"
                              "platform lookup.",
    "ClipsIllustrationView": "THEIRS — the clip names are the participant's "
                             "own words, keyed.",
}


def test_every_native_illustration_is_classified() -> None:
    """A native illustration view states what class its words are.

    The webview builders have had this since 21 Sep; the native half had
    nothing, which is why `interview-with-anna.m4a` shipped in 21 locales
    while `docs/design-i18n.md` used that exact string as its example of what
    not to do ("a Spanish study about Renfe, not a transliterated `anna`").
    """
    body = (REPO / "desktop/Bristlenose/Bristlenose/WelcomeIllustrations.swift").read_text(
        encoding="utf-8"
    )
    declared = set(re.findall(r"^struct (\w+IllustrationView|\w+FanView|\w+ShelfView): View", body, re.M))
    # The webview wrappers are covered by the builder gate; these are the ones
    # that draw natively and so have no `strings:` table to inspect.
    native = {n for n in declared if "WelcomeIllustrationHTML." not in
              body[body.index(f"struct {n}: View"): body.index(f"struct {n}: View") + 2500]}

    unclassified = sorted(native - set(_NATIVE_ILLUSTRATIONS))
    assert not unclassified, (
        f"{unclassified} draw natively and no entry says what class their words "
        "are. Add them to _NATIVE_ILLUSTRATIONS with the reason, or key their "
        "strings."
    )
    stale = sorted(set(_NATIVE_ILLUSTRATIONS) - declared)
    assert not stale, f"{stale} are registered but no longer exist: {stale}"


def test_native_illustration_sample_data_is_keyed() -> None:
    """The ingest and clips sample data carry keys, not finished strings.

    Both are `static let` arrays built before any environment exists, so a
    string resolved into them would freeze in whatever language the app first
    opened in — failure class 6, and invisible to every key-shaped gate. The
    array holds the key; the view resolves it.
    """
    body = (REPO / "desktop/Bristlenose/Bristlenose/WelcomeIllustrations.swift").read_text(
        encoding="utf-8"
    )
    for marker, struct in (("private static let rows: [Row]", "Row"),
                           ("private static let clips: [Clip]", "Clip")):
        start = body.index(marker)
        block = body[start: body.index("]", body.index("[", start + len(marker)))]
        assert "desktop.welcome.examples." in block, (
            f"{struct} sample data no longer carries locale keys — a literal "
            "here cannot follow the language picker."
        )
        assert "i18n.t(" not in block, (
            f"{struct} resolves a key inside a `static let`. That runs once, "
            "before any environment exists, and freezes the language."
        )


#: JS object fields inside a builder's HTML that carry *content* rather than
#: structure. A literal in one of these is a word the researcher reads.
_CONTENT_FIELDS = ("q", "code", "loc", "tag", "title", "subtitle", "name")


def test_builder_content_fields_are_keyed_or_registered() -> None:
    """Content baked into a builder's HTML, which the table gate cannot see.

    `test_strings_tables_resolve_through_i18n` inspects the `strings` table a
    *view* hands down. It is blind to a literal written straight into the
    builder's JS — and that is where six of them were hiding when this file's
    other two gates were both green: four section names on the signal card and
    two AutoCode codes. Found by reading the file rather than by any gate,
    22 Sep 2026, which is the reason this one exists.
    """
    body = (REPO / "desktop/Bristlenose/Bristlenose/WelcomeIllustrations.swift").read_text(
        encoding="utf-8"
    )
    pattern = re.compile(r'\b(' + "|".join(_CONTENT_FIELDS) + r')\s*:\s*"([^"]{2,90})"')
    unexplained = [
        f'{field}:"{value}"'
        for field, value in pattern.findall(body)
        if value not in _DELIBERATELY_ENGLISH_VALUES
        and not re.fullmatch(r"[\w.-]+", value)          # class lists, slugs, ids
    ]
    assert not unexplained, (
        "content fields in an illustration builder hold literals. Read them "
        "from the strings table (S[...]) or register them in "
        "_DELIBERATELY_ENGLISH_VALUES with the class that makes English "
        "correct:\n  " + "\n  ".join(sorted(set(unexplained)))
    )
