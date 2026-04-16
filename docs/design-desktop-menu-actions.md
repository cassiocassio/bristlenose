# Desktop Menu Actions — Bridge Handler Cookbook

Reference for all menu actions wired through `BridgeHandler.menuAction()`. Working context (the 3-file chain, how to add a new handler) lives in `desktop/CLAUDE.md`.

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

### Project operations — native-side or future (8)

These are either native-only (Finder, print) or depend on features not yet built (project list, re-analysis).

| Action | Notes |
|--------|-------|
| `revealInFinder` | Native: `NSWorkspace.shared.selectFile(nil, inFileViewerRootedAtPath:)`. Needs project path from ServeManager |
| `newProject` | Future: project creation flow |
| `openInNewWindow` | Future: multi-window |
| `renameProject` / `archive` / `deleteProject` | Future: project management |
| `reAnalyse` | Future: re-run pipeline |
| `checkSystemHealth` | Navigate to `/report/` and open doctor panel (or call `/api/health`) |
| `pageSetup` / `print` | `NSPrintOperation` on WKWebView snapshot |

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
