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
- [ ] **File ▸ Open in New Window** (`openInNewWindow`, ⇧⌘O) — no web handler.
  _Only remaining group-A item._

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
  can't raise the macOS print panel. Gated on `bridgeHandler.isReady`. Print
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

**Everything else is wired:** all ~50 other web `menuAction` cases and all 15
native notification actions (New Project/Folder, Rename, Move To, Locate, Stop,
Miro, Welcome, AI & Privacy, etc.) resolve to a handler.
