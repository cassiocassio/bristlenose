# Quote filtering — design (present + roadmap)

**Status:** Design-forward; captures a growth path, not a build. **Present:** one binary *Starred* filter — a toolbar **star** toggle plus a View-menu radio (*All Quotes* / *✓ Starred Quotes Only*) — alongside the separate search field. **Future (this doc):** when a *second* filter arrives, the star grows into a toolbar **filter popover** and the View items become a **View ▸ Filter ▸** flyout — the macOS Mail / Photos pattern. No code beyond today's single filter.
**Sibling:** [`design-editable-themes.md`](design-editable-themes.md) owns *sort / arrange* — the other half of the same View menu. This doc owns *filter*. They are siblings with deliberately **different chrome** (§5).
**Grounding:** macOS **Photos** (toolbar filter popover + *View ▸ Filter By* flyout) and **Mail** (*View ▸ Filter* flyout). The tick-vs-command idiom was settled in the editable-themes thread: **tick** = a state within a *scanned set*; a **reset** is a plain command; **Show/Hide** is reserved for *standalone, self-evident* toggles.

---

## Why this exists (one paragraph)

Today there is exactly one filter (starred), and a single star toggle is the right weight for it — a Filter menu wrapping one choice is over-structuring. But research triage is inherently filter-heavy (by sentiment, tag, participant, hidden, un-grouped…), so this surface *will* grow. This doc records the growth path now, so the star's evolution is deliberate and matches the native idiom the moment the second filter lands — rather than being reinvented ad hoc under deadline.

## 1. Present state (ships today)

- **Starred filter** — toolbar **star** toggle + View-menu radio: *All Quotes* / *✓ Starred Quotes Only*. The tick shows the active view; it's a pick-one pair.
- **Search** — a separate search field, *not* a member of this filter model (search is its own affordance in Mail/Photos too).
- One binary filter. **Keep it exactly as-is until a second filter exists** (decided).

## 2. The trigger to grow

Promote to the two-surface model in §3 **when a second filter is added** (candidates in §4). Not before — a popover or submenu for a single choice is the over-structuring the sort thread warned against.

## 3. The grown model — two surfaces, one state (macOS)

Mail and Photos both run the *same* filter state on two surfaces, and we mirror that:

- **Toolbar filter icon → popover** — the **discoverable** surface. A funnel glyph that goes active (blue) whenever any filter is on; clicking opens a popover listing the filters. This is where triage happens, so it earns toolbar prominence.
- **View ▸ Filter ▸ flyout** — the **complete / keyboard** surface. Same options, with ⌥⌘-number shortcuts, reachable from the menu bar (house rule: every command reachable from the menu bar).

Both reflect one `filter` state; changing either updates the other — the same "faces of one state" logic as the sort chrome.

### Menu shape (learned from Mail / Photos)

- **Leads with a reset command, no tick** — *All Quotes* (≈ Photos *All Items*, Mail *Disable Message Filter*). Clears all active filters.
- **Then the filters, ticked when active** — grouped under section headers once the set is large (Mail groups *Include:* / *Addressed:* / …; Photos is a flat ticked list).
- **Multi-select where filters compose** (Mail stacks Unread + Flagged + From…); the reset clears all at once.
- **Idiom:** ticks for the filter members (state in a scanned set); the clear is a plain command; **Show/Hide** stays reserved for a standalone self-evident toggle — though in a filter context a hidden-quotes control is more naturally a *filter member* (see §4) than a Show/Hide command.

## 4. Candidate filters for Bristlenose (the set that justifies the grow)

Plausible members, roughly in value order — *which* ship and in *what* order is a separate product call; this doc only fixes the chrome they'll live in:

- **Starred** — today's filter.
- **Hidden** — include/show hidden quotes (`bn-hidden`). Mirrors Photos *Show Hidden*.
- **By tag / codebook** — quotes carrying a given tag (the desktop tag-dropdown removed in 0.16.1, reborn as a proper filter). May nest to pick the tag.
- **By sentiment** — positive / negative / mixed.
- **By participant / session** — one person's quotes.
- **Not in a theme or section** — the Uncategorised floor as a filter (mirrors Photos *Not in an Album*).
- **Strong reactions** — high-intensity only (the `intensity` field).
- **Edited / touched** — quotes the researcher has changed (mirrors Photos *Edited*).

## 5. Sort vs Filter — why they earn different chrome

Apple draws the line by **frequency**, and so do we:

| | Nature | Home |
|---|---|---|
| **Sort** | set-once state | **View menu** (+ block-header caption). *Not* the toolbar. Owned by [`design-editable-themes.md`](design-editable-themes.md). |
| **Filter** | frequent, exploratory (flipped constantly during triage) | **toolbar popover** (+ *View ▸ Filter* flyout). Owned by this doc. |

Same reasoning, opposite verdict — which is why sort stays out of the toolbar while filter eventually earns the prominent popover.

## 6. Cross-surface (web / serve)

The browser build has no menu bar, so the filter renders as an **in-content toolbar control** (a filter button/popover in the Quotes toolbar) — the "shared taxonomy, render native per surface" fork used elsewhere. Popover *content* is identical; only the host differs. Today's web equivalent is the starred toggle already in the Quotes toolbar.

## 7. Non-goals / notes

- **Search stays separate** — a search field, never a filter-menu member (matches Mail/Photos).
- This doc fixes **chrome and idiom**, not which filters ship or how they compute.
- **Export mode:** filters are view-state; in the read-only offline export they follow the same `isExportMode()` treatment as other view controls where persistence would otherwise be implied.
- **Membership vs. filter:** "Not in a theme/section" reads the same underlying data as the Uncategorised floor, but as a *filter over all quotes* rather than a *rendered bucket*; keep them consistent, don't double-count.

## Appendix — Apple references

- **Photos** — toolbar filter popover (*All Items* + ticked *Favourites / Edited / Photos / Videos / Screenshots / Not in an Album*) and *View ▸ Filter By ▸* flyout with ⌥⌘-number shortcuts.
- **Mail** — *View ▸ Filter ▸* flyout: *Disable Message Filter* (reset) then grouped ticked filters (*Include: Unread ✓ / Flagged*, *Addressed: To/Cc Me*, *Only Mail with Attachments*, *Only from VIP*).
