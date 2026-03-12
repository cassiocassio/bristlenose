# Sidebar Layout & Responsive Playground — Design & Implementation Notes

**Status:** Implemented on `responsive-playground` branch, pending merge.
**Date:** 10 Mar 2026

---

## Problem

The Quotes tab needs dual sidebars — a table of contents (TOC) for section/theme navigation, and a tag filter for codebook-based filtering — without permanently consuming content width. Researchers with 14" laptops shouldn't lose half their viewport to chrome; researchers with 27" displays should be able to pin both sidebars and still read comfortably.

Separately, the dev team needs an interactive tuning environment for responsive layout tokens (quote grid width, spacing, type scale) that doesn't require editing CSS files and refreshing. The values are CSS custom properties — live adjustment with visual feedback is the fastest way to find the right defaults.

## Design principles

1. **Chrome-level layout is orthogonal to content-level layout.** The sidebar grid (`sidebar.css`) controls where TOC/tags/minimap sit relative to the content column. The responsive quote grid (`responsive-grid.css`) controls how quote cards flow within that column. They're independent — each can be enabled/disabled without affecting the other.

2. **Three distinct TOC states.** Closed (icon rail only) → overlay (hover peek, floats above content) → push (committed, grid column expands, content narrows). Overlay is ephemeral — the user hasn't committed to it. Push is intentional.

3. **Sidebar state persists; overlay never persists.** `localStorage` stores toc-open, tags-open, widths. Overlay mode is not persisted — reloading always starts with the TOC closed. This prevents the page loading with a half-visible flyout.

4. **Dev-only playground is zero-cost in production.** Code-split via `React.lazy()` in `AppLayout.tsx` — only loaded when `--dev` flag is set. State in `sessionStorage` (not `localStorage`) — resets on tab close. No CSS tokens are emitted until the user moves a slider.

5. **CSS custom properties are the single source of truth.** Every tuneable value is a `--bn-*` token in `tokens.css`. The playground injects overrides via a `<style>` element on `:root`. Remove the style element and everything reverts to the token defaults.

---

## Architecture: 6-column CSS grid

### Column layout

```
[toc-rail | toc-sidebar | center | tag-sidebar | tag-rail | minimap]
   col 1       col 2       col 3     col 4        col 5     col 6
```

The grid is defined in `bristlenose/theme/organisms/sidebar.css`. The `SidebarLayout` React component (`frontend/src/components/SidebarLayout.tsx`) wraps the Quotes tab content in a `.layout` div and renders all six columns.

### Grid template by state

| State | Col 1 (toc rail) | Col 2 (toc sidebar) | Col 3 (center) | Col 4 (tag sidebar) | Col 5 (tag rail) | Col 6 (minimap) |
|-------|-----------------|--------------------|-----------|--------------------|-----------------|----------------|
| **Closed** | `--bn-rail-width` | `0` | `1fr` | `0` | `--bn-rail-width` | `--bn-minimap-width` |
| **TOC push** | `0` | `--toc-width` | `1fr` | `0` | `--bn-rail-width` | `--bn-minimap-width` |
| **Tags open** | `--bn-rail-width` | `0` | `1fr` | `--tags-width` | `0` | `--bn-minimap-width` |
| **Both open** | `0` | `--toc-width` | `1fr` | `--tags-width` | `0` | `--bn-minimap-width` |
| **TOC overlay** | `--bn-rail-width` | `0` | `1fr` | ... | ... | ... |

In overlay mode, column 2 stays at `0` — the TOC sidebar uses `position: fixed` to float above the content. The grid doesn't change.

### CSS tokens

| Token | Default | Purpose |
|-------|---------|---------|
| `--bn-rail-width` | `36px` | Collapsed icon rail width |
| `--bn-sidebar-width` | `280px` | Default sidebar panel width |
| `--bn-sidebar-min` | `200px` | Minimum resize bound |
| `--bn-sidebar-max` | `480px` | Maximum resize bound |
| `--bn-minimap-width` | `3rem` | Right-edge minimap column |
| `--bn-overlay-shadow` | `4px 0 16px rgba(0,0,0,0.08)` | TOC overlay drop shadow |
| `--bn-overlay-duration` | `0.3s` | Overlay animation speed (currently unused — animations use explicit 300ms values per-element) |
| `--bn-gutter-left` | `2rem` | Gap between rail/sidebar and center content |
| `--bn-gutter-right` | `2.5rem` | Gap between content and minimap/tag rail |
| `--bn-quote-max-width` | `23rem` | Card reading measure (~5 words/line) |
| `--bn-grid-gap` | `1.25rem` | Gap between grid columns |

