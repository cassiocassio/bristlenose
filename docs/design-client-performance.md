# Client performance: what was measured, what was fixed, what was left

Written 4 Nov 2026 after "redraw on window resize is getting slow". Safari was fast and the Mac app was not, so the page was not the whole story. The method is the useful part: every claim below is a number from a recording, and the recordings can be repeated.

## How to measure

| What | Tool | Runs on |
|---|---|---|
| The Mac shell: how often the window takes a new size during a real drag, and where the main thread goes | `desktop/scripts/perf/profile-resize.sh` (real-mouse drag + `xctrace`; README there) | a Debug build against a running `bristlenose serve --dev`; moves the pointer, run it when nobody is at the Mac |
| The web view's own process (WebContent) | `xctrace record --all-processes` during the same drag, then read the busiest `com.apple.WebKit.WebContent` | same |
| The page: layouts, style recalcs, script time, long tasks per route and interaction | `experiments/perf/` (Playwright, Chromium for CDP counters, WebKit for step times) | any browser against the dev server |
| Which JS the page runs per step | `experiments/perf/cpu-profile.cjs` | dev server only (needs unminified source) |

Three traps that cost time. A profile of a study with no report measures a sidebar and no page (an unanalysed study shows a native pane; `select-study` now fails if no web area renders). "Main thread busy" cannot rank builds once the thread is saturated: use window updates per second. And Debug numbers are inflated, so compare Debug with Debug; nothing here was measured in Release.

## What was found and fixed (Debug, rendered report, two runs each, repeatable to ~2%)

Window size updates per second during a 10 s scripted drag (60 is the display):

| build | updates/s | median gap |
|---|---|---|
| before any fix | 10 | 100 ms |
| sidebar held still during live resize; toolbar-inset JS deduped (`635db86d5`) | 33 | 31 ms |
| + ContentView no longer rewrites two `@State` widths per frame (`067c5abe8`) | 58 | 16.7 ms |

The web view, from the system-wide trace of the same drag (WebContent main thread): 4,145 ms busy, 2,337 ms of it `ResizeObserver` callbacks and the React re-render they trigger, layout only 666 ms. `useSidebarStore()` handed every subscriber the whole store and `SidebarLayout` writes the layout width into it on every step, so the whole report re-rendered per pixel, hidden modals and every quote card included. Fixed by `useSidebarSelector` (`a3a2c7b00`): WebContent main thread 4,145 → 1,705 ms, `ResizeObserver` JS 2,337 → 24 ms. Page-side (Chromium, 75-step sweep, Quotes): script 1,496 → 146 ms, long tasks 3 → 0; sessions, dashboard, transcript and signals also fell 49–93%.

## Considered and left, with the reason

- **Shared rAF-coalescing `ResizeObserver` helper across 16 files.** The callback bodies total ~26 ms; the loop-error warning is noise, not cost. Revisit only if a profile names them.
- **`React.memo` on `QuoteCard`, `contain: content`, `will-change`, virtualising the grid.** Each guards or targets work the selector change removed, or layout and paint (1.1 s combined, unchanged).
- **Toolbar layout (`NSToolbarView layout`, ~1.6 s of a Debug trace).** AppKit laying out SwiftUI toolbar items; the window already updates at the display rate.
- **Opaque `WKWebView` (currently `drawsBackground = false`).** No trace points at compositing. An A/B would be one environment variable in a throwaway worktree; do it only if the update rate falls short of 60 in Release.

## Open

- **Click latency, not resize.** `SidebarDeselectMonitor` (`ContentView.swift`) walks the whole view hierarchy to find the sidebar table on every left mouse-down: 190 ms in a Debug trace. A hit-test first, then an ancestor lookup, would replace it. Untested because the coordinator is private.
- **A Release measurement.** The harness needs `BRISTLENOSE_DEV_EXTERNAL_PORT`, which only Debug builds read. A Release number needs the bundled sidecar or a flag.
- **Sidebar toggle and lens switch** in the browser still show a few long tasks (5 and 2 in the interaction profile); not investigated.
- `ActivityStore.test.ts` fails in isolation (`a write that fails after one that worked...`), in files this work did not touch.
