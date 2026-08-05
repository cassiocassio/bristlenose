---
status: parked
last-trued: 2026-08-05
trued-against: HEAD@main on 2026-08-05
---

# Design: Quote context expansion

> **Parked behind a feature flag, 5 Aug 2026.** Built and tested; the
> affordance is withheld. `featureFlags.quoteContextExpansion` in
> [`frontend/src/utils/featureFlags.ts`](../frontend/src/utils/featureFlags.ts)
> is `false`, so no chevrons render and no context segments appear. This doc
> was written *at* the park — the feature shipped without one — so it is both
> the as-built record and the brief for a revisit.

## What it does

Lets a researcher pull the surrounding transcript into a quote card, one
segment at a time, without leaving the Quotes lens. A quote is an excerpt; the
turn before it and the turn after it are often what make it legible.

## Interaction

1. **Hover** the timecode of any quote card
2. Chevrons (`⌃`, and a rotated `⌃` below) fade in above and below it
3. **Click** the up chevron → one transcript segment is fetched and rendered
   above the quote, inside the same `<blockquote>`, in muted `.context-segment`
   styling. Down chevron does the same below
4. Click again → one more segment each time, unbounded until the transcript
   runs out
5. At the transcript boundary the chevron is `disabled` (30% opacity) —
   detected by a short read, not by asking the server how many segments exist

## Architecture

Expansion is **count state, not content state**. `QuoteGroup` holds a reducer
keyed `${sessionId}:${domId}` carrying `{aboveCount, belowCount,
exhaustedAbove, exhaustedBelow}`; a chevron click only increments a count. A
separate effect reconciles counts against fetched content and fills the gap.
This is what makes repeat clicks idempotent and keeps the fetch out of the
event handler.

Segments come from `useTranscriptCache` — a per-session lazy cache that fetches
the **whole** transcript on first expand, indexes it by `segment_index`, and
deduplicates concurrent fetches through a `pending` map. Two lookup paths:
index-based when `segment_index >= 0`, and a timecode-based fallback
(`getContextByTimecode`) that finds the last segment starting at or before the
quote's `start_timecode` — needed for VTT/SRT and plain-text sources where the
importer couldn't assign indices.

| File | Purpose |
|------|---------|
| `frontend/src/components/ExpandableTimecode.tsx` | Wraps a timecode with the two chevron buttons; `stopPropagation` on click so the parent's video seek doesn't fire |
| `frontend/src/components/ContextSegment.tsx` | One muted transcript line; reuses `.quote-row` flex layout so timecode columns line up with the quote's. Hides the speaker badge when the segment's speaker is the quote's own participant |
| `frontend/src/hooks/useTranscriptCache.ts` | Per-session lazy transcript cache + the two lookup paths |
| `frontend/src/islands/QuoteGroup.tsx` | `expansionReducer`, `contextSegments` state, the reconcile effect, `canExpand` gating |
| `frontend/src/islands/QuoteCard.tsx` | Renders `ExpandableTimecode` and the `contextAbove` / `contextBelow` segment lists |
| `bristlenose/theme/atoms/context-expansion.css` | Chevron positioning + hover reveal, `.context-segment` muted styling |

Tests: `ExpandableTimecode.test.tsx` (11), `ContextSegment.test.tsx` (8), plus
the context describes in `QuoteCard.test.tsx`.

### Notable details worth keeping

- **Hover target without layout shift.** `.timecode-expandable` uses
  `padding-block: 0.75rem` cancelled by an equal negative `margin-block`, so
  the chevrons get a real hit area without moving the timecode.
- **Exhaustion is inferred, not asked.** `mark_exhausted_above/below` fires
  when a fetch returns fewer segments than requested. No extra endpoint, and it
  self-corrects if the transcript grows.
- **The whole transcript is fetched on first expand.** Deliberate — one request
  per session beats one per chevron click, and the transcript is already a
  size the transcript lens loads whole.

## Why it's parked (5 Aug 2026)

Two problems, both structural rather than cosmetic.

**The chevrons don't read as controls.** They're hover-revealed, unlabelled,
`--bn-colour-muted`, and live in the timecode gutter — a column that is
otherwise pure metadata. Nothing about a small mark in the gutter says "this
grows the quote", so the interpretation available to a researcher is closer to
decoration than affordance.

**Expansion is one-way.** There is no collapse. Once context is pulled in it
stays for the life of the page — no chevron reverses it, no keyboard route, no
click-outside. The reducer only ever increments; there is no `collapse_above`
action, and adding one is the small half of the problem. The large half is that
a card which has grown by four segments has no visible marker saying it *is*
expanded, so a researcher scrolling back has no way to tell an expanded quote
from a long one, and therefore no reason to look for an undo.

That combination — hard to find, impossible to reverse — is what makes it
unfinished rather than rough. Finishing it means answering how an expanded card
declares itself, which is a design question about the quote card's resting
state, not a tweak to the chevrons.

**No user-visible state is stranded by the park.** Unlike the moderator-question
pill, expansion was never persisted — no localStorage, no server-side record —
so a flag flip leaves nothing behind and needs no migration.

### Before flipping the flag back on

1. Decide how an expanded card signals that it's expanded. Note the one-ring
   rule from Focus Mode: a marker that reads well on one card is noise on
   twenty, and a lens of expanded cards is the case to design against.
2. Add the collapse path — `collapse_above` / `collapse_below` actions, or a
   single "reset this card" gesture. Decide which, don't ship both.
3. Reconsider the trigger. The gutter chevrons were chosen for zero layout
   shift; if the affordance moves into the card body, that constraint changes.
4. Delete the "parked features" describe in `QuoteCard.test.tsx` that pins the
   flag-off behaviour — it's written to fail the moment the flag flips.

If the revisit concludes the transcript lens already serves this need better,
delete the feature and its flag together rather than leaving the flag as a
monument.
