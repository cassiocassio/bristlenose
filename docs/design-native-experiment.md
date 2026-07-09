# Native experiment — how far can the Mac app go fully native?

_Status: completed spike, branch `native-experiment` (6–7 Jul 2026). Conclusion up front: **going fully Mac-native is possible but expensive.** The hybrid app (native shell + WKWebView-hosted React SPA) stays the primary product; full-native is a durable-but-contingent bet, not a commitment. This doc is the postmortem + the reusable findings._

## The question

Bristlenose's macOS app is a native SwiftUI/AppKit **shell** hosting the React SPA in a **WKWebView** — the shell (sidebar, toolbar, menus, settings) is native, the five report lenses (Project/Dashboard, Sessions, Quotes, Codebook, Analysis) are web. That's structurally the "web-in-a-native-shell" pattern Gruber's *Electron and the Decline of Native Apps* is suspicious of, and the seams (scroll inertia, focus, right-click menus, text selection) are the tells a Mac-literate user eventually smells.

The experiment: **how much of the report can stop being WKWebView-hosted React and become genuine native SwiftUI/AppKit, lens by lens** — and what does it cost?

## The architecture that makes it tractable

Three layers, two front-ends over one engine — established during the spike and unchanged by it:

- **Python stays the engine.** The 12-stage pipeline is untouched. Still the sidecar. Nothing native forks pipeline behaviour.
- **The React SPA stays** for Linux/Windows/web — free and OSS. It keeps consuming the local server's JSON exactly as now.
- **Mac gains a native client** of the *same* local HTTP/JSON the SPA already uses. The native app is a peer client alongside the SPA, not a fork of the logic. Additive and flag-gated (`#if DEBUG` here) — the shipping hybrid path is untouched.

Presentation only. On-device intelligence (Foundation Models, Speech, NaturalLanguage) was explicitly **out of scope** — that would fork Mac analysis from the cross-platform engine and is a separate conversation.

## What was built

A `#if DEBUG` **Component Catalogue** (Debug ▸ Component Catalogue) — a "design lens" that renders each design-system element natively **beside** the web version in a WKWebView, both on the same display. Built in phases:

- **Phase 0 — theming:** adaptive light/dark colour tokens (code-only dynamic `NSColor`, no asset catalog) + a Light/Dark/Auto toggle driving both columns (`.preferredColorScheme` + `color-scheme: light dark`).
- **Phase 1 — atoms:** `Button`, `Picker(.segmented)`, `Toggle`, native checkbox, search field, `Gauge` progress ring.
- **Phase 2 — molecules:** dense tag-filter checkbox field (`Toggle{Label}` `.controlSize(.small)`, row-as-target), read-only editable text, SF-Symbol star.
- **Phase 3 — organisms:** stat-card `LazyVGrid(.adaptive)`, sortable `Table`.
- **Phase 4 — charts:** Swift Charts — `BarMark` sentiment bars, axis-hidden `LineMark` sparkline, `RectangleMark` signal heatmap.
- **Phase 5 — lenses:** a composed Dashboard (stat grid + featured-quotes masonry).
- **Phase 6 — AppKit engines:** a working `NSTokenField` `NSViewRepresentable` bridge; `NSOutlineView` and `NSCollectionView` masonry flagged as tracked slices.

Follows the existing `TypeParityView` harness pattern (native-vs-web side-by-side, ephemeral WKWebView, `#if DEBUG` scene + Debug-menu item). Commits `c7a10bfd` → `bf171638`.

## Findings (the reusable part)

**Most of the app is already native.** Only the five report lenses live in the WKWebView; the shell, sidebar, toolbar, 89-item menu bar, and settings are native today. "Complete native conversion" is really "convert five web-rendered lenses."

