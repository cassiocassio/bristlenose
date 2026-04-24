---
status: trued
last-trued: 2026-04-24
trued-against: HEAD@port-v01-ingestion on 2026-04-24
---

> **Truing status:** Trued. Project-ops table rewritten with NotificationCenter / bridge split; old contradicting Future-only table removed. Keyboard shortcuts added throughout. `openInNewWindow` corrected (Shipped, not Future). Help, View, and Codes menus given dedicated sub-sections. Alpha gap (no Analyse/Resume/Retry in context menu) called out inline. See changelog.

## Changelog

- _2026-04-24_ — Tier 1 truing follow-up (post `design-doc-review` audit): deleted the stale Future-only project-ops table that contradicted the rewritten one above it; added Shortcut column to the rewritten project-ops table (⇧⌘R, ⌘N, ⇧⌘N, ⌘⌫, ⇧⌘O); corrected `openInNewWindow` from Future to Shipped (bridge); added `chooseIcon` and `aiPrivacy` rows; added new sub-sections for View menu (Cmd+1–5, toggleSidebar, heatmap toggle), Help menu (6 actions), and Codes menu (6 wired actions, `mergeCode` moved out of project-ops); added inline alpha-gap callout for missing Analyse/Resume/Retry in the project context menu; noted `playPause` triple-dispatch (Video / Quotes / kbd). Section heading count corrected from "(8)" to "(17)".
- _2026-04-23_ — trued up during port-v01-ingestion QA: rewrote §"Project operations — native-only or future" to reflect shipped NotificationCenter-based project ops (newProject, renameProject, deleteProject, locateProject, createNewFolder, renameFolder, deleteFolder, moveSelectedProject); kept `reAnalyse` (`.disabled(true)` per `MenuCommands.swift:397-400`) and `archive` (Phase 5) as Future; added missing entries (`openBlog`, `showAcknowledgements`, `mergeCode`); flagged `revealInFinder` label drift vs shipped `showInFinder`. Anchors: `MenuCommands.swift:355-360, 397-405, 433-466, 692-698`, `ContentView.swift:279-292, 1118-1176`. Commit: 3d9f43c.

# Desktop Menu Actions — Bridge Handler Cookbook

Reference for all menu actions wired through `BridgeHandler.menuAction()`. Working context (the 3-file chain, how to add a new handler) lives in `desktop/CLAUDE.md`.

> **Note (2026-04-23):** Project operations use **two wiring patterns** — actions affecting the native sidebar (project/folder CRUD, rename, move) post `Notification.Name` events that ContentView receives via `.onReceive`, while actions targeting the web layer (re-analyse, archive, codebook ops) dispatch through `bridgeHandler.menuAction()`. The catalogue below should be read with this distinction in mind. Detail in `desktop/CLAUDE.md` "Project menu actions use Notification.Name not bridge."

## Action catalogue

### Already handled — AppLayout (27 actions)

| Action | Handler |
|--------|---------|
| `toggleLeftPanel` | `sidebarAnimations.toggleToc()` |
| `toggleRightPanel` | `sidebarAnimations.toggleTags()` |
| `toggleInspectorPanel` | `toggleInspector()` |
| `find` | Focus search input (expand + focus + select) |
| `useSelectionForFind` | Selection → search query + find pasteboard write |
| `findNext` | Find pasteboard text (from payload) → search query |
| `findPrevious` | Find pasteboard text (from payload) → search query |
| `jumpToSelection` | No-op (WKWebView native) |
| `exportReport` | `setExportOpen(true)` |
| `exportAnonymised` | Open ExportDialog with `initialAnonymise={true}` |
| `exportQuotesCSV` | Build CSV from all quotes → blob download |
| `copyAsCSV` | Copy focused/selected quotes as CSV to clipboard |
| `allQuotes` | Reset search + tag filter + view mode to defaults |
| `starredQuotesOnly` | `setViewMode("starred")` |
| `filterByTag` | Click tag filter dropdown trigger button |
| `showHelp` | Open help modal to "help" section |
| `showKeyboardShortcuts` | Open help modal to "shortcuts" section |
| `showReleaseNotes` | Open help modal to "about" section |
| `sendFeedback` | `setFeedbackOpen(true)` |
| `zoomIn` / `zoomOut` / `actualSize` | CSS `font-size` scaling (±10%, persisted to localStorage) |
| `toggleDarkMode` | Toggle `data-theme` attribute between light/dark |
| `browseCodebooks` | Dispatch `bn:codebook-browse` → CodebookPanel opens picker |
| `importFramework` | Dispatch `bn:codebook-browse` with `{ templateId }` payload → CodebookPanel opens preview |
| `removeFramework` | Dispatch `bn:codebook-remove` with `{ frameworkId }` → CodebookPanel shows confirm dialog |
| `createCodeGroup` | Dispatch `bn:codebook-create-group` → CodebookPanel creates group |
| `createCode` | Dispatch `bn:codebook-create-code` → CodebookPanel creates tag in first researcher group |

