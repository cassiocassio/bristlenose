# Minimap — Design & Architecture

VS Code-style abstract overview of the Quotes tab. A narrow vertical strip showing the full page structure at a glance, with scroll tracking, click-to-scroll, drag-to-scroll, and parallax scrolling for long pages.

## Purpose

Researchers scanning a long quotes report need two things: (1) a sense of where they are in the document, and (2) a way to jump to a distant section without slow-scrolling or hunting the TOC. The minimap provides both. It shows the *shape* of the content — how many quotes are in each section, where the sections/themes division falls — as an abstract representation, like VS Code's code minimap.

## Architecture

### Grid position

The minimap occupies **column 6** of the SidebarLayout 6-column grid:

```
[toc-rail | toc-sidebar | center | tag-sidebar | tag-rail | minimap]
```

Width: `--bn-minimap-width: 3rem` (48px at default font size). After the 8px scrollbar-clearance margin, the effective content width is 40px.

### Data flow

The `Minimap` component fetches `/api/projects/{id}/quotes` independently — it doesn't wait for the main content to render. This means the minimap appears promptly even if the quote grid is still loading. It re-fetches on `bn:tags-changed` events (fired after autocode tag mutations).

### Visual hierarchy

```
.bn-minimap-group-heading   3px tall, 3px side margin    "Sections" / "Themes"
.bn-minimap-heading          2px tall, 4px side margin    section or theme heading
.bn-minimap-quote            2px tall, 6px side margin    individual quote
.bn-minimap-division         0px tall, 8px top+bottom     gap between sections and themes
```

