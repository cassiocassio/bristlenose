/**
 * The Quotes lens's grouping rules. The content sidebar uses them to list the
 * groups the quote column draws; `keepsGroup` mirrors the rule the three
 * column islands apply inline.
 *
 * Kept out of the islands on purpose: the sidebar is on first paint, and
 * importing an island module from it would fold that lazy island into the
 * always-loaded chunk (frontend/CLAUDE.md, "one dynamic owner per island").
 */

import type { QuoteResponse } from "./types";

export interface SessionGroup {
  sessionId: string;
  number: number;
  quotes: QuoteResponse[];
}

/** `s12` → 12; anything else sorts last. */
function sessionNumber(sessionId: string): number {
  const n = Number(sessionId.replace(/^s/, ""));
  return Number.isFinite(n) ? n : Number.MAX_SAFE_INTEGER;
}

/**
 * Quotes grouped by session, a quote once (first occurrence wins), sessions in
 * number order and quotes in time order — the order the Sessions grouping
 * draws them in.
 */
export function groupQuotesBySession(quotes: QuoteResponse[]): SessionGroup[] {
  const seen = new Set<string>();
  const bySession = new Map<string, QuoteResponse[]>();
  for (const q of quotes) {
    if (seen.has(q.dom_id)) continue;
    seen.add(q.dom_id);
    const list = bySession.get(q.session_id) ?? [];
    list.push(q);
    bySession.set(q.session_id, list);
  }
  return [...bySession.entries()]
    .map(([sessionId, list]) => ({
      sessionId,
      number: sessionNumber(sessionId),
      quotes: [...list].sort((a, b) => a.start_timecode - b.start_timecode),
    }))
    .sort((a, b) => a.number - b.number || a.sessionId.localeCompare(b.sessionId));
}

/**
 * Whether the column draws a group: it has a quote the filters let through, or
 * a hidden quote (the group stays so its hidden-count badge can bring it back).
 * The same rule `QuoteSections`, `QuoteThemes` and `QuoteSessions` apply inline.
 */
export function keepsGroup(
  quotes: QuoteResponse[],
  visibleIds: ReadonlySet<string>,
  hidden: Record<string, boolean>,
): boolean {
  return quotes.some((q) => visibleIds.has(q.dom_id) || hidden[q.dom_id]);
}

/** The scroll anchor the column puts on a section or theme heading. */
export function groupAnchor(prefix: "section" | "theme", displayLabel: string): string {
  return `${prefix}-${displayLabel.toLowerCase().replace(/ /g, "-")}`;
}
