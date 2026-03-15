# Design: Sidebar Tag Click-to-Assign

**Status:** Shipped (Mar 2026)

## Problem

Researchers doing qualitative coding need to apply tags to many quotes quickly. The existing workflow — select quotes, click `+`, type tag name, Enter — requires typing for every tag. When the codebook is visible in the sidebar, clicking a tag name should just assign it.

## Solution

The tag sidebar row has two independent click targets:

- **Checkbox** — toggles tag visibility (filter). Always.
- **Badge/tag name** — assigns that tag to all selected quotes. No-op if nothing is selected.

No mode switch. Both controls always do their thing.

## Key decisions

### Selection-only (no focused-quote fallback)

Badge click assigns only to explicitly selected quotes (Shift/Cmd+click, `x` key), NOT to the keyboard-focused quote. Reasons:

- A quote is *always* focused (j/k sets it). Accidental badge clicks would silently tag whatever's focused — possibly off-screen.
- The `r` key already covers the `j → r → j → r` rapid single-quote workflow.
- Matches NVivo's pattern: code tree only applies to explicitly highlighted content.
- Easy to loosen later if users ask for it.

### Hit-target safety

Gap between checkbox and badge increased from 6px to 12px. Checkbox area padded to 24px minimum width. Reduces misclick risk when the two controls do very different things.

### Tab order

Badge uses `tabIndex={-1}` by default. Only `tabIndex={0}` when quotes are selected (`assignActive`). Avoids doubling Tab stops (60+ tags) for the common filter-only workflow.

### Flash animation

Both the sidebar badge and the quote card badges flash on successful assignment (`badge-accept-flash` CSS animation). Confirms the click registered without requiring the user to shift gaze.

### Tag provenance

Tags added via sidebar click are `source: "human"` — same as manual `+` adds.

## File map

| File | Role |
|------|------|
| `frontend/src/components/TagRow.tsx` | Separate checkbox + clickable badge, `onAssign`/`assignActive`/`flashing` props |
| `frontend/src/components/TagGroupCard.tsx` | Forwards assign props to TagRow |
| `frontend/src/components/TagSidebar.tsx` | Consumes FocusContext, `handleSidebarAssign`, `findTagInCodebook`, sidebar flash state |
| `bristlenose/theme/organisms/sidebar-tags.css` | `.tag-checkbox-label`, `.badge-assignable` cursor/hover styles |
| `frontend/src/components/TagRow.test.tsx` | 12 tests for assign behaviour |

## UX review findings

| Finding | Severity | Resolution |
|---------|----------|------------|
| Focused-quote silent assignment | Critical | Selection-only — no focus fallback |
| Misclick risk (6px gap) | Critical | Increased to 12px, padded checkbox to 24px |
| No undo | Major | Deferred — needs `removeTag` store action |
| Discoverability (`cursor:copy` alone) | Major | Deferred — tooltip on hover when selection exists |
| Tab order doubling | Minor | Dynamic `tabIndex` |
| Visual differentiation | Minor | Deferred — "+" overlay on badges when selection exists |

## Follow-ups

- Toast-based undo ("Applied 'Trust' to 3 quotes — Undo")
- Tooltip on badge hover when quotes are selected ("Click to tag 3 selected quotes")
- Subtle "+" icon overlay on badges when selection exists
