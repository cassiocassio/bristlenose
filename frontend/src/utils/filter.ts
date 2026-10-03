/**
 * filterQuotes — pure function for filtering quotes by search, view mode, and tags.
 *
 * Used by QuoteSections and QuoteThemes inside useMemo to filter their
 * data arrays before rendering. Replaces the vanilla JS DOM manipulation
 * pattern (style.display = 'none' on blockquotes).
 */

import { isActiveQuery, parseQuery, type SearchTerm } from "./searchMatch";
import { quoteMatches } from "./searchSuggest";
import { tokenHighlightTerms, tokenMatches, type SearchToken } from "./searchTokens";
import type { QuoteResponse, TagResponse } from "./types";

export interface TagFilterState {
  /** Tag names that are unchecked (hidden). */
  unchecked: string[];
  /** Whether the "(No tags)" row is unchecked. */
  noTagsUnchecked: boolean;
  /** Whether "Clear" was used (all tags unchecked). */
  clearAll: boolean;
}

export const EMPTY_TAG_FILTER: TagFilterState = {
  unchecked: [],
  noTagsUnchecked: false,
  clearAll: false,
};

export interface FilterState {
  searchQuery: string;
  /** Person and tag tokens in the search field, AND-ed with the text. */
  searchTokens: SearchToken[];
  viewMode: "all" | "starred";
  tagFilter: TagFilterState;
  /** Store maps for current state (hidden, starred, tags). */
  hidden: Record<string, boolean>;
  starred: Record<string, boolean>;
  tags: Record<string, TagResponse[]>;
  /** Text edits (QuotesStore.edits): search reads what the card shows. */
  edits: Record<string, string>;
}

/**
 * Returns true if the quote should be visible given the current filter state.
 *
 * Filter order (short-circuit):
 * 1. Hidden quotes are always excluded
 * 2. View mode: "starred" only shows starred quotes
 * 3. Tag filter: check quote tags against unchecked set
 * 4. Search query: every typed word must start a word in the quote text,
 *    speaker name, tag names or sentiment (docs/design-search.md §3; active
 *    from 2 characters)
 * 5. Search tokens: every person and tag token must let the quote through
 *    under its current meaning (docs/design-search.md §5)
 */
export function isQuoteVisible(q: QuoteResponse, f: FilterState): boolean {
  // 1. Hidden quotes are always excluded
  if (f.hidden[q.dom_id]) return false;

  // 2. View mode filter
  if (f.viewMode === "starred" && !f.starred[q.dom_id]) return false;

  // 3. Tag filter
  if (!passesTagFilter(q, f)) return false;

  // 4. Search filter
  const terms = activeTerms(f.searchQuery);
  if (terms && !quoteMatches(q, terms, f.tags, f.edits)) return false;

  // 5. Search tokens
  for (const token of f.searchTokens) if (!tokenMatches(q, token, f.tags, f.edits)) return false;

  return true;
}

/**
 * Filter an array of quotes. Convenience wrapper around isQuoteVisible.
 */
export function filterQuotes(quotes: QuoteResponse[], f: FilterState): QuoteResponse[] {
  return quotes.filter((q) => isQuoteVisible(q, f));
}

// ── Tag filter ────────────────────────────────────────────────────────────

function passesTagFilter(q: QuoteResponse, f: FilterState): boolean {
  const { tagFilter } = f;

  // No filter active — all pass
  if (!tagFilter.clearAll && tagFilter.unchecked.length === 0 && !tagFilter.noTagsUnchecked) {
    return true;
  }

  // "Clear all" — nothing is checked, hide everything
  if (tagFilter.clearAll) return false;

  // Get the quote's current tags (store overrides server data)
  const quoteTags = f.tags[q.dom_id] ?? q.tags;

  // Quote has no user tags
  if (quoteTags.length === 0) {
    return !tagFilter.noTagsUnchecked;
  }

  // Quote has tags — visible if at least one tag is not in the unchecked set
  const uncheckedLower = new Set(tagFilter.unchecked.map((t) => t.toLowerCase()));
  return quoteTags.some((t) => !uncheckedLower.has(t.name.toLowerCase()));
}

// ── Search ────────────────────────────────────────────────────────────────

// isQuoteVisible runs once per quote with the same query, so parse it once.
let lastQuery: string | null = null;
let lastTerms: SearchTerm[] | null = null;

/** The parsed query, or null while it is too short to filter by. */
function activeTerms(query: string): SearchTerm[] | null {
  if (query !== lastQuery) {
    lastQuery = query;
    lastTerms = isActiveQuery(query) ? parseQuery(query) : null;
  }
  return lastTerms;
}

// ── Highlighting ─────────────────────────────────────────────────────────

// One array per filter state, so every card gets the same reference.
const highlightCache = new WeakMap<FilterState, SearchTerm[]>();

/**
 * What to mark in quote text: the typed words, plus the names a "mentions"
 * token found and the tag name a "text contains" token found.
 */
export function highlightTermsOf(f: FilterState): SearchTerm[] {
  let terms = highlightCache.get(f);
  if (!terms) {
    terms = [...(activeTerms(f.searchQuery) ?? []), ...f.searchTokens.flatMap(tokenHighlightTerms)];
    highlightCache.set(f, terms);
  }
  return terms;
}
