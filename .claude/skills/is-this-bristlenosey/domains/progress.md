# Domain: progress, activity, waiting

**Status: drafted.** Smoke-tested only (14 Oct 2026: three held-out questions, fresh agents, one
of them contaminated and rerun; no control arm). Claims trued against the tree the same day.

How Bristlenose tells someone that work is in flight. Inventoried 14 Oct 2026 across the CLI, build
scripts, server, SPA and Mac app (fourteen mechanisms). The governing docs:
`docs/design-desktop-project-status.md` (the sidebar row: placement, precedence, Schema E),
`docs/design-embedded-activity-routing.md` (jobs started in the web view that need native surfaces —
**an open decision**), `docs/design-sidebar-activity-indicators.md` + `design-progress-ring-estimate.md`
(the ring), `docs/design-progressive-lenses.md` §2, `docs/design-motion.md` §4.7 (shimmer),
`docs/design-cli-formatting.md` + `design-cli-just-works.md` (terminal), `desktop/scripts/REPORT-STYLE.md`
(build scripts), `docs/design-pipeline-diagnostic-popover.md` (message kinds, length budgets).

## Kinds and their siblings

Classify by three questions: **who started it** (the researcher, or automatically), **what it belongs
to** (one project, the whole app, one session, the developer's build), **where it runs** (pipeline
subprocess, serve, Swift, browser).

