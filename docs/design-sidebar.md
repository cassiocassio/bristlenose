# Dual-Sidebar Layout — Design Document

## Overview

The Quotes tab gets a dual-sidebar layout: a **table-of-contents sidebar** on the left and a **tag-filter sidebar** on the right. Both sidebars are optional — researchers open whichever they need.

**Scope:** Quotes tab only (`/report/quotes`). Other tabs render normally with no grid, no rails.

**Reference mockup:** `docs/mockups/mockup-sidebar-tags.html`

---

## Layout Architecture

### 5-Column Grid

When the Quotes tab is active, a CSS grid provides the structural skeleton:

```
[toc-rail | toc-sidebar | center | tag-sidebar | tag-rail]
   36px       0/280px       1fr      0/280px       36px
```

- **Rails** (columns 1 and 5): 36px icon strips. Visible when their sidebar is closed. Hidden when open.
- **Sidebars** (columns 2 and 4): 0px when closed, 280px (default) when open. Resizable 200–480px.
- **Center** (column 3): `1fr` — absorbs remaining space. Contains header, nav, toolbar, and quotes.

### Key Constraint: Left-Edge Vertical Alignment

Header, NavBar, toolbar, section headings, and quote cards all live inside the grid's center column. Their left edges align vertically — from the logo down through the content. When sidebars open, the center column shifts but internal alignment is preserved.

This means `SidebarLayout` wraps `AppLayout`'s children (Header, NavBar, Outlet, Footer), not just QuotesTab content. On non-Quotes tabs, the layout renders a pass-through wrapper with no grid.

### 4 Layout States

CSS classes on `.layout` control the grid template:

| State | Classes | Grid columns |
|-------|---------|-------------|
| Both closed | `.layout` | `36px 0 1fr 0 36px` |
| TOC open | `.layout.toc-open` | `0 280px 1fr 0 36px` |
| Tags open | `.layout.tags-open` | `36px 0 1fr 280px 0` |
| Both open | `.layout.toc-open.tags-open` | `0 280px 1fr 280px 0` |

Sidebar widths use CSS custom properties (`--toc-width`, `--tags-width`) with `var(--bn-sidebar-width)` as fallback.

### Animation

Adding `.animating` to `.layout` enables `transition: grid-template-columns 0.25s ease`. This class is added before state changes and removed after transition completes (via `transitionend`). Slightly snappier than `--bn-transition-slow` (0.3s) — the layout slide feels better at 0.25s.

---

## Tokens

| Token | Value | Purpose |
|-------|-------|---------|
| `--bn-sidebar-width` | `280px` | Default sidebar panel width |
| `--bn-sidebar-min` | `200px` | Minimum drag-resize bound |
| `--bn-sidebar-max` | `480px` | Maximum drag-resize bound |
| `--bn-rail-width` | `36px` | Collapsed icon rail width |
| `--bn-weight-light` | `370` | Subordinate text (TOC links) |

All committed to `bristlenose/theme/tokens.css`.

---

## Left Sidebar: Table of Contents

### Content

Two groups of links: **Sections** and **Themes**, matching the quote groupings on the page.

### Data Source

Section and theme headings come from QuotesStore — populated by the quotes API response. No new API endpoint needed.

### Scroll Spy

A `useScrollSpy` hook determines which section is currently visible:
- Listens to `scroll` with `requestAnimationFrame` throttle
- Walks section IDs bottom-to-top
- First element with `getBoundingClientRect().top <= 100px` is "active"
- Active TOC link gets `.active` class (accent colour, emphasis weight, hover background)
- Auto-scrolls active link into view (`scrollIntoView({ block: 'nearest', behavior: 'smooth' })`)

### Typography

| Element | Font size | Weight | Token |
|---------|-----------|--------|-------|
| Section heading ("Sections", "Themes") | 0.85rem | `--bn-weight-emphasis` (490) | — |
| Section link | 0.82rem | `--bn-weight-light` (370) | New token |
| Active link | 0.82rem | `--bn-weight-emphasis` (490) | — |

The light weight (370) makes links feel subordinate to headings. On static fonts (Win 10 Segoe UI), 370 rounds to 400, same as 420 — acceptable degradation.

---

## Right Sidebar: Tag Filter

### Content Hierarchy

