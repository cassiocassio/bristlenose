---
status: partial
last-trued: 2026-08-27
trued-against: HEAD@main (2ac83f6d) on 2026-08-27 (the glyph rule + files popover)
---

> **Trued 27 Aug 2026.** Two rows in the state table below had drifted in
> opposite directions.
>
> `.unreachable` described an *intention* — "inline sidebar glyph, greyed project
> row" — that had never shipped. It ships now, and additionally opens this
> popover: five `UnreachableReason` cases, each with a `MessageKind` and a locale
> key, the body carrying the reason and **the folder path** (which appears nowhere
> else on screen, and is usually the whole diagnosis).
>
> `.partial` / `.stopped` read `not-implemented`, which invites someone to
> implement them. They are a **decision**: a row shows a glyph when there is
> something the researcher would want to *know and might not*, and a run they
> stopped is not news. The rule, and the table of which states earn a glyph and
> which earn a door, is in `docs/design-desktop-project-status.md` §"The glyph
> rule". A second popover — `ProjectFilesPopover` — now shares this surface for
> data drift; same shell, same anchoring, different body.


> **Trued 2026-06-15 (`per-project-activity` @ `518e6d3`) — the toolbar pill was deleted.**
> The per-project pipeline pill (`PipelineActivityItem.swift`) was **removed** (commit `8ffa470`)
> and the diagnostic popover **extracted** into its own reusable view
> `ProjectDiagnosticPopover.swift` (commit `02ad258`). The per-project run *glance* moved to the
> **sidebar row** (spinner + hover-× Stop, `ProjectRowActivityIndicator.swift`); the diagnostic
> popover is now opened by **clicking the row's failure glyph** (selects row, anchors `arrowEdge:
> .trailing`) or via row context-menu / Project-menu "Show Diagnostics…". Throughout this doc, read
> any reference to **"the toolbar pill"**, **`PipelineActivityItem.swift`**, **`unifiedPopoverBody`**,
> or **`runningPopoverBody`** as the per-project surface as *superseded* — the popover taxonomy and
> MessageKind content are unchanged, only the owning view + invocation moved. The running popover
> (`runningPopoverBody`) was deleted with the pill — running state is now the sidebar spinner, no
> running popover. See `docs/design-sidebar-activity-indicators.md` for the new home.
>
> **Update 2026-06-21 — `CopyProgressPill` deleted too.** Copy progress later moved onto the project
> row (determinate ring + `"Copying · N%"` + hover-cancel; `ProjectRowActivityIndicator.swift`,
> `ProjectSubtitle.swift`), and the standalone `CopyProgressPill` was deleted (commit `4313bff`). So
> `OllamaDownloadPill` is now the **only** surviving toolbar pill; read the `CopyProgressPill` mentions
> in the tables below as the row's copy indicator. See `design-desktop-project-status.md` §4.

> **Truing status — corrected 21 Aug 2026. This said "Current" and was a false
> pass signal.** The changelog is the freshest part of this doc; the *spec
> sections beneath it were not brought forward with it*, so a reader who trusts
> the banner reads a body describing a deleted view. Concretely: the schema is
> **v6**, not v5 (`tests/fixtures/pipeline-summary-contract.json` — v6 added
> `source_file`, `cloud_fetch`, `run_completed_partial_cloud_fetch`,
> `run_completed_cached_stage`); `PipelineActivityItem.swift` **does not
> exist** and `unifiedPopoverBody` / `runningPopoverBody` have **zero call
> sites**, yet the display-kind catalogue still lists both as *shipped*; the
> failure-row spec still says rows lead with a red `xmark.circle.fill` and a
> monospaced session id, when since 19 Aug they lead with the **file name** and
> take a per-failure kind, so refusals render warning-orange; and the "there are
> no toasts left on the Mac" claim confuses the six deleted `desktop.toast.*`
> **strings** with the `ToastView` **surface**, which is live at ~8 call sites.
> Read the changelog for state and treat §§ below it as a phase behind.
>
> **One item here is a defect, not drift:** `unusable_input` completed three of
> this doc's own five checklist sites and not the other two — it is absent from
> `PipelineSummary.pillPrecedence` and from `desktop.pipeline.diagnostic.pill.*`
> (6 keys). So a run whose only failures are **refused files** collapses to
> `.unknown` and the pill reads **"Run had failures"** — exactly the
> false-severity wording the 19 Aug work fixed *inside* the popover and not on
> the pill the sidebar shows. Needs an English string settled before it can be
> seeded to 21 locales.
>
> **Historic banner text follows.** Current — schema (v5), IA, message-kind taxonomy,
> fixture contract, CLI vocabulary, Swift popover, and pass-4 cleanup all
> shipped. Python emitter shipped via `bristlenose/ui_kinds.py` (1ab06bf) and
> `pipeline-summary-events` merge (efe4064), fixture v5 contract locked.
> Swift consumer shipped on `pipeline-diagnostic-popover-swift` (May 2026,
> this branch). **Initial design choices were revised during Swift
> implementation** — see the changelog entries below. Read each section's
> body for what's currently shipped; superseded passages carry explicit
> banners. Next-iteration plans are tracked separately as founder-private
> handoff notes.

## Changelog

- _2026-08-22_ — **The reason column started speaking the reader's language.** The pane was half-translated and had been since it shipped: header, count line, bucket labels and Show Log all resolved through `i18n.t`, while the sentence that actually says *why a participant is missing from the findings* rendered English in all 21 non-en locales. Not an oversight — there was nothing to translate **from**. All eight refusals share one `category`, and the discriminator lived only in the English prose of `Cause.message`, so the pane had no key to look up. `refusals.py` had promised the opposite in a comment since Aug 2026 — *"the user-facing surfaces localise from the reason, not from this text"* — describing a field that did not exist. It does now: `Cause.reason` carries `UnusableReason` on the wire (Python `events.py`, Swift `PipelineSummary.swift`, contract fixture **v7** with `run_completed_partial_refusals`, the first scenario to pin a refusal at all — the ingest bucket had shipped uncovered by that contract). `message` stays English on purpose: the events log is a forensic record, so a run analysed while the UI was German must not read as German forever, and `formatDiagnosticPlaintext` keeps the raw English so a pasted bug report reads the same whatever the reporter's language. **Three blind spots made this invisible.** `check-locales.py` diffs each locale against English and so cannot report a key English lacks; `test_pipeline_diagnostic_locale_keys.py` checks hardcoded allow-lists; and `test_swift_contract_parity.py` compares only the *intersection* of fields, so adding `reason` to Python alone would have passed every gate in the repo. The new locale test parametrises over `UnusableReason` itself, which closes the first two for this family — a ninth reason cannot ship without 21 translations. Anchors: `events.py::Cause.reason`, `ProjectDiagnosticPopover.reasonKey` / `.localisedReason`, `IngestOutcomeTests::ReasonLocalisationTests` (21 locales × 8 reasons, plus zh-Hant-HK inheriting rather than dropping to English). Does **not** touch the adjacent open defect in the banner above — a refusal-only run still collapses to `.unknown` and the pill still reads "Run had failures". Find it: `git log -S'localisedReason' --`.
- _2026-08-22_ — **The popover envelope stopped being fixed, and this doc stopped saying it was.** Height now follows content, 360 stays nailed, 320 becomes a ceiling with a scroller only past it. Two sections here asserted the opposite and both are rewritten: the cross-surface conventions list (which also cited `PipelineActivityItem.swift` ≈ 59–63, a file deleted with the pill) and the Resizeability paragraph under Future direction — which had *already predicted* this outcome, listing "a capped height with internal scroll" as the mitigation, so the rewrite reads as that option being taken rather than a reversal. The livelock provenance is preserved in both, as history: the fixed frame was mitigating an NSPopover resize-animation livelock in the live pill's `ProgressView`, and both the pill and the `ProgressView` are gone, leaving a mitigation with nothing to defend. Reasoning, the behaviour ladder, six failure modes and the mockup: [`design-pipeline-popover-sizing.md`](design-pipeline-popover-sizing.md). Commit `5a380eab`.
- _2026-08-20_ — **What the pane actually rendered, once someone looked at it.** The 19 Aug entry below recorded three decisions; a screenshot of the first real run showed none of them had reached the rendering. (1) The name column read `sessionId` alone, so every *ingest* refusal — the case `source_file` was added for, because a failure before a session exists never gets a session id — rendered **anonymous**. Three rows saying "Not a format Bristlenose reads." and naming nothing is a count with extra steps, which is the outcome this surface exists to end. Same in `formatDiagnosticPlaintext`, where a pasted bug report showed `—`. (2) Every row was hardcoded `MessageKind.error`; refusals are **warnings**, and error red beside 42 good sessions says the run died. (3) `"\(n) failures"` was a bare Swift literal — untranslated in an otherwise localised pane, and the wrong noun. Now `notAnalysedCount` / `failureCount`, chosen by `bucketCountKey` (a pure function, so the *decision* is testable — the first version of that test asserted on the rendered string and silently checked the key name, because an unconfigured `I18n` returns raw keys). A sixth reason landed the same day: `NO_SPEECH`, for a recording that decoded and transcribed fine with nobody talking — distinct from `NO_AUDIO`, since the remedies differ. Commits `04bf7a23`, `6497711a`.
- _2026-08-19_ — **`UNUSABLE_INPUT` added; the `ingest` bucket reaches the popover; every toast deleted.** Refusals and damaged files had nowhere to go — `PipelineSummary` had buckets for transcripts / topics / quotes / themes and nothing for stages 1–2, so `StageFailure.source_file` (added Jul 2026 for exactly this) had no slot. The new bucket renders **first** and is labelled **Files**, not "Ingest": `BucketName.label` replaced `rawValue.capitalized`, which happened to be legible for four nouns it was never asked to translate. A declined format and an unreadable file share one category because they share a consequence — a participant missing from the findings — and differ only in `Cause.message`; both read as **WARNING**, never `skipped`, because a policy decision must not rank below a defect when the researcher is chasing a missing interview. The **two-mirror trap** the 15 Jul entry names bit again in a new place: `PipelineFailureCategory` and `PipelineSummary::CauseCategory` are *different case sets* and both decoded unknown values by throwing, so one unmirrored word failed the whole terminus event. Both now fall back to `.unknown`; adding cases does not prevent the next one. Separately, **all six `desktop.toast.*` messages were removed** — see the retired row in the display-kind catalogue and the new anti-pattern. Anchors: `bristlenose/refusals.py`, `events.py` `_OUTCOME_FIELDS`, `PipelineSummary.swift`, `ProjectDiagnosticPopover.humanCategoryLabel`; commits `7a09ce88`, `5598bd39`, `3acfcef0`.
- _2026-07-15_ — **`OUT_OF_CREDIT` added to the failure taxonomy; `QUOTA` narrowed to rate-limit.** Billing exhaustion is now its own non-retryable category (Anthropic serves it as a 400 + "credit balance is too low", OpenAI as a 429 `insufficient_quota`); `QUOTA` means a transient throttle worth retrying. Trued: the pill precedence chain (AUTH > **OUT_OF_CREDIT** > MISSING_BINARY > QUOTA > NETWORK > UNKNOWN), the pill-label locale list, and the failure-category enum row — which now names **both** Swift mirrors. Rewrote step 6 of the "read this before adding a new error" contract into an explicit five-site checklist plus the **two-mirror trap**: this very pass shipped a category that compiled clean while leaving `PipelineSummary::CauseCategory` unable to decode it. The old "the popover renders any registered category automatically" line was the false reassurance that let it through — removed. Classifier lives at `bristlenose/llm/failure_classifier.py`.
- _2026-06-21_ — extended the top banner to note `CopyProgressPill` was also deleted (copy progress moved onto the project row, commit `4313bff`); updated the determinate-progress + copying rows in the state-catalog tables to point at the row indicator (`ProjectRowActivityIndicator` / `ProjectSubtitle`) instead of the deleted pill. `OllamaDownloadPill` is now the only surviving toolbar pill.
- _2026-06-05_ — **Popover & status-surface state catalog + display-kind
  taxonomy added.** New "Popover & status-surface state catalog" section
  enumerates every state the desktop app can show (with real data and its
  invocation path), plus a surface-level "display-kind" taxonomy that *codifies
  the already-shipped popover/pill forms* (a sibling to the atom-level MessageKind
  taxonomy — orthogonal, they nest). Catalogue only — designs nothing new; the
  run's icons, typography, MessageKind glyphs, and diagnostic IA are settled and
  untouched. Surfaced a coverage finding: only the Ollama pill is live-invocable
  from `CommandMenu("Debug")`; the diagnostic popover is env-var + relaunch; every
  other surface is real-condition-only. A deferred appendix ("Future direction —
  in-flight progress as rolling logs") captures the QA observation (fast runs flick
  per-stage screens past unread) and the design conversation behind it, for a
  post-TF pass — design nothing yet. Small fixes from the
  final-pass review: removed unused `action.email` + `action.copied`
  locale keys (Finding 31); renamed `tooltip.completed_partial`
  wording from "Pipeline" to "Analysis" across 6 locales (Finding 44 —
  user-facing convention); fixed ja `overflow_other` ellipsis
  `"..."` → `"…"` (Finding 42); gated `nowTick` timer on popover
  visibility (Finding 32); nil-guarded overflow row rendering
  (Finding 33); annotated debug-fixture sleep heuristic (Finding 34);
  comment-locked plaintext snake_case category (Finding 36); extended
  `check-release-binary.sh` denylist with debug-harness strings
  (Finding 39); added plural-dispatch unit tests for
  `localisedOverflowText` (Finding 40). Spec doc trued against
  shipped reality; review log fully status-swept.
- _2026-05-19_ — **Swift popover shipped** on
  `pipeline-diagnostic-popover-swift`. Implementation diverged from initial
  spec in several places — all reflected in updates below. Headline changes:
  (a) Mac popover rows now use SF Symbols (`xmark.circle.fill` red /
  `exclamationmark.triangle.fill` orange) instead of Unicode — the "no SF
  Symbols inside popover rows" anti-pattern was reversed (rationale in the
  Anti-patterns section); (b) `DisclosureGroup` collapse for ≥3 failures
  removed (was a lying chevron); plain count subhead + all rows inline is
  the honest shape; (c) project-name dropped from popover header — header
  is just the status verb; (d) Email button dropped; Copy is a single
  `doc.on.doc` icon top-right; (e) toolbar pill moved from `.primaryAction`
  to `.status` placement; (f) project-name chip removed from the toolbar
  entirely; (g) `applyScanResult` extended to early-return on the new
  diagnostic states (load-bearing bug fix found mid-branch); (h) skipped
  glyph changed from `minus.circle` `.secondary` to `minus.circle.fill`
  `.cyan` (cool / dormant framing); (i) `MessageKind` Swift mirror grew
  `symbolName` (SF Symbol name) and `tint` (Color) properties; (j) two
  new `PipelineState` cases shipped (`.completedPartial(summary:)`,
  `.failedWithDiagnostic(summary:)`); (k) debug-only fixture harness
  (`BRISTLENOSE_DEBUG_DIAGNOSTIC_FIXTURE`) added with embedded showcase
  scenarios. See "Mac surface as implemented" section.
- _2026-05-07_ — **Initial draft**, established alongside the
  `pipeline-summary-events` (Python emitter, merged) and
  `pipeline-diagnostic-pill` (Swift consumer, in flight) branches.
  Single source of truth for the five-kind `MessageKind` taxonomy
  (`bristlenose/ui_kinds.py`), the popover information-architecture,
  length budgets, and the anti-patterns checklist for new error /
  status / message authors. Incorporates the reframe that the popover
  is a dev-feedback artefact (not a result viewer), the Xcode-build-log
  visual reference, and the truncation-marker contract
  (`STAGE_FAILED_MAX = 10` placeholder shape locked in fixture v4).

# Pipeline-diagnostic popover & message-kind vocabulary

The pill in the toolbar surfaces pipeline run state. When a run finishes
in a non-clean state, clicking the pill opens a small native popover
that shows what happened. This doc covers the UX rules, information
architecture, and the canonical message-kind taxonomy that every status
surface in Bristlenose (CLI, popover, toasts, sidebar glyphs) shares.

**Read this before adding a new error, status, or message that surfaces
in the popover, the pill, the sidebar glyph, or any toast.** New
messages must declare a kind from the taxonomy below — not invent their
own glyph or colour.

> **Where the failures come from:** [design-analysis-lifecycle.md](design-analysis-lifecycle.md)
> §5 catalogues the observed failure modes of analyse / re-analyse / incremental and which of
> the four outcomes each lands in. This doc stays the owner of the *taxonomy* those failures
> are rendered with.

## What the popover is for

- **Telling an alpha tester what failed and helping them tell us.** The
  primary user is someone whose run produced a partial or no result;
  the primary action is share-to-developer (Copy, Email, screengrab).
- **Visual reference: Xcode build log.** Compact tinted Unicode glyphs,
  hierarchical disclosure when warranted, system body type, monospace
  digits in the time column. Restraint over branding.

## What the popover is *not*

- **Not a result viewer.** Partial runs are not interpretable data; we
  do not link to the half-broken report from the partial popover. The
  `Open report` button is intentionally absent in both popover variants.
- **Not a progress display — today.** While a run is in flight the pill
  renders `.running` with the existing spinner-and-elapsed pattern, and the
  bulk of this doc covers terminal states (`.completedPartial`,
  `.failedWithDiagnostic`). A minimal *running* popover does exist, though
  (`runningPopoverBody` — a single replace-in-place status line); the
  catalog below names every state including the running sub-states, and the
  deferred "Future direction — in-flight progress as rolling logs" appendix
  revisits whether the in-flight surface should carry more than a status line.
- **Not a settings surface.** The only operational button is `Retry`
  (and conditionally `Change provider` on `.auth`). Everything else is
  share-affordances.

## Message-kind taxonomy (5 kinds)

The single source of truth is `bristlenose/ui_kinds.py`. Swift mirror at
`desktop/Bristlenose/Bristlenose/MessageKind.swift` — the Swift type now
carries three properties (`glyph`, `symbolName`, `tint`), not just two,
because Mac rendering uses SF Symbols while CLI / plaintext export use
the Unicode glyph. See the Anti-patterns section for the rationale.

| Kind | Unicode (CLI) | SF Symbol (macOS) | CLI colour | macOS tint | When |
|---|---|---|---|---|---|
| `success` | `✓` | `checkmark.circle` (outline) | `green` | `.green` | Step done as expected; "Saved"; "Copied"; cached step (with `(cached)` suffix) |
| `info` | `ℹ` | `info.circle` (outline) | `cyan` | `.blue` | Neutral note, no action needed: "Port in use, trying 8151"; "Ollama not running"; "Themes skipped (no quotes)" if user-meaningful |
| `warning` | `⚠` | `exclamationmark.triangle.fill` | `yellow` | `.orange` | Recoverable, partial, or soft-degrade: stage with sub-failures; "inputs changed — re-running"; partial run pill |
| `error` | `✗` | `xmark.circle.fill` | `red` | `.red` | Action did not complete; user/dev needs to do something: abandoned stage; invalid API key; failed pill |
| `skipped` | `—` | `minus.circle.fill` | `dim` | `.cyan` | Not applicable in this run: `Themes — skipped (transcribe-only)`; PII removal off. Cyan + filled deliberately conveys "cool / dormant / passed over" — earlier `.secondary` outline read as "empty placeholder" |

**Inline-weight rule:** filled symbols for states that earn the eye
(warning, error, skipped); outline for quiet states (success, info).
Filled / outline tracks inline visual weight, not interactivity —
inline glyphs are typographic markers, not buttons. State is carried
redundantly via shape (circle / triangle) and tint, so colour-blind
readers get shape disambiguation for free.

Cached → `success` with metadata suffix. `pending` / `running` are
status, not kinds (use a spinner). `fatal` → `error` (telemetry
subdivides). Don't add a sixth kind without first proving the existing
five demonstrably can't carry the case — file an issue, propose, get
agreement.

### Why these five and not three or seven

- **3 (success/warning/error) is too few** — `info` ("trying 8151") and
  `error` should not look the same in the CLI scrollback or the
  popover. `skipped` is the typography that lets the popover honestly
  represent "we didn't run this" without lying that it succeeded.
- **7+ is over-cataloguing** — `fatal`, `critical`, `degraded`, `retry`,
  `pending` etc. all collapse cleanly into one of the five with
  metadata suffixes or status indicators. More kinds means more glyph
  decisions for every message author; fewer means a fast-path through
  the decision.

### Rendering parity across surfaces

| Surface | Renders as |
|---|---|
| CLI line | `[colour]glyph[/colour] message <padding> [dim]suffix[/dim]` (rendered by `_print_stage()` in `bristlenose/pipeline.py:131–171`; legacy `_print_step` / `_print_warn_step` / `_print_error_step` / `_print_cached_step` are one-line wrappers preserved for call-site stability) |
| Popover row | `Grid { GridRow { Image(systemName: kind.symbolName).foregroundStyle(kind.tint); Text(sid).monospaced.secondary; Text(message).textSelection(.enabled) } }` — three-column layout with hanging-indent wrap on the message column. SF Symbol via `Image`, **not** Unicode `Text(glyph)` — see Anti-patterns for the rationale and the May 2026 reversal of the previous "no SF Symbols inside popover rows" rule. |
| Plaintext export (clipboard / email) | Uses the Unicode `glyph` (CLI-portable). `formatDiagnosticPlaintext` outputs `✗ s2  Whisper transcription timed out` etc. — same glyphs the CLI prints, so a copy-pasted diagnostic renders identically in a terminal or plaintext email. |
| Toast (desktop) | `ToastStore.show(_, kind:)` — leading SF Symbol counterpart `.fill` variants in body type; fade after 3s |
| Sidebar glyph | `Text(glyph).foregroundStyle(tint)` at `.imageScale(.small)` trailing the row |
| Web toast (frontend) | CSS class `.toast--{kind}` mapping to the same colour palette via design tokens |

All six surfaces consult the same `MessageKind` enum. If you add a kind,
every surface picks it up automatically — there is no per-surface
override. (The two macOS surfaces — popover row and plaintext export —
intentionally render different *forms* of the same kind: SF Symbol for
the native UI, Unicode for the cross-platform plaintext.)

## Popover & status-surface state catalog

This section **catalogues what the desktop app already shows** — every
popover / pill / sheet / alert / toast state, with its real data, its name
in the display-kind taxonomy below, and how (if at all) you can invoke it
from a debug affordance. It codifies shipped reality; it designs nothing
new. (Genuinely-new ideas live in the deferred appendix at the end.)

### Display-kinds (a second, surface-level taxonomy)

`MessageKind` (above) is **atom-level** — the glyph on a single row.
*Display-kind* is **surface-level** — the form the **whole** popover/pill
takes for the situation it's in. The two are orthogonal and they **nest**:
a surface's form is one display-kind; within a log / failure form, each row
still carries a `MessageKind`. Don't collapse the two axes.

This library **names forms that already ship** — it is not a wish-list. Each
row points at its canonical shipped exemplar. Treat it as *forms + a
non-dogmatic recommended mapping* from situation to form: a state may pick a
different form when that's more appropriate and natural to the moment.

| Display-kind | Form | Canonical shipped exemplar | Status |
|---|---|---|---|
| **Live status line** | one updating line + spinner/elapsed | running popover (`runningPopoverBody`); LLM-settings dot/spinner | shipped |
| **Phase progression** (one popover, walks named phases, no re-anchor) | step through named phases in a single popover | **`OllamaDownloadPill`** (choosing → needsOllama → waiting → downloading → finishing → failed) | shipped (Ollama) |
| **Accumulating rows / log** | per-bucket grid of `MessageKind` rows | diagnostic `bucketsBody`; boot-failure "last 40 lines" disclosure | shipped |
| **Determinate progress** | 0–100% bar + Cancel | copy-on-row ring (`ProjectRowActivityIndicator`); `OllamaDownloadPill` when byte-total known | shipped |
| **Indeterminate progress** | spinner + short status line | copy-cancelling; project scan; Ollama start/finish; boot "Starting sidecar" | shipped |
| **Choice / picker** | grid or radio list of options | `IconPickerPopover` (symbol grid); Ollama model picker (radio list) | shipped |
| **Dialog / confirmation** (blocking on the user) | prompt + action button(s) | 4 `.alert` sites; AI & Privacy consent sheet; OllamaDownloadPill needs-Ollama phase | shipped |
| **Terminal failure with reason** | failure buckets + reason + Copy / Show Log | diagnostic popover (`unifiedPopoverBody`) | shipped |
| **Ephemeral note** (toast) | bottom-of-window, auto-dismiss or undo | ~~informational toast (3s); undoable-removal toast (8s) — `ToastSurface`~~ | **retired 19 Aug 2026** — all six removed; the display-kind has no shipped instance on the Mac. See the anti-pattern below |
| **Info / explanatory card** | full-content prose + per-item actions | `UnsupportedSubsetView` | shipped |
| **Success poster** | small graphical summary of a settled good state | — _none_ | **not shipped** — the one genuine candidate-new (optional; see deferred appendix) |

Two facts the inventory settled, recorded here so they aren't re-litigated:

- **Dialog/choice is shipped, not a gap.** Four `.alert` sites + the consent
  sheet + the Ollama needs-Ollama phase already cover "blocking on the user".
- **Shipped cross-surface conventions** (codify, don't reinvent): the three
  pills share one visual envelope (Capsule + secondary stroke); toasts share
  `ToastSurface`; toolbar/row spinners use `.controlSize(.small)`; status
  glyphs carry severity while text stays `.secondary`; sidebar row indicators
  never stack (single precedence chain failed > running > warning > ready);
  the diagnostic popover is **fixed in width and content-sized in height**, 360
  wide with a 320 ceiling and a scroller only past it (22 Aug 2026 —
  [`design-pipeline-popover-sizing.md`](design-pipeline-popover-sizing.md); the
  view owns the constants, presenters pass no frame). It was a fixed 360×320
  envelope until then, to dodge an NSPopover resize-animation livelock in
  `PipelineActivityItem.swift` — a file since deleted along with the
  `ProgressView` that caused it; the app uses `.alert` **exclusively** — never
  `.confirmationDialog`.

### The state catalog

Grouped by surface. *Invocation* records how each state can be summoned for
inspection today: `debug-menu (live)` · `fixture (env, relaunch)` · `env var`
· `real-condition-only` · `not-implemented`.

**Pipeline activity pill / popover** — states in `PipelineRunner.swift`,
rendering in `PipelineActivityItem.swift`:

| State | Display-kind | Real text / data | Invocation |
|---|---|---|---|
| `.scanning` / `.idle` | _(hidden — no surface)_ | pill hidden | real-condition-only |
| `.queued(position)` | Live status line | "Queued · N" / "Waiting for another project to finish (position N in queue)" | real-condition-only |
| `.running` — starting (`stageIndex == 0`) | Indeterminate progress | "Starting…" / "Starting up — loading models and validating credentials." | real-condition-only |
| `.running` — resuming (`attachedFromOrphan`) | Indeterminate progress | "Starting…" / "Resuming analysis (reconnected after app restart)." | real-condition-only |
| `.running` — mid-pipeline (`stageIndex > 0`) | Live status line _(the flicking bug; deferred target = phase progression + log)_ | "Stage N · stageName" + elapsed + Stop | real-condition-only |
| `.running` — stopping (`isStopping`) | Indeterminate progress | "Stopping…" / "Waiting for the analysis subprocess to exit." | real-condition-only |
| `.ready(Date)` | _(hidden — clean success)_ | pill hidden | real-condition-only |
| `.failed(message, category)` | Terminal failure with reason _(degraded body)_ | message + `Category:` line | fixture `failed_no_summary` (env, relaunch) |
| `.completedPartial(summary)` | Terminal failure with reason _(accumulating rows)_ | per-bucket failure grid | fixtures `run_completed_partial`, `run_completed_partial_truncated`, `showcase_partial_dense`, `showcase_truncated_varied`, `showcase_typical_partial`, `showcase_overflow_one` |
| `.failedWithDiagnostic(summary)` | Terminal failure with reason | per-bucket failure grid | fixtures `run_failed_abandoned`, `run_failed_abandoned_at_topics`, `showcase_failed_auth_burst`, `showcase_failed_multi_category` |
| `.unreachable(reason)` | Inline sidebar glyph **→ popover** | Reason headline + the folder path; row dimmed | real-condition-only |
| `.partial(kind, stages)` / `.stopped(stages)` | _(no glyph, no popover)_ | — | **by decision, not a gap** — see below |
| `run_completed_clean` | _(validates clean — no override)_ | pill stays hidden | fixture (env, relaunch) |
| `showcase_all_glyphs` | Design gallery _(special-cased body)_ | 5-glyph `MessageKind` reference card | fixture (env, relaunch) |
| `showcase_all_states` | Design gallery _(special-cased body)_ | 5 states, varied message lengths | fixture (env, relaunch) |

Diagnostic fixtures are set via `BRISTLENOSE_DEBUG_DIAGNOSTIC_FIXTURE=<key>`
in the Xcode scheme (read once at launch; relaunch to change). 13 scenarios
+ the `failed_no_summary` sentinel live in `DiagnosticFixture.swift`. There
is no live picker.

**OllamaDownloadPill** — phases in `OllamaDownloadModel.swift`; all 10
`DebugScene` cases are live-invocable from the Debug menu (`MenuCommands.swift`
≈ 76–97: "Cycle ▸ next state" Ctrl+Cmd+O + per-scene buttons) and via
`BRISTLENOSE_DEBUG_OLLAMA_PHASE=<scene>`:

| Scene | Display-kind | Real text / data |
|---|---|---|
| `idle` | _(hidden)_ | pill hidden |
| `choosing` | Choice / picker | model radio grid |
| `needsOllama` | Dialog / choice (blocking) | "Needs Ollama" info + action button |
| `waiting` | Indeterminate progress | hourglass + setup step list (passive: human installing) |
| `downloadingDeterminate` | Determinate progress | % bar + Cancel |
| `downloadingIndeterminate` | Indeterminate progress | spinner + status |
| `finishing` | Indeterminate progress | spinner |
| `failNoInternet` / `failTimedOut` / `failCantReach` / `failGeneric` | Terminal failure with reason | error message + Retry |

**Other surfaces** — none have a debug affordance; all are real-condition-only:

| Surface | State(s) | Display-kind | Invocation |
|---|---|---|---|
| copy-on-row (`ProjectRowActivityIndicator` / `ProjectSubtitle`) | copying / cancelling | Determinate progress / Indeterminate progress | real-condition-only (drag files onto a project) |
| `IconPickerPopover` | symbol grid | Choice / picker | real-condition-only (row context menu "Choose Icon…") |
| AI & Privacy consent sheet | first-run (non-dismissable) / re-access (Done) | Dialog / choice (blocking) | real-condition-only (first launch / Bristlenose ▸ AI & Privacy…) |
| Alerts (`.alert`, 4 sites) | duplicate-project drop; disk-space precheck; locate error; in-flight pipeline switch (destructive) | Dialog / confirmation (blocking) | real-condition-only |
| Toasts (`ToastSurface`, 2) | informational (3s) / undoable removal (8s, shows count + name) | Ephemeral note | real-condition-only |
| `BootView` | startingSidecar / loadingReport | Indeterminate progress | transient (cold start) |
| `BootView` | failed (message + Retry + details disclosure) | Terminal failure with reason | partial — misconfigure `BRISTLENOSE_DEV_SIDECAR_PATH` / `_EXTERNAL_PORT` |
| `UnsupportedSubsetView` | files-not-folder card | Info / explanatory card | real-condition-only |

_(Sibling surfaces, out of scope for a popover catalog but noted: sidebar
inline indicators — row-subtitle status, session count, scan spinner, iCloud
download arrow — are persistent inline status, not popovers.)_

### Invocation coverage (a finding, not a proposal)

The catalog above doubles as a coverage map, and the coverage is uneven:

- **Only the Ollama pill is live-invocable** from a real `CommandMenu("Debug")`
  with no relaunch — the gold-standard harness.
- **The diagnostic popover** is env-var + relaunch only (no live picker).
- **Every other surface is real-condition-only** — no fixture, no SwiftUI
  `#Preview`, no debug hook. To see them you must trigger the real condition.

