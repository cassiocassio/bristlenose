---
status: partial
last-trued: 2026-09-20
trued-against: HEAD@main on 2026-09-20 (835cde98)
---

> **Truing status:** Partial — still shipped and working (trued 2026-09-20), but the
> row gained a **third** click zone since this was written, so §Solution's central
> claim was understating it. §Follow-ups now carries a banner: one item is banned by
> a later decision, and another's stated blocker has cleared.

## Changelog

- _2026-09-20_ — trued up: §Solution said two click targets, there are three (the
  bar+count solos); marked the toast-undo follow-up as **banned** by the 19 Aug
  decision that removed undo toasts repo-wide; recorded that the "needs `removeTag`"
  blocker on undo is gone — `removeTag` shipped, so the gap is real but the reason
  is stale; corrected the `TagRow.test.tsx` count 12 → 20; noted that the assign
  flash fires optimistically, not on success, which the autocomplete doc's Stage 4
  asks for the opposite of. Anchors: `frontend/src/components/TagRow.tsx:127-149`,
  `bristlenose/theme/organisms/sidebar-tags.css:219-221`,
  `frontend/src/contexts/QuotesContext.tsx:322`, `docs/design-undo-debt.md:82-86`,
  commit "five toasts and a fuse removed".
- _2026-03-16_ — initial draft, shipped same day.

# Design: Sidebar Tag Click-to-Assign

**Status:** Shipped (Mar 2026)

## Problem

Researchers doing qualitative coding need to apply tags to many quotes quickly. The existing workflow — select quotes, click `+`, type tag name, Enter — requires typing for every tag. When the codebook is visible in the sidebar, clicking a tag name should just assign it.

## Solution

The tag sidebar row has **three** independent click targets:

- **Checkbox** — toggles tag visibility (filter). Always.
- **Badge/tag name** — assigns that tag to all selected quotes. No-op if nothing is selected.
- **Bar + count** — solos the tag ("show only this"), saving and restoring the
  previous filter state. _Added after this doc was written; see
  `frontend/src/components/TagRow.tsx:127-149` and
  `SidebarStore.ts` `enterSoloMode` / `exitSoloMode` / `savedTagFilter`._

No mode switch. All three controls always do their thing, and each has its own
hover affordance so they read as distinct
(`bristlenose/theme/organisms/sidebar-tags.css:219-221`).

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

Both the sidebar badge and the quote card badges flash on **attempted** assignment, not on success — `TagSidebar.tsx:513-519` calls `addTag` then `flashTag`, and `addTag` is fire-and-forget (`QuotesContext.tsx:303-319`). Worth knowing because `docs/design-codebook-autocomplete.md` §Stage 4 specifies the opposite ("fires after successful API response"), and that sub-item is the one part of Stage 4 still unmet. (`badge-accept-flash` CSS animation.) Confirms the click registered without requiring the user to shift gaze.

### Tag provenance

Tags added via sidebar click are `source: "human"` — same as manual `+` adds.

## File map

| File | Role |
|------|------|
| `frontend/src/components/TagRow.tsx` | Separate checkbox + clickable badge, `onAssign`/`assignActive`/`flashing` props |
| `frontend/src/components/TagGroupCard.tsx` | Forwards assign props to TagRow |
| `frontend/src/components/TagSidebar.tsx` | Consumes FocusContext, `handleSidebarAssign`, `findTagInCodebook`, sidebar flash state |
| `bristlenose/theme/organisms/sidebar-tags.css` | `.tag-checkbox-label`, `.badge-assignable` cursor/hover styles |
| `frontend/src/components/TagRow.test.tsx` | 20 `it()` blocks at HEAD (12 when written) |
| `frontend/src/contexts/SidebarStore.ts` | `enterSoloMode` / `exitSoloMode` / `savedTagFilter` — the solo zone |
| `frontend/src/components/MicroBar.tsx` | two-tone tentative bar, consumed at `TagRow.tsx:140-147` |

## UX review findings

| Finding | Severity | Resolution |
|---------|----------|------------|
| Focused-quote silent assignment | Critical | Selection-only — no focus fallback |
| Misclick risk (6px gap) | Critical | Increased to 12px, padded checkbox to 24px |
| No undo | Major | Deferred — ~~needs `removeTag` store action~~. **The blocker is gone** (`removeTag` shipped, `QuotesContext.tsx:322`); the gap is still real, but not for this reason. See §Follow-ups |
| Discoverability (`cursor:copy` alone) | Major | Deferred — tooltip on hover when selection exists |
| Tab order doubling | Minor | Dynamic `tabIndex` |
| Visual differentiation | Minor | Deferred — "+" overlay on badges when selection exists |

## Follow-ups

> **The first item is banned, not pending (20 Sep 2026).** Undo toasts were removed
> repo-wide on 19 Aug 2026 — commit "five toasts and a fuse removed" — in favour of
> plain ⌘Z with no time limit. `docs/design-undo-debt.md:82-86` names *this doc by
> path* as one of three still proposing one. Undo for sidebar assign remains a real
> gap; a toast is not the shape it should take.

- ~~Toast-based undo ("Applied 'Trust' to 3 quotes — Undo")~~ — **banned**, see above
- Tooltip on badge hover when quotes are selected ("Click to tag 3 selected quotes")
- Subtle "+" icon overlay on badges when selection exists
