# i18n defects — the running register

**What this is:** a place to drop an i18n defect the moment it is *noticed*,
so a nose-to-tail audit has a starting list instead of a blank page.

**What it is not:** `docs/i18n-reviews/` holds per-locale **wording** briefs for
native reviewers — "is this the right word in Czech". This file holds
**engineering** defects — a missing key, a hardcoded string, the wrong
namespace, a plural that will not inflect. Different question, different reader,
different fix.

**Why a file and not a test.** Most of these *cannot* fail a test today.
`scripts/check-locales.py` reports missing keys as warnings and CI runs it
non-strict, and `tests/test_pipeline_diagnostic_locale_keys.py` checks
hardcoded allow-lists rather than en→locale parity — so adding a key to `en`
never obliges anyone to extend anything. A green suite does not mean the locales
are complete, and that is exactly the gap this register covers.

**How to use it.** Add a row when you notice something, even mid-unrelated-work.
Do not fix it there and then unless it is free — the point is to stop losing
them. Strike the row when it lands, with the commit.

| # | Where | Defect | Noticed | Status |
|---|---|---|---|---|
| 1 | `SettingsView.swift` — Accounts pane title | Hardcoded `"Accounts"`; the other five panes use `i18n.t("desktop.settingsTabs.*")` and no `settingsTabs.accounts` key exists. In every non-English build the Settings toolbar shows five translated labels and one English one. No already-translated twin to lift — needs a real translation × 21 locales. | 18 Aug 2026, `/usual-suspects` | open |
| 2 | `AccountsSettingsView.swift` — whole pane | Every user-facing string is English: state headlines, detail sentences, the disconnect alert, section footers. Deliberate for now — §10 books the cloud-import surface as realised i18n debt, and `feedback_hand_tune_copy_before_i18n` says settle the English first. The copy is not settled yet. | 18 Aug 2026 | deliberate — revisit when the copy settles |
| 3 | `CloudImportWindow.swift` and the rest of the cloud-import surface | Same: hardcoded English throughout ("Import 1 Recording", "Filter", the plan-refusal sentences). A window with this many states needs `desktop.*` keys across 21 locales **with CLDR plurals on every count-bearing string** — the counts are the expensive part, not the words. | recorded in `design-cloud-import.md` §10 | open |
| 4 | `tests/test_pipeline_diagnostic_locale_keys.py` | Looks like an en→locale parity gate and is not: it checks `_REQUIRED_PILL_CATEGORIES` / `_REQUIRED_HEADERS` / `_CHROME_COUNT_PREFIXES`, all hardcoded. A new `en` key never obliges anyone to extend them, so a gap ships silently. This is how `export.scope.*` sat in `en` alone and 19 `desktop.json` keys were missing from every non-en locale. | standing | open — by design, but the audit should decide whether `check-locales.py --strict` becomes the CI gate |
| 5 | `bristlenose/pipeline_view/cli.py` | Keeps its own English mirror of `pipeline.*` strings (`_REASON_TEXT` / `_NOTE_TEXT` / `_PROVIDER_DISPLAY`), keyed to the same locale keys. Editing one side and not the other silently diverges the CLI and React surfaces for the same host condition. Has bitten twice. | standing | open — mechanical check would close it |

---

## For the audit itself

Two things worth deciding once rather than per-string, because they keep
recurring:

**Where the line sits on English-by-decision.** Items 2 and 3 are not
oversights; they are "the copy is not settled, and asking 21 locales to carry
unsettled copy wastes reviewer goodwill". But item 1 shows the line is not
"the whole feature" — a *toolbar title* sitting among five translated siblings
reads as unfinished in a way a body sentence does not. The audit should name the
rule, not adjudicate string by string.

**Whether `check-locales.py --strict` becomes the gate.** It already does the
flattened-key diff and honours the fallback chain and CLDR suffixes. It reports
missing keys as warnings and CI runs it non-strict, so the gap ships unless
someone reads the output. Making it strict is a one-line CI change and a
decision about how much drift is tolerable between adding a key and translating
it.
