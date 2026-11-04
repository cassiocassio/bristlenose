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
| Mac | `OSSignposter`, subsystem `app.bristlenose`, category `perf` (`PerfSignpost.swift`) | **built** (`f2c49aa66`); read with `log stream --signpost --predicate 'subsystem == "app.bristlenose" AND category == "perf"'` |
| Page | `useMomentOnPaint` ends `first-card-painted` and `open-transcript` two frames after the content renders, posting `{type: "perf-mark", name}` and leaving `performance.mark("bn.<name>.end")` (`utils/perfMoment.ts`) | **built** (`5cf46895f`); `lens-switch` and search marks are the next entries |

**The bridge is dead against an external dev server** (`BRISTLENOSE_DEV_EXTERNAL_PORT=8484`): the app has no token for it, so the page's `/api/health` fetch fails and `ready` never posts. Signposts only complete against a copy running its own bundled sidecar.

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

## Reviewed targets: the moments a researcher feels most

Three independent Fable reviewers (evidence, measurability, parsimony) checked each of ten perceived-performance candidates against the code at HEAD. **They refuted most of the experiments that were proposed**, often because the thing was already shipped, and corrected the numbers behind the rest. Ranked by how often the moment happens times how much it is felt. All good-enough numbers below are the reviewers' and are **not yet measured**; the first step is always the baseline.

| # | Moment | Frequency | First measurement | Good enough | Smallest experiment (only after the baseline) |
|---|---|---|---|---|---|
| 1 | **Click a lens**: a blank pane until the lazy chunk loads (first visit) and until the read resolves (every visit, since the lens remounts) | many a day | `interaction-profile.mjs` `lenses` case, fixed to stop at the lens's content (not the blank frame), two passes (first visit, revisit), **prod bundle without `--dev`**, on a real-size and a 1,500-quote fixture | revisit p90 ≤ 100 ms, first visit ≤ 200 ms | split decides it: chunk-dominated → preload lens chunks on idle (the Sessions sidebar already does); fetch-dominated → a last-answer cache in `useLensRead`; render-dominated → record and close |
| 2 | **Type in search**: a 150 ms debounce, then one write fanning out to eight `filterQuotes` callers | many a day | a `search` case: field echo per character, last keystroke to results (debounce excluded) | echo < 16 ms; results < 50 ms | if render is cheap, debounce to 0 on both the web and the native field; else dedupe the eight passes |
| 3 | **Double-click the app to a readable report**: launch to Welcome, then click a study to a report | daily | Mac signposts (`launch-to-ready`, `serve-ready`); cold vs warm, 5 each | warm selection to report under about 2 s, the remainder being sidecar import | re-measure on a rebuilt sidecar (the `inflect` change is in it) |
| 4 | **Open or switch a study** | daily | `project-select` signpost; warm and cold | warm p95 < 1 s | none until measured; the 500 ms "invisible" line is in the code's own note |
| 5 | **First click on a timecode, and the Nth click that changes recording** | daily | a mark at click and `canplay` back | first frame < 1 s; seek < 300 ms | after the baseline |
| 6 | Quotes-grid scroll on a big study | occasional | LoAF `blockingDuration` and notch-to-frame at 4× throttle, n=100 vs 1,500 | zero blocking frames > 50 ms; p90 < 33 ms | none; probably already passes |
| 7 | Report sidebar toggle | occasional | 12 toggles, blocking LoAF | 0 of 12 | none |
| 8 | Analyse / Stop | daily | `start()` inclusive time per press | < 100 ms; first progress < 1.5 s | none: both acknowledgements are already synchronous |
| 9 | Hover thumbnails | occasional | fetch p95 | < 300 ms, inside the 700 ms design delay | none |
| 10 | Export | rare | `time_starttransfer` | < 2 s | the 5 s label patience is the only real threshold |

**Declined, with the reason** (so they are not proposed again): a stdout-driven readiness wake (readiness is already stdout-driven; the 500 ms loop is the give-up watchdog); showing the native sidebar at once with the web pane covered (shipped design); prefetching the next lens on sidebar hover (no precedent, a bridge channel for about 20 ms); a warm serve on hover (a speculative ~140 MB spawn, against the no-background-spawn stance); keeping the previous web view dimmed (deliberate veil; the old view is torn down); per-card `contain-intrinsic-size` (already per-card after first layout); idle-slice rendering (virtualisation by another name, left in `design-client-performance.md`); `startTransition` for search (the web field is already responsive and the Mac field is native); optimistic "Starting…" and "Stopping…" (shipped); a faster run poll (the native poll is already 1 s; the 3 s polls are the page's); streaming the export (WebKit's save panel needs the whole body); a hidden player window (needs a user activation); "show nothing until ready" for thumbnails (shipped 13 Oct 2026).

**Corrections to the first research**, which the numbers above already use: the 180 ms lens read is `/quotes` alone at n=1,500 on a synthetic fixture; the warm-slot parked sidecar is unreachable dead code, not a live pool; the first timecode click seeks through the URL hash, not a message; the 3 s polls are the page's (`LastRunStore`, `ConditionStore`), not Swift's; the scroll sweep (17 Apr 2026) never measured scroll, so "jank above about 1,500 quotes" was inferred.

**Switching and cold start belong to the Workspace work** (many projects open, switching instant, post-TestFlight; `docs/design-workspace.md`), whose direction is retained views. The signposts decide how much of each wait is sidecar spawn, web view load or data fetch, which tells that work where retained views would help before the architecture is chosen.

## Candidate queue: engineering (layer research, pending its own review)

Reported, not yet confirmed here. Order is provisional.

| # | Candidate | Layer | First measurement |
|---|---|---|---|
| 1 | ~~Lazy `inflect`~~ | sidecar | **done** |
| 2 | Gzip level on loopback | server | **measured above** |
| 3 | `useQuotesStore()` whole-store subscribers → selectors (the sidebar-store defect class) | page | `filterQuotes` calls per tag-add and per keystroke |
| 4 | Sidebar `reloadData` on every pipeline stdout line | Mac | reloads per second during a replayed stream |
| 5 | Export HTML: batch the per-quote moderator lookup | server | wall time at n=0/500/1500/3000, then `py-spy` |
| 6 | Lazy codebook YAML at import (97 ms) | sidecar | `-X importtime` |
| 7 | Scene-colour decode off the run's critical path | pipeline | `elapsed_ms` and bytes materialised, local and dataless |
| 8 | Per-id focus selector so `j`/`k` doesn't re-render every card | page | renders per keypress |

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

- Baselines for the ten reviewed moments above; none is measured yet.
- The engineering candidates have not had their three-lens review (in progress).
- A launch-to-ready number on the signed sidecar, with and without the `inflect` change (the resize session is rebuilding the sidecar to measure it).
- Measured experiments on our own overhead around LLM calls (batching, concurrency, resume cache hits); none run yet.
