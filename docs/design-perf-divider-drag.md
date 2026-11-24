---
status: partial
date: 20 Nov 2026
last-trued: 2026-11-21
trued-against: HEAD@main (a8087ddbb) on 2026-11-21
area: desktop — sidebar divider drag (NavigationSplitView + NSOutlineView + WKWebView)
---

# Divider-drag performance: a worked case of "instrument, change one thing, re-measure"

Dragging the divider between the projects column and the report ran at **about 10–12 fps**
in the real Mac app. Two small commits took it to **about 40–47 fps** (1000×700 window, same
Mac, same drag) without rebuilding the sidebar. This page records what was measured, what the
causes were, what is fixed and what is deliberately left, so the next performance question
starts from a number instead of a guess.

**The lesson for a future session:** do not reason about a performance problem, measure it.
Every claim below came from a real-mouse drag and a trace, and two of the three wrong turns
in this session were caught only because a number looked wrong.

## Result

| Stage (optimised build, real app, 10 s drag) | Frames/s | Main thread busy |
|---|---|---|
| Before | 11–12 | about 9 s |
| After `40f74d9d3` (hold the outline reload) | about 20 at 1016 pt; 38.7–39.3 at 1000×700 | 7.4 s |
| After `2a4dfc989` (`lastSidebarWidth` into the reference box) | 42.5–46.8 at 1000×700 | 4.9 s |
| Control: bare web view in an AppKit split, report page | about 52–55 | n/a |
| Control: bare web view in a SwiftUI split, report page | about 44–48 | n/a |
| Control: trivial page, either shell | 60 | n/a |

Read the controls first: **the realistic ceiling for this shell is roughly 45–55 fps**, so
"a fact of life" was wrong (there was a 4× gap) and "get to 60" would also be wrong. The
absolute fps depends on window size, so compare only runs at the same size and the same
sweep. Idle is 60.

## Causes

1. **A full outline reload per drag frame.** `SidebarOutlineController.update()` holds its
   reload while a window is in live resize (`liveResizing`, `reloadOwedAfterResize`). A
   *divider* drag raises none of those notifications (measured: 1093 frame changes, 0
   live-resize starts or ends; a window-corner drag gave 1 and 1). So the hold never engaged
   and each frame ran `reloadData`, about 3 s of a 9 s drag.
2. **`ContentView.body` re-evaluated per drag frame.** `lastSidebarWidth` was `@State`,
   written whenever the resting column width changed, which on a divider drag is every frame.
   Only handlers read it, but a `@State` write re-evaluates the whole body and rebuilds the
   toolbar. The 3 Nov 2026 fix had moved `split` and `detail` into the `WidthReadings`
   reference box and missed this one.

## The two approaches

| Commit | Approach | Size |
|---|---|---|
| `40f74d9d3` | **Hold the work.** Observe `NSSplitView.willResizeSubviewsNotification`; while the left button is down and the window is not itself in live resize, call the existing `onLiveResize(true)`. A 50 ms timer polling `NSEvent.pressedMouseButtons` ends it, because the split view posts no "drag ended". | 34 lines, `ProjectSidebarOutline.swift` |
| `2a4dfc989` | **Remove the trigger.** Move `lastSidebarWidth` into `WidthReadings`. Same reads and writes, no body re-evaluation. | 13 lines, `ContentView.swift` |

Each is its own commit and reverts alone (`git revert <sha>`). Neither touches the
auto-collapse decision, `restingColumnWidth` or the geometry readers.

## Method (reuse this)

1. **Controls before blame.** A throwaway app (`experiments/divider-drag/lab.swift`) puts a
   bare `WKWebView` in an AppKit split and a SwiftUI split, loading either a trivial page or
   the real report. This sets the ceiling and shows whether the shell or our code is the cost.
2. **A real mouse, not a synthetic resize.** `drag.swift` / `drag2.swift` post CGEvent
   mouse-down, a 120 Hz sine of ±45 pt for 10 s, and mouse-up, at the divider's live
   position (read from Accessibility by `findsplit.swift`). Needs Accessibility trust; run
   when nobody is at the Mac.
3. **Measure at the page, not the host.** A rAF probe (injected by `wrap.py`, a stand-in dev
   sidecar that fronts `bristlenose serve` and serves its beacons from memory) records frame
   times and `innerWidth`. `appmeasure.sh` turns one 10 s window into fps, gap p50/p95/max,
   gaps over 33 and 50 ms, and the number of width changes. **A run with zero width changes
   did not drag: discard it.**
