---
status: partial
last-trued: 2026-05-07
trued-against: HEAD@main on 2026-05-07 (commit 913a480)
---

> **Truing status:** Partial — schema, IA, message-kind taxonomy, fixture
> contract, and CLI vocabulary all shipped on main via `bristlenose/ui_kinds.py`
> (1ab06bf), Branch 1's `pipeline-summary-events` merge (efe4064), and fixture v4
> (913a480). Swift popover rendering rules are **pending**: Branch 2
> (`pipeline-diagnostic-pill`) hasn't implemented the SwiftUI view code yet, so
> the per-row layout, hierarchy heuristics, and Copy/Email plaintext format are
> design-only. Read this doc as authoritative spec when picking up Branch 2;
> read it as accurate-and-shipped for the rest.

## Changelog

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
`desktop/Bristlenose/Bristlenose/MessageKind.swift`. Five kinds —
anything more is over-cataloguing.

| Kind | Unicode | CLI colour | macOS tint | When |
|---|---|---|---|---|
| `success` | `✓` | `green` | `.green` | Step done as expected; "Saved"; "Copied"; cached step (with `(cached)` suffix) |
| `info` | `ℹ` | `cyan` | `.blue` | Neutral note, no action needed: "Port in use, trying 8151"; "Ollama not running"; "Themes skipped (no quotes)" if user-meaningful |
| `warning` | `⚠` | `yellow` | `.orange` | Recoverable, partial, or soft-degrade: stage with sub-failures; "inputs changed — re-running"; partial run pill |
| `error` | `✗` | `red` | `.red` | Action did not complete; user/dev needs to do something: abandoned stage; invalid API key; failed pill |
| `skipped` | `—` | `dim` | `.secondary` | Not applicable in this run: `Themes — skipped (transcribe-only)`; PII removal off |

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
| Popover row | `HStack { Text(glyph).foregroundStyle(tint); Text(label); Spacer(); Text(suffix).foregroundStyle(.secondary).monospacedDigit() }` |
| Toast (desktop) | `ToastStore.show(_, kind:)` — leading SF Symbol counterpart `.fill` variants in body type; fade after 3s |
| Sidebar glyph | `Text(glyph).foregroundStyle(tint)` at `.imageScale(.small)` trailing the row |
| Web toast (frontend) | CSS class `.toast--{kind}` mapping to the same colour palette via design tokens |

All five surfaces consult the same tables. If you add a kind, every
surface picks it up automatically — there is no per-surface override.

## Information architecture

### What goes where

| Information | Pill | Popover header | Popover row | Sidebar glyph | Toast | Copy/Email |
|---|---|---|---|---|---|---|
| Distinctive failure label ("Whisper timeouts") | ✓ | ✓ | — | — | — | ✓ |
| Project name | — | ✓ | — | — | — | ✓ |
| Run timestamp range | — | ✓ | — | — | — | ✓ |
| Per-stage outcome (verbatim CLI string) | — | — | ✓ | — | — | ✓ |
| Per-stage duration | — | — | ✓ | — | — | ✓ |
| Per-session cause (short, category-derived) | — | — | ✓ (sub-row) | — | — | ✓ |
| Raw `cause.message` (≤4 KB) | — | — | tooltip via `.help(...)` | — | — | ✓ |
| App version + OS + commit | — | — | — | — | — | ✓ (trailer) |
| Persistent run-state indicator | — | — | — | ✓ | — | — |
| Ephemeral confirmations ("Saved") | — | — | — | — | ✓ | — |

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

- **Top level** — one row per pipeline stage (always one of the five
  kinds). Verbatim CLI string + duration trailing.
- **Sub-rows** — per-session cause lines, indented ~3 chars, no leading
  glyph (inherits parent stage's kind). Render only when the parent is
  `warning` or `error`.
- **Nest under DisclosureGroup** only when the parent stage has ≥3
  child failures. ≤2 inline. ≥3 collapsible, expanded by default for
  failed stages.
- **Skipped** rows render once with `—` and the `skipped` suffix. No
  sub-rows.
- **Overflow placeholder** — when a stage failed >10 sessions, the wire
  carries 10 real failures + 1 sentinel `StageFailure` (session_id=null,
  category=unknown, message starts `"... and "`). Render as one muted
  summary row at the bottom of the stage's sub-rows: `— and N more`,
  `.secondary` foregroundStyle. Detection: `failure.sessionID == nil &&
  failure.cause.message.hasPrefix("... and ")`. Lock the contract via
  the `run_completed_partial_truncated` fixture scenario.

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
- **Don't reach for SF Symbols inside the popover.** The popover and
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

## Implementation references

| Area | File |
|---|---|
| Kind enum + glyph/colour tables (Python) | `bristlenose/ui_kinds.py` |
| Kind enum + glyph/tint properties (Swift) | `desktop/Bristlenose/Bristlenose/MessageKind.swift` |
| CLI status helpers | `bristlenose/pipeline.py:131–171` (`_print_stage` + `_print_step` / `_print_warn_step` / `_print_error_step` / `_print_cached_step` wrappers); `bristlenose/cli.py` `_say()` for ad-hoc status lines |
| Cross-language schema fixture | `tests/fixtures/pipeline-summary-contract.json` |
| Pipeline summary Pydantic model | `bristlenose/events.py` (`PipelineSummary`, `StageOutcome`, `StageFailure`) |
| Failure-category enum (single source) | `bristlenose/events.py:CauseCategoryEnum` |
| Swift popover bodies | `desktop/Bristlenose/Bristlenose/PipelineActivityItem.swift` |
| Sidebar subtitle / glyph | `desktop/Bristlenose/Bristlenose/ProjectRow.swift:165–217` |
| Plaintext diagnostic formatter | `formatDiagnosticPlaintext(state:project:summary:)` (in `PipelineActivityItem.swift`) |
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
