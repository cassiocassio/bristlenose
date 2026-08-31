"""The button atom's two silent failures, pinned.

`.bn-btn` is the only styled element in this codebase that shipped with no
`background`. CSS has no error channel for that: the browser paints its own
`buttonface` and the button looks *plausible* — merely drab — so nothing ever
reported it. Seven call sites were rendering a UA-painted control, including
the Install/Uninstall toggle on every codebook card.

The second failure is the fix's own trap. Giving the base a `:hover` makes
`.bn-btn:hover` (0,2,0) outrank `.bn-btn-primary` (0,1,0), so a filled variant
washes to the neutral tint on hover unless it restates its fill in its own
`:hover` rule. Also silent, also only visible while the pointer is down on it.
"""

import re

import pytest

from bristlenose.stages.s12_render.theme_assets import load_default_css

FILLED = ["bn-btn-primary", "bn-btn-danger"]


def _decls(css: str, selector: str) -> str:
    m = re.search(r"(?:^|\})\s*" + re.escape(selector) + r"\s*\{([^}]*)\}", css, re.M)
    assert m, f"no rule for {selector!r} — renamed?"
    # Comments out: they discuss the very properties these tests look for, so a
    # substring search over them reports a declaration that is only being
    # ARGUED about.
    return re.sub(r"/\*.*?\*/", "", m.group(1), flags=re.S)


def _declares(decls: str, prop: str) -> bool:
    """True when `prop` is DECLARED, not merely mentioned.

    `.bn-btn` carries `transition: background var(--bn-transition-fast)`, so the
    obvious `"background" in decls` is true for a rule that declares no
    background at all — and the first cut of this file passed its own negative
    test because of it. Match the property in declaration position: start of a
    declaration, followed by a colon.
    """
    return re.search(rf"(?:^|;)\s*{re.escape(prop)}\s*:", decls) is not None


def test_the_base_declares_a_background():
    # Without this the browser paints `buttonface`: a grey that is not ours,
    # not tokenised, and free to drift with the engine.
    assert _declares(_decls(load_default_css(), ".bn-btn"), "background"), (
        "`.bn-btn` has no background, so every bare `.bn-btn` falls through to "
        "the user agent's buttonface. Give the base a token background."
    )


@pytest.mark.parametrize("variant", FILLED)
def test_a_filled_variant_keeps_its_fill_on_hover(variant):
    css = load_default_css()
    base_hover = _decls(css, ".bn-btn:hover")
    if not _declares(base_hover, "background"):
        pytest.skip("base has no hover background; the specificity trap cannot arise")

    hover = _decls(css, f".{variant}:hover")
    assert _declares(hover, "background"), (
        f"`.{variant}:hover` does not restate its background. `.bn-btn:hover` is "
        f"(0,2,0) and `.{variant}` is only (0,1,0), so the base wins on hover and "
        f"washes the fill out to the neutral tint."
    )


@pytest.mark.parametrize("variant", FILLED)
def test_a_filled_variant_still_wins_at_rest(variant):
    # The base gained a background; a variant must still override it. Same
    # specificity (0,1,0), so this holds only while the variant is declared
    # AFTER the base in the same file — assert the order, not just the text.
    css = load_default_css()
    assert css.index(f".{variant} {{") > css.index(".bn-btn {"), (
        f"`.{variant}` is declared before `.bn-btn`; at equal specificity the "
        f"base would win and the variant would render neutral."
    )
