# Bristlenose TODO Summary (28 Feb 2026)

## Next up (unchecked from "Next session reminder")

- **QA: threshold review dialog on real data** — needs qualitative assessment with real interview projects

## Priority order

1. Moderator Phase 2 — cross-session linking (#25)
2. Dark mode selection highlight (#52)
3. SVG icon set — replace fragile x character glyphs
4. Miro bridge — near-term sharing story
5. Export & sharing — deferred until after React migration
6. Reactive UI architecture (#29)

## React migration progress (Steps 1-10)

- [x] Step 1: Settings panel
- [x] Step 2: About panel
- [x] Step 3: QuotesStore context
- [x] Step 4: Toolbar (SearchBox, TagFilterDropdown, ViewSwitcher, CsvExport, Toast). 87 tests
- [x] Step 5: Tab navigation -> React Router. `react-router-dom` v7, `createBrowserRouter`, single `#bn-app-root`, NavBar, AppLayout, 8 page wrappers, SPA catch-all, backward-compat shims. 45 tests
- [x] Step 6: Player integration. `PlayerProvider` context, `seekTo`, glow highlighting via DOM refs, progress bar CSS custom property. 28 tests
- [x] Step 7: Keyboard shortcuts. `FocusProvider` context, `useKeyboardShortcuts` hook, `HelpModal`, click-to-focus with modifier support, hide handler registry. 62 tests
- [ ] Step 8: Retire remaining vanilla JS
- [ ] Step 9: React app shell
- [ ] Step 10: Export -- DOM snapshot

## Open items by area

### Report UI (17 items)

| Item | Issue | Effort |
|------|-------|--------|
| Dashboard: increase stats coverage | -- | medium |
| Dark mode: selection highlight visibility | #52 | trivial |
| Logo: increase size from 80px to ~100px | #6 | trivial |
| Show day of week in session Start column | #11 | small |
| Reduce AI tag density (tune prompt or filter) | #12 | small |
| User-tags histogram: right-align bars | #13 | small |
| Clickable histogram bars -> filtered view | #14 | small |
| Sticky header decision | #15 | small |
| Refactor render_html.py header/toolbar into template helpers | #16 | small |
| Theme management in browser (custom CSS themes) | #17 | small |
| Dark logo: proper albino bristlenose pleco | #18 | small |
| Lost quotes: surface unselected quotes for rescue | #19 | small |
| .docx export | #20 | small |
| Edit writeback to transcript files | #21 | small |
| Tag definitions page | #53 | small |
| Undo bulk tag (Cmd+Z for last tag action) | -- | medium |
| Multi-page report (tabs or linked pages) | #51 | large |
| Project setup UI for new projects | #49 | large |
| Responsive quote grid layout | -- | medium |
| Content density setting (Compact / Normal / Generous) | -- | small |

### Report JavaScript (8 items)

| Item | Issue |
|------|-------|
| Add `'use strict'` to all modules | #7 |
| Extract shared `utils.js` for duplicated code | #8 |
| Extract magic numbers to config object | #9 |
| Drop `execCommand('copy')` fallback | #10 |
| Split `tags.js` into smaller modules | #22 |
| Explicit cross-module state management | #23 |
| Auto-suggest accessibility (ARIA) | #24 |
| JS tests (jsdom or Playwright) | #28 |

### Pipeline and analysis (8 items)

| Item | Issue | Effort |
|------|-------|--------|
| Signal concentration: Phase 4 -- two-pane layout, grid-as-selector | -- | medium |
| Signal concentration: Phase 5 -- LLM narration of signal cards | -- | small |
| Signal concentration: user-tag x group grid | -- | medium |
| Session enable/disable toggle | -- | medium |
| Delete/quarantine session from UI | -- | medium |
| Re-run pipeline from serve mode | -- | large |
| Moderator Phase 2: cross-session linking | #25 | medium |
| Speaker diarisation improvements | #26 | medium |
| Batch processing dashboard | #27 | medium |
| Quote sequences (3 sub-items) | -- | small-medium |

### CLI (3 items)

- Britannification pass (#40)
- `--prefetch-model` flag for Whisper (#41)
- Doctor: serve-mode checks + Vite auto-discovery

### Packaging (4 items)

- CI: automate `.dmg` build on push
- `.dmg` README: include "Open Anyway" instructions
- Homebrew formula: post_install for spaCy model (#42)
- Snap store publishing (#45)
- Windows installer (winget) (#44)

### Desktop app (4 items)

- Keychain: migrate to native Security framework
- ReadyView: replace `NSOpenPanel.runModal()` with SwiftUI `.fileImporter`
- ProcessRunner: replace `availableData` polling with `AsyncBytes`
- `hasAnyAPIKey()` only checks Anthropic -- rename or extend

### Logging instrumentation (8 items, tiers 2-3)

- Cache hit/miss decisions in `_is_stage_cached()`
- Importer per-entity sync stats
- Promote model name from DEBUG to INFO
- Concurrency queue depth at semaphore creation
- PII entity type breakdown per session
- FFmpeg command and return code on failure
- Keychain resolution: which store, which keys
- Manifest load/save: schema version, stage summary

### Infrastructure

- Storybook / component playground
- Serve-mode mount point injection via Vite backend-integration
- Playwright E2E tests (post-React migration)

## Maintenance

- **Next quarterly dep review**: May 2026
- **Annual review**: Feb 2027
