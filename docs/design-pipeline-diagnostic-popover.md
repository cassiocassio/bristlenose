---
status: current
last-trued: 2026-05-19
trued-against: HEAD@pipeline-diagnostic-popover-swift on 2026-05-19 (working tree, post pass-4 cleanup)
---

> **Truing status:** Current — schema (v5), IA, message-kind taxonomy,
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

- _2026-05-19_ — **Pass-4 cleanup landed.** Small fixes from the
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
- **Not a progress display.** While a run is in flight the pill renders
  `.running` with the existing spinner-and-elapsed pattern; this doc
  applies to terminal states (`.completedPartial`, `.failedWithDiagnostic`).
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
counts prefer non-retryable (AUTH > MISSING_BINARY > QUOTA > NETWORK >
UNKNOWN). Cap at ~28 chars. Locale-keyed under
`desktop.pipeline.diagnostic.pill.<category>`.

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
6. **Where does it route?** A new failure category needs a row in
   `dominantCategory()`'s precedence and an entry in the pill-label
   locale namespace. A new toast surface needs `ToastStore.show(_,
   kind:)`. The popover renders any registered category automatically
   if it appears in `summary.failed[].cause.category`.

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
- Top-right: a single `doc.on.doc` icon button (`buttonStyle(.borderless)`)
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

- `desktop.pipeline.diagnostic.pill.{auth, missing_binary, quota, network, unknown}` — dominant-category pill labels
- `desktop.pipeline.diagnostic.header.{completed_partial, failed}` — popover titles
- `desktop.pipeline.diagnostic.action.copy` — Copy icon tooltip ("Copy details"). `action.copied` and `action.email` were removed in pass-4 cleanup (Finding 31) — the Copy button does silent-copy (no flip), and the Email button was dropped entirely. The locale keys had zero call sites.
- `desktop.pipeline.diagnostic.action.showLog` — Log button label ("Log" / "Registro" / "Journal" / "Protokoll" / "로그" / "ログ"). Shipped on `unify-failure-popover` (May 2026).
- `desktop.pipeline.diagnostic.action.showLogTooltip` — Log button `help(...)` tooltip ("Open the analysis log file"). Shipped on `unify-failure-popover` (May 2026).
- `desktop.pipeline.diagnostic.noStructuredCause` — degraded-body hint line ("Detailed cause not captured.") rendered under EventLogReader's reader string in the `.failed` body. Shipped on `unify-failure-popover` (May 2026).
- `desktop.pipeline.diagnostic.tooltip.completed_partial` — pill help text for `.completedPartial`. Wording uses "Analysis" not "Pipeline" — see the *User-facing vocabulary* note below.
- `desktop.pipeline.diagnostic.overflow_one` / `_other` — CLDR-plural-keyed truncation marker (en/es/fr/de carry both forms; ko/ja carry `_other` only)

ja remains machine-fill English stub pending the native-friend
translation playbook.

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
| Failure-category enum (single source) | `bristlenose/events.py:CauseCategoryEnum`; Swift mirror at `PipelineSummary.swift::CauseCategory` |
| Swift popover bodies | `desktop/Bristlenose/Bristlenose/PipelineActivityItem.swift` |
| Sidebar subtitle / glyph | `desktop/Bristlenose/Bristlenose/ProjectRow.swift` (search for `pipelineStateSubtitle`) |
| State-machine guard against scan clobber | `desktop/Bristlenose/Bristlenose/PipelineRunner.swift::applyScanResult` |
| Event-log → state routing | `desktop/Bristlenose/Bristlenose/EventLogReader.swift::deriveState` |
| Plaintext diagnostic formatter | `PipelineActivityItem.swift::formatDiagnosticPlaintext` (static) |
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
