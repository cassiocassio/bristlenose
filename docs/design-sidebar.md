---
status: current
last-trued: 2026-08-31
trued-against: HEAD@main on 2026-08-31
---

## Changelog

- _2026-08-31_ — trued up: the two sidebars no longer share a default width
  (left nav 240, tag sidebar 280), so every "280px (default)" claim now
  distinguishes them; corrected the Overview's "Quotes tab only" scope, which
  the body already contradicted at § Desktop embedded mode; corrected the
  drag clamp from [200, 320] to [200, 480]; and noted that
  `--bn-sidebar-width` is a fallback rather than the operative default.
  Anchors: `frontend/src/contexts/SidebarStore.ts:40-43`,
  `frontend/src/layouts/AppLayout.tsx:241`, `bristlenose/theme/tokens.css:150`,
  commit "install leads, uninstall recedes".
- _<undated>_ — initial draft.

# Dual-Sidebar Layout — Design Document

## Overview

The Quotes tab gets a dual-sidebar layout: a **table-of-contents sidebar** on the left and a **tag-filter sidebar** on the right. Both sidebars are optional — researchers open whichever they need.

**Scope:** five lenses carry the left panel — Quotes, Sessions, Codebook,
Codebook v2 and Analysis (`showSidebar` in `AppLayout.tsx`). The **right** tag
sidebar is Quotes-only. Lenses outside that set render with no grid and no
rails. _(This said "Quotes tab only" until 31 Aug 2026; the panel grew to the
other lenses without the Overview following — § Desktop embedded mode had
already been trued and named four of them.)_

**Reference mockup:** `docs/mockups/mockup-sidebar-tags.html`

---

## Layout Architecture

### 5-Column Grid

When the Quotes tab is active, a CSS grid provides the structural skeleton:

```
[toc-rail | toc-sidebar | center | tag-sidebar | tag-rail]
   36px       0/240px       1fr      0/280px       36px
```

- **Rails** (columns 1 and 5): 36px icon strips. Visible when their sidebar is closed. Hidden when open.
- **Sidebars** (columns 2 and 4): 0px when closed. **The two open defaults
  differ**: the left nav opens at **240px**, the tag sidebar at **280px**
  (`DEFAULT_TOC_WIDTH` / `DEFAULT_TAGS_WIDTH`). Both resizable 200–480px, and
  both persist per side. The left nav is deliberately the thinner of the two —
  it is shared across every lens, so its width is a cost paid on all of them.
- **Center** (column 3): `1fr` — absorbs remaining space. Contains header, nav, toolbar, and quotes.

### Key Constraint: Left-Edge Vertical Alignment

Header, NavBar, toolbar, section headings, and quote cards all live inside the grid's center column. Their left edges align vertically — from the logo down through the content. When sidebars open, the center column shifts but internal alignment is preserved.

This means `SidebarLayout` wraps `AppLayout`'s children (Header, NavBar, Outlet, Footer), not just QuotesTab content. On non-Quotes tabs, the layout renders a pass-through wrapper with no grid.

### 4 Layout States

CSS classes on `.layout` control the grid template:

| State | Classes | Grid columns |
|-------|---------|-------------|
| Both closed | `.layout` | `36px 0 1fr 0 36px` |
| TOC open | `.layout.toc-open` | `0 240px 1fr 0 36px` |
| Tags open | `.layout.tags-open` | `36px 0 1fr 280px 0` |
| Both open | `.layout.toc-open.tags-open` | `0 240px 1fr 280px 0` |

Sidebar widths use CSS custom properties (`--toc-width`, `--tags-width`) with `var(--bn-sidebar-width)` as fallback.

### Animation

Adding `.animating` to `.layout` enables `transition: grid-template-columns 0.25s ease`. This class is added before state changes and removed after transition completes (via `transitionend`). Slightly snappier than `--bn-transition-slow` (0.3s) — the layout slide feels better at 0.25s.

---

## Tokens

