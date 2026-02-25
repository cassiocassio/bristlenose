/**
 * highlightText — wraps search matches in <mark> elements.
 *
 * Returns a React fragment of text nodes and <mark className="search-mark">
 * elements. The existing search.css provides .search-mark styling.
 *
 * If query is empty or < 3 chars, returns the text unchanged (as a string).
 * Matching is case-insensitive. All occurrences are highlighted.
 */

import React from "react";

/**
 * Split text by search query and wrap matches in <mark> elements.
 *
 * @param text   The text to highlight
 * @param query  The search query (minimum 3 chars to activate)
 * @returns      React nodes with matches wrapped, or plain string if no query
 */
export function highlightText(
  text: string,
  query: string,
): React.ReactNode {
  if (query.length < 3) return text;

  // Escape regex special characters in the query
  const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const regex = new RegExp(`(${escaped})`, "gi");
  const parts = text.split(regex);

  if (parts.length === 1) return text; // No match

  return (
    <>
      {parts.map((part, i) =>
        regex.test(part) ? (
          <mark key={i} className="search-mark">
            {part}
          </mark>
        ) : (
          <React.Fragment key={i}>{part}</React.Fragment>
        ),
      )}
    </>
  );
}
