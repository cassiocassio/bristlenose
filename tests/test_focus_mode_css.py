"""Invariants for Focus Mode's stylesheet (docs/design-focus-mode.md).

These pin the two properties whose violation is *silent* — the mode would keep
rendering correctly and the damage would only surface in a specific interaction,
or on a specific palette, long after the change that caused it:

1. The card dissolve must never reach a selected or keyboard-focused card.
   `.bn-focused` / `.bn-selected` express themselves through `background`
   (atoms/interactive.css), the same property the dissolve sets to transparent.
   Drop the `:not()` guards and focus mode silently blinds selection — visible
   only when someone tries to multi-select, which no smoke test does.

2. Focus Mode must never touch the ground. Recede-only in every appearance is
   what lets the transform stay palette-agnostic and keeps it clear of the
   desktop's translucent detail column, where the webview paints no background
   at all and native owns the ground.

Deliberately NOT tested here: which elements recede, at what opacity, in what
order. Those are taste, tuned on a specimen, and pinning them would make every
future adjustment a two-file edit for no protection. See
docs/design-test-philosophy.md.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from bristlenose.stages.s12_render.theme_assets import _THEME_FILES, load_default_css

_CSS_PATH = (
    Path(__file__).resolve().parent.parent
    / "bristlenose"
    / "theme"
    / "templates"
    / "focus-mode.css"
)


@pytest.fixture(scope="module")
def css() -> str:
    return _CSS_PATH.read_text(encoding="utf-8")


def _strip_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)


class TestShipsInTheStylesheet:
    """A rule nobody serves is a rule that doesn't exist."""

    def test_registered_in_theme_files(self) -> None:
        assert "templates/focus-mode.css" in _THEME_FILES

    def test_loads_after_report_css(self) -> None:
        """Focus overrides values report.css sets; at equal specificity the
        later file in the concatenation wins."""
        assert _THEME_FILES.index("templates/focus-mode.css") > _THEME_FILES.index(
            "templates/report.css"
        )

    def test_rules_reach_the_served_stylesheet(self) -> None:
        assert ".bn-focus-mode" in load_default_css()


class TestSelectionSurvivesFocusMode:
    """Invariant 3 in the design doc — the silent one."""

    def test_every_background_dissolve_excludes_selection_and_focus(self, css: str) -> None:
        body = _strip_comments(css)
        # Any rule that sets `background` on a quote card inside focus mode.
        offenders = [
            selector.strip()
            for selector, block in re.findall(r"([^{}]+)\{([^{}]*)\}", body)
            if ".bn-focus-mode" in selector
            and "quote-card" in selector
            and re.search(r"\bbackground\s*:", block)
            and not (":not(.bn-selected)" in selector and ":not(.bn-focused)" in selector)
        ]
        assert not offenders, (
            "Focus Mode sets `background` on a quote card without excluding "
            "`.bn-selected` / `.bn-focused`. Selection and the keyboard cursor "
            "express themselves through the same property, so this rule wins on "
            "source order and blinds them. Offending selector(s):\n  "
            + "\n  ".join(offenders)
        )

    def test_focused_card_carries_a_cue_of_its_own(self, css: str) -> None:
        """The lesson from the first cut of this file.

        An earlier version of this suite asserted only that the dissolve
        *excluded* `.bn-focused` — which it did, and which bought nothing,
        because `.bn-focused`'s own background IS the page colour. The rule
        passed while the cursor was invisible in dark mode. Test the outcome:
        the focused card must declare something of its own, not merely be
        skipped by someone else's rule.
        """
        body = _strip_comments(css)
        cue = [
            block
            for selector, block in re.findall(r"([^{}]+)\{([^{}]*)\}", body)
            if ".bn-focus-mode" in selector
            and ".bn-focused" in selector
            and "print" not in selector
            and re.search(r"\bbox-shadow\s*:", block)
            and "none" not in block
        ]
        assert cue, (
            "Focus Mode gives the keyboard cursor no cue of its own. Excluding "
            "`.bn-focused` from the dissolve is not enough — its background is "
            "`--bn-colour-bg`, the same colour every dissolved neighbour "
            "resolves to, so the card is invisible in dark mode."
        )


class TestOneRing:
    """The ring is the cursor, and the cursor is singular.

    `.bn-focused` is singular by definition, which is the whole licence for a
    mark this loud. Selection and starred are plural — the starred left border
    was reversed for exactly this reason (it was legible, and wrong on twenty
    cards at once). If someone later reaches for the ring to mark "selected" or
    "search match", the mode dies of rings. This is the guard.
    """

    def test_ring_is_not_applied_to_plural_states(self, css: str) -> None:
        body = _strip_comments(css)
        offenders = [
            selector.strip()
            for selector, block in re.findall(r"([^{}]+)\{([^{}]*)\}", body)
            if ".bn-focus-mode" in selector
            and re.search(r"\bbox-shadow\s*:", block)
            and "none" not in block
            and ".bn-focused" not in selector
            and re.search(r"\.(bn-selected|starred)\b", selector)
        ]
        assert not offenders, (
            "A ring is applied to a state that can be true of many cards at "
            "once. Only `.bn-focused` may carry it — see § The one-ring rule "
            "in docs/design-focus-mode.md. Offending selector(s):\n  "
            + "\n  ".join(offenders)
        )


