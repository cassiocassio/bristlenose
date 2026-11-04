# Performance ledger: the cumulative picture across layers

Opened 4 Nov 2026, after the window-resize work (`docs/design-client-performance.md`, which holds that work's numbers and is not edited from here). That work found its gains by measuring, not by trying to make everything fast. This file does the same for the other layers, one change at a time. Every claim is labelled **measured** (a number from a run you can repeat), **estimated** (reasoned, not run) or **reported** (a researcher's finding not yet checked here).

## The rule each entry follows

1. A **moment** a researcher meets (not a function): "click a lens", "open a study", "double-click the app".
2. A **scripted measurement** of it, with the tool named.
3. **One change**, then the same measurement again.
4. A **good-enough number**, written before the change, and we stop there.
5. What was **declined**, with the number that justified declining.

Ranked by how often a researcher meets the moment per day times how much they feel it. A daily 150 ms stutter outranks a monthly 10 s wait.

**Out of scope, decided:** time bound by external LLM providers; the speed/accuracy tradeoffs of transcription itself (the saving from a good Teams/Zoom transcript is in scope); profiling across different machines (use the silicon well, measure on this Mac only). A layer with nothing to pick off is a valid result.

## Who touches what

| Area | Owner |
|---|---|
| `desktop/Bristlenose/**`, `desktop/scripts/perf/**`, `docs/design-client-performance.md` | the resize session (`cb4d4a`) |
| `bristlenose/server/**`, `bristlenose/utils/**`, `bristlenose/stages/**`, `bristlenose/llm/**`, `scripts/perf-*`, this file | the orchestrating session (`97a82d`) |
| `frontend/src/**`, `bristlenose/theme/**`, `experiments/perf/**` | unowned: message the other session first |

`SidebarStore.ts` has `useSidebarSelector`: a component that reads a few fields selects them and never subscribes to the whole store.

## Shared vocabulary: the moment timer

One name per moment, used by every layer so a click, its request and its paint read on one timeline.

| Layer | Mechanism | State |
|---|---|---|
| Server | `Server-Timing: bn;dur=…, db;dur=…;desc="N queries"` (`bristlenose/server/perf_timing.py`; on with `serve --dev` or `BRISTLENOSE_SERVER_TIMING=1`) | **built** |
| Mac | `OSSignposter`, subsystem `app.bristlenose`, category `perf` | in progress (resize session) |
| Page | `performance.mark/measure`, `bn.<moment>.start/end`, and a `perf-mark` bridge message | not started |

Moments: `launch-to-ready`, `serve-ready`, `project-select`, `lens-switch`, `open-transcript`, `first-card-painted`. Names are lowercase kebab-case; start and end share a name.

## Done

| Change | Measured | Commit |
|---|---|---|
| `inflect` loaded on first plural, not at import | `import bristlenose.cli` 1.05 s → 0.22 s; `import bristlenose.server.app` 1.8 s → 0.8 s (median of 3–5, `.venv`, warm cache). A subprocess test pins it and fails with the eager import put back. | `6f5b0e350` |
| Server-Timing instrument | n/a (instrument) | `041df1eb0` |

`inflect` was found by `python -X importtime`, not by guess: it was 0.84 s of self time on the path of every command, `--help` and `serve` included. Re-measure on the signed sidecar, which this does not cover.

## Baselines (measured, 4 Nov 2026)

`scripts/perf-route-baseline.py 1500`: synthetic 1,500-quote study, this Mac, dev venv, ephemeral port, own token. Time to first byte is the server's `Server-Timing` `bn`; median of ten requests after two warm-ups.

| Route | Queries | ttfb, identity | ttfb, gzip | Wire, identity → gzip |
|---|---|---|---|---|
| `/quotes` | 23 | 87 ms | 99 ms | 978 KB → 68 KB |
| `/sessions` | 38 | 43 ms | 52 ms | 6.8 KB → 1.1 KB |
| `/dashboard` | 33 | 110 ms | 132 ms | 6.7 KB → 1.7 KB |
| `/tapestry` | 13 | 121 ms | 137 ms | 548 KB → 64 KB |
| `/signals/snapshot` | 2 | 2.5 ms | 2.5 ms | 65 B |

- **Gzip costs 9–22 ms a request on a loopback-only server and saves nothing real** (the wire is memory). Repeats across two runs. Whether to lower the level or drop it is a decision for the next entry; the gain per lens switch is that 10–20 ms, which is small beside the other costs below.
- **HTML export: 3.5 s, 9,346 SQL statements (about 6 per quote), 0.49 s inside SQL.** Most of the rest is Python overhead per statement, not the database. Reported candidate: batch the moderator-question lookup.
- **`serve` ready to `/api/health`: 4.6–4.8 s** on the dev venv, including the startup import of this study. Not the signed sidecar.
- The first draft of the wire-size column read the decompressed body; it now counts raw bytes. The timings were never affected.