### Already handled — useKeyboardShortcuts (24 actions)

These are in the `handleMenuAction` switch inside `useKeyboardShortcuts.ts`, sharing closures with the keyboard handlers.

| Action | Handler |
|--------|---------|
| `star` | `handleStar()` — bulk-aware (uses focused/selected) |
| `hide` | `handleHide()` — bulk-aware, moves focus after |
| `addTag` | `handleTagOpen()` — opens TagInput on focused quote |
| `applyLastTag` | `handleQuickApply()` — quick-apply last-used tag |
| `playPause` | `sendCommand("playPause")` — toggle play/pause on open player |
| `skipForward5` / `skipBack5` | `sendCommand("skipRelative", { seconds: ±5 })` |
| `skipForward30` / `skipBack30` | `sendCommand("skipRelative", { seconds: ±30 })` |
| `speedUp` / `slowDown` | `sendCommand("speedStep", { delta: ±0.25 })` |
| `normalSpeed` | `sendCommand("setSpeed", { rate: 1 })` |
| `volumeUp` / `volumeDown` | `sendCommand("volumeStep", { delta: ±0.1 })` |
| `mute` | `sendCommand("toggleMute")` |
| `pictureInPicture` | `sendCommand("togglePip")` |
| `fullscreen` | `sendCommand("toggleFullscreen")` |
| `nextQuote` | `moveFocus(1)` |
| `previousQuote` | `moveFocus(-1)` |
| `extendSelectionDown` | `handleShiftMove(1)` |
| `extendSelectionUp` | `handleShiftMove(-1)` |
| `toggleSelection` | `toggleSelection(focusedId)` + anchor |
| `clearSelection` | `clearSelection()` |
| `revealInTranscript` | `navigate(/report/sessions/:pid#anchor)` |

Video player commands use `sendCommand()` from `PlayerContext` which posts `bristlenose-command` messages to the popout player window. The popout `player.html` handles all commands (skip, speed, volume, PiP, fullscreen). Bridge `getState()` reports live `hasPlayer` / `playerPlaying` from module-level getters in `PlayerContext.tsx` — Swift uses these to dim/enable the Video menu.

### Need new frontend implementation (0)

All Tier 2 actions are wired — moved to "Already handled — AppLayout" above.

### Project operations — native-side or future (17)

These are either native-only (Finder, print) or depend on features not yet built (re-analysis, archive).

