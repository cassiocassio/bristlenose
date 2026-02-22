# Tentative Review Workflow — Design Document

## Context

After AutoCode runs and the researcher applies thresholds, tentative proposals (between the lower and upper confidence boundaries) land on quotes as pulsating proposed badges. The researcher is expected to review these individually — accepting good suggestions, denying bad ones — to calibrate trust in the model and clean up the codebook.

**The problem:** There is no structured path through this review. Tentative badges are scattered across quotes in multiple sections. The researcher encounters them incidentally while scrolling, accepts or denies a few, and moves on. There is no way to:
- See how many tentatives remain
- Navigate directly to the next quote with pending proposals
- Work through them systematically with keyboard shortcuts
- Know when you've reviewed "enough" to trust the rest

This matters because tentative review is the researcher's quality gate — it's how they decide whether to trust the model's judgment. Skipping through it undermines the entire AutoCode value proposition.

## User journey

**Persona:** Anna, UX researcher, 280 quotes tagged with Garrett's UX framework (22 tags). AutoCode proposed 180 tags. She set thresholds at 0.35/0.70 — 90 accepted, 50 excluded, 40 tentative.

1. Anna closes the threshold review modal. The codebook panel shows "40 pending" on the AutoCode button
2. She scrolls through the quotes page. Pulsating badges catch her eye. She hovers on one, sees ✓/✗, accepts it. Then another. She's done 3 out of 40
3. She wonders: "How many are left? Where are the rest? Can I just go through these quickly?"
4. She wants a "next pending" shortcut to jump between quotes that have proposed tags, review each one, and move on — without hunting through 280 quotes

**Goal state:** Anna can review all 40 tentatives in ~5 minutes by navigating through them systematically, accepting or denying each with a single keystroke.

## Design

### Two review contexts

Tentative review can happen in two places. Both should be supported:

| Context | Strengths | Weaknesses |
|---------|-----------|------------|
| **Quotes page** (inline) | Full quote context, surrounding quotes visible, existing j/k nav | Proposals scattered across sections, no "next pending" filter |
| **Threshold review modal** (table) | All tentatives in one list, grouped by session, compact | Decontextualised quote excerpts, no surrounding context |

The quotes page is the **primary** review context (richer context, better for judgment calls). The modal is the **secondary** context (better for rapid triage of obvious accept/deny decisions).

### Quotes page: "next pending" navigation

**New keybinding:** `n` — jump to next quote with pending proposed tags (wraps around at end).

| Key | Action | Notes |
|-----|--------|-------|
| `n` | Focus next quote with pending proposals | Wraps. If none, no-op |
| `Shift+n` | Focus previous quote with pending proposals | Reverse direction |
| `a` | Accept focused proposed tag | Accepts the first pending proposal on the focused quote |
| `d` | Deny focused proposed tag | Denies the first pending proposal on the focused quote |

