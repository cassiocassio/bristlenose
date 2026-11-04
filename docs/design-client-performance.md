# Client performance: what was measured, what was fixed, what was left

Written 4 Nov 2026 after "redraw on window resize is getting slow". Safari was fast and the Mac app was not, so the page was not the whole story. The method is the useful part: every claim below is a number from a recording, and the recordings can be repeated.

## How to measure

| What | Tool | Runs on |
|---|---|---|
| The Mac shell: how often the window takes a new size during a real drag, and where the main thread goes | `desktop/scripts/perf/profile-resize.sh` (real-mouse drag + `xctrace`; README there) | a Debug build against a running `bristlenose serve --dev`; moves the pointer, run it when nobody is at the Mac |
| The web view's own process (WebContent) | `xctrace record --all-processes` during the same drag, then read the busiest `com.apple.WebKit.WebContent` | same |
| The page: layouts, style recalcs, script time, long tasks per route and interaction | `experiments/perf/` (Playwright, Chromium for CDP counters, WebKit for step times) | any browser against the dev server |
| Which JS the page runs per step | `experiments/perf/cpu-profile.cjs` | dev server only (needs unminified source) |

Three traps that cost time. A profile of a study with no report measures a sidebar and no page (an unanalysed study shows a native pane; `select-study` now fails if no web area renders). "Main thread busy" cannot rank builds once the thread is saturated: use window updates per second. Debug inflation turned out small here. A Release-configuration build (hardened runtime, team-signed with the `.dmg` script's development-signing arguments, bundled sidecar, no Debug-only server flag; `BN_RELEASE=1 BN_WAIT=120 profile-resize.sh`) shows the same picture as Debug and as an optimised Debug-signed build: before my fixes 10.2 window updates a second, median gap 99 ms; now 59.1–59.4, median gap 17 ms, p95 23 ms (two runs each). The cost sits in AppKit, SwiftUI's AttributeGraph and WebKit, which are system code. What was not measured is the App Store (Apple Distribution) signing and the sandboxed MAS entitlements, which this build does not carry.

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

## Sidecar start (the `serve-ready` signpost)

`desktop/scripts/perf/serve-ready.sh` reads the app's own `serve-ready` signpost (the sidecar spawned until its port answers) from a copy of the app whose bundled sidecar is the one under test: cold is a fresh copy of the app per run, warm is a relaunch of the same copy. Measured 4 Nov 2026 as an A/B for the lazy `inflect` import (`6f5b0e350`: `import bristlenose.cli` 1.05 s to 0.22 s, `import bristlenose.server.app` 1.8 s to 0.8 s on the dev venv). Debug-signed app, ad-hoc-signed hardened-runtime sidecar (`ensure-sidecar.sh`'s default, which is what Cmd+R builds), the same app binary in both arms, 5 runs each:

| sidecar | serve-ready median (min–max) | project-select median |
|---|---|---|
| old (0.44.0 build from before the change), cold | 3,194 ms (2,960–3,452) | 4,097 ms |
| old, warm | 3,128 ms (2,983–3,487) | 4,000 ms |
| new (rebuilt from the tree), cold | 2,241 ms (2,194–2,299) | 3,106 ms |
| new, warm | 2,330 ms (2,007–3,428) | 3,192 ms |

About 0.9–1.0 s off a study's start, and the same off click-to-ready. Cold was not slower than warm here (a fresh copy of the files did not cost a visible first-exec penalty), so the 15-to-90-second cold-start budget the desktop notes describe is not reproduced by this method. The new sidecar was built from the working tree, which carries other sessions' uncommitted edits (theme CSS and the like); none of them is on the import path.

### Where the rest of `project-select` goes

`PerfSignpost.step` marks points inside it (signpost event `project-select-step`), and `serve-ready.sh` prints the median of each part. Same new sidecar and same Debug app as above; 5 cold runs and 2 usable warm runs (3 warm relaunches in that batch never came up, so there is no warm n=5 here); medians in ms:

