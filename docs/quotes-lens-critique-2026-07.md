# Quotes lens — design critique (UX + information-vis)

_Date: 2026-07-26 · Status: advisory review, no code changes made · Reviewers: two read-only agents (ux-critique + info-vis) run in parallel against `main`._

This is a **critique, not a spec**. It captures findings from a paired review of the Quotes lens (`/report/quotes`) — the view where a researcher reads, stars, tags, hides, and exports extracted quotes. Every finding is grounded in code read at review time and cited by `file:line`. Nothing here has been implemented; acting on any of it is a separate decision.

**Surfaces reviewed:** `frontend/src/pages/QuotesTab.tsx` → `Toolbar` + `QuoteSections` + `QuoteThemes` + `UncategorisedFloor`, all rendering through `frontend/src/islands/QuoteGroup.tsx` → `frontend/src/components/QuoteCard.tsx`; encodings in `bristlenose/theme/tokens.css`, `atoms/badge.css`, `molecules/badge-row.css`, `organisms/blockquote.css`.

---

## Headline: both reviewers independently flagged the same #1 defect

**Sections and Themes are two orthogonal partitions of the same quotes, stacked on one scroll and rendered isovisually — so the same quote reappears under each, and the reader reads recurrence as prevalence.**

- Sections are **exclusive** (quote-exclusivity invariant, `bristlenose/stages/CLAUDE.md`); Themes **overlap**. The same `dom_id` is re-presented under both partitions (`QuoteSections.tsx:49-53` flattens both into one store keyed by `dom_id`).
- Both partitions open with an identical `<h1 class="section-heading">` (`QuoteSections.tsx:212`, `QuoteThemes.tsx:189`) — a Section group and a Theme group are visually indistinguishable, with no "also in…" backlink, no grouping switch, no persistent "where am I" anchor across hundreds of cards.
- Side effects: duplicate `GET /quotes` + triple `getCodebook()` on mount (`QuoteSections.tsx:46,58`, `QuoteThemes.tsx:39,52`, `TagSidebar.tsx:184`); per-group hidden-counts that count shared quotes twice.
- **Direction (IA decision — put to the Boss / formal-IA reviewer before building):** one surface with a "Group by: Sections | Themes" segmented control, reusing the existing All/Starred `ViewSwitcher` primitive, instead of two stacked surfaces. Halves the scroll, kills the double-read, collapses the duplicate fetch, restores orientation.

The UX reviewer reached this from wayfinding/redundancy; the info-vis reviewer from set theory (two different partition _functions_ mapped to identical visual form, so membership type — exclusive vs overlapping — is inexpressible). Independent convergence = highest confidence in the set.

---

## UX critique — ranked

### High
- **H1. Dual grouping / double-read** — as above.
- **H2. Filtering has no feedback loop.** Filtered-to-zero renders two orphan `<h1>`s over a blank page — no "No results", no "clear filters" (the `noResults` string exists at `bristlenose/locales/en/common.json:34` but is wired nowhere in `frontend/src`). An active tag filter (set in `TagSidebar`) leaves _no trace_ in the toolbar; the count label only updates for search ≥3 chars (`Toolbar.tsx:49-54`). The user can't distinguish "too-tight filter" from "empty data" from "broken."
- **H3. Star behaves differently by keyboard vs mouse.** Click-bulk direction = clicked star's own intent (`QuoteGroup.tsx:334-349`, deterministic, with hover preview `.bn-preview-star`). Keyboard `s` = focused-quote heuristic (`useKeyboardShortcuts.ts:110-132`, non-deterministic, no preview). Neither bulk path emits a summary confirmation ("Starred 20 quotes").

### Medium
- **M1. UncategorisedFloor is a read-only dead-end** (`UncategorisedFloor.tsx`) — strands the researcher's own starred/tagged work with no star/hide/tag/re-file, and its ids aren't registered for `j/k` nav (cf. `QuoteSections.tsx:161-168`), so keyboard nav skips it entirely.
- **M2. Bulk mutations thrash the aria-live region** — bulk star/hide/tag loop per-quote `announce()` (`QuotesContext.tsx:252,263,301`); AT users hear one word, no count.
- **M3. Redundant mount waterfall** — two `/quotes` fetches, three `getCodebook()`, two independent loading states popping in separately (falls out of fixing H1).
- **M4. Tab reaches everything except the useful path** — the card has no `tabIndex`, so `Tab` walks every child control across hundreds of cards; the efficient roving `j/k` model is discoverable only via the `?` modal.

