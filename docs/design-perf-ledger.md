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
| `inflect` loaded on first plural, not at import | `import bristlenose.cli` 1.05 s → 0.22 s; `import bristlenose.server.app` 1.8 s → 0.8 s (median of 3–5, `.venv`, warm cache). A subprocess test pins it and fails with the eager import put back. **In the app, `serve-ready` (bundled sidecar) went 3,194 ms → 2,241 ms cold (−30%) and 3,128 → 2,330 ms warm (−25%); `project-select` 4.1 s → 3.1 s** (median of 5, identical app binary in both arms, Debug-signed app, ad-hoc-signed hardened-runtime sidecar; method and spread in `design-client-performance.md` § Sidecar start). | `6f5b0e350`; measured `8000e1b17` |
| Server-Timing instrument | n/a (instrument) | `041df1eb0` |
| Codebook templates parsed with libyaml (`CSafeLoader`) | cumulative import of `bristlenose.server.codebook` 119–143 ms → 36–43 ms (five runs each); all nine templates parse identically | `8cb124763` |
| Keychain reads kept for ten seconds (`credentials_macos.py`) | `load_settings()` ran 3 times per serve start, 5 `security` subprocesses each: 15 spawns, 360 ms → 5 spawns, 106 ms. Spawn to `Report:` line on a copy of a real study, 7 runs each, interleaved, twice: **1,505 / 1,516 ms with the cache off, 1,229 / 1,226 ms on (−19%)**. Reaches the Homebrew and pip route on a Mac; the sandboxed app is documented as not reaching this store, so its gain is for the host session to measure | `0418c7dd1` |
| HTML export skips the moderator-question lookup while the pill is parked (owner's call, 4 Nov 2026) | export of 1,500 quotes **3.1–3.5 s → 1.2 s**; SQL statements 9,346 → 343; time inside SQL 490 → 15 ms; embed 5.99 → 5.75 MB. The constant mirrors `featureFlags.moderatorQuestionPill` and a test reads the frontend default, so turning the pill on cannot leave an export without its data | this commit |
| Startup stage stamps (`BRISTLENOSE_STARTUP_TRACE=1`, `startup_trace.py`) | n/a (instrument: `@startup-stage <name> <epoch_ms>` on stderr at 14 points) | `f1963e516` |
| gzip at level 1 on the loopback-only server | compression of `/quotes` 10.7 → 2.5 ms, `/tapestry` 12.7 → 1.8 ms (zlib on the real bodies, median of 30) | this commit |

`inflect` was found by `python -X importtime`, not by guess: it was 0.84 s of self time on the path of every command, `--help` and `serve` included. The A/B above covers the bundled sidecar; the App Store (Apple Distribution) signing and the sandboxed entitlements were not measured. Warm was noisier than cold (one 3.4 s outlier), and cold was not slower than warm, so this method does not reproduce a first-exec penalty.

## Baselines (measured, 4 Nov 2026)

`scripts/perf-route-baseline.py 1500`: synthetic 1,500-quote study, this Mac, dev venv, ephemeral port, own token. Time to first byte is the server's `Server-Timing` `bn`; median of ten requests after two warm-ups.

| Route | Queries | ttfb, identity | ttfb, gzip | Wire, identity → gzip |
|---|---|---|---|---|
| `/quotes` | 23 | 87 ms | 99 ms | 978 KB → 68 KB |
| `/sessions` | 38 | 43 ms | 52 ms | 6.8 KB → 1.1 KB |
| `/dashboard` | 33 | 110 ms | 132 ms | 6.7 KB → 1.7 KB |
| `/tapestry` | 13 | 121 ms | 137 ms | 548 KB → 64 KB |
| `/signals/snapshot` | 2 | 2.5 ms | 2.5 ms | 65 B |

- **Gzip level.** My first reading was "gzip costs 9–22 ms a request". That was partly noise: the identity arm moved by 30 ms between runs. Timing the compression directly on the real bodies (zlib, median of 30): `/quotes` 10.7 ms at level 9 → 2.5 ms at level 1; `/tapestry` 12.7 → 1.8 ms; `/dashboard` and `/sessions` about 0.1 ms either way. **Level 1 saves 8–11 ms on the two big routes and nothing on the small ones**; the wire grows from 68 KB to 96 KB on `/quotes`, which on loopback is memory. Shipped as `compresslevel=1` (one parameter; a test pins it). A small win, and it lands on `/tapestry`, which the Sessions grid polls.
- **HTML export: 3.5 s, 9,346 SQL statements (about 6 per quote), 0.49 s inside SQL.** Most of the rest is Python overhead per statement, not the database. Reported candidate: batch the moderator-question lookup.
- **`serve` ready to `/api/health`: 4.6–4.8 s** on the dev venv, including the startup import of this study. Not the signed sidecar.
- The first draft of the wire-size column read the decompressed body; it now counts raw bytes. The timings were never affected.

## Where a serve start goes (measured 4 Nov 2026, dev venv, `BRISTLENOSE_STARTUP_TRACE=1`)

Median of five, a synthetic 1,500-quote study (large) beside copies of two real studies (30 and 35 quotes, 3 and 5 sessions; copies, never served in place). Server-side only: the Mac's own steps (spawn call, window, page load) are in `design-client-performance.md`.

| Stage | 1,500 quotes | real study |
|---|---|---|
| Python and the CLI imported | 177 ms | |
| CLI imported → `serve` entered (including its own `load_settings`) | 147 ms | |
| Importing the server app | 417 ms | |
| Database ready → startup import begins (including `load_settings`) | 187 ms | |
| **Startup import** | **1,097 ms** | **74–83 ms** |
| Rest of app construction (event watcher, static mount, MCP mount) | 298 ms | |
| Lifespan, then socket bound | 186 ms | |
| **Spawn → `Report:` line** | **2.54 s** | **about 1.2–1.5 s** |

- **`/api/health` is not doing work.** First call 12–40 ms server-side, the second 7 ms. The 197 ms the Mac measured for it is mostly the client's first connection.
- **The importer is a size cost, not a daily one.** About 0.7 ms per quote (an existence query and an autoflush per quote); 74–83 ms at the 30–35 quotes of the real studies. Declined for now with those numbers. It becomes the largest item above about 1,000 quotes.
- **The imports are diffuse.** The heaviest single module is 35 ms of 414 (`fastapi.openapi.models`); no one fix is worth making.
- **`import mcp` is 275–280 ms on every start**, whether or not Agent Access is on. The largest fixed item left. Deferring it touches a shipped contract (the `/mcp` mount, `health.mcp.mounted`, the lifespan being composed last), so it is a proposal for the owner and the Agent Access work, not a one-liner.
- **One-time cost to know about:** with a cloud key set, a study with no Signals snapshot builds one at start, and that holds the event loop for about 0.8 s at 1,500 quotes (the model call itself is separate). Once per study or contract upgrade.
- **A harness that starts `serve` on a synthetic study and has a key configured makes a real model call at start.** `scripts/perf-route-baseline.py` now sets `BRISTLENOSE_LLM_PROVIDER=local`, which makes serve skip it. Any new harness must do the same.

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

## Engineering candidates, after review

Fifteen candidates, three Fable reviewers each (evidence, measurability, parsimony), then a completeness critic. Most were **partly** right: the idea held and the numbers or the cause did not. Done items are in the Done table.

| Candidate | Verdict | What the reviewers changed |
|---|---|---|
| Codebook YAML via libyaml | **done** | 3 of 3 yes |
| Gzip level | **done** | smaller than first read: 8–11 ms on two routes |
| **Export HTML moderator lookup (S3)** | **done** (owner chose skip while parked). Was: confirmed 3 of 3 | exactly 6 statements per quote. **Simplest fix is to skip the loop while the moderator-question pill is parked**, since the only reader is gated off (`QuoteGroup.tsx`). That needs **an owner call**: the flag's own notes say the embedded data is kept so the pill can return. Otherwise batch per session. Target: statements independent of quote count; n=3,000 from about 8.4 s to about 3.7 s |
| Scene-colour decode (PT2) | partly | one line: run it in a thread (`readable_chain.py`), which ends the event-loop stall and lets platform-transcript sessions decode concurrently. The wait is bounded at 30 min a file, not unbounded; measured about 4 s per hour of video today, not 1.5 |
| Whole-store `useQuotesStore()` subscribers (spa-2) | partly | **smaller than claimed**: six of the eight sites are already inside a `useMemo` keyed on stable state. Try `memo(QuoteCard)` with stable callbacks first, measured with the mutate profile; one site (`QuotesArrival.tsx`) was missing from the list |
| Per-id focus selector (spa-1) | confirmed 2 of 3 | `AppLayout.tsx:302` also subscribes to focus state and re-renders the chrome per keypress; use the `useSidebarSelector` pattern; target one frame per `j`/`k` at 300 quotes |
| Sidebar `reloadData` per stdout line (C1) | partly | **premise stale**: progress moved to the 1 Hz events poll in April, so stdout no longer drives it. Count first; if anything matters, only a `✓` stage line needs to publish |
| Transcript rows / `content-visibility` (spa-3) | partly | not one decision; the baseline splits mount from per-row cost. The harness had no transcript case |
| Whisper alongside a mixed folder's hand-over (PT1) | partly | only when a platform session orders first; one `gather` before the Whisper loop |
| OCR skip on identical frames (MC-2) | partly | already measured on 13 Oct 2026 (31–37% skipped, 95–96% of lines kept); the gate was consciously assigned elsewhere |
| Dashboard / Sessions queries (S2) | measure-first | SQL is at most 4.4 ms a request; the 110 ms I recorded came from one quadratic `any()` scan (`dashboard.py:332`) on a synthetic 300-quotes-per-session shape. Probably not real |
| Project import and migrations deferral (SS-3) | **no** | `import_project` is 0.1–0.2 s on small studies, 0.55–0.9 s on a 242-quote study; migrations 4–150 ms. Nothing to defer |
| VideoToolbox decode (MC-3) | **no** | refuted by two reviewers |

**Gaps the critic found** (moments nobody had covered; none measured yet): correcting a transcript (every write re-reads the whole transcript and rebuilds every word span, 14,228 of them on one real session); typing inside an inline quote edit; the app open all day (three page polls, the Mac's own polls, a sidecar per project; idle CPU and energy impact never measured); following the recording during playback (class toggles on every word span of the paragraph, about four times a second); expanding a Sessions-grid row; memory over a long session; toggling a codebook framework off and on; dropping a folder of recordings to the row becoming selectable.

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
- Baselines for the critic's eight gaps, in order of how often they happen: transcript correction, inline edit echo, idle CPU and energy, playback follow.
- A launch-to-ready number (the full chain from double-click); `serve-ready` and `project-select` are measured above, and `first-card-painted` now begins on a route into `/report/quotes`.
- Measured experiments on our own overhead around LLM calls (batching, concurrency, resume cache hits); none run yet.