The Ollama `CommandMenu("Debug")` live-cycle is the **proven pattern** for
making any catalogued state summonable on demand. Extending it to the rest is
deliberately *out of scope here* — design that step with intention later, when
it's wanted; this section only catalogues what exists.

### Guardrail — settled, do not relitigate

The run's icons, typography, `MessageKind` glyph weights/tints, and the
diagnostic-popover information architecture were arrived at through
substantial design effort and are **settled**. This catalogue *names and
reuses* that vocabulary; it does not reopen it. Any future work (including the
deferred appendix) extends *where* the settled vocabulary is used — never
*what* it is.

## Information architecture

### What goes where

| Information | Pill | Popover header | Popover row | Sidebar glyph | Toast | Copy (plaintext) |
|---|---|---|---|---|---|---|
| Distinctive failure label ("Whisper timeouts") | ✓ | — | — | — | — | ✓ |
| Status verb ("Partial completion" / "Run failed") | — | ✓ | — | — | — | ✓ |
| Project name | — | — | — | — | — | ✓ |
| Run timestamp range | — | — | — | — | — | ✓ |
| Per-stage outcome (verbatim CLI string) | — | — | — | — | — | ✓ |
| Per-stage duration | — | — | — | — | — | ✓ |
| Per-session cause (short, category-derived) | — | — | ✓ | — | — | ✓ |
| Raw `cause.message` (≤4 KB) | — | — | selectable via `.textSelection(.enabled)` | — | — | ✓ |
| App version + OS + commit | — | — | — | — | — | ✓ (trailer) |
| Persistent run-state indicator | — | — | — | ✓ | — | — |
| Ephemeral confirmations ("Saved") | — | — | — | — | ✓ | — |

