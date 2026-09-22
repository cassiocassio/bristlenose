"""The UI language reaches the model, or generated text is in nobody's language.

Measured 22 Sep 2026 across three providers and three passes
(`experiments/generated-language/FINDINGS.md`): unsteered, a Spanish study's
section and theme names came back English 100% of the time on Claude and
inconsistently on the other two. Steered, Spanish 100% of the time on all three.
The instruction works; these tests are about it still being *there*.

Note what is deliberately not tested: whether a given provider obeys. That is a
measurement, it costs money, and it lives in the spike. A unit test that mocked
a provider into obeying would assert only that the mock was written correctly.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from bristlenose.i18n import SUPPORTED_LOCALES, get_locale, set_locale
from bristlenose.llm.output_language import LANGUAGE_NAMES, output_language_steer

STAGES = ("s08_topic_segmentation", "s10_quote_clustering", "s11_thematic_grouping")


@pytest.fixture(autouse=True)
def _restore_locale():
    """`set_locale` mutates a module global; leaking it reorders-breaks the suite."""
    before = get_locale()
    yield
    set_locale(before)


def test_english_sends_no_instruction_at_all() -> None:
    """Not "write in English" — nothing.

    This is what makes the rollout a no-op for most users: the prompt stays
    byte-identical to the one that shipped, so their `prompt_sha` cohort
    baselines stay comparable and a study in any language mixture behaves
    exactly as it did. A steer that said "write in English" would change
    behaviour for everyone to fix a problem only some people have.
    """
    assert output_language_steer("en") == ""


def test_a_non_english_locale_names_its_language_and_code() -> None:
    steer = output_language_steer("es")
    assert "Spanish (es)" in steer
    # The quotes are the participants' and are never touched — the instruction
    # has to say so, or "write everything in Spanish" reads as licence to
    # translate the evidence.
    assert "Do not translate or alter the quotes themselves." in steer


def test_every_supported_locale_can_be_named() -> None:
    """A new language with no entry here generates English in silence.

    `docs/adding-a-language.md` lists nine registration sites and this is a
    tenth. It fails loudly rather than joining them, because the failure it
    prevents is invisible: every locale gate stays green while the researcher's
    themes come back in the wrong language.
    """
    missing = sorted(set(SUPPORTED_LOCALES) - set(LANGUAGE_NAMES))
    assert not missing, f"locales with no English language name: {missing}"
    stale = sorted(set(LANGUAGE_NAMES) - set(SUPPORTED_LOCALES))
    assert not stale, f"named languages that are no longer supported: {stale}"


def test_every_supported_locale_but_english_produces_an_instruction() -> None:
    for locale in SUPPORTED_LOCALES:
        steer = output_language_steer(locale)
        if locale == "en":
            assert steer == "", "English must send nothing"
            continue
        assert LANGUAGE_NAMES[locale] in steer, f"{locale}: language not named"
        assert f"({locale})" in steer, f"{locale}: code not named"


def test_an_unknown_locale_falls_silent_rather_than_guessing() -> None:
    """The honest behaviour for "we do not know what to ask for" is to ask for
    nothing, leaving the prompt as it ships."""
    assert output_language_steer("xx") == ""
    assert output_language_steer("") == ""


def test_it_defaults_to_the_process_locale() -> None:
    """The CLI sets this from `--lang` / `BRISTLENOSE_LANG`; the desktop sets the
    same variable from its picker. Callers pass nothing and get the researcher's
    language."""
    set_locale("de")
    assert "German (de)" in output_language_steer()
    set_locale("en")
    assert output_language_steer() == ""


@pytest.mark.parametrize("stage", STAGES)
def test_the_generating_stages_append_the_steer(stage: str) -> None:
    """Read the source, not a mock.

    The three stages that write what the Quotes lens renders — section
    boundaries, section clusters, theme groups. A stage that stops appending
    this keeps working, keeps its tests green, and quietly generates in
    whatever language the model prefers, which is the exact defect this
    shipped to fix.
    """
    src = Path(f"bristlenose/stages/{stage}.py").read_text(encoding="utf-8")
    assert "system_prompt=_tmpl.system + output_language_steer()" in src, (
        f"{stage} no longer appends the output-language steer to its system "
        "prompt — generated text there is back to whatever the model picks"
    )


def test_the_fallback_bucket_is_not_english_in_a_spanish_run() -> None:
    """The one English string left in a fully-steered Spanish run was ours.

    `s11` folds thin themes into a catch-all, and both its label and its
    description were hardcoded English. It renders under every locale, steered
    or not, and the spike found it only because it showed up in the results as
    if a provider had disobeyed.
    """
    from bristlenose.stages import s11_thematic_grouping as s11

    src = inspect.getsource(s11.group_by_theme)
    # Match the ASSIGNMENT, not the word. The comment above that code explains
    # what the bucket is and names it, and a test that forbade the word would
    # forbid documenting it — the same shape as the illustration gate, which
    # had to match `.innerHTML=` rather than `innerHTML` for exactly this
    # reason. The logger line names it too, in single quotes.
    assert 'theme_label="Uncategorised"' not in src, (
        "the catch-all theme label is hardcoded English again"
    )
    assert "uncategorisedHeading" in src and "uncategorisedIntro" in src, (
        "the catch-all should use the lens's own translated keys"
    )