---

## TOC overlay behaviour

The TOC has three modes, managed by `SidebarStore.ts` as `TocMode: "closed" | "overlay" | "push"`.

### Hover intent (`useTocOverlay.ts`)

| Event | Behaviour |
|-------|-----------|
| Mouse enters rail | Starts 400ms timer → opens overlay |
| Mouse enters rail button (`.rail-btn`) | **Cancels** timer (safe zone — user is aiming to click) |
| Mouse leaves rail button | Restarts timer (mouse is still in rail area) |
| Click rail area | Opens overlay immediately |
| Click rail button | Opens **push** mode (bypasses overlay) |

### Direction-aware close

| Exit direction | Behaviour |
|----------------|-----------|
| Mouse moves **right** (into content area) | Closes overlay (after 100ms grace period) |
| Mouse moves **left** (off-screen) | Ignored — accidental |
| Mouse moves **up/down** (vertical exit) | Ignored — accidental |

Detection: `onPanelMouseLeave` checks `e.clientX >= panel.getBoundingClientRect().right`. Vertical exits have `clientX` within panel bounds → `clientX < right` → not a rightward exit → ignored.

### Overlay animation (clip-path reveal)

The rail is the panel's left edge. `clip-path: inset()` reveals the panel rightward from the rail border — content is visible from frame 1, shadow reveals progressively with the clip.

**Open timeline (300ms):**
- 0–150ms: Rail icon fades out + shifts left (departs)
- 0–300ms: Panel clip-path reveals from rail edge
- 150–300ms: Close × fades in at left of header (where rail icon was)

**Close timeline (300ms):**
- 0–150ms: Close × fades out
- 0–300ms: Panel clip-path hides toward rail
- 150–300ms: Rail icon fades back in

Close × is repositioned to the left of the header via `order: -1` in overlay mode, so it sits in the same spatial position as the rail list icon — enabling the cross-fade illusion.

`SidebarLayout.tsx` orchestrates: add `.toc-closing` → wait for `animationend` (400ms fallback) → remove class → update store (`closeToc()`). `closingRef` prevents overlapping close animations.

**A/B playground toggle:** The dev playground has a "Curtain / iOS inertia" toggle. Curtain (default) reveals content stationary behind the clip. iOS variant adds `translateX(-20px→0)` on the content body with a 40ms delay, creating a "settling into place" inertia effect inspired by iOS navigation transitions. The `.overlay-ios` class is added to `.layout` when the iOS variant is active.

**TOC link click:** In overlay mode, clicking a link starts `scrollIntoView({ behavior: "smooth" })`, then closes the panel after 400ms — the user sees the scroll begin before the panel slides shut, confirming their intent was actioned.

---

## Drag-to-resize (`useDragResize.ts`)

Pointer-event state machine. During drag, CSS custom properties update directly on the layout element (no React re-render) for 60fps. Store actions fire only on `pointerup` to persist the final width.

### Handle instances

| Handle | Position | When visible | Behaviour |
|--------|----------|-------------|-----------|
| `.toc-drag-handle` | Right edge of col 2 | Push mode **or** overlay mode | Resize TOC sidebar |
| `.tag-drag-handle` | Left edge of col 4 | Tag sidebar open | Resize tag sidebar |
| `.tag-rail-drag` | Left edge of col 5 | Tag sidebar **closed** | Drag-to-open from collapsed |

### Constraints

- Width clamped: 200px → 320px (JS constants `MIN_WIDTH`, `MAX_WIDTH`)
- **Snap-close:** dragging below 80px triggers automatic close with grid animation
- **Rail threshold:** drag-to-open from rail requires >20px movement before opening
- `body.dragging` class disables text selection and forces `col-resize` cursor globally

---

## Minimap (`Minimap.tsx`, `minimap.css`)

Column 6 renders an abstract representation of the page structure — VS Code style scrollbar minimap.

- Section/theme headings: darker, wider lines (`--bn-minimap-heading`)
- Individual quotes: pale 2px lines (`--bn-minimap-quote`)
- Viewport indicator: translucent blue rectangle showing current scroll position (`--bn-minimap-viewport-bg`)
- Click/drag on minimap scrolls the page proportionally
- `position: sticky; top: 0; align-self: start` for correct sticky range in the grid cell
- Hidden at `≤600px` viewport width

---

## Responsive quote grid (`responsive-grid.css`)

Content-level responsiveness, independent of the sidebar system.