**Notes on what's NOT in the popover** (revised from initial spec):

- **Project name dropped from header** — it's already in the toolbar
  chip / sidebar / window title (`WindowTitleManager` sets
  `NSWindow.title`); repeating it in the popover header was redundant.
- **Run timestamp range dropped from header** — surfaced only in the
  plaintext Copy output. Header is the status verb only.
- **Per-stage duration dropped from row** — surfaced in plaintext Copy
  only. Row is glyph / sid / message (three Grid columns); no
  monospace time column.
- **`.help(...)` tooltips dropped** — message Text is
  `.textSelection(.enabled)` instead; researchers can drag-select the
  portion they want into clipboard / pasteboard.
- **Email surface dropped entirely** — Copy is a single `doc.on.doc`
  icon button at the top-right of the popover header. No "Email
  support" button. Researchers find feedback channels via app +
  website + GitHub.

### Length budgets

| Slot | Max chars | Truncation |
|---|---|---|
| Pill label (toolbar) | ~28 | ellipsis at toolbar boundary |
| Stage row label | ~50 (proportional) / ~58 (with monospace time column) | wrap to 2 lines, no truncation |
| Per-session cause label (in row) | ~40 | `.lineLimit(1)` + `.truncationMode(.tail)` + `.help(...)` tooltip |
| Raw `cause.message` | 4 KB (capped at write time, see `bristlenose/events.py:CAUSE_MESSAGE_MAX`) — path-sanitised at the source via `_sanitise_message()` | shown only in tooltip + Copy/Email |
| Per-stage `failed[]` list | **10 entries + 1 overflow placeholder** (`STAGE_FAILED_MAX = 10`, see `bristlenose/events.py:_truncate_failed`). Worst-case terminus event line ~43 KB, comfortably under Swift `EventLogReader.readBoundedTail`'s 64 KB read window. | placeholder is a `StageFailure` with `session_id=null`, `cause.category=unknown`, `cause.message="... and N more failures truncated"` — popover renders as a single muted summary row, never as an N+1th session |
| Toast message | ~60 | wrap to 2 lines |