**Element-level: mostly cheap.** Of ~13 element categories, ~8 are near-free native controls, 3 are trivial compositions, and only **3 need real AppKit/custom work**: token input (`NSTokenField` + custom colour cell), the editable codebook tree (`NSOutlineView`, because SwiftUI `OutlineGroup` has a documented dynamic-mutation bug on macOS), and the minimap (`Canvas`, no native primitive). Independently confirms the already-committed sidebar→`NSOutlineView` decision (`design-desktop-sidebar-appkit.md`).

**Typography:** SF Pro renders softer/more elegant than WebKit's Inter (optical sizing, metrics-driven tracking, platform antialiasing). Lean into it; don't fight to match Inter. See `design-native-typography-grid.md`.

**Grid/spacing:** macOS has no numeric token grid — it's a semantic ~8pt rhythm expressed through default stack spacing and bare `.padding()`, with explicit values snapping to 4/8. Bristlenose's own rem-derived tokens land off-grid (2.4, 5.6px); snapping to 4/8 is the native translation. `.controlSize` is the coherent density knob (`.small` for dense fields; `.mini` = the Panther-2003 addition, System-Settings-tight).

**The quotes lens → masonry.** Apple ships true masonry in *none* of its own macOS apps (uniform grids or justified rows only), so it's a web idiom — but it's the **honest fit** for the quotes lens, and here's why the usual objections fall away for *this* surface:
- Digital quotes have a much wider length spread than physical stickies (which capped length), so a uniform grid clamps/wastes and `LazyVGrid` goes ragged.
- The quotes lens is the **main content pane** — always multi-column even on a 14″ laptop with both sidebars — so the single-column list wastes space that's always there.
- Reading order is **not** scrambled: masonry places items in *source order* into the shortest column, and Safari 26.4 ships native CSS masonry ("Grid Lanes") with a `flow-tolerance` knob for exactly this. A SwiftUI `Layout` or `NSCollectionView` waterfall preserves focus order the same way.

Remaining costs for masonry: no Apple-app precedent (a taste/brand call), and virtualising to hundreds of quotes needs a custom `NSCollectionView` waterfall (the SwiftUI `Layout` is eager — fine for a demo, not for scale). The catalogue proves the look/order in SwiftUI; production scale is the AppKit slice.

**Interaction discipline** (behaviour, not appearance): the loudest web tells are absent context menus and hover-reveal affordances. Drop web idioms (hover-reveal, blue underline nav, pointing-hand cursor, animated tooltips); restore Mac idioms (single-click-select / double-click-open, rich right-click menus, drag-from-inactive-window, proxy icon, `@SceneStorage` restoration). Full audit in `design-native-interaction-audit.md`. Note: macOS `WKWebView` has no public delegate to render a *native* right-click menu — a custom right-click menu is easy web-side (Miro/Figma do it), a *native* `NSMenu` needs a `WKWebView` subclass overriding `willOpenMenu` + a web→native hit-test.

## Cost/benefit verdict

**Possible but expensive.** The element work is mostly cheap; the expense concentrates in (a) three AppKit engines, (b) integrating native components into the *real* report lenses in place of the WKWebView (not just a catalogue), and (c) ongoing dual maintenance of native-Mac + web-SPA surfaces. The payoff — shedding the web-in-a-shell seams — is real but only matters to the extent Mac becomes the dominant *paid* channel.

**Decision:** the hybrid app stays primary; the React SPA stays for non-Mac and OSS; full-native is filed as a "could" — a contingent bet gated on paying Mac customers, revisited if the web seams start costing conversions. The catalogue lives on as the native design-system reference (the native cousin of the "component storybook" idea) and de-risks any future per-lens conversion.

## Where things live

- **The catalogue:** `desktop/Bristlenose/Bristlenose/ComponentCatalog*.swift` + `CatalogTokens.swift`, Debug ▸ Component Catalogue (`#if DEBUG`).
- **Interaction audit:** `design-native-interaction-audit.md`.
- **Related:** `design-native-colour-alignment.md` (seam alignment), `design-native-typography-grid.md` (type), `design-native-vs-web-surfaces.md` (which surfaces go native), `design-desktop-sidebar-appkit.md` (the `NSOutlineView` decision).
