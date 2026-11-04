# Native resize profile

A repeatable measurement of what a window drag costs the Mac app. Written 4 Nov 2026 after
"redraw on window resize is getting slow": Safari was fast, the app was not, and a profile
of the app showed why. These tools exist so the next claim of "faster" is a number.

```
desktop/scripts/perf/profile-resize.sh <Bristlenose.app> <label> [seconds=10]
desktop/scripts/perf/summarise-trace.py --compare /tmp/bn-perf/a.json /tmp/bn-perf/b.json
```

`profile-resize.sh` opens a NEW copy of the app against a running `bristlenose serve --dev`
(`BRISTLENOSE_DEV_EXTERNAL_PORT`, default 8484; Debug builds only), selects a study with a
report (`BN_STUDY`, default `Talismanic`) and a lens (`BN_LENS`, default `Quotes`), starts
the window from a fixed 1200 pt frame, and drags its right edge between 900 and 1500 pt with
a **real mouse** (`resize-drag.swift`, CGEvent) while `xctrace` records the main thread.
`select-study.swift` presses the sidebar row through Accessibility and **fails if no web
area renders**: an unanalysed study shows a native "files to analyse" pane, and a profile of
that measures a sidebar with no page behind it (the first runs of 4 Nov did exactly that).

It moves the real pointer for the length of the drag and needs Accessibility trust: run it
when nobody is at the Mac, one run at a time. Debug numbers are inflated (SwiftUI and
AttributeGraph most of all): compare Debug with Debug, Release with Release.

## What the numbers mean

- **window updates / s** and the **gap** rows are the one to believe: how often the window
  actually took a new size while the pointer moved at 120 Hz. A saturated main thread reads
  "busy" however slow or fast each frame is, so *main busy* only locates cost, it does not
  rank builds. 60/s is the display's rate; a 100 ms gap is a stutter.
- The frame rows are inclusive time on the main thread (a frame and everything it calls).
  `WebKit frames` is the main thread's share of the web view; the web view's own layout runs
  in the WebContent process and is not in this trace.

## 4 Nov 2026 result (Debug, Talismanic / Quotes, two runs each, repeatable to ~2%)

| build | window updates/s | median gap | sidebar table layout | ContentView.body | AttributeGraph |
|---|---|---|---|---|---|
| before any fix | 10 | 100 ms | 3.0 s | 0.4 s | 3.1 s |
| sidebar held during live resize, toolbar-inset dedupe | 33 | 31 ms | 0.01 s | 1.2 s | 5.0 s |
| + per-frame `@State` writes removed from ContentView | 58 | 16.7 ms | 0.01 s | 0.01 s | 1.3 s |

The first fix moved the cost: with the sidebar no longer rebuilt, more frames got through,
and each one paid the SwiftUI shell's re-evaluation. The second fix removed that.
