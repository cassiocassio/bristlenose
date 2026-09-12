# Fix the menus — punch list

Running list of macOS menu-bar items that are mislocated, unwired, or stubbed.
Derived from the 27 Jul 2026 menu-wiring audit of `MenuCommands.swift` against
its three handler surfaces (native notifications → `ContentView`, native-direct,
and the `menuAction(...)` web bridge → `AppLayout.tsx` / `useKeyboardShortcuts.ts`).

**Scope:** cataloguing + placement only for now. Wiring and per-item design are
deferred — we'll pick these up item by item. See
`docs/design-desktop-menu-actions.md` for the full action catalogue and the
wiring cookbook.

---

## In progress

- [x] **Move Check Health → Diagnostics menu** (28 Jul 2026). "Check Health"
  reads as a doctor-style diagnostics action, not top-level app chrome. Moved
  from the Bristlenose app menu to the **top** of Diagnostics ▸ Section 1 (ships
  on every channel when the Diagnostics preference is on).
- [x] **Wire Check Health → native Health window** (28 Jul 2026). Replaced the
  dead `menuAction("checkSystemHealth")` bridge dispatch with
  `openWindow(id: "health")`. The `health` `Window` scene (`DoctorReportView`)
  fetches the new serve endpoint **`GET /api/doctor`** (bearer-authed, not
  auth-exempt) — which runs the local, non-network subset of `doctor.py`
  (`run_local_checks`) — and renders the checks as a native `Grid` list using
  the shared `MessageKind` glyph/tint vocabulary, plus a Copy-as-plaintext
  button. Network-bearing checks (API-key validation, reachability, Ollama
  probe) are deferred to a future async pass. Native-only checks (Keychain
  access, sandbox entitlements, bundle integrity) aren't in `doctor.py` yet —
  this window is the right future home for a desktop superset. Orphaned locale
  key `desktop.menu.app.checkHealth` removed from all 20 full locales.

## A. Dead — clickable, dispatches, nothing consumes (silent no-op)

Items that look fully active (no dimming) but do nothing when clicked.

- [x] **Diagnostics ▸ Check Health** (`checkSystemHealth`) — **wired** (28 Jul
  2026, see "In progress" above). Opens the native Health window; the dead
  bridge action is gone.
- [x] **File ▸ Open in New Window** (`openInNewWindow`, ⇧⌘O) — ~~no web handler.~~ **Closed by retirement, 20 Aug 2026**, not by wiring one: the command had no referent distinct from `File ▸ New Window`. The capability lives on in three sidebar context-menu items, which act on a *clicked* row rather than the front window.
## Closed 12 Sep 2026 (the Find sweep)

- [x] **Edit ▸ Find Next / Find Previous** (⌘G, ⇧⌘G) — **withdrawn** 12 Sep 2026
  (`find: withdraw Find Next and Find Previous — a filter has no next`), after QA
  reported ⌘G doing nothing. The plumbing was intact: ⌘E writes the find
  pasteboard, ⌘G reads it back and dispatches `findNext` with that text, and the
  web handler calls `setSearchQuery(text)` — with the text already in the box.
  Same query, same filter, identical result. **The reason is semantic, not
  mechanical:** search on this surface *filters* the quote grid, so every visible
  card is already a match and nothing renders a `<mark>`. "Find Next" presupposes
  a cursor stepping through occurrences in content that stays put; a filter has
  no cursor and nothing to step to. Moving through results is list navigation,
  which `j` and the arrows already do. Gating them (as the ⌘F change did) would
  have been the same lie ⌘J's note refuses. Restore **with transcript search**,
  where a document genuinely has matches to step between; the 21 locale keys and
  the orphaned `AppLayout.tsx` cases stay so it is a one-line re-enable.
  _An earlier draft of this entry blamed an empty find pasteboard. That case is
  real (nothing native writes it — the capsule dispatches `setSearchQuery`, not a
  pasteboard write) but it is not the defect: ⌘G was equally meaningless when the
  pasteboard was populated._

