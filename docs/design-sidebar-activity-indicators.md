# Per-project activity indicators (sidebar) — design

**Status:** Proposal, pre-implementation (14 Jun 2026). TestFlight scope = the visual layer only.

Mockup: `docs/mockups/sidebar-activity-indicators.html` (animated timeline — small + large run on a
sped-up clock).

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
| **Display** | rows show pipeline state as subtitle *text* + `.scanning` spinner + red failure prefix; no `.running` motion, no per-row copy signal | `ProjectRow.swift` |
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

| State | Sidebar element | Shipped as | Source |
|---|---|---|---|
| running (progress known) | **determinate ring (pie)** — Welford ETA-weighted, falls back to stage N/10 | known/unknown switch | `OllamaDownloadPill.swift` |
| running (progress unknown) / scanning | indeterminate spinner | `ProgressView().controlSize(.small)` | `PipelineActivityItem.swift` |
| copying | determinate ring (byte ratio) | `ProgressView(value:)` | `CopyProgressPill.swift` |
| failed | red `xmark.circle.fill` | `MessageKind.error` | `MessageKind.swift` |
| finished with failures | orange `exclamationmark.triangle.fill` | `MessageKind.warning` | `MessageKind.swift` |
| queued / stopped / partial | subtitle text only, no glyph | `subtitleVariant.pipelineText` | `ProjectRow.swift` |
| idle / ready | nothing (date + session count) | existing | `ProjectRow.swift` |
| project identity | chosen SF Symbol in leading slot | `project.icon` | `ProjectRow.swift` |
| folder | folder icon + chevron; **collapsed folder shows aggregate of children** | `FolderRow` / `SidebarItem` | `ProjectIndex.swift` |

Hard rules honoured: motion = healthy / static colour = attention; `MessageKind` is the authoritative
glyph+colour source; absence is information (idle rows stay quiet); sidebar rows are read-only.

## Determinate progress — surface what's measured, don't re-measure

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
3. else `stageIndex / 10` → coarse ring + "Stage N of 10". *(Phase 0a — needs no channel change.)*
4. else (uncalibrated first run / variable-shape cluster+theme stages) → spinner.

**Single source, two render sites:** the toolbar pill and the sidebar ring both consume
`PipelineLiveData.progress[id]`; the sidebar adds a consumer, not a second progress model.

## Phase 0a / 0b

- **Phase 0a (no channel change):** relocate the glance to the sidebar + render the determinate ring at
  rung 3 (`stageIndex / 10`, already crosses) with spinner fallback. Pure display.
- **Phase 0b (small channel-widening):** surface Welford ETA + session fraction (rungs 1–2) via the
  structured events file — plumbing over existing computation, no re-measurement.

### Phase 0b spec — events-channel widening

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

Projects render their chosen SF Symbol; folders render a folder icon + chevron. A **collapsed folder
shows an aggregate indicator** (spinner if any child is running, red glyph if any failed, else nothing)
— a pure function of children's `state`. A collapsed folder is still a visible row, so it earns
compensation; whole-sidebar collapse does not (standing decision — no compensating chrome).

## Controls

Sidebar rows are read-only. A project's Stop / Retry / Show-diagnostic live in a **right-click row
context menu** — the status line says "investigate me," and the native macOS response is right-click.
**Selecting** a project routes the detail to the **main content window**, which owns the explain-and-act
surface (room for a status banner etc., future). No inline chrome, no route-to-fix buttons on the row.

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
- A real Cmd+R run shows idle → scanning → running (determinate ring + terse text) → ready; failure →
  red glyph; partial → orange glyph.
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
