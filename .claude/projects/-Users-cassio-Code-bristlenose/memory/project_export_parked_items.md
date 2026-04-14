---
name: Export parked review items
description: Review findings from quotes export plan review (26 Mar 2026) — parked for later, not acted on today
type: project
---

Parked items from usual-suspects review of quotes CSV/XLS export plan:

- **quote_ids parameter type** — plan doesn't specify whether DOM IDs or DB PKs. Needs resolver pattern from `_parse_dom_quote_id` in `routes/data.py`. Resolve during implementation
- **Zero results: 404 vs 200** — plan returns 404, alternative is 200 with empty CSV. Decide during implementation
- **`aria-describedby` for inline hint** — "Paste into Miro, Excel, or Google Sheets" hint needs `aria-describedby` association with Copy Quotes menuitem
- **Use `announce()` for toasts** — use existing `src/utils/announce.ts` for screen reader announcements, don't create parallel path
- **Apple glossary cross-check** — verify "Save as" pattern in de/fr/es at applelocalization.com before shipping translations
- **Product names stay English in `pasteHint`** — flag for translators: Miro, Excel, Google Sheets are brand names, don't translate

**Why:** Lower priority than the security, a11y keyboard, and i18n plural fixes. Can be resolved during implementation or in a follow-up polish pass.

**How to apply:** Check these when implementing the quotes export feature or doing a polish pass on the export dropdown.