class TestGroundIsNeverTouched:
    """Recede-only: no page background, in any appearance."""

    def test_no_background_on_html_or_body(self, css: str) -> None:
        body = _strip_comments(css)
        offenders = [
            selector.strip()
            for selector, block in re.findall(r"([^{}]+)\{([^{}]*)\}", body)
            if re.search(r"(^|[\s,>])(html|body)\b", selector)
            and re.search(r"\bbackground", block)
        ]
        assert not offenders, (
            "Focus Mode sets a page background. It must be recede-only: the "
            "desktop's WKWebView paints no background (native owns the ground "
            "via the translucent detail column), so this both fights the "
            "vibrancy and reintroduces the seam problem the design deleted. "
            "Offending selector(s):\n  " + "\n  ".join(offenders)
        )

    def test_declares_no_colour_literals(self, css: str) -> None:
        """Palette-agnostic by construction — that's what makes Focus O(0) per
        palette rather than O(1)."""
        body = _strip_comments(css)
        literals = re.findall(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(", body)
        assert not literals, (
            f"Focus Mode hardcodes colour value(s): {literals}. Every value must "
            "be a formula over existing --bn-* tokens so the transform composes "
            "with every palette without per-palette overrides."
        )


class TestMotion:
    """Dusk, not a light-switch — and symmetric on the way back."""

    def test_transitions_hang_off_the_always_present_hook(self, css: str) -> None:
        """Declared under `.bn-focus-ready` (never removed), not
        `.bn-focus-mode` (toggled) — otherwise the transition vanishes with the
        class and the exit snaps instead of fading."""
        body = _strip_comments(css)
        for selector, block in re.findall(r"([^{}]+)\{([^{}]*)\}", body):
            if re.search(r"\btransition\s*:", block):
                assert ".bn-focus-ready" in selector, (
                    "Transition declared on a selector that isn't gated by "
                    f"`.bn-focus-ready`: {selector.strip()!r}. Declaring it under "
                    "the toggled class makes the fade asymmetric — it plays going "
                    "in and snaps coming out."
                )

    def test_every_transitioned_element_is_zeroed_under_reduced_motion(self, css: str) -> None:
        """Set equality, not a substring check.

        This replaced `assert "prefers-reduced-motion" in css`, which passed
        happily while `.description` — added to the transition list the same
        day — was missing from the reduce-motion block, so descriptions kept
        fading over 320ms for exactly the users who asked them not to. An
        existence check cannot fail on the thing it is nominally guarding.
        """
        body = _strip_comments(css)

        reduced = re.search(
            r"@media\s*\(\s*prefers-reduced-motion:\s*reduce\s*\)\s*\{(.*)\n\}",
            body,
            re.DOTALL,
        )
        assert reduced, "No prefers-reduced-motion block in focus-mode.css"

        def selectors_of(scope: str) -> set[str]:
            found: set[str] = set()
            for selector, block in re.findall(r"([^{}]+)\{([^{}]*)\}", scope):
                if not re.search(r"\btransition(-duration)?\s*:", block):
                    continue
                for one in selector.split(","):
                    one = one.strip()
                    if one.startswith(".bn-focus-ready"):
                        found.add(one)
            return found

        transitioned = selectors_of(body[: reduced.start()])
        zeroed = selectors_of(reduced.group(1))

        missing = transitioned - zeroed
        assert not missing, (
            "Element(s) given a Focus Mode transition but not zeroed under "
            "`prefers-reduced-motion: reduce`, so they still animate for users "
            "who asked them not to:\n  " + "\n  ".join(sorted(missing))
        )


class TestPrintRestoresTheArtefact:
    """Print is a deliverable someone else reads — Focus is a screen state."""

    def test_starred_edge_survives_printing(self, css: str) -> None:
        """The print restore must not out-specify `.quote-card.starred`.

        `.quote-card.starred` is (0,2,0); the print restore is (0,4,1), so an
        unguarded `border-left-color` there silently replaces
        --bn-colour-starred with --bn-colour-border and the starred edge
        vanishes on paper. Specificity was *asserted* in a comment rather than
        counted, and the failure only shows in printed output.
        """
        body = _strip_comments(css)
        reduced = re.search(r"@media\s*print\s*\{(.*?)\n\}", body, re.DOTALL)
        assert reduced, "No @media print block in focus-mode.css"

        offenders = [
            selector.strip()
            for selector, block in re.findall(r"([^{}]+)\{([^{}]*)\}", reduced.group(1))
            if re.search(r"\bborder-left-color\s*:", block)
            and ":not(.starred)" not in selector
        ]
        assert not offenders, (
            "A print rule sets `border-left-color` without excluding "
            "`.starred`, which out-specifies `.quote-card.starred` and strips "
            "the starred edge from the printout. Offending selector(s):\n  "
            + "\n  ".join(offenders)
        )