Stage row labels come from `bristlenose/pipeline.py` directly — they are
the canonical CLI message strings, not new UX copy. Don't translate
them; they are domain terminology like "Build" or "Compile" in Xcode.

### Hierarchy rules

- **Layout** — popover body is a SwiftUI `Grid` with three columns:
  glyph / session id / message. The message column flexes and wraps
  *within itself* (hanging indent under the message column edge, not
  back to column 0). Per-Text drag-select on each message; cross-row
  drag-select is sacrificed in exchange for clean column alignment.
- **Per bucket** — a bucket header (e.g. `Transcripts (2/5)` semibold
  callout + secondary count) appears above its failure rows.
- **Failure rows** — one `GridRow` per session, with red
  `xmark.circle.fill` + monospaced sid + message body. Existing-spec
  "indented ~3 chars, no leading glyph, inherits parent kind" was
  revised: each row carries its own `MessageKind.error` glyph.
- **Count subhead** — when a bucket has ≥3 failures, a "N failures"
  caption line renders above the rows. Acts as a scannable count;
  does **not** collapse the rows.
- **Skipped** rows render once with `—` and the `skipped` suffix. No
  sub-rows.
- **Overflow placeholder** — when a stage failed >10 sessions, the wire
  carries 10 real failures + 1 sentinel `StageFailure` (session_id=null,
  category=unknown, message starts `"... and "`). Render as one muted
  summary row at the bottom of the stage's failure list with
  `MessageKind.warning.symbolName` (`exclamationmark.triangle.fill`
  orange) + italic `.secondary` text. Detection: `failure.sessionID ==
  nil && failure.cause.message.hasPrefix("... and ")`. The Swift side
  parses N out of the message and renders via the CLDR plural keys
  `desktop.pipeline.diagnostic.overflow_one` / `_other`. Lock the
  contract via the `run_completed_partial_truncated` fixture scenario.

