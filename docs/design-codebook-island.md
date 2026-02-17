# Codebook React Island — Design Decisions

_Audit completed 17 Feb 2026. Decisions agreed before planning session._

## Context

Milestone 5 migrates the Codebook tab from vanilla JS (`codebook.js`, 981 lines) to a React island. The codebook is the researcher's tag taxonomy: named groups of tags, each with a pentadic palette colour, drag-and-drop reordering, inline editing, and merge/delete operations.

Before planning, we audited every UI element in the vanilla codebook against the React component library (14 primitives, 12 files, 136 Vitest tests). The interactive audit page is at `docs/mockups/codebook-audit.html`.

## Decision log

### 1. Badge data attributes — Skip

**`data-badge-type` and `data-tag-name` are not needed in React.**

These attributes are queried by 6 vanilla JS modules (tags.js, tag-filter.js, search.js, csv-export.js, histogram.js, codebook.js) for DOM-based discovery. In serve mode, React islands get data from the API and manage their own state — they don't need vanilla JS to query their DOM. The vanilla modules operate on server-rendered static HTML quotes (which still have the attributes). The two worlds don't overlap on the same DOM nodes.

### 2. Codebook editing — React EditableText (contentEditable)

**Use the React EditableText component instead of the vanilla `<input>` replacement pattern.**

The vanilla codebook swaps the title span for an `<input class="group-title-input">` on click, causing layout shift. React EditableText uses `contentEditable` on the same element — zero layout shift, no font inheritance quirks, select-all on focus. The `trigger="click"` prop matches the current click-to-edit behaviour.

The `.group-title-input` and `.group-subtitle-input` CSS rules can be retired.

### 3. TagInput — No autocomplete, duplicate guard only

**Use React TagInput with autocomplete disabled. Guard against creating duplicate tag names.**

The codebook is tag _admin_ — creating new codes and organising existing ones. It's a different context from the quote page (where users assign existing tags _and_ create new ones, and autocomplete helps). On the codebook page:

- The user is deliberately creating a _new_ tag name, not picking from existing
- Suggesting existing tags would be confusing (those already appear in the grid)
- The only guard needed: reject input that matches an existing tag name (case-insensitive)

The 0.82rem font size carries over via CSS scope (`.codebook-group .tag-input`), matching the upscaled badges. Tags are centre stage in the codebook, deliberately larger than the discrete badges on quote pages.

### 4. MicroBar — New reusable primitive

**Build a `MicroBar` component for horizontal proportional bars. Reuse in codebook and analysis.**

Two existing bar visualisations in the codebase:

| Context | Current implementation | Appearance |
|---------|----------------------|------------|
| Codebook tag frequency | `.tag-micro-bar` — inline width, no track, palette colour, right-only rounding | `━━━━` 12 |
| Analysis concentration | `.conc-bar-track`/`.conc-bar-fill` — percentage of 96px track, muted colour, full rounding | `[████░░░░]` |

A single `MicroBar` primitive serves both:

```tsx
interface MicroBarProps {
  value: number;        // 0–1 fraction
  colour?: string;      // CSS colour/var — defaults to muted
  track?: boolean;      // show background track? (analysis=yes, codebook=no)
  className?: string;
  "data-testid"?: string;
}
```

- **Codebook**: `<MicroBar value={count/max} colour="var(--bn-bar-emo)" />` — no track
- **Analysis**: `<MicroBar value={pct/100} track />` — with track, replaces `conc-bar-track`/`conc-bar-fill` in Metric

Two consumers from day one justifies the primitive.

### 5. Spacing — Round 6px to 8px (`--bn-space-sm`)

Three places in `codebook-panel.css` use `6px` for gap/margin (`.group-header`, `.tag-row`, `.group-total-row`). The design system scale has no 6px token — nearest are 4px (`--bn-space-xs`) and 8px (`--bn-space-sm`).

Round to `var(--bn-space-sm)` (8px). The 2px difference is imperceptible but puts the codebook on-scale with everything else.

### 6. Merge target colour — `color-mix()` with accent token

**Replace hardcoded `rgba(37, 99, 235, 0.06)` with `color-mix(in srgb, var(--bn-colour-accent) 6%, transparent)`.**

The hardcoded value is `#2563eb` (blue-600) at 6% opacity. This matches the light-mode accent (`#2563eb`) but not the dark-mode accent (`#60a5fa`). In dark mode, the highlight is nearly invisible — dark blue on dark background.

