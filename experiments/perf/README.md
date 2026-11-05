# Page-side perf harness

Measures what the browser does inside the React SPA (layout, style, script, observers) while the
viewport is resized or the user interacts. It does not measure the server, the API or the native shell.
Needs a running `bristlenose serve --dev <project>`; no new dependencies (uses `e2e/node_modules`).

## Run

```sh
cd experiments/perf
node page-resize-profile.mjs                      # all routes, Chromium, width sweep 1500->760->1500 step 20
node page-resize-profile.mjs --browser=webkit     # per-step wall time + ResizeObserver stats only
node page-resize-profile.mjs --routes=quotes --mode=drag --trace   # 4px steps, plus a Perfetto trace
node interaction-profile.mjs [--browser=webkit] [--trace]          # scroll, sidebars, lens tabs on Quotes
node summarise.mjs --baseline=results/<before>.json results/<after>.json
```

Routes: `quotes sessions dashboard transcript signals` (transcript URL is discovered from the sessions page).
Flags: `--tag=name` stamps a label into the JSON, `--verbose` lists the top ResizeObserver callbacks.
`BN_URL` overrides the server (default `http://127.0.0.1:8484`); the scripts exit 2 if it is unreachable.
Results land in `results/` (gitignored), stamped with git sha (`+dirty` if the tree has changes), browser, route and sweep.
Traces go to `results/traces/*.json`: open in https://ui.perfetto.dev or `chrome://tracing`.

## What the numbers mean

- **step mean/p90/max ms**: wall time from `setViewportSize` (or the interaction) to the second `requestAnimationFrame`, i.e. until the frame is produced. Lens-tab steps are click-to-painted. Lower is better; p90 and max matter more than the mean.
- **layouts, layout ms, style ms, script ms, task ms** (Chromium CDP `Performance.getMetrics`, deltas over the run): how many layouts and style recalcs happened and how long the main thread spent in layout, style, JS, and in total. The fastest way to see a change that "does less work".
- **RO calls / RO ms**: ResizeObserver callbacks and the time inside them, summed; `--verbose` breaks it down by callback source. This is the only cost breakdown WebKit gives.
- **RO loop err**: "ResizeObserver loop completed with undelivered notifications" errors; a nonzero count means a callback changed layout that another observed. The page also logs a few on initial load, so compare against a baseline rather than expecting zero.
- **long tasks / LoAF**: tasks over 50 ms, and long animation frames (Chromium only). **CLS**: layout shift score.

## Limits

- WebKit (Playwright's build, not Safari proper) has no CDP: no layout/style counts, no trace, no longtask/LoAF. Its step times are rounded to whole milliseconds and run higher than Chromium's, since the double rAF is paced to the display.
- Neither browser is the macOS WKWebView in the app; use WebKit for direction, not absolute values. Headless frame timing is not display-vsync-accurate.
- Numbers shift run to run (about 10 to 20 percent on step times). Compare like with like (same browser, same route, same project data), repeat once, and trust counts (layouts, RO calls) over milliseconds.
- Trace files are large (tens of MB for a full sweep).

## Compare

Run once on the old code and once on the new, same flags, then `summarise.mjs --baseline=old.json new.json`.
Rows are matched on route and label; the delta column is the percentage change (positive = more work).

## cpu-profile.cjs

`node cpu-profile.cjs` takes a CDP sampling CPU profile of the Quotes page through a 142-step width sweep and prints inclusive time by source location. Against the dev server only (it needs unminified names). Read the `react-dom` rows first: `performSyncWorkOnRoot` is the React work a width step causes, and the components under it are what re-rendered. It found the whole-report re-render of 4 Nov 2026; see `docs/design-client-performance.md`.

## The ledger's two moments (`moments.mjs`)

Baselines for `docs/design-perf-ledger.md` rows 1 and 2. Serve the PROD bundle on your own port (never `--dev`, never the shared :8484):

```sh
.venv/bin/python experiments/perf/serve-fixture.py <copy-of-a-project>     # prints BN_URL=http://127.0.0.1:<port>
cd experiments/perf
BN_URL=... node interaction-profile.mjs --cases=lens-content [--browser=webkit] [--reps=5] [--revisits=6] [--cache=warm]
BN_URL=... node interaction-profile.mjs --cases=search       [--browser=webkit] [--reps=8]
```

- **lens-content**: click a lens tab in the page; the step ends at a double rAF after that lens's own content selector appears, with no sleep inside the timed region (the old `lenses` case sleeps 50 ms and stops at the blank Suspense frame, so its numbers are not a baseline). Each rep is a fresh page (cold HTTP cache unless `--cache=warm`): pass 1 is first visit, passes 2.. are revisits. The step is split from resource timing along the critical path into chunk (click to last JS/CSS byte), mount (chunk end to the lens's own read starting), fetch (the read) and render (read end to painted); `full` is when the card count stopped growing (a lens may draw in batches). The landing lens (Discussion) has no first visit. Signals is disabled on the synthetic fixtures (no sentiment data) and is skipped there.
- **search**: browser field only (`SearchBox.tsx`; the Mac app's field is native). Types a 6-letter word that was probed to change the result set on its last character, at 700 / 170 / 60 ms between keys. Echo is keydown to the second rAF after the input event. Results are last keystroke to the last paint of a changed `.quote-card` count, minus the 150 ms debounce. Chromium also reports CDP script/layout/style ms per typing.
- **Who re-rendered**: `BN_MODE=search BN_COUNT=1 node cpu-profile.cjs` counts components rendered per commit (a DevTools-style commit hook); without `BN_COUNT` it takes a CPU profile of the typing. Both need unminified source: run your own Vite (`BN_VITE`, see the header of `cpu-profile.cjs`).



## The 4 Nov 2026 probes (one line each; all need a served COPY, see `serve-fixture.py`)

- `lens-requests.mjs`: API requests, repeats and chunk requests (and any under two URL prefixes) when a lens opens.
- `page-ready.mjs`: navigation to the embedded `ready` message with a cold cache, as the app's per-study web view has.
- `idle.mjs`: requests per minute and page and server CPU for an open, untouched report.
- `playback.mjs`: what following a recording costs the transcript page (synthetic player time-updates).
- `playback-webkit.mjs`: the same ticks in WebKit, tick-to-painted-frame time, interleaved A/B on the progress variable.
- `transcript-reread.mjs`: what a speaker write's re-read costs the transcript page.