> **Superseded — May 2026, by Swift implementation**
>
> The initial spec said "nest under `DisclosureGroup` only when the
> parent stage has ≥3 child failures. ≤2 inline. ≥3 collapsible,
> expanded by default." This was implemented and then removed during
> the same branch. Reason: `DisclosureGroup(isExpanded: .constant(true))`
> is a lying chevron — it cannot collapse (the binding is constant), so
> the affordance promises something it doesn't deliver. The honest
> replacement is the plain "N failures" count subhead above the rows
> (which is what shipped). If a future cohort needs collapse-on-tap for
> very long failure lists, make the disclosure properly stateful with
> `@State var expanded = true`; until then, a count subhead is the
> right shape.

### Pill label derivation

The pill carries the *distinctive* failure label. Derived from the
*dominant* `PipelineFailureCategory` among `summary.failed[]`. Tied
counts prefer non-retryable (AUTH > OUT_OF_CREDIT > MISSING_BINARY >
QUOTA > NETWORK > UNKNOWN). Cap at ~28 chars. Locale-keyed under
`desktop.pipeline.diagnostic.pill.<category>`.

`OUT_OF_CREDIT` sits beside `AUTH` — both are account-level and terminal
until the user acts out-of-band (top up / fix the key) — and above `QUOTA`,
which since Jul 2026 means a *transient* rate-limit worth retrying. Before
that split, `QUOTA` conflated billing exhaustion with throttling and
rendered as "Rate limited", telling a bankrupt account to wait.

The same string is the popover's `.headline` line. Don't drift them.

## Adding a new message — flowchart

When you find yourself wanting to surface a new error, status, or note,
**read these questions before writing copy**:

1. **Which kind?** Pick from the five. If none fit, you are either
   over-engineering or have found a real gap — file an issue. Don't
   invent a new glyph.
2. **Which surface?** Use the IA table above. A confirmation toast and
   a popover row are different products — pick one.
3. **Length?** Read the budget table. If your message is longer,
   truncate at the surface boundary and put the full text in
   tooltip/Copy diagnostic.
4. **Locale key?** All user-visible chrome strings need entries in all
   six locale files (en, es, fr, de, ko, ja). Domain-vocabulary stage
   names are exceptions — they stay in English everywhere, like Xcode's
   build phases.
5. **Plural forms?** If your string interpolates a count, plan for the
   four-vs-two CLDR plural rule split (en/es/fr/de have `_one` and
   `_other`; ko/ja have `_other` only).
6. **Where does it route?** A new failure category is a **five-site**
   change, and missing any one of them fails silently or loudly:
   1. `bristlenose/events.py::CauseCategoryEnum` (the single source) **and**
      its `_RETRYABLE` entry — the dict is indexed directly, so a missing
      entry is a `KeyError`, not a default.
   2. `PipelineSummary.swift::CauseCategory` — **the wire decoder.** Since
      Aug 2026 it has a custom `init(from:)` that decodes an unknown raw
      value as `.unknown` rather than throwing (see the callout below for
      what that cost before). So a missing case no longer vanishes the
      diagnostic — it renders under the wrong label, which is quieter and
      still wrong. Add the case.
   3. `PipelineRunner.swift::PipelineFailureCategory` — the *other* Swift
      mirror (row summary + popover label). Both `humanSummary` and
      `ProjectDiagnosticPopover.humanCategoryLabel` switch over it
      exhaustively, so these two at least fail at compile time.
   4. `dominantCategory()`'s `pillPrecedence` — a category outside the chain
      silently collapses to `.unknown` in the pill.
   5. The pill-label locale namespace (`desktop.pipeline.diagnostic.pill.*`).

   A new toast surface needs `ToastStore.show(_, kind:)`.

   **A new *refusal reason* is a different, smaller change — three sites, and
   one of them is 21 files.** `UnusableReason` (`bristlenose/events.py`, since
   Aug 2026; `refusals.py` re-exports it) discriminates *within*
   `unusable_input`, so none of the five sites above apply — the category
   already exists. What it needs is:

   1. the enum value, and its sentence in `refusals.py::MESSAGES` — indexed
      directly, so a missing entry is a `KeyError`, not a default;
   2. `desktop.pipeline.diagnostic.reason.<value>` in **all 21 full locales**
      (not `zh-Hant-HK`, which inherits — see the locale-key inventory below);
   3. nothing on the Swift side. `Cause.reason` is a `String?` and the popover
      builds the key from it, so a new reason needs no Mac change at all.

   Site 2 is the one that will be forgotten, and `scripts/check-locales.py`
   **cannot** tell you: it diffs each locale against English, so a key English
   itself is missing is invisible by construction. The gate that does see it is
   `tests/test_pipeline_diagnostic_locale_keys.py::test_every_unusable_reason_has_a_localised_string`,
   which parametrises over the enum rather than an allow-list precisely so the
   obligation cannot be dropped — add a ninth reason and 21 tests go red on the
   same commit.

   > **The two-mirror trap (learned the hard way, Jul 2026).** One Python enum,
   > *two* Swift mirrors. Adding `out_of_credit` to `events.py` +
   > `PipelineFailureCategory` compiled clean and looked done — because the
   > exhaustive switches are on that enum. But `PipelineSummary::CauseCategory`
   > was untouched, so the first real out-of-credit run would have failed to
   > decode its summary entirely. Sites 4 and 5 were also missed. The
   > "renders automatically" claim this step used to make is **false** — it's
   > only true once all five sites are done. Grep both Swift enums whenever
   > `CauseCategoryEnum` changes; the Python-side parity test
   > (`tests/test_events.py::test_cause_category_matches_swift_enum`) pins the
   > *value set* but can't see either Swift file.
   >
   > **Aug 2026 — it bit again, and the fix is structural this time.** Adding
   > `unusable_input` walked into the same shape, plus one the Jul entry
   > didn't name: **the two mirrors are not the same case set.**
   > `output_exists` exists only on `PipelineFailureCategory`,
   > `unusable_input` on both, and neither list is a superset of the other —
   > deliberately, since a refusal of the whole *attempt* can never describe
   > one file. Both enums also decoded an unrecognised value by **throwing**,
   > and the category sits inside `Cause` inside `StageFailure` inside the
   > summary, so one unmirrored word cost the entire terminus event: no
   > summary, no per-stage rows, no cause, for a run that merely used a newer
   > word. Adding the missing case — the Jul fix — does nothing for the next
   > one. Both now decode unknown as `.unknown`
   > (`init(from decoder:)` on each), so the "schema-additive" contract this
   > enum is documented under finally holds in the direction that matters.
   > Pinned by `IngestOutcomeTests.everyKnownCategoryStillDecodesToItself`
   > and `.theTwoCategoryEnumsAreDeliberatelyDifferentSets`. **Grep both
   > enums still — the fallback keeps the event readable, it does not make
   > the label right.**

## Anti-patterns

- **Don't mint a new glyph.** Five Unicode glyphs cover every status
  Bristlenose emits. Octagons, X-marks, gears, custom shapes are out.
  If the existing five don't communicate it, copy isn't the fix.
