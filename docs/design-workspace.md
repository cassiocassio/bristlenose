---
status: pending
last-trued: 2026-08-15
---

> **Pending / aspirational.** Forward-looking design (post-TestFlight multi-project + multi-window). The **serve/view family (A/B/C) is still open**; several *window-level* decisions were taken 15 Aug 2026 and are marked as such in §"Effectively decided vs genuinely open". The "What shipped" section names the A1/A2 increments already on the path (verified against shipped Swift); the rest is not built. Check `TODO.md` / `docs/ROADMAP.md` for status.

## Changelog

- _2026-08-15_ — **Window-level decisions taken; the big architectural call still open.** (1) New §"What a window opens onto": double-click opens *that project* — the Notes model, answering the open question this doc used to end on — and a window restores the **lens** plus an **anchor**, never a pixel offset and never search/filter, from `projects.json`. (2) New §"The command that opens a window": `Window ▸ Bristlenose` becomes `File ▸ New Window` (⌥⌘N), per the HIG's own menu-bar standards; records the missing `applicationShouldHandleReopen` this exposes. (3) Stage 3 split into **3a** (per-window `BridgeHandler`, same-project windows — needs no family call) and **3b** (per-window serve — blocked on A/B/C), because 3a is what actually buys "Quotes here, Analysis there" and is reachable today. (4) New constraint 5: with two windows open the title bar can name a project that isn't on screen — observed, not predicted by the blocker list. Family A/B/C unchanged and still open.

- _2026-07-28_ — **Stage 1 of window-scoping shipped** (see §"Window-scoping the menu commands" below): View ▸ Hide/Show Projects is now per-window via the app's first `focusedSceneValue` seam (`SidebarVisibilityFocus.swift`), replacing a `NotificationCenter` broadcast that toggled every open window. `BridgeHandler.sidebarVisible` and the `.toggleProjectsSidebar` notification are deleted. The remaining **16** menu broadcasts are unchanged and still fire in every window — the staged plan for them is the new section. Doc otherwise still aspirational.
- _2026-06-21_ — added front-matter (`status: pending`) + pending banner on the day the doc was created; confirmed the "What shipped" A1/A2 increments verify against shipped Swift (`ServeManager.swift` single `parked` slot, `generation` token reused; A1 cancel-on-switch modal gone). Currency fix: §"What shipped" called `warm-sidecar-pool` "pending merge" — it merged the same day (`78b2d40`). Body otherwise unaltered (aspirational by design).

# Workspace — genuine multi-project + multi-window (post-TF)

**Status:** Problem definition + option range. The end goal is fixed; the
**architecture is open** — the serve/view family (A/B/C) is the one big call and is
deliberately unmade here. What *has* been decided since is window-level and local:
what a window opens onto, what restores, and the command that creates one. Those are
marked in §"Effectively decided vs genuinely open"; everything else remains the
"promote to a design doc when post-TF planning starts" artefact that the planner's
Workspace item pointed at.

This supersedes the earlier one-line sketch's *assumption* (one serve process
serving N mounted projects) — see "What we now know" — but keeps its bones: the
reader/worker idea (now one option among several), CLI ≡ desktop parity, and the
"when + how, not whether" framing.

## End goal (fixed)

**Multi-project in the most genuine sense a user expects, and multi-window with
it.** The yardstick is every other real multi-thing app — a browser's tabs, an
IDE's windows, Finder, Music:

- Many projects open at once, visible, switchable.
- Switching between them is **instant** — like a browser tab or an app window, not
  a load. (Switch-back already feels *fast* post-A2; the bar is *instant*.)
- Multiple projects can be **doing things at once** — N analyses running in
  parallel, not one-at-a-time-with-the-rest-blocked.
- **Multi-window** — open projects in separate windows, side by side, compare,
  drag between.
- Each project's **state persists** across a switch (scroll, selection, view) —
  you left it where you left it.