> **Trued 2026-04-24.** Most "Future: project management" entries shipped during sidebar Phases 1–3 via the NotificationCenter pattern. Remaining true-Future items are `reAnalyse`, `archive`, `archiveFolder` (all `.disabled(true)` or unwired in `MenuCommands.swift`). Catalogue:
>
> | Action | Shortcut | Status | Notes |
> |---|---|---|---|
> | `showInFinder` | ⇧⌘R | **Shipped** (native) | `NSWorkspace.shared.selectFile` in `MenuCommands.swift:355-361`; also wired to ProjectRow context menu (`ContentView.swift:954-961`). _Doc previously named this `revealInFinder`._ |
> | `newProject` | ⌘N | **Shipped** (NotificationCenter) | `createNewProject` notification → ContentView handler (`MenuCommands.swift:113-116`) |
> | `createNewFolder` | ⇧⌘N | **Shipped** (NotificationCenter) | `createNewFolder` notification (`MenuCommands.swift:118-121`) |
> | `renameProject` | — | **Shipped** (NotificationCenter) | `renameSelectedProject` notification |
> | `renameFolder` | — | **Shipped** (NotificationCenter) | `renameSelectedFolder` notification |
> | `deleteProject` | ⌘⌫ | **Shipped** (NotificationCenter) | `deleteSelectedProject` notification — multi-select bug noted (only deletes focused row, alpha fix); `MenuCommands.swift:412` |
> | `deleteFolder` | ⌘⌫ | **Shipped** (NotificationCenter) | `deleteSelectedFolder` notification (`MenuCommands.swift:352`) |
> | `moveSelectedProject` | — | **Shipped** (NotificationCenter) | "Move to" submenu populated from folders + "No Folder" |
> | `locateProject` | — | **Shipped** (NotificationCenter) | NSOpenPanel for moved/deleted projects |
> | `openInNewWindow` | ⇧⌘O | **Shipped** (bridge) | `bridgeHandler.menuAction("openInNewWindow")` (`MenuCommands.swift:123-126`). Active, not `.disabled` |
> | `chooseIcon` | — | **Shipped** (project-row context menu) | SF Symbol picker via `IconPickerPopover` (`ContentView.swift:967-969`) |
> | `aiPrivacy` | — | **Shipped** (NotificationCenter) | Posts `.showAIConsentSheet` (`MenuCommands.swift:93-96`); opens AIConsentView |
> | `reAnalyse` | — | **Future (shipped as `.disabled(true)`)** | `MenuCommands.swift:397-400` with "Future — Phase 2+" comment. Will dispatch via bridge once incremental re-analyse pipeline lands |
> | `archive` (project) | — | Future | `MenuCommands.swift:402-405`, `.disabled(true)`, Phase 5 |
> | `archiveFolder` | — | Future | Phase 5 |
> | `checkSystemHealth` | — | Bridge dispatch | `bridgeHandler.menuAction("checkSystemHealth")` — handler in frontend |
> | `pageSetup` / `print` | ⌘P (print) | Bridge / future | NSPrintOperation on WKWebView snapshot |
>
> **Alpha gap (24 Apr 2026):** the project-row context menu (`ContentView.swift:944-995`) and the Project menu do **not** include `Analyse`, `Resume`, or `Retry` actions. Today the only Retry lives on the toolbar pill (`ContentView.swift:572`) and the detail-pane error state (`ContentView.swift:1061`). Tracked in the alpha-blocker shortlist (`docs/private/truing-ingestion-lifecycle-2026-04-23.md`).

### View menu (3)

| Action | Shortcut | Status | Notes |
|---|---|---|---|
| `toggleSidebar` | ⌥⌘S | **Shipped** (responder chain) | `NSSplitViewController.toggleSidebar` via `tryToPerform` (`MenuCommands.swift:247-253`) — distinct from `toggleLeftPanel` (web sidebar) |
| Tab switch (Cmd+1…Cmd+5) | ⌘1–⌘5 | **Shipped** (bridge) | `bridgeHandler.switchToTab(tab)` — separate code path from `menuAction` (`MenuCommands.swift:235-243`) |
| `toggleInspectorPanel` (heatmap) | — | **Shipped** (bridge, tab-gated) | Disabled outside Analysis tab (`MenuCommands.swift:267-270`) |

### Help menu (6)

All wired in `MenuCommands.swift:670-699`.

| Action | Status | Notes |
|---|---|---|
| `bristlenoseHelp` / `showHelp` | **Shipped** | Opens help modal to "help" section |
| `showKeyboardShortcuts` | **Shipped** | Opens help modal to "shortcuts" section |
| `releaseNotes` / `showReleaseNotes` | **Shipped** | Opens help modal to "about" section |
| `sendFeedback` | **Shipped** | `setFeedbackOpen(true)` |
| `openBlog` | **Shipped** (native) | NSWorkspace opens Substack URL (`MenuCommands.swift:692`) |
| `showAcknowledgements` | **Shipped** (native) | Opens credits modal (`MenuCommands.swift:698`) |

