"""The lead-paragraph atom can only be defeated one way — pin that way.

`.bn-lead-para` gives a description two ranks by COLOUR: the leading claim in
normal ink, the remainder in `--bn-colour-muted`. The whole mechanism is one
inherited `color` on the paragraph, which makes it uniquely fragile in this
codebase's cascade:

    atoms are concatenated BEFORE organisms (`_THEME_FILES`), so an organism
    rule at equal specificity wins on source order.

`.pg-desc` and `.signal-elaboration` are both organism rules on the very
element that carries `.bn-lead-para`, and both `color: var(--bn-colour-text)`
before conversion. Restoring either declaration would defeat the tint with no
error, no warning, and no visual tell beyond "the description looks flat" —
which reads as a design opinion rather than a bug.

CSS has no error channel, so nothing else catches this. These tests are that
channel.
"""

import re

import pytest

from bristlenose.stages.s12_render.theme_assets import _THEME_FILES, load_default_css

ATOM = "atoms/lead-paragraph.css"

# Every consumer: the class it adds `.bn-lead-para` to, and the file that owns
# that class. Add a row when a new surface adopts the construct.
CONSUMERS = [
    (".pg-desc", "organisms/codebook-v2.css"),
    (".signal-elaboration", "organisms/analysis.css"),
]


def _rule_body(css: str, selector: str) -> str:
    """The declarations of the first rule whose selector is exactly `selector`."""
    m = re.search(
        r"(?:^|\})\s*" + re.escape(selector) + r"\s*\{([^}]*)\}", css, re.M
    )
    assert m, f"no rule for {selector!r} — did it get renamed?"
    return m.group(1)


def test_atom_is_registered():
    assert ATOM in _THEME_FILES, (
        f"{ATOM} is not in _THEME_FILES, so it is never concatenated and every "
        "consumer renders untreated."
    )


@pytest.mark.parametrize("_selector,organism", CONSUMERS)
def test_atom_loads_before_every_consumer(_selector, organism):
    # If an organism ever loaded first, its declarations would LOSE the tie and
    # the atom would win — which happens to be the outcome we want, but by
    # accident. Assert the order the reasoning in the atom's header assumes.
    assert _THEME_FILES.index(ATOM) < _THEME_FILES.index(organism)


@pytest.mark.parametrize("selector,_organism", CONSUMERS)
def test_consumer_does_not_restake_colour_or_weight(selector, _organism):
    body = _rule_body(load_default_css(), selector)
    for prop in ("color", "font-weight"):
        assert not re.search(rf"(?<![\w-]){prop}\s*:", body), (
            f"`{selector}` declares `{prop}`. Atoms load before organisms, so "
            f"this wins the tie on source order and silently defeats "
            f"`.bn-lead-para`. Delete the declaration — the atom owns both, via "
            f"--bn-lead-colour / --bn-lead-rest-colour and their weight twins."
        )


def test_the_atom_actually_declares_the_two_ranks():
    # A gate that only checks what ISN'T there passes just as happily on an
    # empty atom. Assert the treatment exists, and that the two ranks differ in
    # colour — the tint is the whole mechanism.
    css = load_default_css()
    para = _rule_body(css, ".bn-lead-para")
    lead = _rule_body(css, ".bn-lead-para strong")

    assert "var(--bn-lead-rest-colour)" in para
    assert "var(--bn-lead-colour)" in lead

    resolved = dict(re.findall(r"(--bn-lead-[a-z-]+)\s*:\s*([^;]+);", css))
    assert resolved["--bn-lead-colour"].strip() != resolved["--bn-lead-rest-colour"].strip(), (
        "The lead and the remainder resolve to the same colour, so the "
        "construct renders as one rank. Variant A is a COLOUR treatment — see "
        "docs/mockups/lead-sentence-playground.html."
    )
