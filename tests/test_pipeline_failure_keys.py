"""Pipeline failure sentences: a key per category, a sentence per key.

`PipelineRunner.humanSummary` returned an English sentence, built where the
failure was *classified* — a `String` on a type that models a thing rather than
a screen, which is the authoring shape every one of the 21 Sep 2026 Swift audit's
gaps had (`desktop/CLAUDE.md` §"A user-facing string needs a key"). Sixteen
sentences reached the diagnostic popover in English in all 21 locales while the
chrome around them translated correctly.

It is also failure class 6 in `docs/i18n-defects.md` — *resolved once at
construction*. Even translated in place it would have been wrong: the sentence is
fixed when the run exits, so switching language leaves the old one on screen.
The category now travels and the view resolves it, as `Cause.reason` and the
SPA's `failure_kind` already do.

Three things are pinned here, and the first two are the ones no other gate can
see:

* **every category resolves** — a new `PipelineFailureCategory` cannot ship
  rendering a raw key, in any locale;
* **the Swift English equals `en`** — `PipelineRunner.englishFailureSentences`
  is deliberately a second copy (the log and the "Copy error details" payload
  stay English by decision), and a reworded sentence landing in only one of them
  is failure class 3 with nothing to report it;
* **`{{provider}}` appears exactly where `namesProvider` says** — a `Generic`
  sibling that interpolates a provider renders `{{provider}}` verbatim on
  screen, and a naming key that *doesn't* silently drops the one fact that makes
  the summary actionable.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_LOCALES = _ROOT / "bristlenose" / "locales"
_APP = _ROOT / "desktop" / "Bristlenose" / "Bristlenose"
_RUNNER = _APP / "PipelineRunner.swift"
_MESSAGE = _APP / "FailureMessage.swift"
_VALIDATOR = _APP / "LLMValidator.swift"
_SERVE = _APP / "ServeManager.swift"


def _swift() -> str:
    return _RUNNER.read_text(encoding="utf-8")


def _leaves() -> dict[str, str]:
    """`PipelineFailureCategory` case → its locale leaf, read from `localeLeaf`."""
    body = re.search(r"var localeLeaf: String \{(.*?)\n    \}", _swift(), re.DOTALL)
    assert body, "localeLeaf not found — did it move or get renamed?"
    pairs = re.findall(r'case \.(\w+): leaf = "(\w+)"', body.group(1))
    assert pairs, "localeLeaf has no arms"
    return dict(pairs)


def _names_provider() -> set[str]:
    """The cases `namesProvider` returns true for."""
    body = re.search(r"var namesProvider: Bool \{(.*?)\n    \}", _swift(), re.DOTALL)
    assert body, "namesProvider not found"
    true_arm = body.group(1).split("return true")[0]
    return set(re.findall(r"\.(\w+)", true_arm))


def _swift_english() -> dict[str, str]:
    """`englishSentences`, parsed as JSON. Lives on `FailureMessage`, which is
    nonisolated — `EventLogReader` builds one off the main actor."""
    body = re.search(
        r"static let englishSentences: \[String: String\] = \[(.*?)\n    \]",
        _MESSAGE.read_text(encoding="utf-8"),
        re.DOTALL,
    )
    assert body, "englishSentences not found"
    return json.loads("{" + body.group(1).rstrip().rstrip(",") + "}")


#: Keys with no `PipelineFailureCategory`, because they describe a *moment* in
#: the run rather than a classified cause. Both are reached before any cause
#: exists to classify: `stranded` when the process died without writing a
#: terminus, `launchFailed` when the spawn itself threw. `launchFailed` carries
#: `{{reason}}` — Foundation's `localizedDescription`, which macOS has already
#: translated, so it passes through rather than being re-described.
_MOMENT_KEYS = {"stranded", "launchFailed"}


def _expected_keys() -> set[str]:
    leaves = _leaves()
    naming = _names_provider()
    keys = set(leaves.values())
    keys |= {leaves[case] + "Generic" for case in naming}
    return keys | _MOMENT_KEYS


def _full_locales() -> list[str]:
    # zh-Hant-HK is a thin override fork inheriting zh-Hant — absence is correct.
    return sorted(
        d.name
        for d in _LOCALES.iterdir()
        if d.is_dir() and (d / "desktop.json").is_file() and d.name != "zh-Hant-HK"
    )


def _block(locale: str) -> dict[str, str]:
    data = json.loads((_LOCALES / locale / "desktop.json").read_text(encoding="utf-8"))
    return data.get("pipeline", {}).get("failure", {})


def test_every_category_has_a_leaf() -> None:
    """`localeLeaf` is a `switch`, so this is really a guard on the parse."""
    cases = set(re.findall(r"^    case (\w+)", _swift(), re.M))
    # The enum's own cases, as declared before the first `var`.
    declared = set(
        re.findall(r"^    case (\w+)", _swift().split("var localeLeaf")[0], re.M)
    )
    assert declared <= set(_leaves()), (
        f"{sorted(declared - set(_leaves()))} have no localeLeaf arm"
    )
    assert cases  # the regex found something at all


@pytest.mark.parametrize("locale", _full_locales())
def test_every_key_resolves(locale: str) -> None:
    block = _block(locale)
    missing = sorted(_expected_keys() - set(block))
    assert not missing, (
        f"{locale}: {missing} absent, so a failed run's popover would render the "
        f"raw key. Seed the key in every full locale in the same commit as the case."
    )
    empty = sorted(k for k in _expected_keys() if not block.get(k, "").strip())
    assert not empty, f"{locale}: {empty} are empty"


def test_no_orphan_keys() -> None:
    """A key with no category is a translation nobody will ever see."""
    orphans = sorted(set(_block("en")) - _expected_keys())
    assert not orphans, (
        f"desktop.pipeline.failure.{orphans} have no PipelineFailureCategory. Either "
        f"wire them at the classifier or delete them from all 21 locales — a key read "
        f"by nobody is invisible to check-locales.py from both directions."
    )


#: Every key prefix `FailureMessage.englishSentences` carries, and where in
#: `en/desktop.json` its block lives. A new prefix is enrolled here; until it is,
#: `test_every_swift_sentence_is_enrolled` fails rather than letting it go
#: unchecked.
_PREFIXES = {
    "desktop.pipeline.failure.": ("pipeline", "failure"),
    "desktop.llmSettings.validation.": ("llmSettings", "validation"),
    "desktop.llmSettings.revalidating": ("llmSettings", "revalidating"),
    "desktop.boot.failure.": ("boot", "failure"),
}


def _en(*path: str) -> dict:
    data = json.loads((_LOCALES / "en" / "desktop.json").read_text(encoding="utf-8"))
    for part in path:
        data = data[part]
    return data


def test_every_swift_sentence_is_enrolled() -> None:
    """A key in the table under no known prefix is a sentence nothing checks."""
    stray = sorted(
        k for k in _swift_english() if not any(k.startswith(p) for p in _PREFIXES)
    )
    assert not stray, (
        f"{stray} are in FailureMessage.englishSentences under no prefix this "
        f"test knows. Add the prefix to _PREFIXES so its block is compared."
    )


def test_swift_english_matches_the_en_locale() -> None:
    """The two copies of the English, held equal, for every enrolled prefix.

    `englishSentences` exists because the log and the copy-payload stay English
    whatever the UI shows. That makes it a second copy of `en`, and the only
    thing standing between it and silent drift is this assertion.
    """
    table = _swift_english()
    for prefix, path in _PREFIXES.items():
        block = _en(*path)
        if not isinstance(block, dict):  # a single key, not a block
            assert table[prefix] == block, f"{prefix} disagrees with en"
            continue
        mine = {k[len(prefix):]: v for k, v in table.items() if k.startswith(prefix)}
        assert mine == block, (
            f"FailureMessage.englishSentences and en/desktop.json's "
            f"{'.'.join(path)} disagree. Reword both in the same commit — the "
            f"locale gates cannot see this, they only ask whether the key is present."
        )


#: Shell commands the researcher is told to run. They are code, not prose, and a
#: translator who "helpfully" localises `ollama serve` hands someone a command
#: that does not exist. `check-locales.py` validates `{{vars}}` and cannot see
#: these.
_VERBATIM_COMMANDS = {
    "ollamaNoModels": "`ollama pull llama3.2:3b`",
    "ollamaUnreachable": "`ollama serve`",
}


@pytest.mark.parametrize("locale", _full_locales())
def test_shell_commands_survive_translation(locale: str) -> None:
    block = _en_like(locale, "llmSettings", "validation")
    for leaf, command in _VERBATIM_COMMANDS.items():
        assert command in block[leaf], (
            f"{locale}: {leaf} must carry {command} verbatim, backticks and all "
            f"— it is rendered as markdown, and a translated command is one the "
            f"researcher cannot run."
        )


def _en_like(locale: str, *path: str) -> dict:
    data = json.loads((_LOCALES / locale / "desktop.json").read_text(encoding="utf-8"))
    for part in path:
        data = data[part]
    return data


@pytest.mark.parametrize("locale", _full_locales())
def test_every_validation_key_resolves(locale: str) -> None:
    """One key per sentence `LLMValidator` can produce, in every locale.

    The validator is not a view and has no `I18n`; the pane resolves what it
    returns. `LLMSettingsView` is also the pane the language is changed from, so
    a sentence resolved at check time would sit there in the outgoing language.
    """
    produced = set(
        re.findall(r'\.keyed\(Self\.V \+ "(\w+)"', _VALIDATOR.read_text(encoding="utf-8"))
    )
    assert produced, "LLMValidator produces no keyed messages — did the prefix move?"
    block = _en_like(locale, "llmSettings", "validation")
    missing = sorted(produced - set(block))
    assert not missing, f"{locale}: {missing} absent — the pane would render raw keys"
    orphans = sorted(set(block) - produced)
    assert not orphans, (
        f"desktop.llmSettings.validation.{orphans} are produced by nobody. Wire "
        f"them at the validator or delete them from all 21 locales."
    )


@pytest.mark.parametrize("locale", _full_locales())
def test_provider_placeholder_is_where_the_swift_says(locale: str) -> None:
    leaves, naming, block = _leaves(), _names_provider(), _block(locale)
    for case, leaf in leaves.items():
        if case in naming:
            assert "{{provider}}" in block[leaf], (
                f"{locale}: {leaf} must name the provider — `namesProvider` says so, "
                f"and a summary that drops it is the shrug the classifier exists to "
                f"avoid."
            )
            assert "{{provider}}" not in block[leaf + "Generic"], (
                f"{locale}: {leaf}Generic is the no-provider sibling and would "
                f"render {{{{provider}}}} verbatim on screen."
            )
        else:
            assert "{{provider}}" not in block[leaf], (
                f"{locale}: {leaf} interpolates a provider the classifier never "
                f"supplies for this category."
            )


def test_classifier_carries_cases_not_sentences() -> None:
    """The regression guard: `.failed("…", category:)` is where this started."""
    # Anchored on `category:` so this is `PipelineState.failed` and not one of
    # the four unrelated `.failed(String)` cases in the tree — `DoctorReportView`
    # is the System Health window, which is English by decision
    # (`docs/design-i18n.md` §"Which surfaces are targets").
    pattern = re.compile(r'\.failed\(\s*(?:\n\s*)?"[^"]*",\s*\n?\s*category:')
    offenders = []
    for swift in sorted(_APP.rglob("*.swift")):
        body = swift.read_text(encoding="utf-8")
        for m in pattern.finditer(body):
            line_no = body.count("\n", 0, m.start()) + 1
            offenders.append(f"{swift.name}:{line_no}")
    assert not offenders, (
        "PipelineState.failed takes a FailureMessage, not a sentence — an English "
        "literal here renders untranslated in the popover. Use "
        "`.passthrough(…)` for someone else's words, or "
        "`PipelineRunner.failureMessage(for:provider:)` for ours:\n  "
        + "\n  ".join(offenders)
    )
@pytest.mark.parametrize("locale", _full_locales())
def test_every_category_has_a_label(locale: str) -> None:
    """The `Category:` line in the diagnostic popover, one noun phrase per case."""
    data = json.loads((_LOCALES / locale / "desktop.json").read_text(encoding="utf-8"))
    labels = data.get("pipeline", {}).get("category", {})
    leaves = set(_leaves().values())
    missing = sorted(leaves - set(labels))
    assert not missing, f"{locale}: {missing} have no desktop.pipeline.category label"
    orphans = sorted(set(labels) - leaves)
    assert not orphans, f"{locale}: desktop.pipeline.category.{orphans} have no category"
    assert data["pipeline"]["diagnostic"].get("categoryLine", "").count("{{category}}") == 1, (
        f"{locale}: diagnostic.categoryLine must interpolate {{{{category}}}} exactly once"
    )


@pytest.mark.parametrize("locale", _full_locales())
def test_a_declined_file_does_not_read_as_a_failure(locale: str) -> None:
    """`unusableInput` is "Not analysed", not "Failed" — and the distinction is the point.

    A file Bristlenose declined by format is not a run that broke, and the two
    categories sit in the same `Category:` slot. `IngestOutcomeTests` asserted
    this in English until the labels became locale values; it moved here because
    a bare Swift `I18n()` resolves to the key rather than the copy, so the
    assertion there would have been about the key name.
    """
    labels = json.loads(
        (_LOCALES / locale / "desktop.json").read_text(encoding="utf-8")
    )["pipeline"]["category"]
    assert labels["unusableInput"] != labels["unknown"], (
        f"{locale}: a declined file and a broken run read identically"
    )


@pytest.mark.parametrize("locale", _full_locales())
def test_every_boot_failure_key_resolves(locale: str) -> None:
    """The boot screen's failure line, in every locale.

    The *title* above it (`desktop.boot.failedTitle`) was localised and the line
    under it was not — a half-translated view, and the worst possible one to
    leave English: it is what a researcher reads when nothing else in the app
    works, so it is the one screen they cannot navigate around.
    """
    produced = set(
        re.findall(r'Self\.B \+ "(\w+)"', _SERVE.read_text(encoding="utf-8"))
    )
    # `SidecarResolveError.failureMessage` spells its one key in full.
    produced |= set(
        re.findall(
            r'"desktop\.boot\.failure\.(\w+)"',
            (_APP / "SidecarMode.swift").read_text(encoding="utf-8"),
        )
    )
    assert produced, "nothing produces a boot failure key — did the prefix move?"
    block = _en_like(locale, "boot", "failure")
    missing = sorted(produced - set(block))
    assert not missing, f"{locale}: {missing} absent — the boot screen would render raw keys"
    orphans = sorted(set(block) - produced)
    assert not orphans, (
        f"desktop.boot.failure.{orphans} are produced by nobody. Wire them or "
        f"delete them from all 21 locales."
    )


def test_dev_only_sidecar_errors_stay_english() -> None:
    """Three of `SidecarResolveError`'s four cases are reachable only from Xcode.

    Register row 25 called the whole conformer English-by-decision and row 29
    corrected it: `bundledSidecarMissing` is on the shipping path. This pins the
    split, so a future case is classified deliberately rather than by whichever
    arm someone copied.
    """
    body = (_APP / "SidecarMode.swift").read_text(encoding="utf-8")
    block = re.search(r"var failureMessage: FailureMessage \{(.*?)\n    \}", body, re.DOTALL)
    assert block, "SidecarResolveError.failureMessage not found"
    passthrough = re.search(r"case ([^:]+):\n\s*return \.passthrough", block.group(1))
    assert passthrough, "no passthrough arm — is every case localised now?"
    dev_cases = {c.strip().lstrip(".") for c in passthrough.group(1).split(",")}
    assert dev_cases == {"bothDevEnvVarsSet", "invalidExternalPort", "invalidSidecarPath"}, (
        f"the English-by-decision set changed to {sorted(dev_cases)}. Each case there "
        f"must be unreachable outside a #if DEBUG env-var read — check before widening it."
    )