### Codes menu (9)

5 stubs that need native focus context are catalogued separately under "Codebook operations" below. Wired actions:

| Action | Status | Notes |
|---|---|---|
| `browseCodebooks` | **Shipped** (bridge → CodebookPanel) | Dispatches `bn:codebook-browse` |
| `importFramework` | **Shipped** (bridge) | Dispatches `bn:codebook-browse` with `{ templateId }` |
| `removeFramework` | **Shipped** (bridge) | Dispatches `bn:codebook-remove` |
| `createCodeGroup` | **Shipped** (bridge) | Dispatches `bn:codebook-create-group` |
| `createCode` | **Shipped** (bridge) | Dispatches `bn:codebook-create-code` |
| `mergeCode` | **Shipped** (bridge) | Dispatched from Codes menu (`MenuCommands.swift:464-466`) |

### Quotes menu — `playPause` triple-dispatch note

`playPause` appears in three menu-source paths: the Video menu, the **Quotes menu** (`MenuCommands.swift:530-533`), and `useKeyboardShortcuts.ts`. All three resolve to `sendCommand("playPause")` via `PlayerContext`.

### Codebook operations — need native focus context (5 stubs)

These actions need to know WHICH group/code is targeted. Currently stubbed as console warnings in AppLayout.tsx. Wire when the native sidebar tracks focused codebook items.

| Action | Blocked on |
|--------|-----------|
| `toggleCodeGroup` | No expand/collapse state in CodebookPanel — groups are always expanded |
| `renameCodeGroup` | Native sidebar focus tracking (which group is selected) |
| `deleteCodeGroup` | Native sidebar focus tracking |
| `renameCode` | Native sidebar focus tracking (which code is selected) |
| `deleteCode` | Native sidebar focus tracking |

### Edit operations — partially handled (2)

| Action | Status |
|--------|--------|
| `undo` / `redo` | Stub (`canUndo: false` in `getState()`). Needs undo store |

### Internal (not from menu)

| Action | Notes |
|--------|-------|
| `set-appearance` | Sent by `BridgeHandler.syncAppearance()` on `ready`. Frontend applies theme |

## Payload conventions

Most actions are **stateless** — the action string is sufficient because the frontend reads current state from FocusContext/QuotesContext (which quote is focused, which are selected).

Actions that need **payloads** (the optional second argument to `menuAction`):

| Action | Payload shape | Example |
|--------|--------------|---------|
| `set-appearance` | `{ value: "dark" \| "light" \| "auto" }` | Already wired |
| `exportAnonymised` | `{ anonymise: true }` | Proposed |
| `importFramework` | `{ templateId: string }` | Wired — pre-selects template in picker |
| `removeFramework` | `{ frameworkId: string }` | Wired — opens confirm dialog in CodebookPanel |
| `findNext` / `findPrevious` | `{ text: string }` | Wired — reads from `NSPasteboard.find` |

**Rule:** if the frontend already knows the target (focused quote, active tab), don't pass it in the payload. Payloads are for data the native side has that the web side doesn't.

## getState() stubs

`bridge.ts` `getState()` has four hardcoded stubs:

| Property | Stub value | Wired when |
|----------|-----------|------------|
| `canUndo` | `false` | Undo store ships (tracks quote edits, tag changes) |
| `canRedo` | `false` | Same |
| `hasPlayer` | `false` | PlayerContext reports popout window state to bridge |
| `playerPlaying` | `false` | PlayerContext reports playback state to bridge |

These control menu item dimming in Swift. Until wired, the Undo/Redo and Video menus will dim correctly (items disabled when stubs are `false`).

## Recommended implementation order (remaining)

1. ~~**New frontend handlers, no new infra**~~ — Done. All 14 Tier 2 actions wired in `AppLayout.tsx`
2. ~~**Codebook**~~ — Done. 5 actions fully wired (browse, import, remove, create group, create code). 5 stubbed pending native focus context (toggle/rename/delete group, rename/delete code)
3. **Video** — requires PlayerContext bridge (popout window ↔ native state sync)
4. **Project operations** — requires project list feature
5. **Undo/Redo** — requires undo store design
