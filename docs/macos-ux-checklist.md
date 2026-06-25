# macOS UX checklist & references

A standing reference for Bristlenose's native Mac shell — a **remember-and-consider** tool and a reading list, *not* a must-do list. It deliberately does **not** re-derive the HIG (read the live pages, or the local corpus at `~/.local/share/hig-corpus/`) and does **not** duplicate the review rule-set baked into the `what-would-gruber-say` agent. It holds the three things those don't: the meta-rules, a cross-doc map of which experience surfaces are already designed, and the curated reading list from the Jun-2026 prior-art sweep.

> **Respect existing work.** Keyboard shortcuts, keyboard navigation, i18n, menus, settings, diagnostics, and drag-import are **already designed** (each has its own doc). Don't re-litigate them. This file exists to catch genuine gaps + horizon ideas, and to build platform knowledge — not to reopen settled work.

## Two meta-rules (these change the most)

1. **Build the behaviour at the floor; `#available`-gate only the chrome.** Almost every macOS *mechanism* — state restoration, undo, multi-window, focus, drag, `.searchable`, commands — exists at the macOS 15 floor. Only the Liquid-Glass *presentation* (`ToolbarSpacer`, minimized search, SwiftUI `WebView`, `glassEffect`, `backgroundExtensionEffect`) is 26-only. So you build once and gate the glass — the floor costs you presentation, not behaviour.
2. **Route commands through the responder chain** (`sendAction(_:to:nil:from:)` with a nil target / `tryToPerform`) so one verb fires on whichever surface has focus. The NetNewsWire pattern; it underpins keyboard nav, context menus, and Quick Look in one stroke. Already used here for `toggleSidebar`.

## Experience-surface map (where each already lives)

`✓` designed · `◐` partial / parked-but-known · `○` gap. Home doc in brackets.

- Keyboard shortcuts `✓` [`design-keyboard-shortcuts.md`]
- Keyboard navigation & cross-pane focus `✓` [`design-keyboard-navigation.md`]
- Single-key review shortcuts (j/k/s/h/x/t, web) `✓` shipped — desktop `space`=advance variant is a small open call
- Responder-chain command dispatch `✓` [`design-desktop-menu-actions.md`]
- Menu-bar command completeness `✓` [`design-desktop-menu-actions.md`]
- i18n (8 namespaces × 7 locales) `✓` [`design-i18n.md`, `-wiring`, `-locale-negotiation`]
- Settings scene `✓` [`design-desktop-settings.md`]
- Window state restoration (`@SceneStorage`) `✓` scoped — define the exact restored set at build time
- Multi-window (open project in new window) `✓` designed-for-future [`design-desktop-app.md` §Multi-window]
- Undo scope (rename / reorder / delete / icon) `◐` removal-undo shipped; broader scope is backlog [`design-project-sidebar.md` §Future]
- Context menus `✓` shipped; slow-double-click rename `◐` parked (macOS-26 tap-gesture bug; route out: `.contextMenu(forSelectionType:primaryAction:)`)
- Drag-to-reorder projects/folders `◐` parked (multi-select prerequisite now met; folder-drag = likely AppKit surgery)
- Quick Look (spacebar) of session/clip files `◐` nice-to-have (trap: `NSTextView` hijacks the panel — resign first responder first)
- VoiceOver row recipe + automated a11y-audit CI gate `◐` recipe written, deferred to beta
- Reduce Motion / Reduce Transparency / Increase Contrast `✓`; Dynamic-Type native→web scaling curve `○` open (TBD at implementation)
- Sidebar row-height follows the user's icon-size setting `✓`
- **Background run-complete notification** `◐` direction recorded, **post-TF** — banner + single *informational* Dock bounce; no badge; Dock progress = future. TF ships on in-app surfaces. [`design-desktop-nav-toolbar-rearrangement.md` §10.4]
- Web pane API (WKWebView at floor / SwiftUI `WebView` on 26) `✓` [`design-desktop-nav-toolbar-rearrangement.md` §10.8]

## Reading list (to build platform knowledge)

**Native-feel philosophy**
- *Mac-Assed Mac Apps* — Daring Fireball, 20 Mar 2020 — the umbrella definition of "feels native" (menu bar, shortcuts, multiple windows, state restoration; not about implementation language). https://daringfireball.net/linked/2020/03/20/mac-assed-mac-apps
- Becky Hansmeyer, *Apple, Marzipan, Delight* — 14 Jun 2018 — the crowdsourced (Troughton-Smith) "what makes a Mac app feel native" checklist, usable as a rubric. https://beckyhansmeyer.com/2018/06/14/apple-marzipan-delight/
- Tapbots (Mark Jardine) & Cultured Code interviews — *feel over looks; personality belongs in art and sound, not typography* — the canonical articulation of "stay on the system grid."

**Mechanism deep-dives**
- Brent Simmons, *Implementing Single-Key Shortcuts in NetNewsWire* — inessential.com, 5 Mar 2019 — the responder-chain dispatch pattern, with rationale. The keystone read. https://inessential.com/2019/03/05/implementing_single_key_shortcuts_in_net.html
- Daniel Jalkut, *Windows of Perception* — redsweater.com, 2006 — a window taxonomy for reasoning about every panel/popover/inspector you add. https://redsweater.com/blog/97/windows-of-perception
- Majid Jabrayilov (swiftwithmajid.com) — the deepest single well for *macOS-specific* SwiftUI: window management, Commands, NavigationSplitView, state restoration, `FocusedValue`/`FocusedBinding`.
- Nil Coalescing (Matthaus Woolard) — focused how-tos: undo/redo, menu commands from the focused document, reorder-rows-with-text-fields-on-macOS, `SceneStorage`.
- SerialCoder, *Enabling Selection, Double-Click and Context Menus in SwiftUI List on macOS* — 24 Nov 2025 — `.contextMenu(forSelectionType:primaryAction:)` (the double-click escape hatch).

**Apple samples & sessions**
- *Landmarks: Building an app with Liquid Glass* — the architectural match (NavigationSplitView + sidebar/inspector + toolbar glass). https://developer.apple.com/documentation/SwiftUI/Landmarks-Building-an-app-with-Liquid-Glass
- *Building a cross-platform web browser* — the embedded-web-pane behaviours (find-on-page, back/forward, context menu, custom schemes). https://developer.apple.com/documentation/webkit/building-a-cross-platform-web-browser
- *Restoring Your App's State with SwiftUI* · *Bringing Multiple Windows to Your SwiftUI App* · *Adopting drag and drop using SwiftUI* — the floor-level behaviour samples.
- WWDC25 **s229** *Make your Mac app more accessible to everyone* (the on-target a11y reference) · **s323** *Build a SwiftUI app with the new design* · **s231** *Meet WebKit for SwiftUI*.

## See also
- The `what-would-gruber-say` agent — the review-time rule set + live HIG-corpus citation discipline. This file's reading list feeds its "Where to read more" section.
- `docs/design-desktop-nav-toolbar-rearrangement.md` §10 — the per-feature pre-build surface list this generalizes from.
