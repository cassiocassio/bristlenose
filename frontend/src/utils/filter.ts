/**
 * filterQuotes — pure function for filtering quotes by search, view mode, and tags.
 *
 * Used by QuoteSections and QuoteThemes inside useMemo to filter their
 * data arrays before rendering. Replaces the vanilla JS DOM manipulation
 * pattern (style.display = 'none' on blockquotes).
 */

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
  viewMode: "all" | "starred";
  tagFilter: TagFilterState;
  /** Store maps for current state (hidden, starred, tags). */
  hidden: Record<string, boolean>;
  starred: Record<string, boolean>;
  tags: Record<string, TagResponse[]>;
}

/**
 * Returns true if the quote should be visible given the current filter state.
 *
 * Filter order (short-circuit):
 * 1. Hidden quotes are always excluded
 * 2. View mode: "starred" only shows starred quotes
 * 3. Tag filter: check quote tags against unchecked set
 * 4. Search query: match against quote text, speaker name, tag names (min 3 chars)
 */
export function isQuoteVisible(q: QuoteResponse, f: FilterState): boolean {
  // 1. Hidden quotes are always excluded
  if (f.hidden[q.dom_id]) return false;

  // 2. View mode filter
  if (f.viewMode === "starred" && !f.starred[q.dom_id]) return false;

  // 3. Tag filter
  if (!passesTagFilter(q, f)) return false;

  // 4. Search filter (min 3 chars)
  if (f.searchQuery.length >= 3 && !matchesSearch(q, f)) return false;

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

function matchesSearch(q: QuoteResponse, f: FilterState): boolean {
  const query = f.searchQuery.toLowerCase();

  // Check quote text (prefer edited text if available)
  const text = (q.edited_text ?? q.text).toLowerCase();
  if (text.includes(query)) return true;

  // Check speaker name
  if (q.speaker_name.toLowerCase().includes(query)) return true;

  // Check tag names (store overrides)
  const quoteTags = f.tags[q.dom_id] ?? q.tags;
  if (quoteTags.some((t) => t.name.toLowerCase().includes(query))) return true;

  // Check sentiment
  if (q.sentiment && q.sentiment.toLowerCase().includes(query)) return true;

  return false;
}