```css
.quote-group {
    display: grid;
    grid-template-columns: repeat(
        auto-fill,
        minmax(min(var(--bn-quote-max-width), 100%), 1fr)
    );
    gap: var(--bn-grid-gap);
    align-items: start;
}
```

Columns appear automatically as the viewport widens. Modular — remove the file from `_THEME_FILES` to revert to single-column.

| Display | CSS px width | Columns at 23rem |
|---------|-------------|-----------------|
| Skinny window | ~500px | 1 |
| MacBook Air 13" | 1470px | 3 |
| MacBook Pro 16" | 1728px | 4 |
| iMac 24" | 2240px | 5 |
| Pro Display XDR 32" | 3008px | 7 |

---

## Responsive Playground (dev-only)

### Components

| Component | File | Purpose |
|-----------|------|---------|
| `ResponsivePlayground` | `frontend/src/components/ResponsivePlayground.tsx` | Bottom drawer with drag-to-resize top edge |
| `PlaygroundHUD` | `frontend/src/components/PlaygroundHUD.tsx` | Top HUD bar — viewport width, device match, breakpoint segments |
| `PlaygroundFab` | `frontend/src/components/PlaygroundFab.tsx` | Floating ◆ button (bottom-right), portal to `document.body` |
| `PlaygroundStore` | `frontend/src/contexts/PlaygroundStore.ts` | Module-level store (`useSyncExternalStore`), `sessionStorage` |
| `TypeScalePreview` | `frontend/src/components/TypeScalePreview.tsx` | Interactive type scale table with computed sizes |
| `playground.css` | `frontend/src/components/playground.css` | All playground CSS (540 lines) |

### Activation

| Trigger | Action |
|---------|--------|
| `Ctrl+Shift+P` | Toggle playground drawer |
| `Ctrl+Shift+U` | Toggle HUD bar |
| ◆ FAB button | Opens playground (hidden when drawer is open) |

All three paths call `togglePlayground()` / `toggleHUD()` from `PlaygroundStore`. Only loaded in `--dev` serve mode via `React.lazy()` dynamic import in `AppLayout.tsx`.

### Token tuning categories

| Category | Tokens | CSS injection |
|----------|--------|---------------|
| Layout | `--bn-quote-max-width`, `--bn-grid-gap`, `--bn-max-width` | Yes |
| Sidebar layout | `--bn-rail-width`, `--bn-minimap-width`, `--bn-gutter-left`, `--bn-gutter-right`, `--bn-overlay-duration` | Yes |
| JS timing | `hoverDelay` (400ms), `leaveGrace` (100ms) | No — passed as props through `SidebarLayout` → `useTocOverlay` |
| Type scale | `html` font-size, heading sizes (computed from ratio), `body` line-height | Yes |
| Spacing/radius | All `--bn-space-*` and `--bn-radius-*` scaled by multiplier | Yes |
| Visual aids | Grid overlay, baseline grid, dark mode | Body class / `data-theme` attribute |

CSS overrides injected via `<style id="bn-playground-overrides">` on `:root`. Setting a value to `null` removes that override (falls back to token default). "Revert All" resets every override.

### Device presets & breakpoint sets

- `devicePresets.ts`: 15 devices (iPhone SE → Pro Display XDR) with CSS width, category, retina metadata
- `typeScalePresets.ts`: 7 named type scales (Minor Second 1.067 → Golden Ratio 1.618)
- Breakpoint sets: Tailwind, Bootstrap, Material, Custom — visualised as coloured segments in the HUD bar

---

## File map

### New files (this branch)

| File | Purpose |
|------|---------|
| `bristlenose/theme/organisms/responsive-grid.css` | CSS-only responsive quote grid |
| `bristlenose/theme/organisms/minimap.css` | Minimap component styles |
| `frontend/src/components/ResponsivePlayground.tsx` | Dev playground drawer (522 lines) |
| `frontend/src/components/PlaygroundHUD.tsx` | Top HUD bar (146 lines) |
| `frontend/src/components/PlaygroundFab.tsx` | Floating quick-open button |
| `frontend/src/components/TypeScalePreview.tsx` | Type scale table |
| `frontend/src/components/Minimap.tsx` | Scroll minimap component |
| `frontend/src/components/playground.css` | All playground CSS (540 lines) |
| `frontend/src/contexts/PlaygroundStore.ts` | Playground state + CSS injection (477 lines) |
| `frontend/src/hooks/useTocOverlay.ts` | Hover intent + direction-aware leave |
| `frontend/src/data/devicePresets.ts` | Device width/category data |
| `frontend/src/data/typeScalePresets.ts` | Named type scale ratios |

### Modified files

