# Fix: Tag Sidebar Counts Are Inflated (2× or more)

## Problem

The tag sidebar shows inflated counts. For example, with 54 quotes on the page, "frustration" shows 42 when only 7 quotes actually have that tag. All counts are roughly doubled (or worse).

## Root Cause: Quote Duplication in `store.quotes`

Both `QuoteSections.tsx` (line 33–41) and `QuoteThemes.tsx` (line 32–40) independently fetch `/api/quotes` on mount. The API returns a single response containing **both** `sections` and `themes`. Each island extracts ALL quotes from the response:

```typescript
const allQuotes = [
  ...json.sections.flatMap((s) => s.quotes),
  ...json.themes.flatMap((t) => t.quotes),
];
initFromQuotes(allQuotes, replace);  // replace defaults to false
```

`initFromQuotes` in `QuotesContext.tsx` (line 106–139) merges when `replace=false`:

```typescript
const mergedQuotes = replace ? [...quotes] : [...base.quotes, ...quotes];
```

**Timeline on page load:**
1. QuoteSections mounts → fetches → `initFromQuotes([all 54], false)` → store has 54
2. QuoteThemes mounts → fetches → `initFromQuotes([all 54], false)` → store has 108
3. TagSidebar iterates 108 quotes → every tag counted twice

The comment at line 99 says "quotes are exclusive — a dom_id appears in sections OR themes, never both" — this is true at the rendering level, but both islands extract ALL quotes (sections + themes) from the same API response, so every quote enters the store twice.

On `bn:tags-changed` events (line 73 in both files), `fetchQuotes(true)` is called with `replace=true`, which atomically replaces. But the **initial mount** uses `replace=false`, causing accumulation.

## Tag Count Computation

`TagSidebar.tsx` line 222–233 iterates `store.quotes`:

```typescript
for (const q of store.quotes) {
  if (store.hidden[q.dom_id]) continue;
  const tags = store.tags[q.dom_id] ?? q.tags;
  for (const t of tags) {
    counts[lower] = (counts[lower] || 0) + 1;
  }
}
```

Since store.quotes has duplicates, each tag is counted once per duplicate entry.

## Why It Could Be Worse Than 2×

If React StrictMode double-fires effects, or if component remounting occurs (e.g. due to route transitions), `initFromQuotes(allQuotes, false)` could be called 3+ times before any `replace=true` call clears it. The inflation factor = number of times `initFromQuotes(false)` runs before steady state.

## Fix Options

### Option A: Deduplicate in `initFromQuotes` (safest, minimal change)
Add dedup logic based on `dom_id`:
```typescript
const mergedQuotes = replace ? [...quotes] : [...base.quotes, ...quotes];
// Deduplicate by dom_id (last wins)
const seen = new Set<string>();
const deduped = [];
for (let i = mergedQuotes.length - 1; i >= 0; i--) {
  if (!seen.has(mergedQuotes[i].dom_id)) {
    seen.add(mergedQuotes[i].dom_id);
    deduped.unshift(mergedQuotes[i]);
  }
}
```

### Option B: Each island only extracts its own quotes (correct separation)
QuoteSections should only pass section quotes; QuoteThemes only theme quotes:
```typescript
// QuoteSections.tsx
const sectionQuotes = json.sections.flatMap((s) => s.quotes);
initFromQuotes(sectionQuotes, replace);

// QuoteThemes.tsx
const themeQuotes = json.themes.flatMap((t) => t.quotes);
initFromQuotes(themeQuotes, replace);
```
This matches the comment's intent ("quotes are exclusive"). But introduces an ordering dependency — whichever island mounts first populates only half the store.

### Option C: Single fetch point (architectural fix)
Move the `/api/quotes` fetch to the parent page (QuotesTab) and pass data down. Both islands render from the same data, store is populated once. This is cleaner but a larger refactor.

### Option D: First caller uses replace=true
Have both islands call `initFromQuotes(allQuotes, true)`. Since the data is identical (same API response), whichever runs second atomically replaces with the same data. No accumulation.

## Recommended Approach

**Option A** — deduplicate in `initFromQuotes`. It's defensive, minimal, and handles any number of callers without coordination. The other options require careful ordering or refactoring.

## Files to Change

| File | What |
|------|------|
| `frontend/src/contexts/QuotesContext.tsx` | `initFromQuotes()` — deduplicate `mergedQuotes` by `dom_id` |
| `frontend/src/components/TagSidebar.tsx` | No change needed (counts become correct automatically) |
| `frontend/src/contexts/QuotesContext.test.ts` | Add test: calling `initFromQuotes` twice with same quotes doesn't double-count |

## Verification

1. `npm test` — existing + new tests pass
2. `npm run build` — type check
3. Manual QA: open quotes page, check tag sidebar counts match actual tagged quotes
4. Check that `bn:tags-changed` re-fetch still works (edit a tag → counts update)

## Additional Observation

The user also noticed that some tag counts (e.g. "error recovery: 4") didn't match visible quotes (only 1 visible) even accounting for duplication. This could be:
- The tag filter was active ("1 tags" shown in toolbar) hiding some quotes
- Some quotes are in collapsed/hidden sections
- The "All quotes" filter vs starred-only

The duplication bug is the primary issue; once fixed, verify these edge cases too.