**Interaction flow:**
1. Press `n` — focus jumps to the next quote that has at least one `badge-proposed`
2. The proposed badge is highlighted (first pending proposal gets a subtle ring or brightness boost to indicate it's the keyboard target)
3. Press `a` to accept or `d` to deny
4. If the quote had multiple proposed tags, the highlight moves to the next one
5. When all proposals on this quote are resolved, press `n` to jump to the next

**Key choice rationale:**
- `a` for accept: mnemonic, not used by existing shortcuts
- `d` for deny: mnemonic, not used by existing shortcuts
- `n` for next-pending: "next" mnemonic. Not `p` (too close to "previous" in j/k convention). Not `]`/`[` (unfamiliar). `n` is unused in the current keybinding table

**When there are no proposals, `a`/`d`/`n` are no-ops.** No error sound, no toast. The shortcuts are invisible until proposals exist.

### Pending count indicator

A subtle count badge in the toolbar (or near the codebook panel toggle) showing the number of remaining pending proposals across all quotes:

```
  ╭──────────────╮
  │ 37 tentative │   ← disappears when count reaches 0
  ╰──────────────╯
```

**Design:** Same pulsating dashed-border treatment as the proposed badge itself (visual consistency with the threshold review modal's tentative zone counter). Placed in the sticky toolbar, right-aligned. Clicking it is equivalent to pressing `n` (jumps to next pending).

**Progressive delight:** When the count drops to 0, a brief "All reviewed" message appears and fades. The indicator disappears. The researcher knows they're done.

### Threshold review modal: keyboard navigation

The modal's ProposalZoneList (especially the tentative zone, which is expanded by default) should support keyboard navigation:

| Key | Action | Notes |
|-----|--------|-------|
| `j` / `↓` | Focus next proposal row | Within the expanded zone list |
| `k` / `↑` | Focus previous proposal row | Within the expanded zone list |
| `a` / `Enter` | Accept focused row | Same API call as clicking Accept button |
| `d` / `Backspace` | Deny focused row | Same API call as clicking Deny button |
| `Tab` | Move between zones | Standard focus management |

**Focus within the modal:** When the tentative zone is open and the user presses j/k, focus moves between rows. The focused row gets the same shadow-lift treatment used on the quotes page (`.bn-focused`). Accept/deny on a focused row removes it with the existing fade-out animation and auto-advances focus to the next row.

### Keybinding summary (extending `design-keyboard-navigation.md`)

New shortcuts to add to the "Actions on Focused Quote" table:

| Key | Action | Context | Notes |
|-----|--------|---------|-------|
| `n` | Focus next quote with pending proposals | Quotes page | Wraps at end |
| `Shift+n` | Focus previous quote with pending proposals | Quotes page | Reverse |
| `a` | Accept first pending proposal on focused quote | Quotes page + modal | No-op if no proposals |
| `d` | Deny first pending proposal on focused quote | Quotes page + modal | No-op if no proposals |

### What "first pending proposal" means

When a quote has multiple proposed tags, `a`/`d` acts on the **leftmost** (first in DOM order) proposal. After acting, the next proposal becomes the target. This creates a natural left-to-right sweep. Visual feedback: the target proposal gets a brief brightness boost or ring to indicate it will receive the next `a`/`d` keystroke.

## Edge cases

| Case | Behaviour |
|------|-----------|
| `n` with no pending proposals anywhere | No-op. Focus stays where it is |
| `a`/`d` with no focused quote | No-op |
| `a`/`d` with focused quote but no proposals on it | No-op |
| Last proposal on last quote denied | Count indicator shows "All reviewed", `n` becomes no-op |
| Filtering active (search, tag filter) | `n` only navigates to visible quotes with proposals. Hidden quotes are skipped |
| Multiple proposed tags on one quote, user presses `n` | `n` always moves to the *next quote* with proposals, not the next tag on the current quote. Use `a`/`d` to cycle through tags on the current quote |
| Modal keyboard nav with collapsed zone | j/k only navigates within expanded zones. Pressing j/k with all zones collapsed is a no-op |

## Discoverability

Researchers won't know about `n`/`a`/`d` unless told:

1. **Help overlay (`?`):** Add a "Proposals" section to the keyboard shortcuts help overlay
2. **Pending count tooltip:** Hovering the toolbar count badge shows "Press n to review next (a to accept, d to deny)"
3. **First-time nudge:** When the threshold review modal closes and tentatives exist, show a one-time toast: "40 tentative tags on your quotes — press **n** to review them. **a** to accept, **d** to deny." Shown once per project via localStorage flag

## Open questions

1. **Should `n` auto-open the codebook panel?** If the panel is closed, the researcher can still see proposed badges on quotes. But having the codebook visible gives context about which framework the proposal belongs to. Recommendation: don't auto-open — it's opinionated and the researcher may have closed it deliberately.

2. **Should resolved proposals count toward "reviewed" even if done via the modal?** Yes — the count badge should reflect all pending proposals regardless of where they were resolved. The count comes from the same API data (pending proposals across all quotes).

3. **Should the toolbar count badge be per-framework?** When multiple frameworks have been autocoded, showing "37 tentative" is ambiguous. Options: (a) show total across all frameworks, (b) show per-framework with framework name, (c) show total with breakdown on hover. Recommendation: start with total (simpler), add breakdown on hover later if researchers find it confusing.

## Implementation notes

### Quotes page (`n`/`a`/`d`)

- **Finding quotes with proposals:** Query `[data-testid^="bn-quote-"]` elements that contain `.badge-proposed` children. This is a DOM query, not an API call — proposals are already rendered
- **"Next" navigation:** Same pattern as j/k in `focus.js` — maintain a filtered list of quote IDs with proposals, track position, scroll into view on focus change
- **Accept/deny dispatch:** Call the same `onProposedAccept`/`onProposedDeny` callbacks that the Badge component uses. In React islands, this means the keyboard handler needs access to the QuoteGroup's state — likely via a custom event or a shared context

### Modal keyboard nav

- **ProposalZoneList.tsx:** Add `onKeyDown` handler to the list container, track `focusedRowIndex`, apply `.bn-focused` class to the active row
- **Auto-advance:** After accept/deny removes a row, focus moves to the row that takes its position (same index, or last row if at end)

### Pending count

- **Data source:** The codebook panel already tracks `proposedCount` per framework. Expose this as a toolbar element via the same React state. Or: a lightweight API poll (the proposals endpoint with `status=pending` count-only mode)
- **Toolbar integration:** Add a small React island in the toolbar area, or extend the existing toolbar with a conditional element

## Files to modify

| File | Change |
|------|--------|
| `docs/design-keyboard-navigation.md` | Add `n`, `Shift+n`, `a`, `d` to keybinding tables |
| `frontend/src/islands/QuoteGroup.tsx` | Expose accept/deny callbacks for keyboard events |
| `frontend/src/islands/QuoteCard.tsx` | Visual indicator for "keyboard target" proposed tag |
| `frontend/src/components/ProposalZoneList.tsx` | Add j/k/a/d keyboard navigation within zone lists |
| `frontend/src/components/ThresholdReviewModal.tsx` | Forward keyboard events to active ProposalZoneList |
| `bristlenose/theme/atoms/badge.css` | Focus ring style for keyboard-targeted proposed badge |
| New: toolbar pending count component | Count badge + click-to-navigate |

## Verification

1. `npm run test` — new keyboard handler tests pass
2. `npm run build` — TypeScript compiles clean
3. Manual: start serve mode, run autocode, apply thresholds with tentatives, close modal. Press `n` — focus should jump to first quote with proposals. Press `a` — proposal accepted, flash animation. Press `n` — next quote. Press `d` — denied. Verify count badge decrements. Verify `?` help overlay shows new shortcuts