| part | median | min–max |
|---|---|---|
| click to spawn requested | 112 | 105–114 |
| process spawn call | 11 | 10–12 |
| **process spawned to the sidecar printing its port** | **2,076** | 2,008–2,343 |
| port line to the port answering | 67 | 26–73 |
| port answering to `/api/health` answered | 197 | 190–218 |
| health answered to the web view starting to load | 139 | 102–174 |
| web view load started to `didFinish` | 201 | 182–455 |
| `didFinish` to the page posting `ready` | 210 | 168–339 |
| **click to report ready** | **2,948** | |

About 70% of the wait is the sidecar booting (Python start, imports, app construction and bind, up to the line it prints). The 0.8 s after it answers is split roughly evenly between the health call, building the web view, the page load and the SPA mounting, so no single native or page step is large. The next lever is inside the sidecar's own start, and it needs a profile of that process, not of the Mac app.

## Considered and left, with the reason

- **Shared rAF-coalescing `ResizeObserver` helper across 16 files.** The callback bodies total ~26 ms; the loop-error warning is noise, not cost. Revisit only if a profile names them.
- **`React.memo` on `QuoteCard`, `contain: content`, `will-change`, virtualising the grid.** Each guards or targets work the selector change removed, or layout and paint (1.1 s combined, unchanged).
- **Toolbar layout (`NSToolbarView layout`, ~1.6 s of a Debug trace).** AppKit laying out SwiftUI toolbar items; the window already updates at the display rate.
- **Opaque `WKWebView` (currently `drawsBackground = false`).** Measured, no effect. A throwaway build with an environment toggle, scripted drag, two runs per arm: window updates 60.0 / 59.3 per second transparent against 59.8 / 59.2 opaque, main thread busy 6.55–6.61 s against 6.60–6.66 s, WebKit's share the same. The window was already at the display rate, so there was no gap for compositing to explain.
- **Other native ideas from the research, not pursued.** `NSHostingView.layout` and the AttributeGraph (about 1.2 s each in a Debug trace of 6.5 s busy) are the remaining shell cost; splitting `ContentView` into leaf views or setting `sizingOptions` would chase them, but the window is at 60 updates a second, so there is no felt gap to close in Debug. Revisit if a Release build falls short. Automatic row heights for the sidebar outline: not applicable (`rowSizeStyle = .custom`, so the setting is inert).

## Open

- **The App Store signing.** The Release-configuration build above was signed for development (no Apple Distribution identity or MAS provisioning profile locally). It runs the same code, optimised; a TestFlight build is not expected to differ, but that is an inference.
- **Sidebar toggle and lens switch.** Profiled with `BN_MODE=sidebars node cpu-profile.cjs` (dev build, six opens and six closes): about 43 ms of React work per toggle, mostly the panel mounting its own contents (`TagRow`, `TagGroupCard`, `SidebarLayout`) and `QuoteCard` about 5 ms. That is the cost of opening a panel and is not repeated work, so it was left. Lens switch, native side (`BN_ACTION=lens profile-resize.sh`, 20 switches through the sidebar's lens rows, Debug, two runs): about 240 ms of main-thread CPU per switch, accessibility calls from the harness only 4% of it; the SwiftUI graph update is about 100 ms and `NSToolbarView` layout about 49 ms a switch, which is the toolbar morphing its items per lens. That is the designed behaviour (`desktop/CLAUDE.md`, "Toolbar morphing"), and changing it is a toolbar restructure, not a small fix, so it was left. Lens switch, page side (`BN_MODE=lenses`, 24 clicks through the tabs): about 43 ms of React per switch, spread over whichever lens is being mounted; the hidden settings, export and feedback modals re-rendering is about 8% of it (under 4 ms a switch), so it was left.
- `ActivityStore.test.ts` (`a write that fails after one that worked...`) fails on this machine because it runs Node 26 and the repo pins Node 24 (`.tool-versions`): Node's built-in web storage replaces jsdom's `Storage`, so the test's spy on `Storage.prototype.setItem` never intercepts. An environment difference, not a regression: on the pinned Node 24 (`/opt/homebrew/opt/node@24/bin`) that file passes 53 of 53 and the whole frontend suite passes (217 files, 3,855 tests) with a clean `tsc`. Run the suite with the pinned Node.