- > **Superseded — May 2026, by Swift implementation.** The Mac
  > popover now uses SF Symbols inline in failure rows
  > (`xmark.circle.fill` red for failures, `exclamationmark.triangle.fill`
  > orange for overflow placeholders) — `MessageKind` carries the SF
  > Symbol name and tint per kind. Rationale for the reversal:
  >   1. **Mac list-status idiom** — Mail, Xcode Issue Navigator,
  >      Things 3, NetNewsWire all use tinted SF Symbols inside list
  >      rows for status. Unicode glyphs at row-leading position were
  >      an anti-idiomatic carryover from the CLI.
  >   2. **Internal consistency with the pill** — the toolbar pill
  >      already used SF Symbols (`exclamationmark.triangle.fill` for
  >      `.completedPartial`, `exclamationmark.circle.fill` for
  >      `.failedWithDiagnostic`). Unicode rows below an SF Symbol pill
  >      created mixed vocabulary within a single popover surface.
  >   3. **CLI parity preserved where it matters** — the parity
  >      argument was confusing the rendering surface with the
  >      *clipboard surface*. The Mac popover *renders* SF Symbols;
  >      the Copy details *exports* Unicode `glyph` via
  >      `formatDiagnosticPlaintext`. Two formatters, one
  >      `MessageKind` taxonomy. A copy-pasted diagnostic still reads
  >      identically in a terminal or plaintext email.
  >   4. **Colour-blind disambiguation** — SF Symbols have distinct
  >      shapes (circle vs triangle vs square) AND are tintable, so
  >      shape + colour redundancy carries the signal. A single Unicode
  >      `✗` is shape-only.
  >
  > The original anti-pattern is preserved below for historical context.
- **Don't reach for SF Symbols inside the popover.** [*Original
  bullet, now superseded — see banner above.*] The popover and
  the CLI render the same glyphs; SF Symbols would break that. SF
  Symbols are reserved for native chrome that has no CLI counterpart
  (sidebar dots, toolbar pill icon if needed, button affordances on
  modal sheets).
- **Don't re-explain success.** A clean stage gets a `✓`, the verbatim
  CLI message, and a duration. No "successfully completed", no "all
  good!", no decorative copy.
- **Don't link to half-broken results.** A partial run does not get an
  "Open report" button. If the user wants to see what survived, they'll
  start a new run and we won't have abandoned them.
- **Don't add a "Retry failed sessions" placeholder until it works.**
  A disabled button reads as an unimplemented promise.
- **Don't write JSON to clipboard by default.** The Copy diagnostic is
  CLI-replay plaintext (Xcode "Copy Issue" pattern). Machine-readable
  JSON behind Option-Copy is a future affordance.
- **Don't bypass `MessageKind` for "just one weird case".** If a
  message looks like it doesn't fit, it almost certainly does and
  you're over-thinking it. Re-read the kind table.
- **Don't reach for a toast. There are none left on the Mac, and that was a decision.** All six `desktop.toast.*` messages went on 19 Aug 2026 — four drop refusals, an Add-Files scold, and the undoable-removal toast whose 8s window also expired ⌘Z. The replacements are the system's own: `validateDrop` returning `[]` so AppKit draws no highlight, swaps to the operation-not-allowed pointer and springs the item back; a persistent `+N unanalysed` row delta; a dimmed menu item; `NSAnimationEffect.poof`; and Edit ▸ Undo with no clock. **This document already contained the argument** — the bullet below calls transient UI "the auto-dismissing-toast anti-pattern" while the catalogue above listed two toasts as shipped. What was missing was not the rule but the *drawing*: no mockup had ever rendered them, and the review happens on the mockup. Rationale and the HIG citation: `docs/design-analysis-lifecycle.md` §4.2.
- **Don't let in-flight progress flick past unread.** When stages advance
  faster than a human can read, a replace-in-place running surface is the
  auto-dismissing-toast anti-pattern in another costume — transient UI for
  information the user needed to retain ("the user missed it" is the failure
  mode). See the deferred "Future direction — in-flight progress as rolling
  logs" appendix for the design conversation; the fix is to let progress that
  naturally accumulates be readable, not to make every surface a scrollback.

## Mac surface as implemented (May 2026)

Decisions made during the `pipeline-diagnostic-popover-swift` branch
that don't naturally land in any of the cross-platform sections above.
This is the Swift-implementation surface, not the contract.

### Toolbar placement

The pill lives at `ToolbarItem(placement: .status)`, not
`.primaryAction`. On macOS 26, SwiftUI groups multiple `.primaryAction`
items into a single trailing capsule (Share + Search + anything else);
putting the pill there made it look "contained inside the search
field." `.status` placement gives the pill its own zone, separate from
the trailing actions cluster, matching Mac conventions for ambient
status indicators.

### Project-name surface

The toolbar **no longer carries a project-name chip**. The previous
`.navigation`-placement chip sat where the system back affordance
lives, which was wrong real estate for a per-project title. The chip
was removed in this branch; `WindowTitleManager` still sets
`NSWindow.title` to the project name for Mission Control / Cmd+~
window-list / menu bar. A correct in-toolbar project surface is
deferred to a future design pass.

### Popover header + actions

**One popover surface for every failure-shaped state.** `.failed`,
`.completedPartial`, and `.failedWithDiagnostic` all route through the
same SwiftUI code path (`PipelineActivityItem.unifiedPopoverBody`).
Chrome is identical; only the body content branches. Was two surfaces
through May 2026 — the legacy `.failed` popover was undesigned scaffolding
that grew out of spec; `unify-failure-popover` (May 2026) deleted it.

Header (always present):

- Title: the status verb only (`Partial completion` / `Run failed` /
  `Failed`). No project-name repeat (already in the toolbar chip,
  sidebar, and window title).
