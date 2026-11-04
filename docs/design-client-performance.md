# Client performance: what was measured, what was fixed, what was left

Written 4 Nov 2026 after "redraw on window resize is getting slow". Safari was fast and the Mac app was not, so the page was not the whole story. The method is the useful part: every claim below is a number from a recording, and the recordings can be repeated.

## How to measure

| What | Tool | Runs on |
|---|---|---|
| The Mac shell: how often the window takes a new size during a real drag, and where the main thread goes | `desktop/scripts/perf/profile-resize.sh` (real-mouse drag + `xctrace`; README there) | a Debug build against a running `bristlenose serve --dev`; moves the pointer, run it when nobody is at the Mac |
| The web view's own process (WebContent) | `xctrace record --all-processes` during the same drag, then read the busiest `com.apple.WebKit.WebContent` | same |
| The page: layouts, style recalcs, script time, long tasks per route and interaction | `experiments/perf/` (Playwright, Chromium for CDP counters, WebKit for step times) | any browser against the dev server |
| Which JS the page runs per step | `experiments/perf/cpu-profile.cjs` | dev server only (needs unminified source) |

Three traps that cost time. A profile of a study with no report measures a sidebar and no page (an unanalysed study shows a native pane; `select-study` now fails if no web area renders). "Main thread busy" cannot rank builds once the thread is saturated: use window updates per second. Debug inflation turned out small here: an optimised build (`-O`, no debug dylib, still Debug-signed so the external-server flag works) gave the same picture as Debug (before 10.3 updates/s, after 57–60), because the cost sits in AppKit, SwiftUI's AttributeGraph and WebKit, which are system code. The App Store Release build itself was not measured (it needs production signing and the bundled sidecar).

## What was found and fixed (Debug, rendered report, two runs each, repeatable to ~2%)

Window size updates per second during a 10 s scripted drag (60 is the display):

| build | updates/s | median gap |
|---|---|---|
| before any fix | 10 | 100 ms |
| sidebar held still during live resize; toolbar-inset JS deduped (`635db86d5`) | 33 | 31 ms |
| + ContentView no longer rewrites two `@State` widths per frame (`067c5abe8`) | 58 | 16.7 ms |

The web view, from the system-wide trace of the same drag (WebContent main thread): 4,145 ms busy, 2,337 ms of it `ResizeObserver` callbacks and the React re-render they trigger, layout only 666 ms. `useSidebarStore()` handed every subscriber the whole store and `SidebarLayout` writes the layout width into it on every step, so the whole report re-rendered per pixel, hidden modals and every quote card included. Fixed by `useSidebarSelector` (`a3a2c7b00`): WebContent main thread 4,145 → 1,705 ms, `ResizeObserver` JS 2,337 → 24 ms. Page-side (Chromium, 75-step sweep, Quotes): script 1,496 → 146 ms, long tasks 3 → 0; sessions, dashboard, transcript and signals also fell 49–93%.

## Click latency (not resize)

`SidebarDeselectMonitor` ran on every left mouse-down in the window and walked the whole view tree to find the sidebar's table before it looked at where the click was. It now hit-tests first and walks up from the view that was hit, with the same rule as before (a click only counts if it landed on the table or inside it). Forty scripted clicks in the report area (`BN_ACTION=click profile-resize.sh`, Debug, two runs each): the monitor's time 649 / 666 ms → 8 / 9 ms (about 16 ms → 0.2 ms a click), main thread busy 1,274 / 1,272 → 725 / 708 ms. The behaviour (deselecting on a click below the rows, not on a button drawn over the list) is unchanged by construction and has no unit test, because the coordinator is private.

## Considered and left, with the reason

- **Shared rAF-coalescing `ResizeObserver` helper across 16 files.** The callback bodies total ~26 ms; the loop-error warning is noise, not cost. Revisit only if a profile names them.
- **`React.memo` on `QuoteCard`, `contain: content`, `will-change`, virtualising the grid.** Each guards or targets work the selector change removed, or layout and paint (1.1 s combined, unchanged).
- **Toolbar layout (`NSToolbarView layout`, ~1.6 s of a Debug trace).** AppKit laying out SwiftUI toolbar items; the window already updates at the display rate.
- **Opaque `WKWebView` (currently `drawsBackground = false`).** Measured, no effect. A throwaway build with an environment toggle, scripted drag, two runs per arm: window updates 60.0 / 59.3 per second transparent against 59.8 / 59.2 opaque, main thread busy 6.55–6.61 s against 6.60–6.66 s, WebKit's share the same. The window was already at the display rate, so there was no gap for compositing to explain.
- **Other native ideas from the research, not pursued.** `NSHostingView.layout` and the AttributeGraph (about 1.2 s each in a Debug trace of 6.5 s busy) are the remaining shell cost; splitting `ContentView` into leaf views or setting `sizingOptions` would chase them, but the window is at 60 updates a second, so there is no felt gap to close in Debug. Revisit if a Release build falls short. Automatic row heights for the sidebar outline: not applicable (`rowSizeStyle = .custom`, so the setting is inert).

## Open

- **The App Store Release build.** Needs production signing and the bundled sidecar, and `BRISTLENOSE_DEV_EXTERNAL_PORT` is Debug-only, so the harness cannot drive it. The `-O` build above is the closest proxy.
- **Sidebar toggle and lens switch.** Profiled with `BN_MODE=sidebars node cpu-profile.cjs` (dev build, six opens and six closes): about 43 ms of React work per toggle, mostly the panel mounting its own contents (`TagRow`, `TagGroupCard`, `SidebarLayout`) and `QuoteCard` about 5 ms. That is the cost of opening a panel and is not repeated work, so it was left. Lens switch (`BN_MODE=lenses`, 24 clicks through the tabs): about 43 ms of React per switch, spread over whichever lens is being mounted; the hidden settings, export and feedback modals re-rendering is about 8% of it (under 4 ms a switch), so it was left.
- `ActivityStore.test.ts` (`a write that fails after one that worked...`) fails on this machine because it runs Node 26 and the repo pins Node 24 (`.tool-versions`): Node's built-in web storage replaces jsdom's `Storage`, so the test's spy on `Storage.prototype.setItem` never intercepts. An environment difference, not a regression; it passes on the pinned Node.
