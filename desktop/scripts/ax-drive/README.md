# ax-drive — drive the shipped Bristlenose.app over the Accessibility API

A driver for the **real** app, not a harness: it reads AppKit's geometry and
the SPA's DOM rects out of the live `WKWebView` (WebKit exposes
`AXDOMClassList`, so `.center`, the nav and the TOC entries come back with
frames), and sends the inputs a researcher's hands send — toolbar and menu
presses, ⌥⌘S / ⌥⌘L, window resizes, and CGEvent mouse drags on the projects
seam and on the window edge (a *live* resize, dozens of frames). Written
25 Sep 2026 for `docs/sidebar-column-diagnosis.md`; it turned S4–S7 from
reports into measurements in an afternoon, and reruns any cell in seconds.

## Build and run

```bash
cd desktop/scripts/ax-drive
swiftc -O -framework AppKit -o bndrive bndrive.swift
BNDRIVE_PID=$(pgrep -x Bristlenose) ./bndrive window
./bndrive            # lists every command
```

`bndrive` (no arguments) prints the command list: `window`, `tree`, `find`,
`summary`, `resize`, `move`, `frame`, `press`, `key`, `menu`, `drag`, `click`,
`splitters`, `splitter`, `activate`, `trusted`. `snap.sh "<label>"` prints one
combined snapshot. Coordinates are screen points, top-left origin, as AX and
CGEvent both use them; every frame is also printed as `winX=` relative to the
window.

## Three things that cost time

**The caller must be AX-trusted, and the grant is per app, not per session.**
Nothing spawned from a Claude session is trusted until *Claude* is added under
System Settings ▸ Privacy & Security ▸ Accessibility — and once it is, **every**
Claude session on the Mac can drive every window. Two sessions drove the same
window for five minutes on 25 Sep before either noticed. One driver per
instance; `BNDRIVE_PID` is mandatory when more than one instance is running.
Don't fire the trust prompt from a script (`AXIsProcessTrustedWithOptions`) —
`./bndrive trusted` reads the state without prompting.

**The sidebar-fit trace lights without a relaunch.** `defaults write
app.bristlenose …` fails from a shell — the container is TCC-protected — but
`SidebarFitTrace.isEnabled` reads `UserDefaults.standard` live, and a sandboxed
app reads the global domain from the real `~/Library/Preferences`:

```bash
defaults write NSGlobalDomain BristlenoseDebugSidebarFit -bool YES
/usr/bin/log stream --predicate 'subsystem == "app.bristlenose" AND category == "sidebar-fit"' --style compact > trace.log &
# … drive …
defaults delete NSGlobalDomain BristlenoseDebugSidebarFit
```

The launch argument in `SidebarFitTrace.swift`'s header still works; this is
for an instance that is already running (Xcode's, with the debugger attached).
Delete the key afterwards — the geometry readers log every frame of a live
resize.

**Every app-hosted test host is the same bundle id.** `xcodebuild test` hosts
share the container, read the same flag, log into the same category, and open
the app's own `ContentView` window under the same autosave name. Filter trace
reads on `processID`, and expect the projects column's width to be whatever
the last process saved (`NSSplitView Subview Frames main-AppWindow-1, …`).

## Two answers the real app gave that a harness could not

- The projects column comes back at its **autosaved** width, not the 220
  ideal; 180 pt of column is 160 pt of cells (`AXRow` 180, `AXCell` 160, no
  card element in AX). Session 2's host read the key from inside the
  container; this driver measured the same 209 from outside.
- On the launch pass, every line read `floor=nil`: the first split-geometry
  reading is the WindowGroup's 1000-pt `defaultSize` before the frame restore,
  but the SPA has not posted a floor yet, so `decide` returns `.none`. A guard
  on that pass would protect only a `ContentView` that mounts with a floor
  already set — a second window carrying a report seed, perhaps — which was
  **not observed**. Recorded so the disagreement in the brief has its evidence.
