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