The `color-mix()` approach references the token, so it automatically adapts. Same browser support as `light-dark()` (Baseline 2023), which we already require.

The same bug (hardcoded `rgba(37, 99, 235, ...)`) was already fixed in `--bn-glow-colour` and `--bn-focus-ring` with `light-dark()` variants. The merge-target was missed.

### 7. Placeholder border — 1px

**Change `.new-group-placeholder` border from `1.5px dashed` to `1px dashed`.**

1.5px is a sub-pixel value — renders as 2px on 1x screens, 1.5px on retina. Inconsistent across displays. 1px is standard for all other dashed borders in the design system (`.badge-add`, `.tag-add-badge`).

### 8. Modal — React component (contextual, not centred overlay)

**Build a React `ConfirmDialog` component positioned near the affected element.**

_Not_ a centred viewport overlay (vanilla `modal.js`) and _not_ `<dialog>` (forces top-layer rendering). Instead: a small tinted card anchored near the element being acted on (the tag being deleted, the group being removed, the merge target). Interaction model:

- Enter / click primary button = confirm
- Escape = cancel
- No "Cancel" button required (Escape is sufficient, saves space)
- Background tinted to match the group's codebook colour
- Positioned via CSS (absolute, anchored to parent) not JS measurement

This keeps the researcher's eyes on the codebook grid instead of yanking attention to a centred modal. The same component can be reused anywhere that needs lightweight inline confirmation.

### 9. Drag and drop — Native HTML5 drag API

**Use the browser's native HTML5 drag API, matching the current vanilla implementation.**

The codebook has three drag gestures:

| Gesture | Result |
|---------|--------|
| Tag → different group column | Move tag to group |
| Tag → another tag row | Merge tags (with confirmation) |
| Tag → "+ New group" placeholder | Create new group with tag |

The native API handles all three. No library needed.

Why not @dnd-kit: the codebook is a desktop researcher tool, touch drag is not a requirement, and the "drag onto peer = merge" pattern doesn't map cleanly to @dnd-kit's sortable/droppable model. 15KB dependency for 3 gestures in one component.

Why not custom pointer events: building your own drag library (hit testing, scroll-during-drag, pointer capture, cancel gestures) is 200+ lines of careful work that solves already-solved problems.

Performance note: use `useRef` for drag state (not `useState`) so highlight classes are toggled via `classList` rather than re-renders, exactly like the vanilla code does.

### 10. Read-only vs interactive — Interactive from the start

**Ship the codebook with full CRUD mutations in one go.**

The Dashboard was read-only because it's a display surface. The Codebook is fundamentally an editing surface — without mutations (group CRUD, tag drag-drop, merge, inline editing) it's just a static rendering of data the user already has. All the primitives for editing are built (EditableText, TagInput, Toggle, Badge with delete). Shipping read-only first would mean building the same component twice.

## CSS cleanup during migration

| File | Change | Why |
|------|--------|-----|
| `codebook-panel.css` | `padding: 12px` → `var(--bn-space-md)` | Same value, use the token |
| `codebook-panel.css` | `gap: 4px` → `var(--bn-space-xs)` | Same value, use the token |
| `codebook-panel.css` | Three `6px` gaps → `var(--bn-space-sm)` | On-scale (decision #5) |
| `codebook-panel.css` | `.merge-target background` → `color-mix()` | Dark mode fix (decision #6) |
| `codebook-panel.css` | `.new-group-placeholder` border → `1px` | Sub-pixel fix (decision #7) |
| `codebook-panel.css` | Add `.codebook-group .tag-input { font-size: 0.82rem }` | Match upscaled badges |
| `codebook-panel.css` | Remove `.group-title-input` / `.group-subtitle-input` rules | Replaced by EditableText |

## New primitives to build

| Component | Location | Tests | Consumers |
|-----------|----------|-------|-----------|
| **MicroBar** | `frontend/src/components/MicroBar.tsx` | `MicroBar.test.tsx` | Codebook (tag frequency), Analysis (concentration/breadth bars via Metric) |
| **ConfirmDialog** | `frontend/src/components/ConfirmDialog.tsx` | `ConfirmDialog.test.tsx` | Codebook (delete tag, delete group, merge tags), future: histogram, any inline confirmation |