Each quote occupies **3 vertical pixels** (2px height + 1px bottom margin). This is a fixed height — quotes are not scaled to their rendered height in the main content. See [Design decisions](#design-decisions) for why.

## Stress-test math

The minimap must work for the longest reasonable study:

| Metric | Value |
|--------|-------|
| Study length | 10 hours of spoken English |
| Speech rate | ~150 words/minute |
| Coverage | 85% usable content |
| Usable words | 76,500 |
| Avg quote length | ~25 words (2 sentences) |
| Extraction rate | 40–60% |
| **Realistic max quotes** | **1,200–1,800** |
| Stress-test upper bound | **2,000 quotes** |

### Pixel budget at 2,000 quotes

- Minimap content height: 2,000 × 3px + headings/divisions ≈ **6,200px**
- 13" MacBook Air (800px viewport): 6,200 ÷ 800 = **7.75× overflow** → heavy parallax
- 16" MacBook Pro (1,024px viewport): 6,200 ÷ 1,024 = **6× overflow** → moderate parallax
- Viewport indicator size: `(800 / 40,000) × 6,200 = 124px` — visible and proportional

The mockup's Large dataset (2,550 quotes) exceeds the realistic maximum. A Vitest smoke test renders 2,000 quote lines and verifies they all appear without error.

## Two scrolling modes

### Simple mode (content fits viewport)

When the minimap content height ≤ viewport height, no parallax is needed. The content stays at `transform: none`. The viewport indicator slides directly within the content:

```
indicatorTop = scrollRatio × (contentHeight − indicatorHeight)
```

### Parallax mode (content overflows viewport)

When content height > viewport height, the minimap content scrolls at a different rate than the document — like VS Code's minimap for long files. The content is shifted upward via `translateY()`:

```
parallaxOffset = scrollRatio × (contentHeight − viewportHeight)
content.style.transform = translateY(−parallaxOffset)
```

The viewport indicator is positioned in content space, then offset by the same parallax to keep it in the visible clip area:

```
indicatorTop = scrollRatio × (contentHeight − indicatorHeight)
viewport.style.top = indicatorTop − parallaxOffset
```

### Key identity: `scrollRatio = pointerY / viewportHeight`

For click-to-scroll and drag-to-scroll in parallax mode, we need to convert a pointer position (in minimap pixel space) to a document scroll position. The naïve approach reads the CSS transform string via regex, but there's an algebraic shortcut.

In parallax mode, the visible portion of the minimap always corresponds exactly to the visible portion of the document (that's what parallax means). So the pointer's position within the viewport height directly gives the scroll ratio:

```
scrollRatio = pointerY / viewportHeight
```

**Derivation:** The pointer is at position `y` in the minimap slot. The visible content starts at `parallaxOffset = scrollRatio × (ch − vh)`. So the content position is `contentY = y + parallaxOffset`. The scroll ratio is `contentY / ch`:

```
scrollRatio = (y + scrollRatio × (ch − vh)) / ch
scrollRatio × ch = y + scrollRatio × ch − scrollRatio × vh
scrollRatio × vh = y
scrollRatio = y / vh  ✓
```

This eliminates CSS transform regex parsing and frame-latency feedback loops during drag operations. Both `handleClick` and `handleViewportPointerDown` in `Minimap.tsx` use this identity.

In simple mode (no parallax), the ratio is `pointerY / contentHeight` — the content is 1:1 with the visible area.

## Interaction patterns

### Scroll sync (document → minimap)

Window `scroll` and `resize` events update the minimap via `requestAnimationFrame` (single RAF, latest-wins). The update function:
1. Computes `scrollRatio = scrollY / maxScroll`
2. Computes `indicatorHeight = max(8, (viewportHeight / scrollHeight) × contentHeight)`
3. Applies parallax transform if needed
4. Positions the viewport indicator

### Click-to-scroll (minimap → document)

Clicking the minimap background (not the viewport indicator) computes a scroll ratio from the click position and smooth-scrolls the document. The click handler skips if `isDraggingRef` is true (prevents click firing after a drag release).

### Drag-to-scroll (viewport indicator → document)

Pointer-down on the viewport indicator starts continuous scrolling. Pointer-move computes the ratio and scrolls instantly (no smooth scroll — needs to track the pointer). Pointer-up cleans up.

The drag captures `contentHeight`, `viewportHeight`, and `scrollHeight` at pointer-down and reuses them for the duration. If the page layout changes during a drag (unlikely), the next interaction will pick up fresh dimensions.

## Scrollbar offset

`.minimap-slot` has `margin-right: 8px` to avoid collision with the macOS auto-hiding scrollbar (~15px wide when visible). This reduces the minimap content box from 48px to 40px. Quote lines (6px side margins) become 28px wide; headings (4px margins) become 32px. Both remain visually distinct.

The viewport indicator (`position: absolute; left: 0; right: 0`) is relative to the slot's content box, so it automatically respects the margin.

## Responsive behaviour

Hidden entirely below 600px viewport width:

```css
@media (max-width: 600px) {
    .minimap-slot { display: none; }
}
```

## Design tokens

Four minimap-specific colour tokens in `tokens.css`, with `light-dark()` switching for dark mode:

| Token | Light | Dark | Usage |
|-------|-------|------|-------|
| `--bn-minimap-quote` | `#e5e7eb` | `#333333` | Quote line |
| `--bn-minimap-heading` | `#b0b5bd` | `#555555` | Section/theme heading line |
| `--bn-minimap-viewport-bg` | `rgba(37, 99, 235, 0.15)` | `rgba(96, 165, 250, 0.2)` | Viewport indicator fill |
| `--bn-minimap-viewport-border` | `rgba(37, 99, 235, 0.3)` | `rgba(96, 165, 250, 0.4)` | Viewport indicator stroke |

Layout token: `--bn-minimap-width: 3rem` (48px).

## File map

| File | Purpose |
|------|---------|
| `frontend/src/components/Minimap.tsx` | React component |
| `frontend/src/components/Minimap.test.tsx` | 11 tests including 2,000-quote smoke test |
| `bristlenose/theme/organisms/minimap.css` | Visual styling — lines, viewport indicator |
| `bristlenose/theme/organisms/sidebar.css` | `.minimap-slot` grid position and sticky behaviour |
| `bristlenose/theme/tokens.css` | 4 colour tokens + width token |
| `docs/mockups/mockup-minimap.html` | Interactive prototype with Small (120), Typical (540), Large (2,550) datasets |

## Design decisions

### Fixed line heights, not proportional

Each quote is 3px in the minimap regardless of its rendered height in the main content. This is the same approach VS Code uses (1px per code line, regardless of wrapping or fold state). Proportional heights would require a ResizeObserver on every quote card, recalculation on resize, and a layout dependency — significant complexity for marginal benefit. The parallax mechanism handles the position mapping correctly; the minimap is an abstract structural map, not a literal scale model.

### Parallax, not clipping

When the minimap content overflows the viewport, it scrolls at a reduced rate (parallax) rather than being clipped or scaled down. This matches VS Code's behaviour and keeps individual lines readable. The alternative (scaling the entire minimap to always fit the viewport) would make lines sub-pixel at large quote counts and defeat the purpose of showing structure.

### Independent data fetch

The minimap fetches quotes data independently from the main content. This avoids prop-drilling or shared state for a component that only needs the quote/section/theme counts, and lets the minimap render without blocking on the quote grid.

### No scroll-to-element anchoring

Click-to-scroll and drag-to-scroll use ratio-based `window.scrollTo()` rather than scrolling to a specific DOM element. This is simpler and doesn't require correlating minimap lines to specific quote DOM IDs.