- **No modal friction** — never "stop the current thing to look at another."

Multitasking has been a settled user expectation for decades (the 1989 OS/2 Warp
"juggling" ad is the canonical artefact). The cohort tells us about the *analysis*
surface (quote / theme / tag / signal quality); they do not tell us about
concurrency architecture — so this is a **when + how, not whether** question, owned
by engineering judgement, not cohort feedback.

## What shipped (the increments already on the path)

- **Phase A1 — view-freedom** (`background-runs-view-switch`): a run continues in
  the background while you switch to view another project; the cancel-on-switch
  modal is gone. Pipelines are independent `--no-serve` subprocesses with
  per-project WAL DBs.
- **Phase A2 — warm-sidecar pool** (`warm-sidecar-pool`, merged 21 Jun 2026): switching
  *back* to the previous project re-points to a parked, still-running sidecar
  instead of teardown+restart — kills the boot wait and the rapid-switch crash.
  **Single parked slot** (current + most-recent-previous), not an N-pool.

A1+A2 deliver *fast, crash-free* switching for the A↔B case. They do **not**
deliver the end goal: switching is fast-not-instant, only one prior project is
warm, runs are still effectively single-slot, and it's single-window.

## What we now know (constraints that reframe the architecture)

These are established facts (verified during A2), not assumptions:

1. **The serve sidecar is single-project-per-process.** `create_app(project_dir)`
   binds a per-project DB (`db_url_for_project`), startup importer, event watcher,
   and media routes at startup. A running sidecar **cannot** be re-pointed at
   another project. ⇒ The earlier "one serve process, N projects mounted" sketch
   is **not how the server works today** — it implies a real server
   re-architecture, not just a Swift change. This is the single biggest open call.
2. **Warm *server* ≠ warm *view*.** A2 keeps the Python server alive, but the
   WebView still cold-mounts the SPA on switch (required by the per-sidecar token +
   per-project isolation). Browser-back-*instant* needs the rendered **view**
   retained, not just the server. Full tier model + the WebKit-vs-Safari reasoning:
   `docs/design-desktop-switch-performance.md`.
3. **Memory is the governing cost.** Each warm sidecar is a Python process (~70–90
   MB) and each retained WebView is a live WebKit content process + a rendered
   heap. N of each, on the 8 GB Apple-Silicon floor, is real pressure — any
   "N live" model needs a small cap + eviction.
4. **The plumbing is settled and reusable:** `bind(0)` kernel-assigned ports, the
   sidecar's own parent-death watcher (self-terminate on host death), and the
   single `generation` ownership token. Any new model must keep these contracts.
5. **With two windows open, the title bar can name a project that isn't on screen.**
   Observed 15 Aug 2026: two windows titled `bn-eviction-test` and `project-ikea2`,
   both rendering the same content (38 quotes, 10 signals, identical sections).
   Selection is `@State` and therefore *already* per-window, so each title names its
   own sidebar pick — but the content comes from the single fronted sidecar, so at
   most one of those titles is true. This is blocker 2 below surfacing as a
   **truthfulness** failure rather than a convenience one, and the blocker list did
   not predict it. It sharpened the same day the window subtitle gained a folder
   disambiguator and live run state: the title is now more specific, and therefore
   more credible, on a window that may be showing something else entirely. The
   consequence for sequencing is that multi-window cannot ship half-done — a window
   that lies about which study it shows is worse than a window you can't open.

## Problem definition

Today the desktop is **project navigation chrome**: a sidebar holds many projects,
exactly one is *fronted* (served + viewable), switching is a per-switch sidecar
lifecycle event, and only one pipeline runs at a time. The gap to the end goal has
four independent dimensions, each currently at "one":

| Dimension | Today | Genuine multi-project |
|---|---|---|
| **Viewable at once** | 1 fronted | N mounted, switch is instant |
| **Warm (no re-load)** | 1 parked (A2) | all open projects |
| **Running at once** | 1 (A1 backgrounds it) | N in parallel (capped) |
| **Windows** | 1 | N, side-by-side |

