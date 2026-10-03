/**
 * highlightText — wraps search matches in <mark> elements.
 *
 * Returns a React fragment of text nodes and <mark className="search-mark">
 * elements. The existing search.css provides .search-mark styling.
 *
 * Marks follow the same rules as the filter (utils/searchMatch.ts): each typed
 * word is marked where it starts a word, a quoted phrase where it appears
 * whole, with case and accents folded. Below the activation length (2
 * characters) the text is returned unchanged, as a string.
 */

import React from "react";
import { isActiveQuery, markRanges, parseQuery, type SearchTerm } from "./searchMatch";

/**
 * Wrap every match of `query` in `text` in a <mark>.
 *
 * @param text   The text to highlight
 * @param query  The search query as typed
 * @returns      React nodes with matches wrapped, or the plain string if none
 */
export function highlightText(text: string, query: string): React.ReactNode {
  return isActiveQuery(query) ? highlightTerms(text, parseQuery(query)) : text;
}

/**
 * Wrap every match of already-parsed `terms` in `text` in a <mark>. The quote
 * cards use this with `highlightTermsOf(filterState)`, which adds what a
 * "mentions" or "text contains" token found to the typed words.
 */
export function highlightTerms(text: string, terms: SearchTerm[]): React.ReactNode {
  if (terms.length === 0) return text;
  const ranges = markRanges(text, terms);
  if (ranges.length === 0) return text;

  const parts: React.ReactNode[] = [];
  let at = 0;
  for (const [start, end] of ranges) {
    if (start > at) parts.push(<React.Fragment key={`t${at}`}>{text.slice(at, start)}</React.Fragment>);
    parts.push(
      <mark key={`m${start}`} className="search-mark">
        {text.slice(start, end)}
      </mark>,
    );
    at = end;
  }
  if (at < text.length) parts.push(<React.Fragment key={`t${at}`}>{text.slice(at)}</React.Fragment>);
  return <>{parts}</>;
}
