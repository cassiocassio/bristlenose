# Domain: progress, activity, waiting

**Status: drafted.** Claims trued against the tree 14 Oct 2026. Tested the same night with a
control arm (three questions, three runs with this file and three without, frozen tree at
`0035fdd8`, graded blind against a rubric fixed in advance): **no measurable benefit** — mean 12.3/17
with the file, 13.0 without; the file produced both the best answer and the two worst. Cause found:
rule 1 then carried an invented clause ("a view's own content → that view") falsely cited to §4,
which pulled two runs off the row. Removed and re-tested the same night (three runs, same tree,
same grader and rubric): 16, 10, 17 (mean 14.3/17, no false claims) against the control's 13.0
(one). Better, not proven: n=3, one oracle, and one run still chose the lens, citing the
scene-strip job as the nearer sibling (correctly listing the row as an open call).

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

Every rule quotes its source, `«verbatim» — path`, and `tests/test_skill_bristlenosey.py` fails if a
quote no longer appears in the file it cites (markdown emphasis, backticks, comment markers and
line wraps are ignored). A rule with no source in the tree is labelled **Inference**: weigh it as
an argument, never as precedent.

1. **Status lives where its subject lives.** One project's work goes on its row; app-wide work in
   the toolbar `.status` zone.
   «What surfaces on a project's row is what's *scoped to that project*» — docs/design-desktop-project-status.md
   «The placement axis — per-project on the row, app-global in the title-bar pill» — docs/design-desktop-project-status.md
2. **One winner per line, and a clean row is silent.** Activities outrank the resting deltas.
   «Precedence picks a winner» — docs/design-desktop-project-status.md
   «Schema E — the clean row is silent» — docs/design-desktop-project-status.md
   «An active local copy (or its cancellation) outranks the resting date/delta.» — desktop/Bristlenose/Bristlenose/ProjectSubtitle.swift
3. **The ring is a stop control.**
   «hovering the running indicator swaps the spinner for a grey» — docs/design-sidebar-activity-indicators.md
   **Inference:** work that cannot be stopped from the row therefore gets no ring.
4. **Never fake a fraction.**
   «Never fake a fraction we don't have.» — desktop/scripts/REPORT-STYLE.md
5. **No estimate until it is earned.**
   «_MIN_N_ESTIMATE = 4» — bristlenose/timing.py
   «_MIN_N_RANGE = 8» — bristlenose/timing.py
   «if remaining_total < 10.0:» — bristlenose/timing.py
   **Inference:** a constant (a fixed minutes-per-hour figure) is not an estimate.
6. **A count is the question a closed window leaves.**
   «A count rather than a percentage or an ETA, because a count is the question a closed window leaves» — desktop/Bristlenose/Bristlenose/SidebarSubtitleText.swift
7. **Terse.**
   «EN_LABEL_MAX = 24» — tests/test_sidebar_status_line_contract.py
   «| Pill label (toolbar) | ~28 |» — docs/design-pipeline-diagnostic-popover.md
   «| Toast message | ~60 |» — docs/design-pipeline-diagnostic-popover.md
   «console = Console(width=min(80, Console().width))» — docs/design-cli-formatting.md
   «Width — target 92 cols» — desktop/scripts/REPORT-STYLE.md
8. **Stopping is acknowledged at once.**
   «PipelineProgress.isStopping is the immediate-ack contract.» — desktop/CLAUDE.md
9. **Progress is a status, not a message kind.**
   «pending/running → status, not a kind» — bristlenose/ui_kinds.py
10. **Persisted progress carries counts and timings, never identities.** (On-screen rows may name
    what is being worked on, as the progressive Sessions grid does.)
    «never an id, filename, speaker label» — bristlenose/events.py
11. **The terminal is English; the report and the Mac app are localised.**
    «CLI terminal chrome — `--help`, Rich output, checkmark lines, `man` page | **English**» — docs/design-i18n.md
12. **Shimmer means work with no estimate.**
    «indeterminate work in progress, no ETA» — docs/design-motion.md

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