### Low / nits
- L1. Bespoke inline CSS in error/loading states (`QuoteSections.tsx:179,190`; `#c00` fallback won't dark-mode-adapt) — `.bn-empty-state` class already exists.
- L2. `ViewSwitcher` is a dropdown for a binary (All/Starred) choice.
- L3. Search silently no-ops under 3 chars (`filter.ts:57`) with no hint.
- Smart-quote inconsistency (`UncategorisedFloor.tsx:40-42` literal vs `QuoteCard.tsx:692-694` escaped); `announce.ts` docstring drift (5s vs `frontend/CLAUDE.md` 1s).

### Genuinely good — keep
Card text/metadata hierarchy + starred-weight renormalisation (`quote-actions.css:3-17`); hide button reveals on keyboard focus not just hover (`toggle.css:38-40`); the hidden-quotes recovery dropdown; `content-visibility:auto` for the long list (`blockquote.css:85-88`).

---

## Information-vis critique — ranked

### High
- **H1. Two partitions rendered isovisually → double-counting** (same defect, encoding angle).
- **H2. Sentiment _valence_ is not encoded on the card, and is cross-lens-inconsistent.** Identity is honest (word label = redundant channel, survives colour-blindness — `QuoteCard.tsx:711-718`, `Badge.tsx:145-153`). But the negative/neutral/positive grouping (`tokens.css:16-37`) is carried by nothing on the card, and hues fight valence (frustration `#ea580c` vs surprise `#d97706` are near-identical oranges of opposite valence). The **Analysis lens encodes valence by position** — positive-on-top (`bristlenose/stages/s12_render/sentiment.py:24,76`) — using the _same_ tokens; that organising channel evaporates in Quotes, where badges sit in tag-insertion order. The two lenses disagree about how the same dimension is structured.
- **H3. Provenance collapses in the badge row.** AI sentiment / human tag / accepted-autocode tag are near-isovisual, distinguished only by text-colour saturation on identical pale pills (`badge.css:35-43` vs `:80-86`). Pending autocode proposals are strongly differentiated (dashed + pulse, `badge.css:156-166`), but on _accept_ they become `variant="user"` (`QuoteGroup.tsx:621-631`) — visually identical to a hand-typed tag, though the model still records `source: autocode` vs `human` ("Not yet surfaced in UX", `frontend/CLAUDE.md`). Collision is exact when the Sentiment framework is imported as codebook tags (`frontend/src/utils/colours.ts:17,30-34`). "The machine guessed frustration" vs "I coded this as a trust breakdown" is epistemically load-bearing and currently invisible.

### Medium
- **M1. The two quantitative cues a qual reader most needs are absent from the group header:** (a) _group size_ — "this finding rests on 3 quotes vs 40" — the primary weight signal, invisible (the header's only counter counts _hidden_ quotes, `QuoteGroup.tsx:825-859`); (b) _participant spread_ — "8 people said X" vs "one person said it 8×" render identically (one `PersonBadge` per quote, no aggregate). Both are honest plain integers ("12 quotes · 5 participants"), not chartjunk, and their absence forces the exact Analysis-lens trip that reading-time design should avoid. (A per-group sentiment sparkline would be borderline — Analysis already owns that distribution; hold the line there.)
- **M2. Tag overplotting** — `.badges` is uncapped `flex-wrap` (`badge-row.css:3-10`); on a heavily-coded quote the badge mass can out-ink the quote text (data-ink inverted), and it lands worst on the most-analysed quotes. No "+N more" collapse.

### Low
- L1. Analytic hues reuse UI-chrome hues (confidence text `#2563eb` ≈ interactive accent `#007aff`, `colors/palette-default.css:16`) — a blue-text badge can read as interactive.
- L2. Anonymisation encoded only by _absence_ of a name (`PersonBadge.tsx:22-26`) — ambiguous; no positive "anonymised" marker.
- L3. Reading-surface data-ink otherwise well controlled (noted the always-drawn idle star + fixed action gutter as minor persistent ink).

---

## Convergence map (both reviewers agree = act with most confidence)

| Theme | UX | Info-vis |
|---|---|---|
| Dual Sections+Themes stacking / double-counting | H1 | H1 |
| Missing per-group counts / participant spread | (implied) | M1 |
| Provenance human-vs-autocode invisible | (data noted) | H3 |
| Tag row weight vs quote text | — | M2 |
| Filter / zero-state feedback | H2 | — |
| Star kbd/mouse divergence | H3 | — |

## If acting later — cleanest two candidates
1. **Sections/Themes IA decision** — put to the Boss (formal-IA reviewer) first; the segmented-grouping option is the obvious direction.
2. **Per-group counts + participant spread** in group headers — honest, low-risk, removes a forced Analysis-lens trip.
