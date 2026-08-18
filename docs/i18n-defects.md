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
| 1 | ~~`SettingsView.swift` — Accounts pane title~~ | ~~Hardcoded `"Accounts"`; the other five panes use `i18n.t("desktop.settingsTabs.*")` and no `settingsTabs.accounts` key exists. In every non-English build the Settings toolbar shows five translated labels and one English one. No already-translated twin to lift — needs a real translation × 21 locales.~~ | 18 Aug 2026, `/usual-suspects` | **struck — `d0478b15`**, 18 Aug 2026 |
| 2 | ~~`AccountsSettingsView.swift` — whole pane~~ | ~~Every user-facing string is English: state headlines, detail sentences, the disconnect alert, section footers.~~ **The stated rationale was false when written** — it cited §10 booking the cloud-import surface as realised debt, but that debt had been *paid* two days earlier (`49ec8a50`, 16 Aug), so the pane was not keeping company with an English neighbour; it was the only one left. Worth keeping visible: a "deliberate" status is only as good as the fact it rests on, and nothing re-checks that fact once the row is written. | 18 Aug 2026 | **struck — `d0478b15`**, 18 Aug 2026 (20 keys × 21 locales) |
| 3 | `CloudImportWindow.swift` and the rest of the cloud-import surface | Same: hardcoded English throughout ("Import 1 Recording", "Filter", the plan-refusal sentences). A window with this many states needs `desktop.*` keys across 21 locales **with CLDR plurals on every count-bearing string** — the counts are the expensive part, not the words. | recorded in `design-cloud-import.md` §10 | open |
| 4 | `tests/test_pipeline_diagnostic_locale_keys.py` | Looks like an en→locale parity gate and is not: it checks `_REQUIRED_PILL_CATEGORIES` / `_REQUIRED_HEADERS` / `_CHROME_COUNT_PREFIXES`, all hardcoded. A new `en` key never obliges anyone to extend them, so a gap ships silently. This is how `export.scope.*` sat in `en` alone and 19 `desktop.json` keys were missing from every non-en locale. | standing | open — by design, but the audit should decide whether `check-locales.py --strict` becomes the CI gate |
| 5 | `bristlenose/pipeline_view/cli.py` | Keeps its own English mirror of `pipeline.*` strings (`_REASON_TEXT` / `_NOTE_TEXT` / `_PROVIDER_DISPLAY`), keyed to the same locale keys. Editing one side and not the other silently diverges the CLI and React surfaces for the same host condition. Has bitten twice. | standing | open — mechanical check would close it |

---

## For the audit itself

Two things worth deciding once rather than per-string, because they keep
recurring:

**Where the line sits on English-by-decision.** Items 2 and 3 were not
oversights; they were "the copy is not settled, and asking 21 locales to carry
unsettled copy wastes reviewer goodwill". But item 1 showed the line is not
"the whole feature" — a *toolbar title* sitting among five translated siblings
reads as unfinished in a way a body sentence does not. The audit should name the
rule, not adjudicate string by string.

_**Overtaken by events, 18 Aug 2026 — still needs deciding.**_ Both items were
struck by shipping the English **verbatim** into 21 locales the same day. So the
rule was not applied, and it is worth being honest about why rather than
back-filling a justification: the pane had been through review, the copy had
stopped moving, and the alternative was a sixth English label sitting among five
translated ones for an unbounded wait. That is a defensible read of *"settled"* —
but it is a read, not the rule, and `feedback_hand_tune_copy_before_i18n` still
says settle the English first. **Open question for the audit: does "settled"
mean "no longer being edited" (in which case this was correct and the rule needs
that wording), or "reviewed against the glossary and signed off" (in which case
this jumped the gun and the machine-seeded strings owe a native pass before the
copy is trusted)?** The 21 locales carry a machine seed either way, pending
native review like every other wave.

**Whether `check-locales.py --strict` becomes the gate.** It already does the
flattened-key diff and honours the fallback chain and CLDR suffixes. It reports
missing keys as warnings and CI runs it non-strict, so the gap ships unless
someone reads the output. Making it strict is a one-line CI change and a
decision about how much drift is tolerable between adding a key and translating
it.
