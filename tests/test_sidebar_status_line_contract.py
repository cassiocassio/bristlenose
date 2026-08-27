"""The sidebar project status line — one contract, enforced against real data.

Written after the 26 Aug 2026 audit, which found five English sentences rendered
verbatim on the macOS sidebar row with **no locale key in any file, including
`en`**. Every gate in the repo was green throughout, and each was green for its
own reason:

* ``check-locales.py`` diffs each locale *against English*, so a key absent from
  English cannot be reported missing from anywhere (``CLAUDE.md``, the third i18n
  blind spot). Nothing was missing; the feature was simply never enrolled.
* ``test_pipeline_diagnostic_locale_keys.py`` checks hard-coded allow-lists, so a
  surface nobody added to a list is invisible to it.
* The Swift tests passed throwaway strings (``"volume gone"``, ``"offline"``,
  ``"x"``) and asserted the payload round-tripped. The payload was ``String``, so
  every string was legal and there was nothing to inspect.

So this file reads the **Swift source** for the set of states, and the **locale
files** for what each one says. A new ``UnreachableReason`` case with no keys
fails here rather than shipping an English sentence to twenty-one locales.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
LOCALES = ROOT / "bristlenose" / "locales"
DESKTOP = ROOT / "desktop" / "Bristlenose" / "Bristlenose"

# `zh-Hant-HK` is a thin *override* fork, not a full locale: it carries only
# genuine HK-idiom differences and inherits the rest via zh-Hant → en. An
# English placeholder there would pin the key and break that inheritance.
FULL_LOCALES = sorted(
    d.name
    for d in LOCALES.iterdir()
    if (d / "desktop.json").is_file() and d.name != "zh-Hant-HK"
)

# Every count-free label that can occupy the sidebar's status line. Placeholder-
# bearing strings are excluded from the length bound only (a `{{...}}` token is
# longer than what it renders); the punctuation rule still applies to them.
STATUS_LINE_KEYS = [
    "stopping",
    "stopped",
    "partialRun",
    "transcribed",
    "analysing",
    "resuming",
    "copying",
    "queuedPosition",
    "importBatch",
]

# `ProjectRow.swift`: "budget is ~22 EN chars before DE/ES/FR swell truncates".
# 24 gives two characters of headroom rather than pinning the exact figure; the
# point is to catch a *sentence* (the string this file exists for was 36), not to
# police a word choice. Non-English gets a looser ceiling because swell is real —
# the longest shipping label is 30 ("Ficheiro do projeto danificado").
EN_LABEL_MAX = 24
ANY_LABEL_MAX = 34

TERMINAL_PUNCTUATION = (".", "。", "！", "!", "?", "？")


def _locale(name: str) -> dict:
    return json.loads((LOCALES / name / "desktop.json").read_text())


def _pipeline(name: str) -> dict:
    return _locale(name).get("chrome", {}).get("pipeline", {})


def _unreachable_cases() -> list[str]:
    """The `UnreachableReason` cases, read from Swift rather than duplicated.

    A hand-maintained list here would drift silently the first time someone adds
    a case — which is the whole failure mode this file exists to prevent.
    """
    source = (DESKTOP / "UnreachableReason.swift").read_text()
    body = source.split("enum UnreachableReason", 1)[1]
    cases = re.findall(r"^\s*case\s+([a-zA-Z][a-zA-Z0-9]*)\s*$", body, re.MULTILINE)
    assert cases, "no cases parsed — did UnreachableReason.swift change shape?"
    return cases


class TestUnreachableIsLocalised:
    """The five literals. Every case, both keys, all twenty-one locales."""

    def test_every_case_has_a_sidebar_label_in_every_locale(self):
        cases = _unreachable_cases()
        missing = [
            f"{loc}:{case}"
            for loc in FULL_LOCALES
            for case in cases
            if not _pipeline(loc).get("unreachable", {}).get(case)
        ]
        assert not missing, f"unreachable labels missing: {missing}"

    def test_every_case_has_a_popover_explanation_in_every_locale(self):
        cases = _unreachable_cases()
        missing = [
            f"{loc}:{case}"
            for loc in FULL_LOCALES
            for case in cases
            if not _locale(loc)
            .get("pipeline", {})
            .get("diagnostic", {})
            .get("unreachable", {})
            .get(case)
        ]
        assert not missing, f"unreachable explanations missing: {missing}"

    def test_swift_references_no_literal_reason_string(self):
        """`PipelineRunner` must construct reasons from the enum, never a string.

        This is the original defect in its exact form: `.unreachable(reason:
        "Taking too long to respond.")`. It is cheap to reintroduce by copying a
        neighbouring line, and nothing else in the repo would notice.
        """
        source = (DESKTOP / "PipelineRunner.swift").read_text()
        literals = re.findall(r'unreachable\(reason:\s*"', source)
        assert not literals, (
            f"{len(literals)} literal-string unreachable reason(s) in "
            "PipelineRunner.swift — use an UnreachableReason case, which carries "
            "a MessageKind and a locale key"
        )


class TestStatusLineHouseStyle:
    """Shape rules the five literals broke, checked against every shipping label.

    Four of the five ended in a full stop and one did not, while *nothing* else
    in the status-line vocabulary has terminal punctuation at all — the signature
    of strings written outside a system rather than inside one.
    """

    @pytest.mark.parametrize("locale", FULL_LOCALES)
    def test_no_terminal_punctuation(self, locale: str):
        pipeline = _pipeline(locale)
        labels = {k: pipeline[k] for k in STATUS_LINE_KEYS if k in pipeline}
        labels |= {
            f"unreachable.{k}": v for k, v in pipeline.get("unreachable", {}).items()
        }
        offenders = {
            k: v
            for k, v in labels.items()
            if isinstance(v, str) and v.rstrip().endswith(TERMINAL_PUNCTUATION)
        }
        assert not offenders, (
            f"{locale}: status-line labels end in punctuation {offenders} — the "
            "row is a label, not a sentence ('Stopped', not 'Stopped.')"
        )

    @pytest.mark.parametrize("locale", FULL_LOCALES)
    def test_labels_fit_the_row(self, locale: str):
        pipeline = _pipeline(locale)
        limit = EN_LABEL_MAX if locale == "en" else ANY_LABEL_MAX
        labels = {k: pipeline[k] for k in STATUS_LINE_KEYS if k in pipeline}
        labels |= {
            f"unreachable.{k}": v for k, v in pipeline.get("unreachable", {}).items()
        }
        too_long = {
            k: (len(v), v)
            for k, v in labels.items()
            # A `{{token}}` is wider on the page than what it renders to.
            if isinstance(v, str) and "{{" not in v and len(v) > limit
        }
        assert not too_long, (
            f"{locale}: status-line labels exceed {limit} chars {too_long} — the "
            "sidebar is the attention surface; detail belongs in the popover"
        )


class TestPopoverExplanationsAreSentences:
    """The inverse rule, one surface out: the popover body *is* prose."""

    @pytest.mark.parametrize("locale", FULL_LOCALES)
    def test_explanations_end_in_a_full_stop(self, locale: str):
        block = (
            _locale(locale)
            .get("pipeline", {})
            .get("diagnostic", {})
            .get("unreachable", {})
        )
        # CJK closes a sentence with the ideographic full stop.
        offenders = {
            k: v
            for k, v in block.items()
            if not v.rstrip().endswith((".", "。"))
        }
        assert not offenders, (
            f"{locale}: popover explanations must be complete sentences {offenders}"
        )