4. **Profile with xctrace Time Profiler**, attached for the drag, aggregated by main-thread
   inclusive time (`top3.py`). The first profile named the culprit
   (`updateNSViewController` 3.05 s); the later ones showed it gone and what remained.
5. **One change per commit, re-measured at the same window size.** For experiment 2 a
   baseline without it was rebuilt and measured alongside, so "39 → 42–47" is like for like.
6. **Build optimised, in a scratch DerivedData.** `xcodebuild ... -derivedDataPath <scratch>
   SWIFT_OPTIMIZATION_LEVEL=-O SWIFT_COMPILATION_MODE=wholemodule ENABLE_TESTABILITY=NO`. An
   optimised Debug-configuration build performed identically to plain Debug here. A copy
   must be re-signed with the **Apple Development identity and the original entitlements**
   (an ad-hoc signature fails to spawn: "Launchd job spawn failed, 163"). The dev hooks
   `BRISTLENOSE_DEV_SIDECAR_PATH` / `BRISTLENOSE_DEV_EXTERNAL_PORT` are `#if DEBUG` only.

## Pitfalls hit (each cost a rerun)

- A **full-screen window** ignores `setsize` and moves the divider's screen position: every
  hard-coded coordinate is then wrong. Leave full screen, resize, then read the divider.
- A drag with no width changes looks like "60 fps". Always check `width_changes`.
- The harness found the installed app (same bundle id `app.bristlenose`) before the scratch
  build; address the scratch copy by PID, and never click in the installed app.
- `NSWindow.willStartLiveResize` is the wrong signal for a divider drag (see cause 1).
- Compare like with like: a 700 pt window gave 22–24 fps where 1016 pt gave 20.
- The sandbox blocks a wrapper writing a log file; keep timestamps in memory and serve them.

## What remains, and what was deferred

Profile of the final build: main thread busy 4.9 s of 10. About 1.76 s is the split view
handling the drag and laying out its columns; `NSToolbarView.layout` about 0.56 s;
SwiftUI `sizeThatFits` passes about 0.1 s each; the web view's layer-tree commit about
0.15 s. No Bristlenose function is among the hot spots.

Deferred, with the reason:

- **Toolbar relayout** (about 0.56 s, roughly 11% of the remaining busy time). Means changing
  the toolbar's structure; the riskiest remaining item. Owner decision, 20 Nov: not before
  App Store submission.
- **Short-circuit `update()`** when nothing relevant changed. Riskier; likely after submission.
- **Is fix 1 still needed now that fix 2 exists?** Unmeasured. Measure fix 2 alone before
  removing anything.
- **A test for the hold.** None exists, so a future AppKit change could quietly return the
  drag to 11 fps. It reads live mouse state; extract `shouldBeginHold(timerActive:inLiveResize:
  buttonsDown:)` with an injectable button reader to make it testable.
- **Buttonless divider moves** (keyboard, accessibility, the collapse/expand animation) still
  reload per frame. A time-based hold (release N ms after the last `willResizeSubviews`)
  would cover them, at the cost of a debounce constant and a short stale tail.
- **Not measured:** a literal Release build, Mail and Finder, other Macs, macOS 15 (whether
  `NavigationSplitView` there posts the same notification; if not, behaviour is the old
  per-frame reload, not a break).
- **WebKit bug 323132** (compositor lag) is separate work; the rAF probe does not measure it.

## Known downsides of what shipped

- The hold can outlast the drag by up to one 50 ms tick, or through a later tracking loop or
  modal; sidebar rows such as run progress freeze until release, then recover.
- Any left press during the hold window starts or extends it (a title-bar drag, the
  collapse animation). Harmless; it ends on mouse-up.
- One Mac (M2 Max, macOS 27), one 90 pt sweep, a 200–300 pt sidebar range.
- Review (Fable code-review agent, read-only, 20 Nov 2026): verdict good, no correctness bug
  found; it read the code and ran nothing.
- Swift suite: one failure, `PoolStarvationTimeoutTests.aTimedReadGivesUpWhenOnlyAFewReads
  AreStuck` (timing, unrelated), passed alone in 0.5 s; not re-run against a clean baseline.

## Related

- `desktop/scripts/perf/README.md` — the 4 Nov window-drag profile this extends.
- `desktop/gotchas.md` §"Sidebar, toolbar and window layout" — the divider-drag gotcha.
- `docs/sidebar-column-diagnosis.md` — the projects-column width logic (the scar tissue;
  untouched here).
- `experiments/divider-drag/` — the harness sources (not lint-clean; excluded from ruff).
