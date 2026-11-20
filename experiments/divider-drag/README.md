# Divider-drag harness

Throwaway tools from the 20 Nov 2026 session that took the sidebar divider drag from about
11 to about 45 fps. Method, results and pitfalls: `docs/design-perf-divider-drag.md`.
Copied from a scratch directory, so paths are not wired up: compile the Swift files with
`swiftc -O <file>.swift -o <file>` next to each other, and edit `appmeasure.sh` for the app
copy you are measuring.

| File | What it does |
|---|---|
| `lab.swift` | Control: a bare `WKWebView` in an AppKit or SwiftUI split, trivial or real page. Writes page and host frame stats. |
| `drag.swift` | Real-mouse divider drag for the control (CGEvent, 120 Hz sine). |
| `drag2.swift` | Same drag against the real app: `drag2 <x> <y> <centre-offset> <amp> <secs> <hz>`. |
| `findsplit.swift` | Prints the app's AX splitters and window frame; the drag's x and y come from here. |
| `setsize.swift`, `axclosewelcome.swift`, `axrows.swift` | Size the window, close Welcome, list sidebar rows (Accessibility). |
| `wrap.py` | Dev-sidecar stand-in: runs the real `bristlenose serve`, injects the rAF probe, keeps beacons in memory (`/__lab/dump`, `/__lab/dumpw`). Set `BN_BIN` to override the binary. |
| `appmeasure.sh` | One 10 s measurement: fps, gap percentiles, stalls over 33 and 50 ms, width changes. |
| `top3.py` | Aggregates an xctrace Time Profiler trace by main-thread inclusive time. |

Rules learned the hard way: leave full screen before resizing; a run with zero width
changes did not drag; re-sign a copied build with the Apple Development identity and its
original entitlements; compare runs at the same window size only.