The job is to lift each from "one" to "N" **without** regressing isolation
(per-project token + ephemeral store), the local-first contract, or 8 GB-floor
viability — and keeping CLI ≡ desktop parity (one codebase, packaging differences
only; `docs/design-modularity.md`).

## Implementation options (undecided — the range, with trade-offs)

The central open question: **how do N projects become live + instantly
switchable?** Three families, each composable with the orthogonal decisions below.
None is chosen here.

### Family A — N single-project sidecars + N retained WebViews (extend A2)

Each project keeps its own `bristlenose serve` process (today's model) AND its own
retained, fully-rendered WebView; switching = show/hide the right window/view.
- **For:** no server re-architecture (builds straight on A2 + the warm pool);
  isolation is free (each sidecar already its own origin/token/store); a retained
  view never re-points, so the per-sidecar-token problem simply doesn't arise.
- **Against:** heaviest on memory (N processes + N WebViews); needs a view-pool
  manager outside SwiftUI's `.id`-recreation lifecycle + shared eviction with the
  sidecar pool; staleness handling (a parked view is frozen as-of-park).

### Family B — one multi-project serve + one/few WebViews (the original sketch)

Re-architect `create_app` to mount N projects (path-mapped `/report/{slug}/`,
per-project DB/importer/watcher behind one process); switching = URL change.
- **For:** process-light (one server); "switching is free" is just navigation;
  closest to the browser mental model.
- **Against:** significant server rework (single-project bindings → multi-tenant;
  the ~12 hard-coded `/api/projects/1/` frontend sites; media/event routing per
  project); **shared-fate risk** (one project's bug/wedge can take down all);
  contradicts today's single-project-per-process reality (constraint 1).

### Family C — hybrid reader/worker (the refined sketch)

One multi-project **reader** process (read-only over finished manifests, serving
all reports) + per-project **worker** subprocesses for runs (semaphore-capped).
- **For:** decouples *viewing many* (cheap, one reader) from *running many*
  (capped workers); manifest + events log stay the truth surface, no new IPC;
  maps cleanly to a CLI `bristlenose workspace add/serve/run` and a desktop
  `ServeManager`→`Workspace` rename.
- **Against:** still needs the reader to be multi-project (a chunk of Family B's
  server rework); two lifecycle models to maintain (reader vs workers); the
  reader is still a shared-fate component for *viewing*.

### Orthogonal decisions (compose with any family)

- **Instant switching → retain the rendered WebView (Tier 2).** Needed for the
  browser-back feel regardless of family (even Family B benefits from not
  re-mounting). The threshold-aware switch-progress treatment (instrument first,
  spinner only > ~1 s) is the near-term polish. Detail:
  `docs/design-desktop-switch-performance.md`.
- **Multi-window → Phase C.** `WindowGroup(for: Project.ID)` + a per-window serve
  registry + fixing the hard-coded `/api/projects/1/` frontend sites. Composes
  with A/B/C. Non-negotiable for the paid product (the free CLI+Safari path
  already delivers instant multi-window switching, so the paid app must match it).
- **Parallel runs → Phase B (cap-2 + queue).** `PipelineRunner` single-slot →
  2-slot, 3rd queues (policy already chosen: ruled out unbounded — GPU + provider
  rate-limit contention). Orthogonal to the serve/view model.
- **Memory governance.** Whatever goes "N live" needs a small cap + shared LRU
  eviction across the sidecar pool and the WebView pool, sized for the 8 GB floor.
- **Per-project view-state persistence** (scroll/selection/view) falls out of
  retained views (Family A / Tier 2) for free; Family B would need explicit
  state save/restore.

## Effectively decided vs genuinely open

- **Decided (direction):** instant switching = retained views (Tier 2);
  multi-window = Phase C, non-negotiable for paid; parallel-runs policy = cap-2 +
  queue; CLI ≡ desktop parity; keep `bind(0)` + parent-death-watcher + single
  `generation` token; isolation (per-project token + ephemeral store) is
  non-negotiable.
- **Decided 15 Aug 2026 (window-level, independent of the family call):**
  double-click opens *that project* in a new window (Notes model); a window restores
  the lens + an anchor and nothing else; `File ▸ New Window` (⌥⌘N) replaces
  `Window ▸ Bristlenose`; window title = project name, subtitle = count or live run
  state. All four sit in the two new sections below and none of them waits on A/B/C.
- **Genuinely open (the big call):** Family **A vs B vs C** — the serve/view
  architecture. This is a battle-tested-engineer decision (process model, shared
  fate, memory, server rework cost), not a UX or cohort call. Pick it at post-TF
  planning with real multi-project-machine data, not before.

## Window-scoping the menu commands (the Notes-experience prerequisite)

Prompted by "double-click a project → new window, sidebar closed" (28 Jul 2026).
Assessed against shipped code; **Stage 1 is built**, Stages 2–3 are not.

**The finding that reframes it:** the sidebar wasn't shared state. `ContentView`
owns `columnVisibility` as `@State`, so it was always per-window — but the
*command* was a `NotificationCenter.default` broadcast every window received. Two
windows moved in lockstep. This is systemic: there were **17** `post` sites in
`MenuCommands.swift` and **zero** uses of `FocusedValue` anywhere in the app. With
two windows open, New Project fires twice and Rename prompts in both.

Three blockers sit under the Notes experience, all from every model being one
app-level `@StateObject` injected into `WindowGroup(id: "main")`:

1. **One `ServeManager`** — one sidecar, one port, one warm-park slot; and
   `create_app(project_dir)` is single-project-per-process (constraint 1 above).
   Two projects ⇒ two sidecars.
2. **One `BridgeHandler`, one `weak var webView`** — last WebView registered wins,
   so every `menuAction` drives the wrong window. Its ~28 `@Published` properties
   are global too, so `activeTab` is shared: **two windows cannot show different
   lenses.** This kills the "Quotes here, Sessions there" value even for two
   windows on the *same* project.
3. **`WindowGroup(id: "main")` carries no value**, so `openWindow(id:)` duplicates
   the same state rather than opening a project.

### Stages

- **Stage 1 — window-scoped sidebar. ✅ Shipped 28 Jul 2026.** `focusedSceneValue`
  publishes the key window's binding; the menu drives it directly and dims when no
  project window is frontmost. Scene-scoped (not view-scoped) so it survives focus
  moving into the WKWebView. Decision logic extracted to `SidebarToggle`
  (+ `SidebarToggleTests`) per the testable-helper convention.
- **Stage 2 — `@FocusedValue` for the remaining commands.** The real keystone: it is
  what makes *any* multi-window behaviour correct, and Stage 3 would have to invent
  it anyway. Also fixes double-fire bugs that exist today the moment a user opens a
  second window. **The count is now 19, not the 16 recorded on 28 Jul 2026** —
  re-counted 15 Aug. That drift is itself the finding: new commands are still being
  written with the broadcast pattern, because it is the path of least resistance and
  nothing fails when you take it. The number grows until Stage 2 lands and makes
  `focusedSceneValue` the obvious idiom to copy.
- **Stage 3a — per-window `BridgeHandler` (same-project windows).** Split out of
  Stage 3 on 15 Aug 2026 because it is the half that **actually delivers the felt
  feature** — "Quotes in this window, Analysis in that one" — and it needs **no
  family call**. One `BridgeHandler` per window, each owning its own `weak var
  webView` and its ~28 published properties; both windows point at the *same*
  sidecar, so there is no second Python process and no serve rework. Note that
  Stage 2 alone does **not** get you here: `@FocusedValue` routes the *command* to
  the right window, but the lens is shared because the *state* is shared. 3a is the
  one that fixes it.
- **Stage 3b — per-window serve + `WindowGroup(for:)` (cross-project windows).**
  Two projects visible at once ⇒ two sidecars (constraint 1). This is the part
  blocked on the family choice (A/B/C) above. "Sidebar closed by default" is ~2
  lines at the *end* of this stage (seed `columnVisibility = .detailOnly` when the
  window opens with a project value) — none of the cost is there.

**The open question this section used to end on is answered** (15 Aug 2026): double-
click means *new window on that project* (the Notes model). The "same project,
different lens" case is not the compromise it looked like — it is served by
`File ▸ New Window`, so both behaviours exist, and 3a delivers the cheaper one
first. See §"What a window opens onto".

## What a window opens onto (decided 15 Aug 2026)

Double-click on a project in the sidebar opens **that project** in a new window.

### It restores where you left, not the dashboard

The app already holds this position one level down. `SessionsRouteMemory` remembers
which session you were reading inside the Sessions lens, and its doc comment states
the principle: *"Visiting the grid RESETS the memory — 'the view the user left' is
the index in that case, not the transcript they saw an hour ago."* This decision is
the same rule one level up — project instead of session, lens instead of route.

The reason is an **asymmetry, not a preference.** A wrong restore costs one click:
you wanted the overview, you click Project. A wrong reset can be unrecoverable: you
wanted the quote you were part-way through tagging, and you are now hunting for a
position among 312 that you never consciously memorised. One is a click, the other
is a search.

Precedent: **Finder stores view state per folder** — view style, sort, scroll — and
restores it when you open that folder. A Bristlenose project *is* a folder and the
lens is the view style. That contract predates OS X.

The counter-case — the Project dashboard is the orientation surface, and a
researcher returning after three months wants the overview — mostly dissolves on
inspection: a project with **no** stored lens lands on the dashboard already, and
that is exactly the never-opened case. The genuinely awkward case is a months-old
memory, and the fix for it is **not** a time heuristic ("restore if closed
recently"). An invisible clock deciding where you land is an unlearnable rule — the
researcher cannot see it, so they cannot predict it. Either always or never. (Same
objection, and the same answer, as the conditional folder disambiguator in the
window-subtitle work.)

### What is restored, and what deliberately isn't

| | Restored | Why |
|---|---|---|
| **Lens** | Yes | Cheap, robust, and most of the felt value — Quotes vs the dashboard is the difference a researcher notices. |
| **Position** | As an **anchor**, never a pixel offset | The content is mutable: a re-analysis rewrites the quote set, hiding twenty quotes shifts everything. A stored offset into changed content lands *somewhere* and looks deliberate — confidently wrong, which is worse than landing at the top. A section anchor either resolves or falls back honestly. |
| **Search / filter** | No | A query restored days later shows 6 of 312 quotes with no visible cause. Mail clears search between openings for the same reason. (The tag filter keeps its own existing persistence rule; this decision doesn't touch it.) |

### Two mechanisms, different owners

- **Relaunch** — macOS state restoration, per window, restoring each window as it
  was. The OS owns this; we don't reimplement it.
- **Opening a project fresh** (double-click, `File ▸ New Window`) — the per-project
  last-lens memory, stored in `projects.json`, which already carries per-project
  desktop state (`icon`, `position`, `lastOpened`, `agentAccess`) and is
  machine-local. It does **not** go inside the researcher's project folder: this is
  window management, not study data, and it has no business travelling with the
  study to a client's Drive.

That split also settles two windows on one project: each restores itself on
relaunch; a *new* window on that project uses the per-project memory.

### Dependency

The lens lives in `BridgeHandler`, one app-level object today — so this rides
**Stage 3a** and cannot land before it. Once 3a exists it is nearly free, since each
window finally has somewhere to put its own lens. `SessionsRouteMemory` is the shape
to copy: a small value type carrying the decision, unit-testable, fed by the
`route-change` bridge messages that already flow.

## The command that opens a window (decided 15 Aug 2026)

`Window ▸ Bristlenose` becomes **`File ▸ New Window`, ⌥⌘N**.

Two things are wrong with it today. It is in the **wrong menu** — Apple's standard
Window-menu command list contains no new-window command at all, while
`File ▸ New <Item>` is defined as *"Creates a new document, file, or window."* And
its **label is the brand name** on an item that calls `openWindow(id: "main")`
against a `WindowGroup`, which *spawns* a window rather than reopening one: it is
already a New Window command wearing a reopen label, and it is how a second window
gets opened by accident today.

⌥⌘N rather than ⌘N because ⌘N is New Project. That is Mail's exact split — ⌘N makes
a new *thing* (a message), ⌥⌘N makes a new *window onto existing things*.

Rejected: *New Bristlenose Window* (Finder names itself only because its menu bar is
also the desktop's; for an ordinary app the app name is noise) and *New Project
Browser* (names the chrome rather than the content, and "browser" is a loaded Mac
term for NSBrowser's column view, which this is not).

**A gap the rename exposes.** There is no `applicationShouldHandleReopen` in the
app, so `Window ▸ Bristlenose` is currently the *only* way back after closing the
last window. Clicking the Dock icon should do that and today does nothing. That
handler has to land **with** the rename, not after it.

**Settled by the same HIG pass:** window-list entries are listed *"in alphabetical
order for easy scanning"* — a second, independent reason the
`Project view: <folder>: <project>: <lens>` title scheme was withdrawn, since a type
prefix sorts every window under one letter and destroys the scan. The shipped scheme
is title = project name, subtitle = count or live run state; the options weighed and
the edge cases are drawn in `docs/mockups/window-menu-naming.html`.

## Sequencing

Post-TF. A1 ✅ and A2 ✅ already removed the "stuck on one project" felt blocker,
so this is enhancement, not blocker-fix — but it is the **paid-product** bar (the
free CLI+Safari path sets it). The phases compose: Phase B (parallel runs) and the
serve/view family choice are independent; Phase C (multi-window) + Tier-2 (retained
views) are the instant-multi-window pair. Likely order once planning opens:
choose the family → Tier-2 retained views → Phase C multi-window → Phase B
parallel runs (or B earlier if run-throughput feedback demands it).

**Stages 2 and 3a are the exception to "post-TF".** Neither waits on the family
call, and Stage 2's bugs are **live today, not hypothetical**: a second window is
reachable right now via `Window ▸ Bristlenose`, and `MenuCommands.swift` currently
holds **19** `NotificationCenter.default.post` sites (up from the 17 counted on
28 Jul), every one of them a broadcast that fires in every open window. With two
windows open, New Project fires twice and Rename prompts in both. Constraint 5 —
a title bar naming a project that isn't on screen — is the same class of problem
and lands on 3a. The honest framing is that today's app is *single-window software
that can be made to open a second window*, and the cheapest way to stop that being
true is Stage 2 → Stage 3a, in that order, independent of everything else here.

## References

- `docs/design-desktop-switch-performance.md` — the switch-latency slice (tiers,
  WebKit≠Safari, the instant-switch path). This doc is the umbrella; that one is
  the latency sub-concern.
- `docs/mockups/window-menu-naming.html` — the window-title/Window-menu naming
  options and their edge cases, with the 15 Aug decisions marked on each. The
  source for §"The command that opens a window" and for what a restored window is
  called once it opens.
- `docs/design-modularity.md` — CLI ≡ desktop parity, what ships where.
- `desktop/CLAUDE.md` — warm-sidecar pool (A2) mechanics, the `generation` token,
  `bind(0)` + parent-death-watcher contracts.