- Top-right `Show Log` button (conditional): small bordered text button
  (`.buttonStyle(.bordered)` + `.controlSize(.small)` — HIG popover idiom,
  matches Apple's Calendar / Mail VIP popover examples) rendered
  immediately to the left of the Copy icon, present only when
  `PipelineRunner.logFileURL(for: project)` exists on disk. Click →
  `NSWorkspace.shared.open(logURL)` — opens the per-project CLI log in
  the user's default `.log` handler (Console.app for most). LaunchServices
  brokers the file vend across the process boundary so the call works
  under App Sandbox without extra entitlements. Verb-first label matches
  Apple's "Show in Finder" / "Show Package Contents" idiom for
  reveal-and-look gestures.
- Top-right: a single `doc.on.doc` icon button (`buttonStyle(.bordered)` + `.controlSize(.small)` — symmetric chrome with the Show Log button, asymmetric content; Apple's Finder toolbar idiom for bordered icon-only buttons next to bordered text buttons)
  with `help("Copy details")` tooltip. Click → write plaintext to
  `NSPasteboard`. No "Copied" tick flip (silent copy is the native
  Finder / Safari Copy URL pattern). Dispatches on state — uses
  `formatDiagnosticPlaintext` for summary-bearing cases,
  `formatDiagnosticPlaintextDegraded` for `.failed`.

**No bottom action row anywhere.** No Retry, no Change provider, no
Re-analyse…, no Email, no Show technical details disclosure.
Retry / Re-analyse live in the project's natural run affordance
(sidebar context menu, toolbar Run button); Change provider lives in
Settings (Cmd+,). The popover stays a calm, diagnostic-only surface
across all three failure states.

Body content branches on the state:

- `.failedWithDiagnostic` / `.completedPartial` → `bucketsBody`:
  per-bucket Grid with SF Symbol + session id + message rows. Unchanged
  from `pipeline-diagnostic-popover-swift`.
- `.failed` → `degradedBody`: three lines — the `EventLogReader`-emitted
  reader string (e.g. `Analysis stopped unexpectedly.` for the orphan
  path; `cause.message` for older sidecars), the localised
  `desktop.pipeline.diagnostic.noStructuredCause` hint
  ("Detailed cause not captured."), and `Category: <humanCategoryLabel>`.
  No stdout tail in the visible body — stdout (when populated) flows
  into the Copy plaintext + the on-disk log reachable via the Log button.

### Two new `PipelineState` cases

`PipelineRunner` ships two new states beyond the prior taxonomy:

- `.completedPartial(summary: PipelineSummary)` — `run_completed`
  terminus event with `summary.totalFailureCount > 0`. A report was
  written but at reduced fidelity.
- `.failedWithDiagnostic(summary: PipelineSummary)` — `run_failed`
  terminus event with populated `summary`. Run was abandoned
  mid-pipeline; no usable report.

`EventLogReader.deriveState` routes terminus events into these new
states when `summary` is populated, falling through to the legacy
`.failed(summary:category:)` path otherwise. Backwards-compatible with
older log files that don't carry a `summary` field.

### `applyScanResult` guard (load-bearing bug fix)

`PipelineRunner.applyScanResult` early-returns for `.running` /
`.queued` / `.failed` / `.completedPartial` / `.failedWithDiagnostic`.
Without this guard, the periodic manifest scan during a project's
lifecycle would overwrite a fresh diagnostic state with a stale
`.ready` / `.stopped` reading from the manifest. The two new
diagnostic states needed to be added to this list; pre-fix, the pill
would briefly show the diagnostic popover then revert mid-render to
the manifest-derived state. Found during the branch's manual walk
fixture work; documented as Finding 30+ in the review log.

### Debug-only fixture harness

`BRISTLENOSE_DEBUG_DIAGNOSTIC_FIXTURE=<scenario>` env var in the
active Xcode scheme overrides the selected project's state at app
launch with a synthetic `PipelineSummary`. Scenarios are embedded
in Swift (not loaded from disk — App Sandbox blocks worktree reads).
`#if DEBUG`-gated, absent from Release builds. Scenarios cover
contract-mirrored shapes (typical partial, abandon, abandon-at-topics,
truncation overflow, clean baseline) plus richer showcase scenarios
for visual evaluation (dense multi-bucket, multi-category, varied
truncation, all-glyphs swatch, all-states design-review). Used during
this branch for the manual walks against the fixtures and for design
assessment of the SF Symbol vocabulary.

### Locale-key inventory (May 2026)

Shipped on this branch, in all six `desktop.json` locale files:

- `desktop.pipeline.diagnostic.pill.{auth, out_of_credit, missing_binary, quota, network, unknown}` — dominant-category pill labels (`out_of_credit` added Jul 2026 with the billing/rate-limit split; `en` only so far — the other locales fall back to `en` until the i18n sweep)
- `desktop.pipeline.diagnostic.header.{completed_partial, failed}` — popover titles
- `desktop.pipeline.diagnostic.action.copy` — Copy icon tooltip ("Copy details"). `action.copied` and `action.email` were removed in pass-4 cleanup (Finding 31) — the Copy button does silent-copy (no flip), and the Email button was dropped entirely. The locale keys had zero call sites.
- `desktop.pipeline.diagnostic.action.showLog` — Log button label ("Log" / "Registro" / "Journal" / "Protokoll" / "로그" / "ログ"). Shipped on `unify-failure-popover` (May 2026).
- `desktop.pipeline.diagnostic.action.showLogTooltip` — Log button `help(...)` tooltip ("Open the analysis log file"). Shipped on `unify-failure-popover` (May 2026).
- `desktop.pipeline.diagnostic.noStructuredCause` — degraded-body hint line ("Detailed cause not captured.") rendered under EventLogReader's reader string in the `.failed` body. Shipped on `unify-failure-popover` (May 2026).
- `desktop.pipeline.diagnostic.tooltip.completed_partial` — pill help text for `.completedPartial`. Wording uses "Analysis" not "Pipeline" — see the *User-facing vocabulary* note below.
- `desktop.pipeline.diagnostic.overflow_one` / `_other` — CLDR-plural-keyed truncation marker (en/es/fr/de carry both forms; ko/ja carry `_other` only)
- `desktop.pipeline.diagnostic.reason.{unsupported_format, empty, incomplete, not_a_recording, no_audio, no_speech, unreadable_folder, unreadable}` — **added 22 Aug 2026**, the sentence that says why a file isn't in the report. Keyed by `UnusableReason` raw value, same convention as `pill.*`. Ships in all 21 full locales; `zh-Hant-HK` deliberately carries none — these eight sentences have no HK-idiom divergence, so seeding them there would pin the fork and break the `zh-Hant-HK → zh-Hant` inheritance that `ReasonLocalisationTests.zhHantHKInheritsRatherThanFallingBackToEnglish` pins.

> **The counts above are the May 2026 state and are no longer literal.** "All
> six `desktop.json` locale files" is now 21 full locales plus the `zh-Hant-HK`
> override, and the two "`en` only so far" / "machine-fill English stub"
> caveats are spent — `ja` is a full locale and `pill.*` ships everywhere
> (`test_pill_categories_present` pins it). Left in place rather than rewritten
> because the section is dated and reads as history; the live answer is always
> `scripts/check-locales.py` plus `tests/test_pipeline_diagnostic_locale_keys.py`.

### User-facing vocabulary: "Analysis", not "Pipeline"

Per the glossary's tone-guide register, **user-facing chrome** uses
"Analysis" / "Analysing" / "Run" — never "Pipeline". The latter is a
correct CS term and stays where it belongs:

- ✓ User-facing chrome (locales, popover tooltips, sidebar, menus, settings labels, error toasts) → **"Analysis"**
- ✓ CLI command verbs (`bristlenose run`, `bristlenose analyse`) → **"Run"**, **"analyse"**
- ✓ Man page, commit messages, internal Python module names, design docs, CHANGELOG → **"Pipeline"** is fine (CS term, accurate, internal audience)
- ✗ Don't introduce "Pipeline" into a chrome string just because the implementation file is named `pipeline.py`.

Reason: researchers don't have "pipelines"; they have analyses and
runs. "Running analysis on these interviews" reads naturally;
"Running the pipeline on these interviews" reads like a Pythonista
talking to themselves. The glossary spelling rule also locks the
British English form (`analyse`, not `analyze`).

Existing leak: `bristlenose/cli.py:857` prints `"Pipeline failed."` —
pre-existing, not introduced by this branch. Worth a follow-up sweep.

### Text selection

Every message-body `Text` carries `.textSelection(.enabled)`. Per-Text
drag-select works within a single message. Cross-row drag-select
across the Grid was experimented with via `AttributedString` in a
single Text but reverted because the layout — column alignment with
hanging indent — was the higher-value affordance. Researchers who want
the whole popover content as text use the Copy button.

## Future direction — in-flight progress as rolling logs (deferred, post-TF)

> **Status: captured, not designed.** This appendix records a design
> conversation (5 Jun 2026) so it isn't lost. Nothing here is decided or
> scheduled, and per the catalog's guardrail it reuses the settled
> icon/typography/`MessageKind` vocabulary unchanged — it only proposes
> extending *where* that vocabulary is used.

**The QA observation.** On a fast `bristlenose run`, the `.running` popover
(`runningPopoverBody`) replaces its single status line each time a stage
completes (`StdoutProgressParser` increments `stageIndex` on every `✓ <stage>`
stdout line). Stages can advance faster than a human can read — the tester
couldn't even screenshot them. This is the auto-dismissing-toast failure mode:
transient UI for information the user needed to retain.

**Nature of the information governs the treatment — not run speed.** Three
categories (user framing, verbatim: *"there are some things that naturally
scroll, and other things that are a complete state change — if it got that far
you don't care about the previous history (devs do, in debug logs, but not
regular users)"*):

1. *Naturally-scrolling / progressive* — stage progress; accumulates. The bug
   is that we replace it instead of letting recent progress stay readable.
2. *Complete state change* — terminal outcomes supersede; replace-in-place is
   correct (what the terminal popovers already do).
3. *Full history* — a developer concern; lives in the on-disk `bristlenose.log`
   (Show Log). Don't turn the user surface into a debug log.

But the categories aren't hermetic: *sometimes being able to see the previous
states or steps is useful* even to a regular user ("which stages completed
before this failed?"). The state leads; the path is worth a glance.

**Unifying concept: the popover is a series of rolling logs.** Rather than a
bare replace-in-place running paragraph versus a rich terminal grid, both are
the *same* surface — a rolling log — at different points in the process, using
the same row vocabulary already developed from the CLI output. Consistent with
this doc's Xcode-build-log visual reference. Two composable modes:

- *Accumulating history* — reviewable `MessageKind` rows.
- *Phase progression* — a known, named, ordered itinerary (user metaphor,
  verbatim: *"other times it's moving through states, e.g. on the launchpad,
  countdown, launch phase, orbiting, translunar injection, etc."*). This names
  the current bug: the pipeline *is* a phase progression but is rendered as an
  opaque, too-fast `Stage N · stageName` counter — neither a legible itinerary
  nor a log.

The modes **nest** (verbatim: *"and for each state you want the log"*): the
phase itinerary is the spine; each phase owns a rolling log of its detail —
structurally what the terminal `bucketsBody` already does, played forward. And
**relevance recedes with distance** (verbatim: *"when you're in lunar descent
you don't want to scrollback all the way to the launchpad"*): completed phases
collapse to a one-line outcome summary, the active phase is expanded with its
live log, any phase expands on demand — bounded by structure, not a 1000-line
scroll. This revisits the superseded `DisclosureGroup` note as a properly-
stateful disclosure, and is, again, the Xcode build navigator.

**Rendering mechanism — two candidates (undecided):** (A) a vertical collapsing
accordion (whole itinerary at a glance; grows tall); or (B) a horizontal
carousel of time-sliced phase-windows (user proposal, verbatim: *"perhaps we
can conceptualise each phase as a sublog that can scroll, but they are a series
of windows onto a time-sliced phase? so perhaps just a tiny pair of carousel
controls at the bottom of the popover left-right to go back in time is
enough?"*) — one window at a time, "back to the launchpad" = N pages left, not
N screens of scroll; compact and low-chrome. Tradeoffs for (B): loss of
at-a-glance overview (mitigable with a `Phase 3 of 7` position indicator); and
the `tail -f`-vs-scrollback live-follow question (does it auto-advance while
running; is there a "jump to live" after paging back?).

**Resizeability** (discussed, resolved): no user drag-resize handle (that
implies the content wants to be a window); size-to-content auto-fit is fine and
idiomatic. **Auto-fit is now what ships** (22 Aug 2026): 360 wide, height from
the content, 320 as a ceiling, scroller only past it — the capped-height-with-
internal-scroll option this paragraph anticipated. The fixed 360×320 envelope it
used to align with was a mitigation for an NSPopover resize-animation livelock,
and that livelock belonged to the live activity pill's `ProgressView`; the
terminal-state popover's body is a pure function of `state`, so its size is
decided once at present time and never animated. Full reasoning and the failure
modes: [`design-pipeline-popover-sizing.md`](design-pipeline-popover-sizing.md).
The one wrinkle a carousel would reintroduce is a popover height that jumps per
page; a stable per-page height would be needed. A live run-status log is legitimate native status chrome; a
durable, browsable history is data and belongs in Show Log / the on-disk log /
the React SPA, not a stretched popover.

**Open questions (for the later, intentional pass):** where legible human-named
phase names live (a single source the CLI/popover/sidebar share, replacing
`Stage N · sNN_internal`); default expansion policy; whether the in-flight
itinerary and the terminal `bucketsBody` become literally one view; per-phase
log depth before internal scroll. The lone genuinely-new display-kind, the
**success poster**, also belongs to this pass — present as an option, not a
default.

## Implementation references

| Area | File |
|---|---|
| Kind enum + glyph/colour tables (Python) | `bristlenose/ui_kinds.py` |
| Kind enum + glyph / SF Symbol / tint properties (Swift) | `desktop/Bristlenose/Bristlenose/MessageKind.swift` |
| CLI status helpers | `bristlenose/pipeline.py:131–171` (`_print_stage` + `_print_step` / `_print_warn_step` / `_print_error_step` / `_print_cached_step` wrappers); `bristlenose/cli.py` `_say()` for ad-hoc status lines |
| Cross-language schema fixture (v5) | `tests/fixtures/pipeline-summary-contract.json` |
| Showcase scenarios (debug-only, visual evaluation) | embedded in `DiagnosticFixture.swift` (sandbox-proof — Swift can't read worktree paths under App Sandbox) |
| Pipeline summary Pydantic model | `bristlenose/events.py` (`PipelineSummary`, `StageOutcome`, `StageFailure`) |
| Pipeline summary Swift Codable mirror | `desktop/Bristlenose/Bristlenose/PipelineSummary.swift` |
| Failure-category enum (single source) | `bristlenose/events.py:CauseCategoryEnum` — **mirrored by TWO Swift enums, both of which must be updated together**: `PipelineSummary.swift::CauseCategory` (decodes `cause.category` off the wire) and `PipelineRunner.swift::PipelineFailureCategory` (drives the row summary + popover label). See the two-mirror trap below. |
| Swift diagnostic popover | `desktop/Bristlenose/Bristlenose/ProjectDiagnosticPopover.swift` (extracted from the deleted `PipelineActivityItem.swift`, commit `02ad258`) |
| Sidebar run indicator (spinner + hover-× Stop) | `desktop/Bristlenose/Bristlenose/ProjectRowActivityIndicator.swift` |
| Sidebar subtitle / failure glyph → popover | `desktop/Bristlenose/Bristlenose/ProjectRow.swift` (search for `pipelineStateSubtitle`; glyph `Button` → `.popover`) |
| State-machine guard against scan clobber | `desktop/Bristlenose/Bristlenose/PipelineRunner.swift::applyScanResult` |
| Event-log → state routing | `desktop/Bristlenose/Bristlenose/EventLogReader.swift::deriveState` |
| Plaintext diagnostic formatter | `ProjectDiagnosticPopover.swift::formatDiagnosticPlaintext` (static) |
| Debug-only fixture harness | `desktop/Bristlenose/Bristlenose/DiagnosticFixture.swift` |
| Toast store (desktop) | `desktop/Bristlenose/Bristlenose/ToastView.swift` |
| Toast component (frontend) | `frontend/src/components/Toast.tsx`, `AutoCodeToast.tsx` |

## Related design docs

- `docs/design-pipeline-resilience.md` — failure-mode taxonomy, abandon
  decision, event sourcing
- `docs/design-html-report.md` — interactive report features (the
  popover deliberately does not link here for partial runs)
- `docs/design-i18n.md` — locale file structure, `dt()`/`ct()` forking,
  CLDR plural rules
- `docs/design-modularity.md` — cross-channel component strategy
  (CLI ≡ macOS Python code; this popover is a Mac-only UI surface that
  consumes the same shared `MessageKind` vocabulary as the CLI)

Established 7 May 2026 alongside branches `pipeline-summary-events`
(Python emitter) and `pipeline-diagnostic-pill` (Swift consumer).

## Proposed — the three-part body for a survivable failure (P5 / D4-B)

> **Status: PROPOSED, 3 Sep 2026. Nothing in this section ships yet.**
> Mockup: `docs/mockups/analysis-failure-states.html` (16 states, real SF
> Symbols, measured against `ProjectCellSpec` and this popover's own 360×320).
> Depends on D4-B — serving the last good analysis behind a failed run — which
> is what makes a "still showing" line true in the first place.

### Why the body grows a third part

The popover today answers **what went wrong**. Under D4-B the researcher's
project survives a failed analysis intact, which raises two questions it does
*not* answer: *what am I looking at?* and *what is under my control?* So the
body becomes three parts, in this order:

1. **State** — "Still showing your previous analysis — **5 of 7 interviews**,
   from 3 minutes ago."
2. **Cause** — the existing per-file breakdown (`bucketsBody`) or the global
   cause sentence.
3. **Action** — one line naming what the researcher can do.

### The content model: a shortfall from an attempted reality

A failed incremental run is not "an error", it is a **gap between what you have
and what you asked for**. Both numbers already exist and are already read by the
sidebar (`SourceFilesReader.readSnapshot` → `ingested=7, sessions=5`); the popover
states the gap and the cause explains it. This is why the state line carries a
count and not just a date.

**The verb carries the distinction the count cannot.** A `run_failed` and a
`run_completed_partial` produce near-identical popovers and mean opposite things:

| | DB moved? | state line | row |
|---|---|---|---|
| `run_failed` | no — serve re-imports only on `run_completed` | "**Still showing** your previous analysis — 5 of 7 interviews" | `Analysis failed · 5 of 7` |
| `completedPartial` | yes | "Your analysis **now has** 6 of 7 interviews" | `Analysed · 6 of 7` |

Get this wrong and the researcher cannot tell whether their curation survived.

### The category → action mapping

The cause column largely exists as `pipeline.diagnostic.pill.*` labels, but those
are **nouns sized for a row**; the popover has room for a sentence that names the
actor. The action column is new — ten strings, 21 locales, and separable from the
gates that let the report through at all.

| category | cause line | action line |
|---|---|---|
| `out_of_credit` | Your Claude account is out of credit. | Add credit to your Claude account, then analyse again. |
| `auth` | Claude wouldn't accept the API key. | Check the key in Settings ▸ LLM Provider, then analyse again. |
| `quota` | Claude is rate-limiting requests. | Nothing needs fixing — try again in a few minutes. |
| `api_server` | Claude had a problem at their end. | Nothing to fix here — try again shortly. |
| `network` | Couldn't reach Claude. | Check your connection, then analyse again. |
| `disk` | The disk ran out of space while transcribing. | Free up space on _\<volume\>_, then analyse again. |
| `unusable_input` | _per-file reasons — no global cause line_ | Replace or remove _\<these N\>_, then analyse again. |
| `missing_binary` | A tool Bristlenose needs is missing. | Check Diagnostics ▸ Check Health. |
| `whisper` | The transcription model didn't load. | Check Diagnostics ▸ Check Health. |
| `unknown` | Detailed cause not captured. | Open Show Log for what the analysis was doing when it stopped. |

**`quota` and `api_server` are load-bearing**: they are the only rows whose action
is *do nothing*, and the only ones a naive mapping gets wrong by inventing a chore
— sending the researcher to check a key that was never wrong. If the column ever
grows a default it must be "try again shortly", never "check your settings".

### Vocabulary: analysis, not run

"Run" is computer science; **analysis** is what the researcher believes is
happening. The shipped corpus already contradicts itself —
`pipeline.diagnostic.header.failed` says `Run failed` while
`pipeline.diagnostic.tooltip.completed_partial` says
`Analysis finished with failures`. This settles it in the direction the tooltip
already chose. Affected: that header, `pipeline.status.headline.failed`,
`pipeline.diagnostic.pill.unknown` ("Run had failures").

### Two states that are decisions, not drawings

- **All new files refused** collapses today to `unknown` → the row reads "Run had
  failures", which is false severity for a run in which nothing malfunctioned.
  Proposed header: **"Nothing new to analyse"**. This needs the missing
  `unusable_input` entries in `PipelineSummary.pillPrecedence` and the pill
  strings — the defect this doc's own truing banner already logs.
- **First-ever analysis failed** drops the state line entirely: with no previous
  analysis there is nothing to still be showing, and that is precisely the
  boundary where the status page keeps the whole surface.

### Relative time

The state line reuses `chrome.pipeline.analysedRelative` ("Analysed 3 minutes
ago"), which already renders in this very row — not a new date format. Shared
formats have three renderers to agree with (`docs/design-shared-formats.md`);
a fourth is not wanted.
