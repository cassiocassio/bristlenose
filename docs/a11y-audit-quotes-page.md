---
status: partial
last-trued: 2026-09-20
trued-against: HEAD@main on 2026-09-20
---

# WCAG 2.1 AA Accessibility Audit — Quotes Page

> **Trued 20 Sep 2026 — 7 of 17 findings are STILL OPEN, including one Critical.**
> This doc was classified `D` (archive) by the corpus triage and that was **wrong**:
> it was re-measured finding-by-finding against `HEAD` and half of it is still live.
> It stays in `docs/`. The line anchors below are from Mar 2026 and have drifted —
> **trust the status table, not the line numbers.**

## Status at 20 Sep 2026 — measured, not estimated

| # | Sev | Status | Evidence at HEAD |
|---|---|---|---|
| 1 | Critical | ✅ fixed | `islands/QuoteCard.tsx` + `components/Badge.tsx` carry **0** `<span onClick>`; 5 and 1 `<button>` respectively |
| **2** | **Critical** | 🔴 **OPEN** | `components/TagInput.tsx` (12.5 KB) carries `aria-hidden="true"` ×2 **and nothing else** — zero `role="combobox"`, `aria-expanded`, `role="listbox"` |
| 3 | Major | ✅ fixed | `components/NavBar.tsx` — **0** `role="tablist"` |
| 4 | Major | ⚪ moot | `components/HelpModal.tsx` deleted 2026-07-10 (`3f49d170`, "retire the SPA help modal"); the surface shipped as `islands/AboutPanel.tsx` |
| 5 | Major | 🟠 **partly open** | `SearchBox.tsx` ✅ (2 `aria-label`), `TagSidebar.tsx` ✅ (1) — **`TagInput.tsx` still 0**. `TagFilterDropdown.tsx` **no longer exists**, so that row is moot |
| 6 | Major | ✅ fixed | `components/ViewSwitcher.tsx:79` `tabIndex={0}`, `:83` `onKeyDown` |
| **7** | **Major** | 🔴 **OPEN** | `theme/colors/palette-default.css:62-63` still `--bn-colour-icon-idle: #c9ccd1` / `--bn-colour-starred: #999`; `:150-151` dark still `#595959`. **Unchanged since the audit** |
| **8** | **Major** | 🔴 **OPEN** | `islands/Toolbar.tsx` — **0** `role="status"`, **0** `aria-live` |
| 9 | Major | ⚪ moot | `components/Counter.tsx` deleted |
| 10 | Major | ✅ fixed | `<main>` present in `layouts/AppLayout.tsx` |
| **11** | Minor | 🔴 **OPEN** | `components/TocSidebar.tsx:140` — `<a>` are direct children of `<nav>`, separated by `<div class="toc-heading">`. No `<ul>`/`<li>` |
| 12 | Minor | ✅ fixed | `components/ModalNav.tsx` — **0** `role="navigation"` |
| **13** | Minor | 🟠 **partly open** | `QuoteCard.tsx` ✅, `Toolbar.tsx` ✅ — **`NavBar.tsx` 2 `<svg>` / 0 `aria-hidden`**, **`SearchBox.tsx` 2 `<svg>` / 0 `aria-hidden`** |
| 14 | Minor | ✅ fixed | 13 files under `bristlenose/theme/` carry `prefers-reduced-motion` |
| **15** | Minor | 🔴 **OPEN** | `utils/announce.ts` + `components/AnnounceRegion.tsx` exist and are wired for star / hide / tag (`contexts/QuotesContext.tsx:256,270,317,331`) — but **no call site announces a search or filter result count** |
| 16 | Minor | 🔵 decided | Not a gap. `theme/molecules/quote-actions.css:7-12` reasons it out explicitly: the card carries **font-weight + a bar** as second, non-colour cues and the glyph is deliberately "the mark". `aria-pressed` was already correct |
| 17 | Minor | ✅ fixed | `components/SettingsModal.tsx` — **0** `<code onClick>` |

**Open: 7** (1 Critical, 3 Major, 3 Minor) · fixed 7 · moot 2 · decided 1.

### Revised fix order (supersedes the one at the foot of this doc)

1. **#2 + #5** — `TagInput.tsx` combobox pattern **and** its `aria-label`; they are one edit.
2. **#7** — three token values in `palette-default.css`; CSS-only, no JS.
3. **#8** — `role="status"` on the Toolbar toast container; `AnnounceRegion.tsx` already exists to copy.
4. **#15** — one `announce()` call on the filter path; the utility is already wired elsewhere.
5. **#13** — `aria-hidden="true"` on the 4 decorative SVGs in `NavBar.tsx` / `SearchBox.tsx`.
6. **#11** — wrap `TocSidebar` links in `<ul>`/`<li>`.

---

_Original audit below, unedited. 18 Mar 2026 — code-based audit._

## Context

Code-based audit of the `/report/quotes/` page — the most complex page in Bristlenose, with ~46 React files involved (sidebar layout, quote cards, toolbar, modals, keyboard navigation, tag autocomplete). The audit reviewed source code and CSS across `frontend/src/` and `bristlenose/theme/`.

**Existing good patterns:** `Toggle` uses `aria-pressed`, `SidebarLayout` uses `inert` on closed panels, drag-resize handles have `role="separator"` with full ARIA value attributes and keyboard support, `TocSidebar` uses `aria-current="location"`, `SettingsModal` has proper focus trapping and focus return via `ModalNav`.

---

## Critical (blocks fundamental workflows)

### 1. Non-focusable interactive elements — bare `<span onClick>`

Several clickable elements are `<span>` with `onClick` — invisible to keyboard users and screen readers.

