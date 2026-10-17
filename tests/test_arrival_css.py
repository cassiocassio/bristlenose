"""The arrival flash is driven by its tokens (docs/design-arrival-flash.md).

One cue marks the thing a link landed on: a transcript paragraph, a quote card,
a group heading, a screen's title, a Discussion asking. The owner's ask was
that the colour, decay time and easing change everywhere at once, so the
property worth pinning is that nothing animates the cue with a literal: every
target goes through `@keyframes bn-arrival` and the three `--bn-arrival-*`
tokens. Also pinned, because it fails silently: no `forwards` and no `to`
frame. A fill that ends on `transparent` strips a card of its own background
for good; a keyframe with only a `from` ends on whatever background the
element has.

Deliberately not guarded by prefers-reduced-motion: a colour fade is the
reduced form already (atoms/arrival.css says why).

Not pinned: the values. 5 s and ease-out are taste.
"""

from __future__ import annotations

import re

import pytest

from bristlenose.stages.s12_render.theme_assets import _THEME_DIR, _THEME_FILES, load_default_css


def _strip_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)


@pytest.fixture(scope="module")
def css() -> str:
    return _strip_comments(load_default_css())


def _rules(css: str) -> list[tuple[str, str]]:
    """Top-level and one-level-nested (selector, body) pairs, at-rule preludes included."""
    return [(m.group(1).strip(), m.group(2)) for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css)]


def _selectors(prelude: str) -> set[str]:
    return {" ".join(s.split()) for s in prelude.split(",") if s.strip()}


def _arrival_rules(css: str) -> list[tuple[str, str]]:
    return [(sel, body) for sel, body in _rules(css) if re.search(r"animation[^;]*\bbn-arrival\b", body)]


def test_the_keyframes_read_the_colour_token(css: str) -> None:
    m = re.search(r"@keyframes\s+bn-arrival\s*\{(.*?)\}\s*\}", css, flags=re.DOTALL)
    assert m, "no @keyframes bn-arrival in the theme"
    frames = m.group(1)
    assert "var(--bn-arrival-colour)" in frames
    # Only a `from`: the fade ends on the element's own background, whatever it is.
    assert not re.search(r"\b(to|100%)\s*\{", frames), "a `to` frame overrides the target's own background"


def test_every_arrival_animation_reads_the_timing_tokens(css: str) -> None:
    rules = _arrival_rules(css)
    assert rules, "nothing animates bn-arrival"
    for sel, body in rules:
        decl = re.search(r"animation\s*:([^;]*)", body)
        assert decl, sel
        value = decl.group(1)
        assert "var(--bn-arrival-duration)" in value, (sel, value)
        assert "var(--bn-arrival-easing)" in value, (sel, value)
        assert not re.search(r"\b\d+(\.\d+)?m?s\b", value), f"literal time in {sel}: {value}"
        assert "forwards" not in value and "both" not in value, f"a fill strips {sel} of its background"


def test_the_spa_marker_is_animated_and_beats_the_playing_glow(css: str) -> None:
    animated = set().union(*(_selectors(sel) for sel, _ in _arrival_rules(css)))
    assert ":root [data-arrived]" in animated
    # (0,2,0) ties `.bn-timecode-glow.bn-timecode-playing`, so the flash wins only by loading after
    # it; moved earlier, a paragraph the player is on would never flash.
    assert _THEME_FILES.index("atoms/arrival.css") > _THEME_FILES.index("atoms/timecode.css")


def test_the_tokens_are_defined_and_the_colour_follows_the_palette() -> None:
    tokens = _strip_comments((_THEME_DIR / "tokens.css").read_text(encoding="utf-8"))
    for name in ("--bn-arrival-colour", "--bn-arrival-duration", "--bn-arrival-easing"):
        assert re.search(rf"{name}\s*:", tokens), f"{name} not in tokens.css"
    assert re.search(r"--bn-arrival-colour\s*:\s*var\(--bn-colour-highlight\)", tokens)


def test_nothing_else_retimes_or_fills_the_cue(css: str) -> None:
    """A longhand after the shorthand, or a fill anywhere on a target, overrides the tokens unseen."""
    for sel, body in _rules(css):
        if not re.search(r"data-arrived|anchor-highlight", sel):
            continue
        assert not re.search(r"animation-[a-z-]+\s*:", body), f"an animation longhand on {sel}"
        assert len(re.findall(r"(^|;)\s*animation\s*:", body)) <= 1, f"two animation shorthands on {sel}"


def test_one_keyframes_and_one_definition_of_each_token(css: str) -> None:
    # The last @keyframes of a name wins in CSS; the tests above read the first.
    assert len(re.findall(r"@keyframes\s+bn-arrival\b", css)) == 1
    for name in ("--bn-arrival-colour", "--bn-arrival-duration", "--bn-arrival-easing"):
        assert len(re.findall(rf"{name}\s*:", css)) == 1, f"{name} is defined more than once"
