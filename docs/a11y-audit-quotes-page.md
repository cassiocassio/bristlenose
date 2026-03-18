# WCAG 2.1 AA Accessibility Audit — Quotes Page

_18 Mar 2026 — code-based audit_

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