| Element | File | Line |
|---------|------|------|
| "Add tag" `+` button | `islands/QuoteCard.tsx` | ~741 |
| AI badge delete action | `components/Badge.tsx` | ~137 |
| Proposed badge accept/deny | `components/Badge.tsx` | ~73 |

**Fix:** Convert to `<button>` elements with `aria-label`.

### 2. TagInput missing combobox ARIA pattern

`components/TagInput.tsx` — the autocomplete input has none of the required ARIA combobox attributes:
- No `role="combobox"`, `aria-expanded`, `aria-autocomplete="list"`, `aria-controls`
- Suggestion list has no `role="listbox"`, items have no `role="option"`
- No `aria-activedescendant` for highlighted suggestion
- No `aria-label` on the input (placeholder "tag" is insufficient)

**Fix:** Implement WAI-ARIA combobox pattern. Add `aria-label="Add tag"`.

---

## Major

### 3. NavBar uses `role="tablist"` incorrectly

`components/NavBar.tsx:35` — `<nav role="tablist">` with `<NavLink role="tab">`. These are router links, not ARIA tabs. No matching `role="tabpanel"` exists.

**Fix:** Remove `role="tablist"` and `role="tab"`. The semantic `<nav>` with links is correct.

### 4. HelpModal lacks dialog semantics and focus trap

`components/HelpModal.tsx` — missing `role="dialog"`, `aria-modal="true"`, focus trap, and focus-return. Keyboard users can Tab behind the modal. SettingsModal already has the correct implementation via `ModalNav`.

**Fix:** Add `role="dialog"`, `aria-modal="true"`, `aria-labelledby` → h2. Port focus trap from ModalNav. Track `document.activeElement` on open, restore on close.

### 5. Missing input labels

| Input | File | Fix |
|-------|------|-----|
| Search input | `SearchBox.tsx` | Add `aria-label="Filter quotes"` |
| Tag input | `TagInput.tsx` | Add `aria-label="Add tag"` |
| Tag sidebar search | `TagSidebar.tsx` | Add `aria-label="Search tags"` |
| Tag filter search | `TagFilterDropdown.tsx` | Add `aria-label="Search tags"` |

### 6. ViewSwitcher dropdown has no keyboard navigation

`components/ViewSwitcher.tsx` — menu items (`<li role="menuitem">`) have no `tabindex`, no Arrow key navigation, no Enter/Space to select, no Escape to close.

**Fix:** Implement standard menu keyboard pattern.

### 7. Non-text contrast failures on icon colours

| Token | On background | Ratio | Required |
|-------|--------------|-------|----------|
| `--bn-colour-icon-idle: #c9ccd1` | `#fff` | ~1.8:1 | 3:1 |
| `--bn-colour-starred: #999` | `#fff` | ~2.8:1 | 3:1 |
| Dark mode `--bn-colour-icon-idle: #595959` | `#111` | ~2.4:1 | 3:1 |

**Fix:** Darken light-mode idle icons to `≥#888`, starred to `≥#767676`. Lighten dark-mode idle to `≥#888`.

### 8. Toast notifications not announced

`islands/Toolbar.tsx` — toast messages (e.g. "3 quotes copied as CSV") have no `aria-live` region.

**Fix:** Add `role="status"` or `aria-live="polite"` to the toast container.

### 9. Counter unhide action not keyboard-accessible

`components/Counter.tsx:107` — `.bn-hidden-preview` unhide action is a `<span onClick>`.

**Fix:** Change to `<button>`.

### 10. No `<main>` landmark

`pages/QuotesTab.tsx` — page content renders in a bare fragment with no `<main>` landmark.

**Fix:** Wrap `<Outlet>` in AppLayout's center column with `<main>`.

---

## Minor

### 11. TOC links not in list structure

`TocSidebar.tsx` — links are direct `<a>` children of `<nav>`, not wrapped in `<ul>/<li>`. Screen readers can't announce "list, 8 items".

### 12. ModalNav has redundant `role="navigation"` on `<ul>`

`ModalNav.tsx:205` — the `<ul>` inside a `<nav>` doesn't need `role="navigation"`.

### 13. SVGs missing `aria-hidden="true"`

Decorative SVGs inside labelled buttons lack `aria-hidden="true"`: NavBar icons, SearchBox icons, QuoteCard HideIcon, Toolbar CopyIcon. (SidebarLayout icons already do this correctly.)

### 14. No `prefers-reduced-motion` media query

`atoms/interactive.css` — animation suppression is JS-only (`.bn-no-animations` class). The OS-level `prefers-reduced-motion` preference is not respected via CSS. Also: hide/unhide ghost animations in `QuoteGroup.tsx` and badge pulse animation don't check reduced-motion.

### 15. No live region for filter result counts

When search filters quotes, the count of visible results is not announced to screen readers.

### 16. Starred quotes rely on colour alone for sighted users

Star toggle uses colour change only. Adding filled vs outline distinction would help low-vision users. (The `aria-pressed` state is correct for screen readers.)

### 17. Settings modal `<code>` copy action not focusable

`SettingsModal.tsx:376` — env var `<code>` with `onClick` for copy is not keyboard-accessible.

---

## Recommended fix order

1. **Critical #1 + #2** — non-focusable elements and TagInput combobox (biggest impact, blocks keyboard users)
2. **Major #4** — HelpModal focus trap (pattern already exists in ModalNav)
3. **Major #3 + #5** — NavBar roles + missing input labels (quick wins)
4. **Major #7** — icon contrast tokens (CSS-only change)
5. **Major #6 + #8 + #9 + #10** — ViewSwitcher keyboard, toast live region, Counter button, main landmark
6. **Minor issues** — incremental cleanup