```
Tag Sidebar
├── Header (title + close button)
├── Subtitle ("47 tags across 5 frameworks")
├── Actions (Select all | Clear | Open »)
├── Search input
└── Body
    ├── Codebook Framework (details/summary disclosure)
    │   ├── Summary (chevron + title + author + eye toggle)
    │   └── Body
    │       ├── Tag Group Card (tinted background)
    │       │   ├── Header (name + subtitle + group eye)
    │       │   ├── Tag Rows
    │       │   │   └── Tag Row (checkbox + badge + micro-bar + count)
    │       │   └── Total Row (TOTAL label + count)
    │       └── ... more groups
    └── ... more frameworks
```

### Data Flow

```
TagSidebar → getCodebook() → CodebookResponse (existing API)
  → frameworks (grouped by framework_id)
  → tag counts → micro-bar widths (proportional to max count)

Checkbox change → QuotesStore.tagFilter → quotes re-filter
Eye toggle → local React state (NOT QuotesStore, NOT persisted)
Tag search → local React state → filter groups/tags by substring
```

### Shared State with Toolbar

Tag sidebar checkboxes and toolbar's `TagFilterDropdown` share the same `QuotesStore.tagFilter` state. Changes in either are immediately reflected in both. No sync logic needed — two views of one state.

### Eye Toggle Philosophy

Eye toggles are **visual declutter only**, not data filters.

**Group eye:**
- Default (open): tags visible, subtitle visible, eye icon hidden
- Hover anywhere over the group → open-eye fades in (top-right)
- Click eye → group collapses: name in grey, subtitle hidden, tags hidden
- Closed state: closed-eye icon always visible as affordance to reopen
- Click closed eye → reopens

**Framework eye:**
- Same visual pattern but acts as bulk toggle
- Click → hides or shows all groups within that framework
- All groups hidden → framework eye shows closed
- Any groups visible → framework eye shows open

**Effect on quotes:** None. Quotes with hidden-eye tags still show. Checkboxes are the data filter. Eyes say "tidy these tags away so I can focus on the ones I'm working with."

### 2-Column Masonry

When the tag sidebar width ≥ 380px, it switches to 2-column masonry layout:

```css
.tag-sidebar.two-col .codebook-body {
    columns: 2;
    column-gap: 0.35rem;
}
.tag-sidebar.two-col .tag-filter-group {
    break-inside: avoid;
}
```

CSS `columns` packs group cards tightly (no row-based whitespace gaps). `break-inside: avoid` keeps each group card as an unbroken unit.

---

## Drag-to-Resize

### Handles

4 drag handles:
- **Sidebar edge handles** (`.toc-drag-handle`, `.tag-drag-handle`): visible when sidebar is open, positioned at the sidebar's outer edge
- **Rail edge handles** (`.toc-rail-drag`, `.tag-rail-drag`): positioned at the rail's inner edge, allow drag-to-open from closed state

### Behaviour

- `mousedown` → record start X/width, add `body.dragging` (disables text selection, sets `col-resize` cursor)
- `mousemove` → compute delta, clamp width to [200, 480]
- **Snap-close**: if dragged below 80px → snaps closed (sets width to 0, removes open class)
- **Drag-to-open from rail**: drag >20px threshold triggers open, then continues as resize
- `mouseup` → cleanup, persist width to `localStorage`

### Visual Affordance

Drag handles are 6px invisible strips. On hover: subtle blue highlight (accent colour, 30% opacity). Centered within the handle: a 2px × 24px dot that fades in on hover.

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `[` | Toggle TOC sidebar |
| `]` | Toggle tag sidebar |
| `\` or `⌘.` | Toggle both (any open → close all; all closed → open both) |

> **Note:** `⌘[` / `⌘]` and `⌘1` / `⌘2` were considered but are browser-native shortcuts (history back/forward and tab switching) that cannot be reliably intercepted. Plain `[`, `]`, `\` have no browser conflicts and are spatially intuitive (left bracket = left sidebar, right bracket = right sidebar). `⌘.` is kept as an alias for toggle-both (Figma convention).

Guarded by `!editing && !helpModalOpen`. Added to the existing `useKeyboardShortcuts` hook.

---

## Persistence

`localStorage` keys:
- `bn-toc-open` — boolean
- `bn-tags-open` — boolean
- `bn-toc-width` — number (clamped to [200, 480] on read)
- `bn-tags-width` — number (clamped to [200, 480] on read)

Default: both closed, width 280.

---

## State Management

`SidebarStore` follows the module-level store pattern (same as `QuotesStore`):

```typescript
// Module-level state + useSyncExternalStore
type SidebarState = {
  tocOpen: boolean;
  tagsOpen: boolean;
  tocWidth: number;
  tagsWidth: number;
};

