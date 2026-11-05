# Performance ledger: the cumulative picture across layers

Opened 4 Nov 2026, after the window-resize work (`docs/design-client-performance.md`, which holds that work's numbers and is not edited from here). That work found its gains by measuring, not by trying to make everything fast. This file does the same for the other layers, one change at a time. Every claim is labelled **measured** (a number from a run you can repeat), **estimated** (reasoned, not run) or **reported** (a researcher's finding not yet checked here).

## Scoreboard: done, outstanding, and what is left to gain

Updated 5 Nov 2026 (closing review). **Measured** is a number from a repeatable run; **estimate** is reasoned from a measured part and says so; **unmeasured** has no number yet and is not guessed. Gains are per occurrence on this Mac unless stated.

### Done

| Change | Moment | Gain | Basis | Commit |
|---|---|---|---|---|
| `inflect` loaded on first plural | every CLI command, every serve start | `import cli` 1.05 → 0.22 s; in the app `serve-ready` 3.19 → 2.24 s cold (−30%), 3.13 → 2.33 s warm (−25%); `project-select` 4.1 → 3.1 s | measured, identical app binary | `6f5b0e350`, `8000e1b17` |
| Keychain reads kept 10 s | Mac CLI `serve` start (Homebrew / pip) | spawn → `Report:` 1.51 → 1.23 s (−19%), 15 → 5 subprocess reads | measured, interleaved ×2. App: unmeasured | `0418c7dd1` |
| Export skips the parked pill's lookup | Export HTML | 1,500 quotes: 3.1–3.5 → 1.2 s, 9,346 → 343 statements. Real studies now 120–140 ms (the before at that size was not measured) | measured | `bcfae9c24` |
| Codebook YAML via libyaml | every serve start | import 119–143 → 36–43 ms (−85 ms) | measured, 5 runs | `8cb124763` |
| gzip level 1 | `/quotes`, `/tapestry` | −8 to −11 ms at 1,500 quotes; **about 0 at real size** (35–59 KB bodies) | measured (compression timed directly) | `b70c0787e` |
| Scene-colour decode in a thread | first analysis, platform-transcript sessions | removes an event-loop stall of about 4 s per hour of video | estimate (the stall itself unmeasured) | `4b79de03a` |
| Window resize, sidebar hold, selector fix, click monitor | resize, click | 10 → 59 window updates/s; WebContent main thread 4,145 → 1,705 ms | measured (earlier work, `design-client-performance.md`) | see that doc |
| Sessions grid chunk preloaded on idle and rendered directly (`pages/SessionsTab.tsx`) | first click on Sessions | **first visit 361 → 86 / 91 ms (−75%, two runs)**; the gap before its read starts 280 → 10 ms; revisit and every other lens unchanged within noise; bundle 211.7 kB of 222 | measured, Chromium, production bundle, real-size study (242 quotes) | `f8a325e53` |
| One URL space for the bundle (`/assets/`, no rewrite to `/static/assets/`) | every first visit; correctness | 6+ shared chunks (`common`, `i18n`, `jsx-runtime`, `settings`, `enums`, `preload-helper`) were fetched twice and evaluated as two module instances; now 65 requests, 65 distinct files, 0 duplicated; first-visit chunk time −5 ms per lens, totals within noise | measured (`chunk-urls.mjs`) | `213cce521` |
| Playback progress variable registered as not inherited (`atoms/timecode.css`) | following a recording in the transcript | layout passes per tick **20 → 0.5**; layout 12 → 5 ms and style recalc 9 → 5 ms a tick, so about 21 → 10 ms of main-thread work at 4 ticks a second on a 396-word paragraph (−55%; a 1,912-word paragraph: layout 3.8 → 2.1 ms). Total busy time unchanged in headless Chromium, where software painting dominates and is not representative: unmeasured in WKWebView | measured, A/B interleaved ×2, then again with the real file | `8b63dd00d` |
| Sessions preload on WebKit's timer fallback (250 ms, was 1.5 s) | first Sessions click in the Mac app's engine | WebKit has no `requestIdleCallback`. First click 400 and 900 ms after load: **366 / 368 → 101 / 94 ms**; at 2 s: 95 (unchanged); only a click inside the first 250 ms still pays. Whole first visit in WebKit (harness): 406 → 144 ms (−65%) | measured, 6 reps each | `070aa2c30` |
| MCP endpoint built on its first request (`server/mcp_mount.py`, `LazyMCP`), owner's choice 4 Nov 2026 | every app launch | **spawn → first `/api/health` 200: 1,445–1,463 → 983–1,027 ms (−30%)** (Screens off), interleaved A/B ×2, identical bundle, desktop-hosted, real-study copy; the first agent call pays 365–476 ms once, then 8–13 ms. **The app's end-to-end function was verified by the resize session (Agent Access on, a real call through the connected MCP client, no timeout); its launch time in the sandboxed app is not yet measured with an interleaved A/B.** **Corrected twice after review:** the first commit measured only the `Report:` line, and `/api/health` still imported the SDK on its first call (343 ms), which the code review found; `_project_key` moved to the light module and a test pins it. CLI `serve` gains less: its connect banner still imports the SDK after the `Report:` line | measured in dev; app launch unresolved | `34c1ce020`, `ce2681442` |
| Screen-text availability check moved off the event loop (`screen_text_job.py`) | every Mac-app launch (Screens is on by default there) | the first availability check imports four pyobjc frameworks (`Foundation`, `objc`, `Quartz`, `Vision`: 260 ms) and the lifespan called it synchronously. **Screens on: spawn → first health 1,450 → 1,158 / 1,184 ms (−20%)** (this change alone). Both changes together, Screens on, against the commit before the lazy MCP mount: 1,817 → 1,191 ms (−34%). A 1.5 s delay on top gained nothing (1,223 vs 1,191) and was dropped. My dev runs missed this for hours because they had Screens off. **Not confirmed in the sandboxed app:** the resize session's batch with the fix (5 cold + 2 warm, not interleaved, a busy Mac with a 25 s UI stall in two runs) shows `lifespan-begin → lifespan-tasks-started` 307 → 4 ms as predicted, but spawn → socket-bound 1,809 ms (1,507–2,117) against 1,818 and 1,878 before, and stages before the lifespan grew by about what it lost, so in the frozen bundle the Vision import may now overlap the startup imports and cost the same. Only an interleaved A/B in the app on a quiet machine can settle it | measured in dev (interleaved ×2); app unresolved | `62f039c96` |
| Standby sidecar (`serve --standby`, `StandbySidecar.swift`): a sidecar booted before a study is chosen, claimed over stdin | every study open from a cold launch | **Python half: claim → `Report:` 1.36 → 0.74 s (Screens off), 1.39 → 0.75 s (Screens on)**, interleaved, 8 reps each, spread under 50 ms, real-size study, dev. The standby's own boot, 0.64 s, is hidden while the user chooses. **Not run in the sandboxed app**: it needs a rebuilt sidecar, and the code-signature cost, the sandbox lease inheritance and the Swift handover are only measurable there. Two reviews; the code review found a blocker (nothing owned the adopted standby, so a claim would have timed out at 90 s) that every unit test missed | measured in dev; app unmeasured | `fcf1ae9f8`, `e373db000`, `83395564f`; `docs/design-standby-sidecar.md` |
| Instruments | all | `Server-Timing`, startup stamps (`BRISTLENOSE_STARTUP_TRACE`), `perf-route-baseline.py`, Mac signposts, page marks | n/a | `041df1eb0`, `f1963e516`, `7cba2417e`, `f2c49aa66`, `5cf46895f` |