| File | Changes |
|------|---------|
| `bristlenose/theme/tokens.css` | 12 new layout/sidebar/minimap tokens |
| `bristlenose/theme/organisms/sidebar.css` | 6-column grid, 4 state variants, overlay/closing CSS, drag handles, gutters, sticky fix |
| `frontend/src/components/SidebarLayout.tsx` | Full rewrite: overlay animation, safe zone, drag handles in push+overlay, playground store wiring |
| `frontend/src/components/TocSidebar.tsx` | Scroll-spy nav with section/theme headings |
| `frontend/src/contexts/SidebarStore.ts` | `TocMode` tri-state replacing boolean, overlay/push/closed, localStorage persistence |
| `frontend/src/hooks/useDragResize.ts` | Sidebar + rail source modes, snap-close animation |
| `frontend/src/hooks/useKeyboardShortcuts.ts` | `[`/`]`/`\`/`⌘.` sidebar shortcuts; `Ctrl+Shift+P/U` playground |
| `frontend/src/layouts/AppLayout.tsx` | Lazy-load `ResponsivePlayground` + `PlaygroundHUD` in dev mode |

---

## Testing

### Automated (934 Vitest + 1856 pytest)

| Test file | Count | Coverage |
|-----------|-------|----------|
| `PlaygroundStore.test.ts` | 29 | CSS injection, persistence, reset, sidebar layout tokens |
| `PlaygroundFab.test.tsx` | 5 | Visibility, click, a11y label |
| `SidebarLayout.test.tsx` | 17 | Grid classes, drag handle rendering per mode, inline styles |
| `SidebarStore.test.ts` | 43 | Tri-state mode, overlay/push persistence, width storage |
| `useTocOverlay.test.ts` | 17 | Safe zone, direction-aware leave, timer lifecycle |
| `useDragResize.test.ts` | 21 | Sidebar/rail modes, snap-close, width clamping |
| `Minimap.test.tsx` | 11 | Data fetching, rendering, click-to-scroll |
| `devicePresets.test.ts` | 9 | Data integrity, category coverage |

### Manual QA checklist

- [ ] Hover TOC rail → overlay slides in (~0.3s) → grab right edge → resize → width persists
- [ ] Drag overlay narrow → snap-close at <80px
- [ ] Click list button → push mode → content narrows, rail hides
- [ ] `[` and `]` keyboard shortcuts toggle sidebars on Quotes tab only
- [ ] Mouse out overlay left/up/down → stays open; mouse right into content → closes
- [ ] Scroll to bottom of long content → rail icons stay pinned at top
- [ ] Tag sidebar content flush to right edge, × button has small margin
- [ ] 2rem left gutter, ~2.5rem right gutter visible between rails and content
- [ ] ◆ FAB button: click opens playground, disappears when drawer is open
- [ ] `Ctrl+Shift+P`: toggles playground drawer
- [ ] Playground sliders update CSS in real time; "Revert All" clears all overrides
- [ ] HUD bar shows viewport width, device match, breakpoint segment bar
- [ ] Resize window → quote columns add/remove automatically
- [ ] Close playground → reopen → slider positions restored from sessionStorage
- [ ] Close tab → reopen → playground state is gone (sessionStorage, not localStorage)

---

## Gotchas

- **Module-level stores persist across tests.** Always call `resetSidebarStore()` / `resetPlaygroundStore()` in `beforeEach`. The `SidebarStore.test.ts` incident (localStorage pollution across tests) is the canonical example.
- **`hoverDelay` and `leaveGrace` are JS-only values**, not CSS custom properties. They're passed as optional props through `SidebarLayout` → `useTocOverlay`. The playground store holds them but doesn't emit CSS for them.
- **Overlay mode `position: fixed` changes the containing block** for absolutely-positioned children (like drag handles). `right: -3px` on `.toc-drag-handle` resolves relative to the fixed panel, not the viewport. This is correct — the handle sits on the panel's right edge.
- **Overlay z-index stack:** panel at 110, drag handle at 121, modals at 150+. The drag handle must beat the panel so it's grabbable above the overlay shadow.
- **`align-self: start` on sticky columns** is required for correct sticky range. Without it, `stretch` (the grid default) makes the cell height equal the row height, leaving zero sticky travel.
- **Animated close uses `animationend`** — both open and close use `@keyframes` animations (clip-path reveal/hide). The 400ms fallback timeout catches cases where `animationend` doesn't fire (e.g., element removed mid-animation).
- **Escape key closes TOC instantly** (no animation) — keyboard users expect immediate response. Only mouse-initiated closes (hover leave, click outside) use the animated path.
