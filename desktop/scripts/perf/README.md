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

`BN_ACTION=click` posts 40 real clicks in the report area (what a click costs the main thread) and `BN_ACTION=lens` cycles the sidebar's lens rows; `BN_APP_ENV=NAME=value` gives the copy one more variable, for an experiment arm.

`serve-ready.sh <template.app> <label> [cold] [warm]` reads the `serve-ready` signpost for an A/B of the bundled sidecar (swap `Contents/Resources/bristlenose-sidecar` in a copy of the app). The signposts themselves (`PerfSignpost.swift`) are read with `log stream --signpost --predicate 'subsystem == "app.bristlenose" AND category == "perf"'`.

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


## The sidecar A/B for the lazy-MCP and Screens changes (4 Nov 2026, not yet run in the app)

Dev measurements say the lazy MCP mount and the Screens-check-off-the-loop change shorten the
sidecar's start; one noisy, non-interleaved batch in the app did not show it. To settle it, on an
otherwise idle Mac: build the Debug app once, copy it per run, swap only
`Contents/Resources/bristlenose-sidecar` between arms built from `58f0477e3` (before the lazy
mount), `34c1ce020` and HEAD, alternate the arms 8 times each with Screens on (the Mac default),
and read `serve-ready.sh <template.app> <label> 8 0`. Drop runs with a UI stall and count them.

"Idle" means measured, not assumed: `uptime` 1-minute load under ~2 **and** `sysctl vm.swapusage`
with swap mostly free. On 5 Nov 2026 the A/B was not started because load read 11 to 162 and swap
was 25.5 of 26.6 GB used (no single process to blame: a 13-day Virtualization.framework service,
Claude's renderer, a long-running `python3`, `fileproviderd`). Swap that full means any run can
page, so a quiet load average alone is not enough. Free the memory first (quit the VM or restart).


## The standby A/B (5 Nov 2026)

`standby-app-ab.sh` alternates standby off and on (`APP=… STUDY_DIR=… BN_STUDY=… REPS=6`). Result and method: `docs/design-standby-sidecar.md`. Three things it taught about running these in the app:

- **`BN_APP_ENV` does not reach the sidecar.** The app builds the sidecar's environment from the researcher's settings, so `BRISTLENOSE_LLM_PROVIDER=local` does nothing there. A study with no Signals snapshot builds one at every serve start with the real provider, and killing the app after the port answers means it never saves, so every launch spends. Check `llm-calls.jsonl` before and after the first launch, and let one run finish the build before measuring.
- **Idle is judged by CPU and memory pressure, not by two stale numbers.** `vm.swapusage` stays full long after the pressure has gone (74% memory free with swap 13 of 14 GB used); `memory_pressure` and a `top` sample say what is happening now. The load average lags by minutes after any build.
- **`serve-ready.sh <app> <label> <cold> <warm>` now honours a count of 0.** BSD `seq 1 0` counts down and printed `1 0`, so `8 0` ran two warm launches.
