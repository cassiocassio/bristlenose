---
status: partial
last-trued: 2026-06-18
trued-against: HEAD@progress-text-surfacing on 2026-06-18
---

# Per-project activity indicators (sidebar) — design

> **Trued 2026-06-18** against `progress-text-surfacing`. **Phase 0b shipped** — the
> determinate ETA ring landed in `010910a` ("desktop: determinate ETA progress ring in the
> sidebar (phase 0b)"), and its deferred **progress-text tier** shipped on this branch: the
> running-row subtitle now reads e.g. "Transcribing · 2 of 3 · <1 min left" via the pure
> `RunProgressSubtitle` composer (`desktop/Bristlenose/Bristlenose/RunProgressSubtitle.swift`),
> degrading to "Analysing · <1 min left" then "Analysing…". The earlier (2026-06-15) truing
> described 0a's spinner-only state and banner-marked the ring + events-channel as "0b,
> unbuilt"; **those banners are flipped to shipped reality below.** The 0b *plan* prose is
> preserved (it's still the design rationale) — what changed is "built", not the design.
> **Still aspirational:** Phases 1–3 (concurrent execution, multi-window, global-concern
> unification) and the collapsed-folder aggregate.

**Status:** Phase 0a shipped 15 Jun 2026 (`b3bbaab..518e6d3`); Phase 0b shipped (ring
`010910a`, 17 Jun; progress-text tier 18 Jun); Phases 1–3 aspirational. TestFlight scope =
the visual layer only.

Mockup: `docs/mockups/sidebar-activity-indicators.html` (animated timeline — small + large run on a
sped-up clock). The mockup's determinate ring + ticking progress text now match shipped 0b.

## Shipped in Phase 0a (ground truth, `b3bbaab..518e6d3`)

What actually landed on the `per-project-activity` branch — the rest of this doc is the
surrounding plan, parts of which are deferred (see banners):

- **Per-project run indicator** on the sidebar row: an **indeterminate spinner**
  (`ProgressView().controlSize(.small)`) while running/scanning — *not* a determinate ring.
  New pure view `ProjectRowActivityIndicator.swift`, addressed by `project.id`.
- **Hover-to-stop:** hovering the running indicator swaps the spinner for a grey
  `xmark.circle.fill` (×) in a fixed 16pt container (crossfade, Reduce-Motion-aware); click →
  `PipelineRunner.cancel(project:)`. (`ProjectRowActivityIndicator.swift`)
- **Failure glyph → diagnostic popover:** `.failed`/`.failedWithDiagnostic` → red
  `xmark.circle.fill`; `.completedPartial` → orange `exclamationmark.triangle.fill`
  (MessageKind, "Finding 13"). The glyph is a `Button(.plain)` → selects the row + opens
  `ProjectDiagnosticPopover` anchored to the glyph (`arrowEdge: .trailing`). The popover was
  **extracted** from the deleted toolbar pill into its own reusable view
  (`ProjectDiagnosticPopover.swift`, commit `02ad258`). "Show Log" inside it is gated on a
  real log file existing.
- **Stop backstops:** row context-menu "Stop Analysis" + "Show Diagnostics…"
  (`ContentView.swift`), and **Project-menu "Stop Analysis" with ⌘.** (`MenuCommands.swift`,
  gated by `BridgeHandler.selectedProjectIsRunning`).
- **Toolbar pill removed:** the per-project pipeline pill (`PipelineActivityItem.swift`) was
  **deleted** (commit `8ffa470`); the per-project glance now lives on the row. Only
  `OllamaDownloadPill` + `CopyProgressPill` remain in the toolbar (app-global concerns).

**Shipped in Phase 0b (`010910a` + `progress-text-surfacing`):** the determinate ETA ring
(`ProjectRowActivityIndicator` → `ProgressView(value:)`, monotonic + asymptote-clamped by
`RunProgressMath`), the `run_progress` events channel (Python `RunProgressEvent` →
`EventLogReader.latestProgress` → 1 Hz poll in `PipelineRunner`), and the **progress-text
tier** (`RunProgressSubtitle` composes stage · N-of-M · ETA into the row subtitle +
VoiceOver phrase + tooltip). Report auto-reload-on-completion also landed (`d277017`,
`c11f68c`).

**Still deferred:** the collapsed-folder aggregate indicator, copy-on-row, the during-run
*detail-pane* surface (the detail pane still shows the server "Nothing to see here, yet."
page on a first run), and everything in Phases 1–3.

## Problem

Two tangled problems:

1. **Toolbar hygiene** — multiple ambient pills (pipeline / copy / model-download) crowd the toolbar.
2. **Per-project visibility** — the toolbar pipeline pill only ever describes the *selected* project,
   so you can't see at a glance which *other* projects are running, queued, copying, or failed.

The organizing principle that resolves both: **status lives where its subject lives.** A pipeline run
belongs to a project → it shows on that project's sidebar row. A model download (Ollama/Whisper)
belongs to the app → it stays in the toolbar. Moving the pipeline indicator "to the logical part of
the screen" both surfaces per-project state and declutters the toolbar.

## Scope

**TestFlight = the visual layer only** (Phase 0): per-project progress visible in the sidebar; global
progress (e.g. model download) in the toolbar. No execution rearchitecture, no multi-window. The
display is built **forward-compatible** so later phases need no UI rework.

Post-TF, sequenced and named (not built here):
- **Phase 1** — concurrent pipeline execution (lift the single-slot FIFO).
- **Phase 2** — concurrent serve / multi-window (the Notes/Word model: single-click switches in place,
  double-click opens a project in its own window = two live SPAs).
- **Phase 3** — global-concern unification (a single "Background" toolbar pill).

## The three axes (state today)

| Axis | Today | Evidence |
|---|---|---|
| **Display** | _(pre-0a baseline)_ rows showed pipeline state as subtitle *text* + `.scanning` spinner + red failure prefix; no `.running` motion. **0a shipped `.running` spinner + hover-× + clickable failure glyph** (`ProjectRowActivityIndicator.swift`) | `ProjectRow.swift` |
| **Concurrent execution** | single-slot FIFO; one `bristlenose run --no-serve` subprocess at a time | `PipelineRunner.swift` |
| **Concurrent serve** | one sidecar/port; selecting a project tears down + restarts serve | `ServeManager.swift` |

Foundation already in place: per-project SQLite DBs (WAL — zero cross-project write contention);
pipeline and serve are already separate subprocesses; the Python pipeline core is concurrency-safe
across projects (no global singletons, per-output-dir PID lock); Ollama/copy are already async +
decoupled. **Viewing is inherently single** (one content area) → serve can stay single-for-selected;
serve(Z) + run(X) already coexist. So the gap to "X,Y active in sidebar, Z served" is **display +
concurrent execution**, not concurrent serve.

## Visual vocabulary (reuse, do not reinvent)

The sidebar inherits the toolbar/popover vocabulary that already ships:

Shipped 0a, or 0b where marked _(0b, now built)_:

| State | Sidebar element | Shipped as | Source |
|---|---|---|---|
| running | _(0b)_ **determinate ETA ring** + subtitle progress text ("Transcribing · 2 of 3 · <1 min left"), spinner only until the first measured signal | `ProgressView(value:)` + `RunProgressSubtitle` | `ProjectRowActivityIndicator.swift`, `ProjectRow.swift` |
| scanning | transient indeterminate spinner (pre-run, after 250 ms) | `ProgressView().controlSize(.small)` | `ProjectRow.swift` |
| running, hovered | spinner swaps → grey `xmark.circle.fill` (×) in fixed 16pt frame; click → `cancel(project:)` | `Button(.plain)`, crossfade, Reduce-Motion-aware | `ProjectRowActivityIndicator.swift` |
| copying | determinate ring (byte ratio) — _toolbar pill only; copy-on-row is post-TF_ | `ProgressView(value:)` | `CopyProgressPill.swift` |
| failed | red `xmark.circle.fill`, clickable → diagnostic popover | `MessageKind.error` | `MessageKind.swift`, `ProjectRow.swift` |
| finished with failures (`.completedPartial`) | orange `exclamationmark.triangle.fill`, clickable → diagnostic popover | `MessageKind.warning` | `MessageKind.swift`, `ProjectRow.swift` |
| failure glyph clicked | selects row + opens `ProjectDiagnosticPopover` anchored to glyph (`arrowEdge: .trailing`) | `Button(.plain)` + `.popover` | `ProjectRow.swift`, `ProjectDiagnosticPopover.swift` |
| queued / stopped | subtitle text only, no glyph | `subtitleVariant.pipelineText` | `ProjectRow.swift` |
| idle / ready | nothing (date + session count) | existing | `ProjectRow.swift` |
| project identity | chosen SF Symbol in leading slot | `project.icon` | `ProjectRow.swift` |
| folder | folder icon + chevron. _(0b: collapsed folder aggregate — not shipped, see Folders.)_ | `FolderRow` | `FolderRow.swift` |

Hard rules honoured: motion = healthy / static colour = attention; `MessageKind` is the authoritative
glyph+colour source; absence is information (idle rows stay quiet). _Note on "read-only": the row's
**text** is read-only, but 0a added two click targets in the trailing slot — the hover-× and the
failure glyph — consistent with `feedback_sidebar_row_chrome_is_readonly` (tap targets = the row +
detail-of-this-row segments)._

## Determinate progress — surface what's measured, don't re-measure

> **Shipped in Phase 0b (`010910a` + `progress-text-surfacing`).** This section is now built,
> not plan: the ETA-weighted ring (`RunProgressMath`), the honesty rules (monotonic +
> asymptote), the best-available ladder, and the two-render-sites claim (ring + subtitle text)
> all ship. **One correction from the plan:** the `run_progress.stage` field carries
> `timing.py ALL_STAGES` — the estimator's six *coarse* ids (`transcribe`, `speakers`,
> `topics`, `quotes`, `cluster`, `render`) — NOT the finer `manifest.py STAGE_ORDER` the plan
> implied; `RunProgressSubtitle.knownStages` mirrors the six (a unit test pins them). The
> within-stage **session fraction** ("N of M") is emitted per-file during transcription
> (`pipeline.py` `_on_transcribe_progress`, not estimator-gated); the **ETA** comes from the
> Welford estimator at stage boundaries (gated on calibration). A *cached* run that skips
> transcription emits only the initial post-ingest estimate (`stage=None`) → the text reads
> "Analysing · <1 min left".

The measurement layer is built and calibrated; the gap is the channel + render, not the maths.

- **Already computed in Python:** Welford ETA per stage with ±band, persisted + calibrated across runs
  (`timing.py`, `~/.config/bristlenose/timing.json`); 10-stage canonical order (`manifest.py
  STAGE_ORDER`); per-session completion (`mark_session_complete`); counts; structured terminus events.
- **Crosses to Swift today (narrow):** only `✓ ` stdout lines → `stageIndex` + `stageName`.
  `sessionsComplete/Total` exist on `PipelineProgress` but are never populated; the Welford ETA is
  printed as prose, never parsed; the events file is read terminus-only.

**The pie fills by Welford ETA-weighted completion (time, not stage-count)** — stages are wildly
unequal (transcription dominates), so a stage-count pie would lie. Two honesty rules: **monotonic**
(when the estimate revises up, the ring never runs backwards — only the "~N min left" text updates) and
**asymptote** (cap ~95–99% until the terminus event, so an over-running estimate reads "nearly there,"
not a stalled 100%).

**Text vs pie:** the pie encodes *time*; the **text** carries the discrete markers — stage ("Stage 4"
/ stage name), per-session fraction ("Transcribing — 3 of 8"), and the estimate ("~4 min left"). The
text ticking over is itself a liveness signal. Same `PipelineProgress` + ETA feed both.

**Best-available ladder (mirrors the shipped `OllamaDownloadPill` known/unknown switch):**
1. Welford ETA-weighted ring + "~N min left" (when calibrated).
2. else within-stage session fraction → ring + "N of M sessions".
3. else `stageIndex / 10` → coarse ring + "Stage N of 10".
4. else (uncalibrated first run / variable-shape cluster+theme stages) → spinner.

> **Correction (trued 2026-06-15):** the original plan labelled rung 3 as "Phase 0a — needs no
> channel change." That is **not** what shipped — **0a shipped rung 4 (the plain spinner)** and
> deferred all determinate rendering (rungs 1–3) to 0b. The coarse `stageIndex/10` ring was never
> built.

**Single source, two render sites:** the toolbar pill and the sidebar ring both consume
`PipelineLiveData.progress[id]`; the sidebar adds a consumer, not a second progress model.

## Phase 0a / 0b

- **Phase 0a (shipped, `b3bbaab..518e6d3`):** relocate the glance to the sidebar + render the
  **indeterminate spinner** for running/scanning, with hover-× Stop and the clickable failure-glyph
  popover. Pure display, no channel change. _(The plan originally proposed a coarse `stageIndex/10`
  determinate ring here; that was dropped — see the correction above.)_
- **Phase 0b (shipped — `010910a` ring + `progress-text-surfacing` text):** surfaces Welford ETA
  + session fraction (rungs 1–2) via the structured `run_progress` events file — plumbing over
  existing computation, no re-measurement. The ring fills by time (`predictedTotalSeconds`) or
  within-stage fraction; the coarse `stageIndex/10` ring (rung 3) was **not** needed and not
  built. The text tier (`RunProgressSubtitle`) renders the same ladder as words.

### Phase 0b spec — events-channel widening

> **Shipped (`010910a` + `progress-text-surfacing`).** The spec below landed largely as
> written: `RunProgressEvent` in `bristlenose/events.py`, emitted via `RunHandle.progress`
> (`run_lifecycle.py`) from `pipeline.py` hooks; consumed by `EventLogReader.latestProgress`
> + the 1 Hz poll in `PipelineRunner`, folded into the ring by `RunProgressMath` and into the
> subtitle by `RunProgressSubtitle`. Deltas from the spec: the `stage` field uses the
> estimator's six coarse ids (see the correction above), and the localised stage verb lives
> Swift-side under `desktop.chrome.pipeline.stage.<id>` (not `desktop.pipeline.stage.<id>`).

Plumbing + render, not new measurement. The writer (`append_event`, O_APPEND+fsync) and reader
(`EventLogReader`) exist; `timing.py`'s docstring already anticipates it ("a future visual UI can
consume the same data via the PipelineEvent callback").

**Python — emit:**
1. `events.py`: add `EventTypeEnum.RUN_PROGRESS = "run_progress"` + `RunProgressEvent(_EventBase)` with
   all-optional-where-unknown fields: `stage` (canonical id), `stage_index`, `stage_count`
   (= `len(STAGE_ORDER)`), `sessions_complete/total`, `eta_seconds/eta_stddev_seconds`,
   `predicted_total_seconds`, `elapsed_seconds`.
2. `append_event(...)` at hooks that already fire in `pipeline.py`: after-ingest initial estimate; each
   stage boundary (`_emit_remaining_estimate`); each `mark_session_complete`. Welford values come off
   the existing `Estimate` — no new maths.
3. Throttle: per-stage + per-session only (~tens of lines/run), never per-stdout-line; keep events lean
   to stay well under Swift's 64 KB tail window.

**Swift — consume (extend `EventLogReader` terminus-only → live):**
4. Add `run_progress` to the Swift `EventType` mirror + new optional `Event` fields (schema-additive;
   `try?` decode already skips unknown lines).
5. `latestProgress(at:for:)` reads the bounded tail for the newest `run_progress` of the active run.
6. Observe the events file while a run is active (DispatchSource file-watch or ~1s poll); keep the
   `✓`-stdout parse as a coarse fallback.
7. Populate the new `PipelineProgress` fields; apply the honesty rules client-side (interpolate elapsed
   locally between events).
8. i18n: localize stage id → verb Swift-side (`desktop.pipeline.stage.<id>`); English-first for TF.

## Sidebar width + truncation

Current: `.navigationSplitViewColumnWidth(min: 180, ideal: 220, max: 300)`; title + subtitle
`.lineLimit(1)`. **Some truncation is expected and acceptable** — names always truncate (user-set,
unbounded), status sometimes; the full text lives in the row tooltip. The determinate ring lets the
status text be terse (markers + ETA, no restated verb), which fits the narrow column. **German /
long-locale width is not a TF concern** — tune the TF default against the real *English* strings; lay
out against the real in-code strings (never lorem ipsum). The exact progress copy is a separate copy
pass. Default ideal stays ~220–240, resizable + persisted; collapse = `NavigationSplitView` hide.

## Cloud (out of this branch — availability, already settled)

Cloud-evicted is a `ProjectAvailability` concern, **not** an activity indicator. Only iCloud is
introspectable, and only coarsely (`ubiquitousItemDownloadingStatusKey`); `percentDownloaded` is
deprecated and third-party File Providers are opaque — no reliable progress to show. Shipped posture
(commits `e4037d5`, `b0ed701`): detect iCloud-eviction, render a static outline `icloud` glyph
(status-only, no click), let macOS fetch transparently on open. Dropbox / Google Drive are not
special-cased — that's the user's relationship with their cloud provider, not ours. A determinate
"Downloading X of Y" + Cancel was proposed and walked back earlier. **No active "Fetching…"
indicator.** The activity-indicator work must not touch the cloud/availability path.

## Folders

Projects render their chosen SF Symbol; folders render a folder icon + chevron.

> **Aspirational — NOT shipped in 0a.** `FolderRow.swift` renders name + folder icon + rename only;
> no aggregate state logic. The plan below stands as the intended behaviour.

A **collapsed folder
shows an aggregate indicator** (spinner if any child is running, red glyph if any failed, else nothing)
— a pure function of children's `state`. A collapsed folder is still a visible row, so it earns
compensation; whole-sidebar collapse does not (standing decision — no compensating chrome).

## Controls (as shipped, `b3bbaab..518e6d3`)

The row's **text** stays read-only; controls reach the running/failed run three ways, no inline button
chrome on the row body:

- **Stop a run:** (1) hover the spinner → it becomes the × (fast path, mouse); (2) **right-click row →
  "Stop Analysis"** (works for any project incl. non-selected/queued; hidden when not running, per
  context-menu HIG); (3) **Project menu → "Stop Analysis" ⌘.** (acts on the selected project; *dimmed*
  when it isn't running). ⌘. is the canonical macOS stop. (`ProjectRowActivityIndicator.swift`,
  `ContentView.swift`, `MenuCommands.swift`)
- **Diagnose a failure:** click the failure glyph (selects the row + opens `ProjectDiagnosticPopover`
  anchored to the glyph), or **right-click row → "Show Diagnostics…"**. The popover carries the
  per-stage breakdown, Copy, and a "Show Log" button gated on a real log file existing.
- **Retry / Re-analyse is NOT a row affordance** — "Re-analyse…" is a Project-menu item (currently
  `.disabled`, future Phase 2+); it is not in the row context menu. _(The original plan listed "Retry"
  in the row context menu — that did not ship.)_

Future: **selecting** a project may route an explain-and-act surface to the main content window (room
for a status banner etc.) — not built; the glyph popover is the shipped failure surface.

## Forward-compatibility contract (Phase 0 must not preclude Phases 1–2)

- **Address state by `project.id`, never "selected"/"current."** The indicator is a pure function of
  one project's `state[id]`; Phase 1 (N runs) and Phase 2 (N windows) just read more of the same dict.
- **Keep execution/display state owners App-level singletons** (`PipelineRunner`, `CopyMachinery`,
  `OllamaDownloadModel`, `ProjectIndex`); only `ServeManager` becomes per-window in Phase 2.
- **`IndicatorKind` is a pure exhaustive `switch`** — adding a case later is compiler-forced.
- **Controls via row context menu**, not a selection-scoped toolbar popover only (Phase 2 "selected" is
  per-window).
- **Don't touch serve in Phase 0.**
- **Folder aggregate is a pure function of children's states.**

## Acceptance / verification (Phase 0)

- Debug gallery renders each indicator; motion-vs-static legible at a glance.
- A real Cmd+R run (fresh transcription) shows idle → scanning → running with the **determinate
  ETA ring** + the **progress-text ladder** ("Transcribing · 2 of 3 · <1 min left" → "Identifying
  speakers · …" → "Finding topics · …") → ready; failure → red glyph; partial → orange glyph.
  Hovering the running ring reveals the × (Stop); clicking a failure glyph opens the diagnostic
  popover. **Caveat:** a *cached* run (transcripts already present) emits only the initial estimate,
  so it reads "Analysing · <1 min left" throughout — and the **bundled sidecar must be rebuilt**
  (`build-sidecar.sh`) to a version that emits `run_progress`, or both ring and text stay at their
  indeterminate floor (the whole 0b channel was latent on desktop until the sidecar was rebuilt).
- Idle/ready/cloud rows visually unchanged; whole-sidebar collapse adds no compensating chrome.
- VoiceOver announces state via the subtitle path; the ring is `accessibilityHidden`. The
  `accessibilityLabel` is extended to include pipeline state (name → state → counts).
- Debug-gallery scheme env var committed `isEnabled = "NO"`; `xcodebuild test` green.
- QA via the worktree's `.app` (visual), not preview tools.

## Edge cases (stress-test set)

First-run no-calibration (coarse ring vs spinner); estimate overrun (asymptote / escalate text);
cancel mid-run (context-menu Stop; ring freeze vs clear); rename mid-run (live name); whole-sidebar
collapse (no compensation); cloud fetch stall (availability failure ≠ pipeline failure); copy +
pipeline on the same project (precedence); many concurrent runs (cap visible motion, Phase 1);
indeterminate-within-determinate stages; queue depth + reorder; Reduce Motion (spinner → static);
very short runs (suppress below threshold); quit/relaunch mid-run (orphan attach, ETA re-baseline);
accessibility ordering; two progress kinds one shape (copy bytes vs pipeline time).

## References

- `docs/mockups/sidebar-activity-indicators.html` — animated timeline mockup.
- `docs/design-project-sidebar.md` — row anatomy.
- `docs/design-pipeline-diagnostic-popover.md` — `MessageKind` taxonomy.
- `docs/design-motion.md` — motion vocabulary.
- `docs/design-multi-project.md` — multi-project scope.
- Commits `e4037d5`, `b0ed701` — cloud-evicted shipped decisions.