- [x] **Edit ▸ Find** (⌘F) — **wired**, after doing nothing since it shipped
  (see the correction at the foot of this doc for how the audit missed it).
  Now native on both ends and never crosses the bridge:
  `BridgeHandler.requestSearchFocus()` bumps the published counter
  `focusSearchRequests`, which `QuotesSearchToolbarControl` observes to expand
  and take focus. A counter, not a `Bool` — ⌘F must work twice in a row.
  The whole Find family is now lens-scoped:
  `canSearch = canDispatch && activeTab == .quotes`
  (`MenuCommands.swift:765`), because search exists only on Quotes and the
  other three lenses carry `SearchComingSoonButton`. `canDispatch` as well as
  the lens, because `currentPath` survives an in-place reload — `activeTab` can
  still say `.quotes` over a freshly-loaded status page.
- [x] **Edit ▸ Jump to Selection** (`jumpToSelection`, ⌘J) — **withdrawn**
  12 Sep 2026, not deleted and not dimmed. Same treatment as `mergeCode` below
  and for the same reason: it is unimplemented, not ungated. The web side is an
  explicit `break` behind a comment claiming the native layer handles it, and no
  native handler exists. It could never have reached WKWebView as
  `centerSelectionInVisibleRect:` either — a SwiftUI `.keyboardShortcut`
  installs an NSMenu key equivalent, matched *before* the responder chain. So ⌘J
  has done nothing since it shipped. Commented out at
  `MenuCommands.swift:740-761` with the blocking question (what does "jump to
  selection" mean in a quote grid?); the 21 locale keys are deliberately kept so
  restore stays one line.
- [x] **Menu gates moved off `isReady`** (`b06f923a`). `BridgeHandler` gained
  `hasChannel` — a published mirror driven by `webView`'s `didSet`, so a menu
  gate can never disagree with the `guard let webView` it stands in for — and
  `canDispatch` (`hasChannel && documentState == .spa`). `isReady` was never the
  right signal: it is force-set 2s after *any* load, status page included.
  `webView` is now cleared by `WebView.dismantleNSView` under an identity guard
  rather than by `reset()`, which had two owners with no defined order wiping a
  live registration. File ▸ Export Report gained `.disabled(!canDispatch)`,
  reaching parity with its toolbar twin.

## Closed 30 Jul 2026 (mechanical sweep)

- [x] **Popover↔menu glyph alignment** — Extract Clips `scissors`→`film`; Copy Quotes
  and Copy as CSV `doc.on.doc`→`doc.on.clipboard`. The shipped export popover is the
  vocabulary; the menu follows it.
- [x] **Project ▸ Show Transcripts in Finder** — the popover had a command the menu bar
  didn't. Wired via `.revealTranscripts`, sharing the fallback ladder through the new
  `TranscriptsRevealTarget` helper (+ tests). `doc.text`, not a second `folder`.
- [x] **Dead code removed** — `syncAppearance()`/`set-appearance` emitter (nothing ever
  consumed it; appearance works via `.preferredColorScheme` → WKWebView inheritance →
  `prefers-color-scheme`); `BridgeHandler.isDarkMode` (declared + reset, never read);
  `toggleDarkMode` fn+case and `exportAnonymised` case in `AppLayout.tsx`.
- [x] **Four orphaned locale key sets removed ×20 locales** — `moveFocusToProjects`,
  `switchToLightMode`, `switchToDarkMode`, `exportAnonymised`.
  **`dropOntoAnalysedProject` deliberately kept** — an audit called it orphaned; it is
  live at `ContentView.swift:1425` for file-subset projects.
- [x] **`importer.py:1409` pin-predicate docstring** — headline said three arms while its
  own body documented four (the placement arm). Now says four.
- [x] **`desktop/CLAUDE.md:448`** — "its sole command is `serve`" corrected; the sidecar
  passes through `doctor` and `run`.
- [x] **File ▸ Page Setup…** (`pageSetup`) — **wired** 28 Jul 2026. Now calls
  `NSApp.runPageLayout(nil)` (standard macOS panel, edits the shared `NSPrintInfo`).
- [x] **File ▸ Print…** (`print`, ⌘P) — **wired** 28 Jul 2026. Native
  `NSPrintOperation` via `PrintActions.print(webView:window:)`; prints whichever
  lens is on screen, since the operation renders the web view's current document.
  The bridge was never the right target — `window.print()` inside a WKWebView
  can't raise the macOS print panel. ~~Gated on `bridgeHandler.isReady`.~~
  **Gated on `bridgeHandler.hasChannel` since 12 Sep 2026** — `hasChannel`, not
  `canDispatch`, because printing hands the web view to AppKit and never
  dispatches JS, so the guard it stands in for is `PrintActions.print`'s own
  `guard let webView`, not the presence of `window.__bristlenose`. A status page
  is a real document and prints (`MenuCommands.swift:620-628`). Print
  *fidelity* is now a CSS concern (`@media print`), not a Swift one.
- [x] **Codes ▸ Merge Codes** (`mergeCode`) — **withdrawn** 28 Jul 2026, not
  deleted. Merging needs a *source* and a *target*, and the codebook lens has no
  multi-select — so drag-one-code-onto-another in `CodebookPanel` is the only way
  to express it, and a menu item can't say which two codes it means. Commented out
  in `MenuCommands.swift` with the restore note; the web half
  (`mergeCodebookTags`) already works. Returns when codebook selection lands
  (now on the planning board, QoL/Should).

## B. Warn-stub — `case` exists, logs "requires native focus context — not yet wired"

All in the **Codes** menu (`AppLayout.tsx`), gated on `isCodeTab`. Each needs a
focused group/code context from the native sidebar that isn't built yet.

- [ ] **Codes ▸ Rename Code Group** (`renameCodeGroup`)
- [ ] **Codes ▸ Delete Code Group** (`deleteCodeGroup`)
- [ ] **Codes ▸ Show/Hide Code Group** (`toggleCodeGroup`)
- [ ] **Codes ▸ Rename Code** (`renameCode`)
- [ ] **Codes ▸ Delete Code** (`deleteCode`)

(For contrast, `createCodeGroup`, `createCode`, `browseCodebooks`,
`importFramework`, `removeFramework` in the same menu **are** wired.)

All five need a **selection model in the codebook lens** — there is no way to
name the target group/code today. Tracked on the planning board as
"Codebook lens — multi-select of codes and code groups" (QoL / Should,
28 Jul 2026), which also gates restoring Merge Codes.

## C. Disabled by design — `.disabled(true)`, future phases (not bugs)

Tracked so they're not mistaken for regressions. Leave disabled until the phase
lands.

- [ ] **Project ▸ (folder) Archive** — empty body, `// Phase 5`.
- [ ] **Project ▸ Re-analyse** (`reAnalyse`) — `// Future — Phase 2+`.
- [ ] **Project ▸ Archive** (`archive`) — `// Future — Phase 5`.

## D. Unreachable — no web handler, permanently disabled by an always-false flag

- [ ] **Edit ▸ Undo** (⌘Z) — the *web* `undo` action has no handler, but the
  web branch only fires when `bridgeHandler.canUndo`, derived from
  `BridgeState.canUndo` = hard-coded `false` (`bridge.ts`, "wired when undo
  store ships"). The **removal-undo** branch (`removalStore.undoLastRemoval()`)
  *is* wired, so ⌘Z works for project removals today.
- [ ] **Edit ▸ Redo** (⇧⌘Z) — `redo` has no web handler; always disabled
  (`BridgeState.canRedo` = hard-coded `false`). Fully inert.

---

**Everything else resolves to a handler:** all ~50 other web `menuAction` cases
and all 15 native notification actions (New Project/Folder, Rename, Move To,
Locate, Stop, Miro, Welcome, AI & Privacy, etc.) reach one.

> **"Resolves to a handler" is not "works" — corrected 12 Sep 2026.** This line
> read *everything else is wired* until ⌘F was found dead in every project, on
> every lens, since it shipped. It dispatched `menuAction("find")`, the case
> existed in `AppLayout.tsx`, the handler ran — and queried `.search-input`, an
> element `Toolbar` never renders in embedded mode (`if (isEmbedded()) return
> null`). It resolved cleanly and did nothing. There was no log line, because
> the bridge was working perfectly; the failure was one layer below it.
>
> This audit's method — *does a `case` exist for the action?* — cannot see that
> class. Every group-A entry above was found by asking whether a handler
> exists; none of them would have caught ⌘F. Treat the counts here as a
> statement about wiring, not about behaviour — and see the open Find Next /
> Find Previous / Use Selection for Find entry in group A for three actions the
> method still passes today.