| Token | Value | Purpose |
|-------|-------|---------|
| `--bn-sidebar-width` | `280px` | **Fallback only.** `SidebarLayout` sets `--toc-width` / `--tags-width` from the store whenever a panel is open, so this is reached only while the panel is closed and its width is 0. The operative defaults are `DEFAULT_TOC_WIDTH` (240) and `DEFAULT_TAGS_WIDTH` (280) in `SidebarStore.ts` |
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
- `mousemove` → compute delta, clamp width to [200, 480] (`MIN_WIDTH` / `MAX_WIDTH` in `useDragResize.ts`; the earlier temporary 320 cap for single-column layout has been lifted)
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
| `\` or `⌘.` or `§` | Toggle both (any open → hide all, stashing the arrangement; all closed → restore it) |

> **Note:** `⌘[` / `⌘]` and `⌘1` / `⌘2` were considered but are browser-native shortcuts (history back/forward and tab switching) that cannot be reliably intercepted. Plain `[`, `]`, `\` have no browser conflicts and are spatially intuitive (left bracket = left sidebar, right bracket = right sidebar). `⌘.` is kept as an alias for toggle-both (Figma convention).
>
> **`§` is an ISO-layout alias, not an advertised binding.** It is the unmodified top-left key on Apple British — the closest a Mac gets to Photoshop's `Tab` — but US ANSI has no `§` key at all (`⌥6`) and its position varies elsewhere (`⇧3` on German; absent from the Spanish top-left slot). So it stays a bare web-layer key behind the `isEditing()` guard, and the desktop menu advertises `⌘⌥\` instead. It could not be a menu key equivalent in any case: a bare `NSMenuItem` equivalent fires before the responder chain and would swallow `§` in every rename field and inline editor.

### Hide all sidebars — stash, don't toggle

Hiding stashes the current arrangement and showing puts **that** back, rather than opening everything. Lineage is Photoshop's `Tab` (and `⇧Tab`, which keeps the toolbar) rather than Figma's Show/Hide UI: Figma can use a bare toggle because its panels are always both present, whereas here mixed arrangements are the norm. Without the stash, "TOC open, tags closed → hide → show" hands back **both** — you gain a sidebar you never had. The stash is ephemeral (never persisted); with nothing stashed, "show all" means all, so the command is never a no-op.

Scope is the sidebars. The Analysis heatmap inspector is a bottom panel on the data rather than navigation chrome, and the toolbar stays — in the desktop app it is the only affordance for the web panels (see § Desktop embedded mode), so hiding it would make this a one-way door.

**Desktop adds the projects column.** `⌘⌥\` in View ▸ **Hide All Sidebars** covers all three; the web keys stay scoped to the two content panels, which in the browser *is* all of them. Native decides the direction — it is the only side that can see the column and the panels at once — and sends an explicit `hideAllSidebars` / `showAllSidebars` rather than a toggle, reading the web half over the `panel-state` bridge mirror. The column deliberately has no stash of its own: it is binary, and "Show All Sidebars" showing it is exactly what the label says.

Guarded by `!editing && !helpModalOpen`. Added to the existing `useKeyboardShortcuts` hook.

---

## Persistence

`localStorage` keys:
- `bn-toc-open` — boolean
- `bn-tags-open` — boolean
- `bn-toc-width` — number (clamped to [200, 480] on read)
- `bn-tags-width` — number (clamped to [200, 480] on read)

Default: both closed. On first open, left nav 240 and tag sidebar 280.

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

The `.layout` wrapper exists only in the React tree (SPA mode). The stage-12 static-render byproduct never produces a `.layout` element, so sidebar CSS is inert there — it ships in the theme bundle but has no visual effect. (Post-A3, 12 May 2026 — `bristlenose render` removed; byproduct still on disk, never surfaced.)

---

## Desktop embedded mode — rails removed

In the macOS app the SPA runs inside a WKWebView and `isEmbedded()` is true (`window.__BRISTLENOSE_EMBEDDED__`, injected at document-start; `?embedded` also works for browser QA). The sidebars are toggled from the **native toolbar** (`toggleLeftPanel` / `toggleRightPanel` → `sidebarAnimations.toggleToc` / `toggleTags`, already wired in `AppLayout.tsx`) and the `[` / `]` keys — so the web icon rails, their drag-to-open handles, and the close-× are redundant web chrome. They're an alien idiom in a Mac window, and the two 36px rails waste horizontal space the WKWebView (which fills the detail pane with **zero inset** — `ContentView.swift:2023`) could give to content.

**Sessions-lens exception (14 Aug 2026):** the embedded Sessions lens has **no web left panel at all** — the native session-switcher popover replaced it (`docs/design-sessions-popover-navigation.md`). `AppLayout` gates `showSidebar`, the `leftPanel` prop, the `[` key and the `panel-state` `leftOpen` flag off the embedded sessions route, and the toolbar's Sessions slot presents the popover instead of a toggle. Everything below applies to the panels that remain (Quotes TOC, tag sidebar, codebook, signals) — and to the browser, where Sessions keeps its sidebar unchanged. Note this makes the `?embedded` browser-QA URL an accurate preview of the *web-side* removal (no sidebar, no sticky-header dropdown) with no native popover to stand in — that's the true embedded web state, not a bug; the switching affordance is native chrome the browser can't show.

**What changes** (all gated on `.layout.embedded` / `isEmbedded()`, browser untouched):
- `SidebarLayout.tsx` adds the `embedded` class to the active grid and the inert branch; gates both close-× buttons behind `!embedded`; and, because the now-hidden rail button can't receive focus, redirects focus-on-close to the `.center` region (made programmatically focusable with `tabIndex={-1}` in embedded only).
- `sidebar.css`: `.layout.embedded { --bn-rail-width: 0 }` — one token override collapses the rail track in **every** `grid-template-columns` variant (closed, `toc-open`, `tags-open`, both, `layout-no-right`, `layout-inert`). `display: none` on `.toc-rail` / `.tag-rail` stops the 0-width box still painting its 1px border. The native `NSSplitView` divider draws the left edge; the window edge bounds the right.
- The right gutter (`--bn-gutter-right: 0.5rem`) was sized assuming a 36px rail sat beyond it. On minimap-less tabs (`layout-no-right` / `layout-inert`) the webview now butts the window edge, so embedded restores a symmetric inset matching the left (`--bn-gutter-left`, 2rem).

**Consequence:** overlay/hover-peek mode is unreachable in embedded (it was only ever triggered from the rail), so the TOC collapses to a clean **closed ↔ push** model like the tag side — matching native split-view semantics.

**Verified geometry** (Playwright against `bristlenose serve`, 1440px viewport, Quotes tab): browser grid `36 0 1240 80 0 36`; embedded grid `0 0 1312 80 0 0` — center reclaims exactly 72px (1240 → 1312), rails `display:none`, 0 close buttons, center `tabindex=-1`. On the Analysis (no-right) tab, embedded `padding-right` is bumped 8px → 32px so content clears the window edge.

**Reference mockup:** `docs/mockups/mockup-desktop-rail-removal.html` (pale-banded geometry study, browser vs desktop, states A–D).

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

2. **Eye toggles are persisted to SQLite** via `hiddenTagGroups` in `SidebarStore` and the `/hidden-tag-groups` API. They survive page reloads and tab switches. Framework-level hidden state is derived: a framework is hidden when all its groups are in `hiddenTagGroups`.

3. **Tag sidebar and toolbar dropdown share `QuotesStore.tagFilter`** — no sync needed. But if you add a third tag-selection UI, it gets the same state for free.

4. **Scroll spy walks bottom-to-top** — this handles the case where multiple sections are above the threshold. The lowest one that's still above the viewport top is the most relevant.

5. **Animation class timing** — `.animating` must be added before changing open/close state and removed after `transitionend`. If removed too early, the grid snaps. If never removed, subsequent mouse events on sidebar content feel sluggish (the grid is still in transition mode).

6. **Drag handles use `position: absolute`** — they overlay the sidebar edge. The sidebar needs `position: relative` (already has `position: sticky` which establishes a containing block).

7. **`body.dragging`** — uses `!important` on cursor to override all child cursors during resize. This is one of the few legitimate `!important` uses.

8. **Tab checkboxes in mockup use inline `input[type="checkbox"]` selectors** — production should use the `.bn-checkbox` atom class from `atoms/checkbox.css` instead.

---

## Eye Toggle → Hide Badges on Quotes (Phase 4b)

### The Three Distinct Interactions

There are three conceptually different actions a researcher takes with tags in the sidebar:

| Gesture | What it means | Effect on quotes | Persistence |
|---------|--------------|-----------------|-------------|
| **Checkbox** (uncheck a tag) | "Exclude quotes with this signal from my deliverable" | Removes quotes from the visible list | Session (QuotesStore.tagFilter) |
| **Eye toggle** (hide a group) | "Declutter — too many signals, hide these badges for now" | Quotes stay in list, but badges for hidden tags are suppressed on quote cards | Persistent (server, per project) |
| **Remove codebook** | "I don't want this framework at all" | Destructive server-side removal (restorable) | Persistent (server) |

### Current State

Eye toggles currently only collapse the tag group card in the sidebar. They do **not** affect quote card badge rendering. This means hiding "Behaviour" in the sidebar still shows all Behaviour-tagged badges on every quote card — defeating the declutter purpose.

### Desired Behaviour

When a tag group's eye toggle is closed:
1. The group card collapses in the sidebar (already works)
2. Tag badges for that group's tags are **hidden on quote cards** (not yet implemented)
3. Quotes remain in the list — no filtering effect
4. The quote's remaining visible badges still render normally

When a framework-level eye toggle is closed:
1. All groups within that framework collapse (already works)
2. All tag badges from that framework are hidden on quote cards
3. Same: no filtering, just visual declutter

### Why This Matters

Researchers experience tag overload. A report with 5 frameworks × 10 groups × 5 tags = 250 possible tag badges. Each quote card might show 8–12 badges. The eye toggle is the researcher saying "I believe these signals exist, but I'm not thinking about them right now — hide them so I can focus on what I'm building a case around."

This is fundamentally different from unchecking (which says "this quote isn't part of my case") and from removing a codebook (which says "this framework isn't relevant to this project").

### Implementation (completed)

- `hiddenTagGroups: Set<string>` lives in `SidebarStore` (module-level store, same pattern as QuotesStore)
- Persisted to SQLite via `HiddenTagGroup` table (one row per hidden group, project-scoped, `UniqueConstraint`)
- API: `GET/PUT /projects/{id}/hidden-tag-groups` — full-state replacement, fire-and-forget PUT from frontend
- `initHiddenTagGroups()` hydrates from API on TagSidebar mount
- `TagGroupCard` reads eye state from store (no local `useState`) — eye open/closed is derived from `hiddenTagGroups.has(name)`
- Framework-level hidden is derived in TagSidebar via `useMemo`: a framework is hidden when all its groups are in `hiddenTagGroups`
- `QuoteGroup` filters `userTags` and `proposedTags` by checking `hiddenTagGroups` before passing to `QuoteCard`
- Performance: O(1) set lookup per badge, negligible

### Remaining Open Questions

1. Should there be a visual indicator on quote cards that badges are being hidden? (e.g., a subtle "+3 hidden" count)
2. When the eye reopens, should badges animate in or just appear?

---

## AutoCode Toast Dismissal

The completed AutoCode toast (showing "Report" link to review thresholds) is **non-dismissible** — no × button, no auto-dismiss timer. The user must click "Report" to open the threshold review modal. This prevents the scenario where a user dismisses the toast and loses access to threshold review entirely, getting default thresholds applied silently.

**TODO:** Add a persistent "Review AutoCode results" entry point on the Codebook page so users can revisit threshold decisions even after the toast is gone. This needs more design thinking — noted for a future session.

Running/pending/failed toasts retain the × button and auto-dismiss behaviour.

---

## Extensibility

Future tabs may have their own sidebars. The infrastructure is reusable:
- `SidebarLayout` is a container with content slots, not Quotes-specific
- Grid/rails/drag/keyboard are shared infrastructure
- `sidebar.css` is the shared layout organism
- `sidebar-tags.css` is Quotes-specific content styling
- Each future tab gets its own `sidebar-{context}.css` organism and its own sidebar components
