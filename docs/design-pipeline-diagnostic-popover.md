---
status: partial
last-trued: 2026-06-15
trued-against: HEAD@per-project-activity (518e6d3) on 2026-06-15
---

> **Trued 2026-06-15 (`per-project-activity` @ `518e6d3`) — the toolbar pill was deleted.**
> The per-project pipeline pill (`PipelineActivityItem.swift`) was **removed** (commit `8ffa470`)
> and the diagnostic popover **extracted** into its own reusable view
> `ProjectDiagnosticPopover.swift` (commit `02ad258`). The per-project run *glance* moved to the
> **sidebar row** (spinner + hover-× Stop, `ProjectRowActivityIndicator.swift`); the diagnostic
> popover is now opened by **clicking the row's failure glyph** (selects row, anchors `arrowEdge:
> .trailing`) or via row context-menu / Project-menu "Show Diagnostics…". Throughout this doc, read
> any reference to **"the toolbar pill"**, **`PipelineActivityItem.swift`**, **`unifiedPopoverBody`**,
> or **`runningPopoverBody`** as the per-project surface as *superseded* — the popover taxonomy and
> MessageKind content are unchanged, only the owning view + invocation moved. The surviving toolbar
> pills are `OllamaDownloadPill` + `CopyProgressPill` only. The running popover (`runningPopoverBody`)
> was deleted with the pill — running state is now the sidebar spinner, no running popover. See
> `docs/design-sidebar-activity-indicators.md` for the new home.

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
| **Determinate progress** | 0–100% bar + Cancel | `CopyProgressPill`; `OllamaDownloadPill` when byte-total known | shipped |
| **Indeterminate progress** | spinner + short status line | copy-cancelling; project scan; Ollama start/finish; boot "Starting sidecar" | shipped |
| **Choice / picker** | grid or radio list of options | `IconPickerPopover` (symbol grid); Ollama model picker (radio list) | shipped |
| **Dialog / confirmation** (blocking on the user) | prompt + action button(s) | 4 `.alert` sites; AI & Privacy consent sheet; OllamaDownloadPill needs-Ollama phase | shipped |
| **Terminal failure with reason** | failure buckets + reason + Copy / Show Log | diagnostic popover (`unifiedPopoverBody`) | shipped |
| **Ephemeral note** (toast) | bottom-of-window, auto-dismiss or undo | informational toast (3s); undoable-removal toast (8s) — `ToastSurface` | shipped (see toast anti-pattern) |
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
  popovers are **fixed-size** (`PipelineActivityItem.swift` ≈ 59–63: a fixed
  360×320 envelope, to dodge an NSPopover resize-animation livelock); the app
  uses `.alert` **exclusively** — never `.confirmationDialog`.

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
| `.unreachable(reason)` | _(inline sidebar glyph, not the pill)_ | greyed project row | real-condition-only |
| `.partial(kind, stages)` / `.stopped(stages)` | _(no pill/popover rendering)_ | — | not-implemented |
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
| `CopyProgressPill` | copying / cancelling | Determinate progress / Indeterminate progress | real-condition-only (drag files onto a project) |
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
idiomatic. This aligns with the shipped fixed-size (360×320) popover envelope,
which exists for a concrete reason — an NSPopover resize-animation livelock. The
one wrinkle is a carousel of differently-sized windows making the popover height
jump per page; mitigate with a stable window height or a capped height with
internal scroll. A live run-status log is legitimate native status chrome; a
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
| Failure-category enum (single source) | `bristlenose/events.py:CauseCategoryEnum`; Swift mirror at `PipelineSummary.swift::CauseCategory` |
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