// Actions
toggleToc(), toggleTags(), toggleBoth()
setTocWidth(w), setTagsWidth(w)
closeToc(), closeTags()

// Hook
useSidebarStore() → SidebarState
```

Module-level (not React Context) because:
- Consistent with QuotesStore pattern
- Accessible from keyboard shortcuts and toolbar without provider nesting
- Not dependent on React tree structure

---

## Static Render Isolation

The `.layout` wrapper exists only in the React tree (SPA mode). The static render path (`bristlenose render`) never produces a `.layout` element, so sidebar CSS is inert — it ships in the theme bundle but has no visual effect.

---

## Responsive Behaviour

When the TOC sidebar is open, the center column narrows. To compensate:
- `.layout.toc-open .toolbar-btn-label { display: none }` — toolbar button labels collapse to icon-only
- Below 900px viewport: labels also hidden via `@media (max-width: 900px)`

---

## CSS Files

| File | Layer | What it covers |
|------|-------|----------------|
| `organisms/sidebar.css` | Organism | 5-column grid, rails, sidebar panels, drag handles, animated transitions, TOC links, responsive label hide |
| `organisms/sidebar-tags.css` | Organism | Tag sidebar content: framework disclosure, group cards, eye toggles, tag rows, group totals, 2-col masonry, search |
| `atoms/checkbox.css` | Atom | Ghost checkbox (shared by sidebar and toolbar dropdown) — already committed |

---

## React Components

| Component | Purpose |
|-----------|---------|
| `SidebarLayout.tsx` | Grid container — active on Quotes, pass-through elsewhere |
| `TocSidebar.tsx` | TOC: sections + themes with scroll-spy |
| `TagSidebar.tsx` | Root: codebook tree + search + bulk actions |
| `CodebookFramework.tsx` | `<details>` disclosure with framework eye |
| `TagGroupCard.tsx` | Tinted group card with eye toggle |
| `TagRow.tsx` | Checkbox + badge + micro-bar + count |
| `EyeToggle.tsx` | Reusable open/closed eye SVG button |

---

## Gotchas

1. **`SidebarLayout` wraps at `AppLayout` level**, not `QuotesTab` level. This is necessary for full-height sidebars that span from above the header to below the footer. On non-Quotes tabs, it renders a pass-through `<div>` with no grid.

2. **Eye toggles are local React state** — not in QuotesStore, not persisted. They reset when navigating away. This is intentional: eye toggles are quick "tidy up the sidebar" gestures, not persistent preferences.

3. **Tag sidebar and toolbar dropdown share `QuotesStore.tagFilter`** — no sync needed. But if you add a third tag-selection UI, it gets the same state for free.

4. **Scroll spy walks bottom-to-top** — this handles the case where multiple sections are above the threshold. The lowest one that's still above the viewport top is the most relevant.

5. **Animation class timing** — `.animating` must be added before changing open/close state and removed after `transitionend`. If removed too early, the grid snaps. If never removed, subsequent mouse events on sidebar content feel sluggish (the grid is still in transition mode).

6. **Drag handles use `position: absolute`** — they overlay the sidebar edge. The sidebar needs `position: relative` (already has `position: sticky` which establishes a containing block).

7. **`body.dragging`** — uses `!important` on cursor to override all child cursors during resize. This is one of the few legitimate `!important` uses.

8. **Tab checkboxes in mockup use inline `input[type="checkbox"]` selectors** — production should use the `.bn-checkbox` atom class from `atoms/checkbox.css` instead.

---

## Extensibility

Future tabs may have their own sidebars. The infrastructure is reusable:
- `SidebarLayout` is a container with content slots, not Quotes-specific
- Grid/rails/drag/keyboard are shared infrastructure
- `sidebar.css` is the shared layout organism
- `sidebar-tags.css` is Quotes-specific content styling
- Each future tab gets its own `sidebar-{context}.css` organism and its own sidebar components