## Candidate queue

From the 8-layer research (provider-bound LLM time and transcription tradeoffs excluded), pending the three-lens Fable review. **Reported, not yet confirmed here.** Order is provisional and will change after review.

| # | Candidate | Layer | First measurement |
|---|---|---|---|
| 1 | ~~Lazy `inflect`~~ | sidecar | **done** |
| 2 | Gzip level on loopback | server | **measured above** |
| 3 | Signposts and launch-to-ready / project-switch harness | Mac + sidecar | cold and warm, 5 each, signed build labelled |
| 4 | React Profiler hook; keynav, search and mutate modes in `experiments/perf` | page | renders and script ms per step at 100/300/1000 quotes |
| 5 | `useQuotesStore()` whole-store subscribers → selectors (same defect class as the sidebar fix) | page | `filterQuotes` calls per tag-add and per keystroke |
| 6 | Sidebar `reloadData` on every pipeline stdout line | Mac | reloads per second during a replayed stream |
| 7 | Export HTML: batch the per-quote moderator lookup | server | wall time at n=0/500/1500/3000, then `py-spy` |
| 8 | Lazy codebook YAML at import (97 ms) | sidecar | `-X importtime` |
| 9 | Scene-colour decode off the run's critical path | pipeline | `elapsed_ms` and bytes materialised, local and dataless |
| 10 | Per-id focus selector so `j`/`k` doesn't re-render every card | page | renders per keypress |

## The moments a researcher feels most (perceived performance)

These come first because they happen many times a day. All are **unmeasured end to end**: the 43 ms and 240 ms lens-switch figures in `design-client-performance.md` are CPU totals, not click-to-painted.

| Moment | Why it matters | Source of the wait (reported) |
|---|---|---|
| Cold app start to a readable report | first impression, every day | 500 ms start-watchdog poll; 2 s "ready" fallback; first-launch code-signature checks on the bundled sidecar |
| Open or switch a study | every study change | a new web view per study; the warm-sidecar pool is one parked slot; nothing times it |
| Switch lens | the most repeated action | `Suspense fallback={null}`: a blank pane on a lens's first visit; each lens re-reads its data on open (about 180 ms at n=1500 per `design-perf-stress-findings.md`) |
| Search as you type | constant | a 150 ms debounce before any filtering; `startTransition` and `useDeferredValue` unused in `frontend/src` |
| First click on a timecode | every clip | opens a popout window and loads the video before it seeks |
| Analyse / Stop acknowledgement | every run | status polling at 3 s; Stop is a signal ladder |

**Switching and cold start belong to the Workspace work** (many projects open, switching instant, post-TestFlight; `docs/design-workspace.md`). The direction there is retained views for instant switching, with the warm-sidecar pool already a single parked slot. The signposts above decide how much of the wait is sidecar spawn, web view load or data fetch. That tells the Workspace work where retained views would help most, before the architecture is chosen.

## Instruments

| Need | Tool | State |
|---|---|---|
| Mac window and main thread, real mouse | `desktop/scripts/perf/profile-resize.sh` + `xctrace` | have (moves the pointer: run it when nobody is at the Mac; never two at once) |
| Page, Chromium counters and CPU profile | `experiments/perf/` | have |
| Server per request | `Server-Timing` (`perf_timing.py`) | built |
| Server per route at a given size | `scripts/perf-route-baseline.py` | built |
| Import time | `python -X importtime` | have |
| Server CPU in a live process | `py-spy`, `pyinstrument` | not installed |
| Repeated CLI wall-clock | `hyperfine` | not installed |
| WebContent inside the Mac app | Safari Web Inspector on a Debug app (`isInspectable`) | manual |
| SwiftUI body re-evaluation | Instruments SwiftUI template | have Xcode; unused |

Gate on **counts and sizes, not milliseconds**: shared CI runners cannot hold 2% on timings (`design-perf-regression-gate.md`). Keep milliseconds for local before/after.

## Not yet done

- Reviewed targets with good-enough numbers (three-lens Fable review in progress).
- Page-side moment marks and the `perf-mark` bridge message.
- A launch-to-ready number on the signed sidecar.
- Measured experiments on our own overhead around LLM calls (batching, concurrency, resume cache hits); none run yet.
