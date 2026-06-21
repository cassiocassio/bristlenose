# Workspace — genuine multi-project + multi-window (post-TF)

**Status:** Problem definition + option range. Nothing here is decided — this is the
"promote to a design doc when post-TF planning starts" artefact that the planner's
Workspace item pointed at. The end goal is fixed; the architecture is open.

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
- **Phase A2 — warm-sidecar pool** (`warm-sidecar-pool`, pending merge): switching
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
- **Genuinely open (the big call):** Family **A vs B vs C** — the serve/view
  architecture. This is a battle-tested-engineer decision (process model, shared
  fate, memory, server rework cost), not a UX or cohort call. Pick it at post-TF
  planning with real multi-project-machine data, not before.

## Sequencing

Post-TF. A1 ✅ and A2 ✅ already removed the "stuck on one project" felt blocker,
so this is enhancement, not blocker-fix — but it is the **paid-product** bar (the
free CLI+Safari path sets it). The phases compose: Phase B (parallel runs) and the
serve/view family choice are independent; Phase C (multi-window) + Tier-2 (retained
views) are the instant-multi-window pair. Likely order once planning opens:
choose the family → Tier-2 retained views → Phase C multi-window → Phase B
parallel runs (or B earlier if run-throughput feedback demands it).

## References

- `docs/design-desktop-switch-performance.md` — the switch-latency slice (tiers,
  WebKit≠Safari, the instant-switch path). This doc is the umbrella; that one is
  the latency sub-concern.
- `docs/design-modularity.md` — CLI ≡ desktop parity, what ships where.
- `desktop/CLAUDE.md` — warm-sidecar pool (A2) mechanics, the `generation` token,
  `bind(0)` + parent-death-watcher contracts.
