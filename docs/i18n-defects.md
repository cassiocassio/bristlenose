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
| 6 | `ProjectDiagnosticPopover.humanCategoryLabel` | English-only, and **a translation is the wrong fix**. It is the single source for two different readers: the category label rendered in the popover, and the English-only plaintext that `formatDiagnosticPlaintext` writes to the pasteboard for a bug report. Localising it in place would translate the copy payload too — which a maintainer then receives in Czech. Needs a **UI-vs-plaintext split** (a localised label for the pane, a stable English token for the payload), not 21 translations of one function. | cz i18n review Finding 13 (deferred); re-confirmed on screen 20 Aug 2026 | open |
| 7 | ~~`ProjectDiagnosticPopover` — bucket failure count~~ | ~~`Text("\(realFailures.count) failures")` — a bare Swift literal in a pane that is otherwise fully localised, and the wrong noun besides: a bucket of refusals is outcome 2, a pass.~~ Worth keeping visible next to item 6: **the same file held two instances of the same class**, one three lines from the other, and only one was on anyone's list. A register catches what someone noticed; it does not sweep. | 20 Aug 2026, from a screenshot of a real run | **struck — `04bf7a23`**, 20 Aug 2026 (`notAnalysedCount` / `failureCount` × 21) |
| 5 | `bristlenose/pipeline_view/cli.py` | Keeps its own English mirror of `pipeline.*` strings (`_REASON_TEXT` / `_NOTE_TEXT` / `_PROVIDER_DISPLAY`), keyed to the same locale keys. Editing one side and not the other silently diverges the CLI and React surfaces for the same host condition. Has bitten twice. | standing | open — mechanical check would close it |
| 8 | `en/common.json` — `codebook.foldedSummary_one` / `_other` | In `en` alone since `c0f4ec29` (26 Jul 2026) and absent from **all 21 full locales**, so the folded-codebook meta line renders English everywhere. This is 21 of the 22 warnings `check-locales.py` currently prints — i.e. almost the whole of that output is this one key. Already booked as a deferred follow-up in `design-codebook-library.md:527`, which says "19 locales": a count two language waves stale, and a good illustration of why the count belongs in the tool and not in prose. | measured 20 Aug 2026 | open |
| 9 | `it/server.json`, `zh-Hant/server.json` — `statusPage.*` | The whole 11-key block is missing from exactly these two locales; `en` and the other 19 all carry it in full. Not a partial gap and not a plural-shape artefact — checked. Whatever pass seeded the rest skipped two, and nothing since has noticed, because these are warnings and CI runs non-strict. | measured 20 Aug 2026 | open |
| 10 | `en/common.json` — `codebook.{heading,yourTags,builtIn,frameworks}`, `nav.codebook` | **A class no gate here can see.** 0.26.0 rewrote the English on five keys — Codebook→**Codebooks**, Your tags→**Manual tags**, Built-in→**Default**, Frameworks→**Library** — and left every translation in place. The 20 non-English full locales now render a faithful translation of *superseded* English: `es` still says `Tus etiquetas`, `de` `Integriert`, `ja` `ビルトイン`. `check-locales.py` is silent by construction, because the key is present on both sides and it diffs **key sets, not values**. So this is not the allow-list hole (item 4) and not the absent-`en`-key hole either: it is a third one, where English changes meaning and orphans its own translations with nothing to report. The release notes book it deliberately ("the other twenty locales keep their current words until the English settles"), which makes the wording a decision — but nothing anywhere tracks the debt, and the next reader of these files has no way to tell a stale translation from a current one. | measured 20 Aug 2026 | open — the row is the detection gap, not the words |
| 11 | `docs/platform-text-map.md` | The locale counts were trued 20 Aug (`7162eb54`); the **key** counts were not. `~150 desktop-only` describes the rows the doc happens to list, roughly a quarter of `desktop.json`'s 615; `~25 preflight` is 33; the forked table names four keys where one live `dt()` call site survives. The doc says it is regenerable from `en/desktop.json` — until it is, it is a map that undercounts the territory. (Same family, smaller: `design-sessions-popover-navigation.md:406` says `sessions.speakerPlaceholder.*` "exist only in `en` today"; they are seeded in all 21 now.) | 20 Aug 2026 | open — regeneration, not a cell edit |

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

_**A second live instance, 20 Aug 2026 — and it went the other way.**_ Item 10
is the same question asked three days later and answered in the opposite
direction: the sidebar rewording shipped to `en` **only**, with the other twenty
locales explicitly left holding the old words "until the English settles". So
the register now holds one feature that shipped unsettled English into 21
locales because a lone English label looked unfinished, and one that withheld
settled-enough English from 20 because the copy might still move. Both are
defensible; they cannot both be the rule. Whatever the audit decides, item 10
shows the decision needs a **mechanism** attached — a deliberate divergence that
nothing records is indistinguishable from an accidental one six weeks later.

**Whether `check-locales.py --strict` becomes the gate.** It already does the
flattened-key diff and honours the fallback chain and CLDR suffixes. It reports
missing keys as warnings and CI runs it non-strict, so the gap ships unless
someone reads the output. Making it strict is a one-line CI change and a
decision about how much drift is tolerable between adding a key and translating
it.

Worth knowing before that decision: **items 8 and 9 are the entire current
warning output** — 21 lines for one key plus 2 for one block. `--strict` today
would cost two fixes, not a backlog. And note it would still not catch item 10,
which is the argument for a **value**-side check (an `en` string that changes
without its translations being re-flagged) rather than only a stricter key
diff.
