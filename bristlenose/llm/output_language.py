"""What language the pipeline's *generated* text comes back in.

Section names, theme titles and their subtitles are written by the model, and
until 22 Sep 2026 nothing steered the language they came back in. Measured
across three providers and three passes (`experiments/generated-language/`),
the answer was "undefined, leaning English": Claude produced English over
Spanish quotes on every pass of every corpus, while ChatGPT and Gemini drifted
into Spanish on one corpus and not others. A Spanish researcher got English
theme titles sitting over Spanish quotes, inconsistently.

**V1, decided 22 Sep 2026: one language, the UI language.** A study whose
sessions are in different languages is forced into the one the researcher is
working in. A section the participant saw as *Configuració* on a Catalan site
may come back as *Ajustes*; that cost is accepted, and it was measured rather
than assumed — see `experiments/generated-language/FINDINGS.md` §3.

`docs/design-i18n.md` §"PARKED: what language should sections and themes be
generated in" holds the longer argument, including the V2 candidate (the
language of the conversation, per session). **This module is agnostic between
them.** It turns a locale into an instruction; where the locale came from is
the caller's business, and a per-session answer would use the same mechanism
with a different source.

Two properties worth keeping if this is ever rewritten:

**English is the empty string, not "write in English".** An English UI sends
no instruction at all, so the prompt is byte-identical to the one that shipped
before this existed. That makes the rollout a no-op for most users, keeps the
`prompt_sha` cohort baselines comparable for them, and means a study in any
language mixture behaves exactly as it did while the UI is English.

**The instruction lives at the call site, not in the prompt file.** Prompt
bodies carry a `sha` that telemetry and cohort baselines key on, so steering by
editing `bristlenose/llm/prompts/*.md` would churn `cohort-baselines.json` for
every run in every language. `docs/design-i18n.md` names the call-site
instruction as the cheaper seam; this is it.
"""

from __future__ import annotations

from bristlenose.i18n import SUPPORTED_LOCALES, get_locale

#: Locale code → the language's name **in English**, because the prompt around
#: it is English and a model reads `Write ... in Japanese` more reliably than
#: `Write ... in 日本語`. Must cover `SUPPORTED_LOCALES` exactly:
#: `tests/test_output_language.py` fails on a locale with no name here, which is
#: the gate that stops a newly-added language silently generating English while
#: every locale check stays green.
LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "es": "Spanish",
    "ca": "Catalan",
    "ja": "Japanese",
    "fr": "French",
    "de": "German",
    "ko": "Korean",
    "cs": "Czech",
    "it": "Italian",
    "pl": "Polish",
    "ru": "Russian",
    "uk": "Ukrainian",
    "da": "Danish",
    "sv": "Swedish",
    "nb": "Norwegian Bokmål",
    "tr": "Turkish",
    "nl": "Dutch",
    "fi": "Finnish",
    "pt-BR": "Brazilian Portuguese",
    "pt-PT": "European Portuguese",
    "zh-Hant": "Traditional Chinese",
    # The thin override fork inherits zh-Hant's UI strings, but it is a real
    # choice a researcher can make and its generated text should read as Hong
    # Kong Chinese rather than Taiwan Chinese.
    "zh-Hant-HK": "Traditional Chinese as written in Hong Kong",
}

#: The measured sentence. **Do not reword it casually** — the 100% compliance
#: figure in FINDINGS.md is a measurement of these exact words, and a rewrite is
#: an unmeasured prompt. The last clause is the weakest part and is kept
#: deliberately: it was ignored on the mixed corpus (every on-screen term was
#: translated anyway) but honoured on the Spanish one, where `Checkout` and
#: `Shopping Bag` survived. Unreliable and free, so it stays until something
#: better replaces it — passing the terms in as data, most likely, since asking
#: the model to recognise them demonstrably does not work.
_STEER = (
    "\n\nWrite every generated label, name, title, subtitle and description in "
    "{language} ({code}). Do not translate or alter the quotes themselves. Keep "
    "product names, brand names and on-screen UI labels as the participants "
    "said them."
)


def output_language_steer(locale: str | None = None) -> str:
    """The sentence to append to a generating stage's system prompt.

    Returns the empty string for English and for any locale with no entry in
    :data:`LANGUAGE_NAMES` — in both cases the prompt is left exactly as it
    ships, which is the honest behaviour for "we do not know what to ask for".

    Args:
        locale: A locale code. Defaults to the process locale, which the CLI
            sets from ``--lang`` / ``BRISTLENOSE_LANG`` and the desktop sets
            from the language picker via the same environment variable.
    """
    code = locale if locale is not None else get_locale()
    if code == "en" or code not in SUPPORTED_LOCALES:
        return ""
    language = LANGUAGE_NAMES.get(code)
    if language is None:
        return ""
    return _STEER.format(language=language, code=code)