### Outstanding, ranked by frequency × felt, with what is left to gain

| Candidate | Moment | Frequency | Estimated gain still available | Confidence | State |
|---|---|---|---|---|---|
| Lens revisit: Transcript p90 165–190, Quotes p90 150–160 against a ≤ 100 target | click Transcript or Quotes | many a day | render-bound at scale (Quotes 280 ms of render at 1,500 quotes); `QuoteCard` memoisation with stable props is the lever, gain **unmeasured** | medium | measure with `BN_COUNT=1 cpu-profile.cjs` |
| Search at a typical typing pace: the first letter's commit re-renders every card | type in search at 1,500 quotes | many a day | echo 170 ms → under 16 ms if a not-yet-active query re-renders nothing (**estimate**, same lever as above) | medium | baselines done; fix pending |

| Whole-store `useQuotesStore()` subscribers → selectors; per-id focus | tag, star, `j`/`k` | many a day | **unmeasured**; the sidebar fix was −58% WebContent main thread. Smaller than first claimed (six of eight sites already memoised) | low | needs mutate / keynav baselines |

| Startup importer skip-when-unchanged | study start | daily | about 70 ms at real size; about 1 s at 1,500 quotes (measured importer cost, fast-path untested) | medium | declined at real size |
| Remaining fixed start: Python + imports 740 ms, `create_app` tail 300 ms, lifespan 130 ms | every launch | daily | diffuse, no single item over 35 ms except `mcp`; **about 0** from further import work | high | declined |
| Idle CPU / energy: the Mac app's own polls (agent pulse 1.5 s, screens 3 s, run 1 s) and the WebContent process | app open all day | continuous | **estimate, read from `ServeManager.swift` (5 Nov 2026): only while a window is visible and the serve is running, one `/api/agent-activity` every 1.5 s and, with Screens on (the Mac default), one `/api/projects/1/screens/status` every 3 s, plus `pollAgentActivity` every 20 s: about 1.0 request a second. At the page polls' measured ~7 ms of server time a request that is about 0.7% of a core, in the same band as the page's own 0.57% (which passed the 1% bar). The Swift side's cost is unmeasured (the app was not running; the poll endpoints need the serve's auth token, which the fixture helper does not expose)**. Slowing the pulse trades the live agent-activity indicator for under 1% of a core: declined unless an energy measurement says otherwise | n/a | for the resize session: `idle.mjs` shows the method |
| Playback follow: what remains after the variable fix is paint (about 200 ms a tick in headless software rendering, half of it the `bn-timecode-playing` animation) and the per-tick scan of every word span | watching a recording | daily | **WebKit (Playwright, not the app) 5 Nov 2026: no difference to the tick-to-painted-frame time, 80 ms (two frames of that engine's headless pace) whether the variable inherits or not, p90 81–82, 3 interleaved reps each (`playback-webkit.mjs`)**, so the fix shows up as main-thread headroom, not as a faster paint. The app's own WKWebView remains unmeasured: measure in the app before touching it | n/a | for the resize session, with `playback.mjs` |
| Sidebar `reloadData` per stdout line | during a run | occasional | premise stale (progress moved to the 1 Hz events poll); **about 0** until counted | low | measure first |
| Signals snapshot holds the loop at start | first start after upgrade | once per study | about 0.8 s at 1,500 quotes, one-off | medium | declined |
| Whisper alongside a mixed folder's hand-over | mixed folders only | rare | start latency only | low | declined for now |

**Next, not started (5 Nov 2026):** the Quotes and search lever (`React.memo` on `QuoteCard`). The ownership block has cleared (the display control is committed, `cfe9697c3`; `QuoteCard.tsx`, `QuoteGroup.tsx`, `QuotesContext.tsx` and `Toolbar.tsx` are clean), but the display-preferences session still has about 20 uncommitted files nearby. It is not a one-line change: `QuoteGroup` passes `QuoteCard` fresh values on every render (`allTagNames`, the `?? []` defaults, the `onExpandAbove` / `onExpandBelow` and `onProposed*` lambdas), so a `memo` does nothing until each is stabilised. Re-baseline against the current `QuoteCard`, stabilise, then A/B. Gain **unmeasured**. **Re-baselined 5 Nov 2026 against the current `QuoteCard`, 500-quote fixture, six reps, `interaction-profile.mjs --cases=search`: typical typing pace echo p50 13.6 ms, p90 46.9 ms (the first letter; the other letters 6–14 ms); slow typing p90 13 ms; burst p90 11 ms. The first-letter spike scales with the card count (170 ms at 1,500), so at a real study's 242 quotes it is about 25 ms, under the 100 ms bar. The search half of this lever is therefore worth little below roughly 1,000 quotes: demoted, not worth the invasive prop change on its own. The Quotes revisit (150–160 ms p90 at 242 quotes) is the remaining reason, and stays unstarted.**

**Quotes revisit re-split at real size (5 Nov 2026, 242-quote study, `--cases=lens-content`, 6 reps × 6 revisits, Chromium, current bundle):** Quotes revisit p50 116.6 / p90 172.8 ms, of which **fetch 92 ms and render 15 ms**; Transcript 122.6 / 179.3 (fetch 76, render 42). The `QuoteCard` memo can only touch the 15 ms render, so it cannot bring Quotes near 100 ms at this size, and the one experiment on the fetch half (sharing identical in-flight reads) moved Quotes 110 → 107 ms. **The memo lever is demoted to "only matters above ~1,000 quotes" and is not started on purpose.** What is left of the Quotes and Transcript revisit is the 15 requests a Quotes open fires and the browser's queue behind them, which the dedupe did not shorten: a design question (cache the lens's data across switches, with the staleness risk after an edit), not a render fix.

### Tried and not kept: bulk-validate the Transcript route's words

A `cProfile` of `/transcripts/{sid}` on a real 12,000-word session put 43 of 77 ms in pydantic's per-object `__init__` (12,386 `WordTimingResponse` objects). Validating each segment's words in one `TypeAdapter(list[...])` call returned **byte-identical responses on all 10 sessions**, and a first A/B read 300 → 266 ms. The interleaved repeat did not hold: **before 278 / 283 ms, after 271 / 269 ms over the ten sessions, about 1 ms a session, which is noise.** The profiler had inflated the cost of many tiny Python calls. Reverted. The route is 19–55 ms for 370–730 KB bodies, so the Transcript lens's 75 ms fetch is mostly the transfer and the parse in the page, not this. **A profile names a suspect; only a wall-clock A/B, interleaved and repeated, is a result.**

### Idle: an open, untouched report (measured 4 Nov 2026, `experiments/perf/idle.mjs`)

Quotes lens open on a real-size study, nothing touched, 90 s, headless Chromium and the serve: **40 requests a minute** (`/condition` and `/last-run`, every 3 s each), **page main thread 0.08% of a core** (70 ms of task time, 19 ms script), **server 0.49% of a core** (440 ms, about 7 ms a request). Bar set beforehand: combined CPU ≤ 1% and ≤ 1 request a second per window; passed (0.57% and 0.67 a second). Pausing the polls while the window is hidden would save about 0.5% of a core while hidden: declined. Not covered: the Mac app's own polls and its WebContent process, and powermetrics energy impact (needs sudo).

### A transcript write (measured 4 Nov 2026, `experiments/perf/transcript-reread.mjs`)

The critic's worry was that every speaker pick, split or join re-reads the transcript and rebuilds every word span. Firing the event the page listens for (`bn:speakers-written`) on three real transcripts: **the word spans are kept, not replaced; one DOM mutation record per re-read; 8 ms of script on 3,183 words, 18 ms on 14,254, 25 ms on 12,049; style and layout 0**. Nothing to fix. Not covered: the server's read (19–55 ms per session, measured above) and a real UI-driven write.

### Design note (5 Nov 2026, not built): a standby sidecar

The one big lever left on opening a study. **Estimate, not measured:** about 0.85 s per open, from the sandboxed app's own stage stamps (851 of 1,818 ms of a cold start is before `create_app`, and nothing in it depends on which study is chosen). Everything below is read from `cli.py` (`serve` binds the study at process start: `project_dir` goes in as an argument, `_refuse_unsafe_study` runs before the app is built, `create_app(project_dir, ...)` does the import) and `ServeManager.swift` (`start(projectPath:)` spawns per study, with the `ServeStartPolicy` watchdog).

- **What can be paid early:** interpreter start and imports (Python plus imports about 740 ms in dev), which do not read the study. **What cannot:** `create_app`, the database, the importer, the study-safety check and the auth token tied to the port.
- **Shape:** the app starts one standby `bristlenose serve --standby` at launch, which imports everything and then waits for one line (study path, token) on stdin or a control socket, and runs the existing bind path. The first open of a session is then mostly hidden behind the app's own launch; a second open needs a new standby started after the first is claimed.
- **Cost and risk, each a reason it is a design decision and not a fix:** an idle process holding about 140 MB (the figure behind the earlier decline of "warm on hover"); the standby must be thrown away when anything its environment was built from changes (provider, Screens, Agent Access); the study-safety refusal and the project-identity checks must still run on the claim, not at standby start; the sandbox hands a child the app's access, but a study chosen by bookmark needs its scope open before the claim; a standby that crashes must fall back to today's cold spawn, never to a hang.
- **Gate before building:** the interleaved sandboxed-app A/B (the open chip) must first show where the app's 851 ms really goes, because the dev numbers did not carry over once already.

### Design note (5 Nov 2026, not built): lens revisit from the last-known data

The lever behind the 92 ms Quotes revisit fetch (and Transcript's 76 ms): show a lens's last-known data at once and refresh it in the background, so a revisit costs the render (15 ms Quotes, 42 ms Transcript) instead of fetch plus render. **Estimate, not measured:** Quotes revisit p50 about 117 → 25–30 ms at real size, Transcript about 123 → 55 ms.

- **Why it is not a small change:** `apiGet` (`utils/api.ts`) returns one promise, so it cannot hand back stale data and then fresh data. Each lens's loader (`QuotesContext`, the transcript page, the Sessions grid, Codebooks, Signals) would need a two-phase read, and the sharing-identical-reads experiment already showed that moving fetch time around can turn up as render time elsewhere.
- **The risk is correctness, not speed:** after an edit (star, hide, tag, rename, a re-run) the revisit must not show the old value for a frame and then flip. The write path would have to invalidate or update the cache entry in the same step (a write epoch, as the dedupe experiment used), and an analysis run must clear it. A stale flash in a research tool is a trust problem, which is why this is the owner's call and not a tuning step.
- **Cheapest honest spike, if wanted:** Quotes only, one cache keyed by project and a write epoch, A/B with `lens-content` at 242 and 1,500 quotes, mutation-prove the invalidation. Decide on that number.

### What is left of the Screens-on premium

Delaying the Vision import does not remove it (1.5 s: 1,223 vs 1,191 ms; 4 s: 1,103–1,122 vs 1,070–1,124 ms; Screens off 927–969 ms), so about 100–150 ms at first health with Screens on is unexplained and inside this machine's noise: not chased. The `/screens` route handlers are plain `def`, so one that lands before the job's first check imports Vision in a threadpool thread, not on the event loop.

### Declined with the number

| Idea | Why |
|---|---|
| Faster server reads for a lens switch | 2–11 ms per route at real size |
| Import-time work beyond `inflect`, YAML and `mcp` | heaviest remaining single module 35 ms of 414 |
| Hover-prefetch and warm-sidecar on hover | no precedent, speculative ~140 MB spawn, 20 ms to gain |
| Dashboard query rework (S2) | SQL ≤ 4.4 ms; the 110 ms was a synthetic shape |
| Project import / migration deferral (SS-3) | 0.1–0.9 s import, 4–150 ms migrations, nothing to defer |
| VideoToolbox decode (MC-3) | refuted by two reviewers |
| First-request cost | our handler is 25 ms of 96; the rest is framework first-use |
| Share identical in-flight GETs (`apiGet`) | built, tested, measured, reverted: Codebooks 60 → 42 ms but Quotes 110 → 107 ms at real size (fetch time reappears as render) |
| Bulk-validate the transcript's words | a profiler mirage: 278/283 → 271/269 ms over ten sessions, about 1 ms each |
| Everyday CLI commands | `--help` 270 ms, `--version` 240, `status` 270, `use` 260 (all after the `inflect` fix); `codebooks` 1.1 s (the first plural loads `inflect`, 0.82 s, so it is a real need) and `pipeline` 1.3 s (any-llm readiness for a configured any-llm model, 0.72 s): rare commands, not daily; `doctor` 1.7 s does real checks |
| Pre-bind the last-opened study at launch | the app deliberately has no last-used fallback (it would spawn a sidecar on a study the researcher had not chosen), and `create_app` is welded to the study (database, watchers, the Screens, scene-strip and Signals jobs, which can make a paid call): a quiet bind would be a refactor of the server's core. The generic standby takes the part that does not depend on the study |
| Preload lens chunks on idle (all lenses) | chunks cost 8–40 ms; only Sessions suffered, from the Suspense throttle, and that is fixed on its own |

## Opening a study: the numbers and where the time goes

The moment: click a study in the sidebar, the report is ready. Measured in the Mac app (Debug build, the resize session's signposts, `design-client-performance.md` § Sidecar start); the page part measured here.

| | Median | Basis |
|---|---|---|
| Before the work | 4.1 s | measured |
| After the lazy `inflect` change | **3.1 s** (3,106 cold, 3,192 warm) | measured in the app, 5 runs, identical app binary |

Where a cold open goes, **from a separate batch of the same app** (5 cold runs, a different set of runs, so its 2,948 ms total and these medians do not sum to the 3,106 above):

| Part | Median |
|---|---|
| Click to spawn requested | 112 ms |
| **Sidecar boot to its port line** | **2,076 ms (70%)** |
| Port answers, then `/api/health` | 264 ms |
| Web view built and loading | 340 ms |
| Page mounts and posts `ready` | 210 ms |

- **The page is not the lever.** One run of `experiments/perf/page-ready.mjs` (10 reps, cold cache as the app's per-study web view has, on the 242-quote real-study copy; the output was not saved as a file): navigation to `ready` **WebKit 243 ms (220–272), Chromium 160 ms (144–197)**, 51 script files and about 290 KB on the wire before `ready`, four API calls (`health`, `condition`, two export statuses). Playwright's WebKit is not WKWebView and the app's 210 ms starts at `didFinish`, so read it as the same order of magnitude. `ready` follows one `/api/health` round trip after the shell mounts; that round trip was not timed.
- **Since then, in dev only:** the lazy MCP mount (about −0.4 s) and the Screens check off the event loop (about −0.3 s) took spawn → first health from 1,817 to 1,191 ms (−626 ms). **Not confirmed in the app**: the one noisy, non-interleaved app batch showed no drop. If the full 0.6 s carried over, a cold open would be about 2.5 s; that is arithmetic on a number the app has not shown yet.
- **Not measured:** reopening a study whose sidecar is still alive (the app keeps one for 90 s after its window closes, so it may skip the spawn), switching between two open studies, a large study (the importer adds about 0.7 ms a quote), a Release build. Not requested of anyone; named so the gap is visible.
- **The app A/B** (interleaved, quiet Mac) was approved by the owner: "Yes, run it when I'm away from the Mac". The session that owned the Mac-side measurements has ended; the method is in `desktop/scripts/perf/README.md`.
- **The big lever is not tuning, and its size can be bounded.** In the sandboxed app the sidecar reaches `create-app-start` **851 ms after spawn, of 1,818 ms to socket-bound (47%)** (the resize session's stage stamps): Python start and imports, which do not depend on which study is opened. In dev, with the same split, it is 776 of about 1,150 ms (the three project-independent parts: Python start, `serve` entry and importing the server app, 186 + 164 + 426 ms). A pre-started sidecar with its imports done, waiting for a study path, could therefore save **about 0.85 s per study open in the app** (an estimate from measured stages, assuming only the project-bound work is left after the click). It needs `create_app(project_dir)` split so binding happens after start, which is a design change, and costs about 140 MB of idle memory per spare. The "warm slot" in the code is dead. This is the Workspace item.

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
| HTML export skips the moderator-question lookup while the pill is parked (owner's call, 4 Nov 2026) | export of 1,500 quotes **3.1–3.5 s → 1.2 s**; SQL statements 9,346 → 343; time inside SQL 490 → 15 ms; embed 5.99 → 5.75 MB. The constant mirrors `featureFlags.moderatorQuestionPill` and a test reads the frontend default, so turning the pill on cannot leave an export without its data | `bcfae9c24` |
| Startup stage stamps (`BRISTLENOSE_STARTUP_TRACE=1`, `startup_trace.py`) | n/a (instrument: `@startup-stage <name> <epoch_ms>` on stderr at 14 points) | `f1963e516` |
| gzip at level 1 on the loopback-only server (kept as a one-line setting; its pin test was dropped on review, since the gain is about 0 at real size) | compression of `/quotes` 10.7 → 2.5 ms, `/tapestry` 12.7 → 1.8 ms (zlib on the real bodies, median of 30) | `b70c0787e` |

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

## Lens switch and search: the page baselines (measured 4 Nov 2026)

Production bundle, Chromium, headless Playwright against a copy of a real study (242 quotes, 10 sessions) and synthetic 500 and 1,500-quote studies. Each rep is a fresh page with a cold cache; pass 1 is the first visit, six more passes are revisits (n = 5 and 30 per run). `experiments/perf/moments.mjs`, `lens-requests.mjs`. Medians in ms; p50 repeats to 2–5% on revisits, p90 and first-visit values do not (n = 5).

| Lens | first visit p50 | revisit p50 / p90 | revisit target ≤ 100 |
|---|---|---|---|
| Project | 90 | 54 / 62 | pass |
| Sessions | **361 → 86–91** (this work) | 80 / 90 | pass |
| Transcript | 172 | 133 / 190 | **fail** |
| Quotes | 148 | 112 / 161 | **fail** |
| Codebooks | 74 | 59 / 67 | pass |
| Signals | 68 | 52 / 55 | pass |
| Discussion (landing) | n/a | 19 / 21 | pass |

- **Chunks never dominate**: 8–40 ms on a first visit over loopback. "Preload lens chunks" would save at most that.
- **The wait is the fetch, then the render.** At 1,500 quotes a Quotes revisit is 515 ms (fetch 417, render 72; in WebKit render 678). The server itself answers in under 10 ms at real size, so the fetch figure is mostly the queue behind duplicate requests.
- **Sessions first visit** was 360 ms because of **React 19's Suspense fallback throttle**: when a lazy component suspends, React commits the empty fallback and then holds the content back until 300 ms after that commit (`FALLBACK_THROTTLE_MS`). A 10 ms chunk cost 280 ms with the main thread idle. A patched react-dom with the throttle at 0 started the read at 46 ms instead of 309. A plain `import()` prefetch does not help, because a fresh `lazy()` always suspends on its first render; the loaded component itself must be rendered. Done for Sessions only, because only Sessions' chunk (a dependency chain) is slower than React's own commit of the fallback.
- **Search** (the browser field; the Mac's is native): echo 10 ms at one key every 700 ms, fine. **At a typical typing pace (a key every 170 ms, just over the 150 ms debounce) at 1,500 quotes the second key's echo is 170 ms**: the first letter's debounced commit lands as the second key arrives and re-renders all 1,500 cards (22k component renders per commit), blocking the field; 44 ms at 500 quotes, none at 242. Most of the cost is re-rendering and re-highlighting cards, not filtering (`filterQuotes` is about 4% of the React work).
- **A Quotes open fires 15 requests**: `/quotes` ×4, `/codebook` ×4, `/info` ×2; a Codebooks open fires 12. Lens chunks are also requested under two URL prefixes (`/assets/` and `/static/assets/`), so each is downloaded and evaluated twice (about 10 ms each, local).

### Tried and not kept: share identical in-flight reads (`apiGet`)

Identical GETs in flight together shared one request, with a write epoch (a read begun after a write never joins one begun before it), a one-second window and a copy per caller; 12 tests, four mutation proofs, full suite green. Quotes open went from `/quotes` ×4 to ×2. But: Codebooks revisit 60 → 42 ms (−30%); **Quotes revisit 110 → 107 ms at 242 quotes (noise) and 515 → 446 ms at 1,500 (−13%)**, because the fetch halves (88 → 44 ms) and the saved time reappears as render (14 → 54 ms) now that every consumer receives the data at once. Not worth a write epoch, a window and a copy rule for 18 ms on one lens. Reverted before commit. What it shows: at real size the Quotes lens is **render-bound**, so the lever is card re-render cost (`QuoteCard` memoisation with stable props), not the request count.

## At real study sizes the server is not the wait (measured 4 Nov 2026)

Server time to first byte on copies of two real studies (30 and 35 quotes, 3 and 5 sessions; `Server-Timing`, gzip on, median of ten after the first). Every read is a few milliseconds:

| Route | project-ikea | IKEA with uxfriends |
|---|---|---|
| `/quotes` | 9.0 ms, 36 queries, 35 KB | 9.6 ms, 36 queries, 59 KB |
| `/sessions` | 8.0 ms | 8.3 ms |
| `/dashboard` | 7.4 ms | 10.9 ms |
| `/tapestry` | 7.7 ms | 8.4 ms |
| `/codebook` | 6.1 ms | 7.9 ms |
| `/signals/snapshot` | 5.0 ms | 2.6 ms |
| HTML export | 122 ms, 327 queries, 2.4 MB | 139 ms, 385 queries, 2.5 MB |

So **a lens switch on a real study spends under 10 ms on the server**; whatever wait remains is the lens chunk loading and the page rendering, which is what the page baselines measure. This closes the server-side lens-switch candidates (S2, the Dashboard query cost, and the gzip work above) as not the lever at this size. The 1,500-quote numbers earlier in this file are the scale case: they matter for a study ten times the size of any real one here, not for the daily moment.

The first `/quotes` request of a serve's life is slower (about 90 ms against 9): the handler itself is 25 ms cold, and the rest is the framework's first use. Declined, with that number.

## Across macOS versions (correctness only, 4 Nov 2026)

The one thing in today's changes that depends on the OS is the `security` command-line tool behind the Keychain cache. Checked in the Iona guests (`sequoia` 15.7.3, `tahoe` 26.6.2) and on the host (27):

| | macOS 15.7.3 | macOS 26.6.2 | host (27) |
|---|---|---|---|
| Key not found | exit **44** | exit **44** | exit 44 |
| Write into a locked login keychain | exit **36** ("User interaction is not allowed") | exit **36** | n/a |
| Five lookups | 0.08 s | 0.11 s | 0.106 s |

So the cache's rule (keep a found key and exit 44; never keep anything else) matches what the OS returns on all three, and exit 36 is a real transient case, not a theory. Not run in the guests: the Python suite (they have only the system Python 3.9 and no project environment; building one for this question was not proportionate).

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