| Kind | Sibling | Code | Notes |
|---|---|---|---|
| An analysis run (per project) | the run's status line + ring | Python `RunProgressEvent` → events log → `PipelineRunner.applyEventProgress` → `RunProgressSubtitle.compose`; ring `ProjectRowActivityIndicator` / `SidebarActivityRing` | Run identity throughout: `run_id`, `KindEnum`, and `timing.ALL_STAGES` (the last pinned Swift↔Python by `tests/test_swift_python_contract.py`). Not reusable for work that is not a run. |
| An activity on one project that is not a run (copying in, a cloud batch) | the **activity tier** of the row | `ProjectSubtitle.resolveIdle`: adding › importing batch › copying, then deltas, then silence; text in `SidebarSubtitleText.activityText` | Yields to a run automatically (runs resolve first). Info kind: no glyph, no door (`glyphAction`/`glyphKind`). Strings `desktop.chrome.*`, all 21 locales. |
| Work started in the web view (AutoCode, catch-up, clip export) | the activity chip | `ActivityStore` → `AppLayout.chipJobs` → `ActivityChip(Stack)`, polled 2 s | Floats over the report, in the Mac too. Native routing is **open**: `design-embedded-activity-routing.md` (Strategy 1 docking recommended, unbuilt; Strategy 2 blocked because a run owns the row's slots); `docs/mockups/codebook-v2-autocode-progress.html` proposes "Tagging · 48 of 72" on the row. |
| Work in the server the Mac must show | (no settled sibling) | Swift reads serve state by polling authed routes from each project's own `ServeManager` (one serve per project, `ServeFleet`): `pollAgentPulse` (`/api/agent-activity`, 1.5 s, only while a window is visible) beside a 20 s `/api/health` poll | `ServeInstance` → `ServeManager` → `ServeFleet` re-publish every change app-wide, and the menus observe them: a republish per tick collapsed an open Window menu (20 Sep 2026). Two remedies, both used: write only on change (`ServeInstance.noteAgentCallCount`), and keep fast-changing state in a dedicated store (`PipelineLiveData` is the run's). |
| App-wide work (not one project's) | the toolbar `.status` pill | `StatusPill` | Placement rule `design-desktop-project-status.md` §4: per-project on the row, app-wide in a pill. |
| Starting up / waiting for the report | `BootView`; the server status page | `BootView`, `server/status_page.py` | Boot: an indeterminate bar and no words, deliberately; a deferred (lazy-start) window shows nothing until its serve starts. |
| A run, in the terminal | Rich status + ✓ lines | `cli.py`, `pipeline._print_stage`, `ui_kinds.cli_prefix` | Elapsed time on finished stages; one estimate after ingest; "never silent more than ~5 s without saying why". |
| Build and release scripts | `@bn` report lines; the release board | `report.sh`, `build_report.py`; `scripts/release-board.py` | Bar only with a real count; heartbeat, not a time axis. |
| Progressive arrival in the report | per-row states in the grid, lens availability | `server/progressive.py`, `ConditionStore`, `LensAvailability` | No skeletons; nothing in the lens rail shimmers. |

## Rules that come with the siblings

1. **Status lives where its subject lives.** One project → its row (and, for the key window, the
   window subtitle). The whole app → a toolbar pill. A view's own content → that view.
   (`design-desktop-project-status.md` §4.)
2. **One winner per line**: severity › causation › recency; a run beats activities; activities beat
   deltas ("+N new", missing, forked); a clean row is silent (Schema E). Never compose two states
   (sole exception `completedPartial`).
3. **The ring means hover-to-stop.** The run and copy rings swap to ✕ on hover on both sidebars; the
   cloud-batch ring and its stop exist only on the AppKit sidebar (`ProjectSidebarOutline.cellRightSlot`,
   behind `BristlenoseFlags.appKitSidebar`; the SwiftUI `ProjectRowActivityIndicator` has run and copy
   only). Exception: while a copy is cancelling, a spinner with no ✕. Otherwise, work that cannot be
   stopped from the row gets no ring.
4. **Never fake a fraction.** No fraction → spinner or no bar; a bar only with a real count or byte
   total (ring, build report, Ollama-style pills all follow this).
5. **No estimate until it is earned.** The pipeline: ≥4 prior runs for an ETA, ≥8 for a range, none
   under 10 s. A constant is not an estimate.
6. **A count is the question a closed window leaves.** "3 of 4" (cloud batch: the count *is* the
   sentence, no verb). Counts over percentages for discrete work.
7. **Terse.** Row line: `EN_LABEL_MAX = 24` in `tests/test_sidebar_status_line_contract.py` (which
   cites `ProjectRow.swift`'s "~22"); measured width 163 pt at a 220 pt sidebar
   (`design-desktop-project-status.md`, which says measurement superseded the character estimate).
   Pill ~28; toast ~60 (`design-pipeline-diagnostic-popover.md`); CLI 80 columns; build report 92
   (`REPORT-STYLE.md`).
8. **Stopping is acknowledged at once** (`isStopping`) and outranks progress everywhere.
9. **Progress is a status, not a message kind** (`ui_kinds.py`): no glyph.
10. **Privacy**: persisted progress (events, logs, telemetry) carries counts and timings, never
    names, ids, filenames or transcript text (`RunProgressEvent` docstring). On-screen rows may name
    what is being worked on (the progressive Sessions grid shows the filename being processed,
    `design-progressive-lenses.md`).
11. **Strings**: the row and titlebar are localised (21 locales, value pins); the CLI and
    App-Store-hidden diagnostics are English by decision (`design-i18n.md`).
12. **Motion**: shimmer means "thinking, no ETA", honours the animation preference and Reduce Motion.

## Open calls (siblings disagree — name them, do not choose)

- **Count vs percentage**: copy says "Copying · N%"; cloud batch and AutoCode use counts.
- **Shimmer on lines that carry a count or ETA**: the motion spec says shimmer means "no ETA", yet
  every `.running` row shimmers, as does the chip's "48/72".
- **Cancelled glyph**: the chip shows ✗ (error); cloud import uses the skipped glyph ("a red cross
  would say something went wrong").
- **Mac toasts**: retired per the popover doc, yet `ToastStore` is live for copy errors, rejections,
  feedback and alpha expiry.
- **Serve jobs on the native row**: the routing decision in `design-embedded-activity-routing.md` is open.
- **Polling**: several independent pollers at different cadences (1 s to 20 s), multiplied per
  running project; no shared rule.
- **Spellings of counts and times** differ by surface: "2 of 3" / "(2/5 files)" / "48/72"; "~N min
  left" / "~8 min (±2 min)" / "1:48".

## Worked cases

(Kept few. Some known answers are deliberately absent so the file can be tested blind.)

- **Cloud import batch on the row** (`docs/mockups/cloud-import-sidebar-progress.html`): an activity on
  one project, started by the researcher in a window that may be closed → the activity tier, count
  only ("3 of 4"), ring with hover-stop, outranks a local copy.
