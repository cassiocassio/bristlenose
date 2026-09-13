/**
 * One card per set of quotes.
 *
 * Once a card is a (location × tag group), a project with several codebooks
 * installed draws the same quotes several times over — under one ikea section
 * the analysis computes nine cards from seven quotes by two participants, and
 * two of the nine are the *same two quotes* named once in Nielsen's vocabulary
 * and once in Norman's.
 *
 * Attention is the expensive thing. A researcher asked to read the same two
 * quotes under five headings spends it five times for one answer, and the
 * answer they reach the fifth time is the one they reached the first. On a
 * whiteboard you do not duplicate a sticky across five clusters; you put it in
 * the strongest group under the strongest interpretation.
 *
 * Measured over nine trial projects, 74 locations and 106 cards: the rule hides
 * 21 and costs NO evidence, because every quote keeps a card pointing at it.
 * It is purely a multi-codebook effect — every single-codebook project in the
 * corpus already draws exactly one card per location.
 *
 * Decision trail: docs/mockups/signals-sidebar-row-layouts.html §R.
 */
import type { UnifiedSignal } from "./types";

/**
 * A quote's identity across cards.
 *
 * Two cards that cite the same quote cite it with the same session, timecode
 * and participant — there is no quote id on the wire, and this triple is what
 * `quote_dom_id` uses on the server for the same reason.
 */
function quoteKey(q: { sessionId: string; startSeconds: number; pid: string }): string {
  return `${q.sessionId}|${q.startSeconds}|${q.pid}`;
}

/**
 * Is this the Sentiment card?
 *
 * It carries a standing exemption from being hidden. Sentiment is a one-group
 * framework, so its concentration is structurally 1.00 — the leading factor of
 * the composite is mute for it, which handicaps it against every codebook card.
 * Unguarded, the rule deletes the Sentiment card in 5 of 74 locations, once
 * where it was the second-strongest card present. This is an interim guard, not
 * the design: the fix is normalising the score (docs/design-signal-strength.md).
 */
export function isSentimentSignal(s: UnifiedSignal): boolean {
  // Two ways it can arrive: as the sentiment framework's one group (the
  // codebook path, group name "Sentiment"), or from the /analysis/sentiment
  // lens, which sets no codebook name at all. Both are exempt.
  return s.columnLabel === "Sentiment" || s.codebookName === "";
}

/**
 * Did this card come from the /analysis/sentiment lens rather than a codebook?
 *
 * Only that kind carries a sentiment VALUE in `columnLabel` — "frustration",
 * "delight" — which is what the card's sentiment styling and participant
 * denominator are for. The Sentiment GROUP card is a codebook card whose group
 * happens to be named Sentiment; styling it as a sentiment value would look up
 * `badge-Sentiment`, a class that does not exist. The sentiment framework's
 * display name is "Emotional & Cognitive Signals", never "Sentiment", so the
 * codebook name is the reliable discriminator and the group name is not.
 */
export function isFromSentimentLens(s: UnifiedSignal): boolean {
  return s.codebookName === "";
}

/**
 * Keep a card only if it brings a quote no stronger kept card already carries.
 *
 * Ties break on quote count, then group name. Without that tie-break the two
 * 0.214 cards under ikea's busiest section swap places and the location keeps
 * five cards instead of four — a silent difference nobody would look for. The
 * bigger card winning a tie is also the right reading: where two cards are
 * equally strong, the one covering more quotes is the better single invitation.
 *
 * Quotes are location-exclusive (measured: zero quotes appear under both a
 * section and a theme), so per-location and global de-duplication are the same
 * thing; grouping by location is for the ordering, not for correctness.
 */
export function dedupeSignals(signals: UnifiedSignal[]): UnifiedSignal[] {
  const byLocation = new Map<string, UnifiedSignal[]>();
  for (const s of signals) {
    const bucket = byLocation.get(s.location);
    if (bucket) bucket.push(s);
    else byLocation.set(s.location, [s]);
  }

  const kept = new Set<UnifiedSignal>();
  for (const bucket of byLocation.values()) {
    const covered = new Set<string>();
    const ranked = [...bucket].sort(
      (a, b) =>
        b.compositeSignal - a.compositeSignal ||
        b.quotes.length - a.quotes.length ||
        a.columnLabel.localeCompare(b.columnLabel),
    );
    for (const s of ranked) {
      const keys = s.quotes.map(quoteKey);
      const redundant = keys.length > 0 && keys.every((k) => covered.has(k));
      if (redundant && !isSentimentSignal(s)) continue;
      kept.add(s);
      for (const k of keys) covered.add(k);
    }
  }

  // Preserve the caller's order — the ranking is theirs to decide, not ours.
  return signals.filter((s) => kept.has(s));
}

export interface SignalPlace {
  location: string;
  cards: UnifiedSignal[];
}

/**
 * Locations, ordered by their strongest signal; cards in the caller's order.
 *
 * Both the sidebar and the cards column group the same list through here, so
 * they cannot disagree about what exists or where it sits — the navigation is
 * one-to-one with the main content by construction rather than by accident.
 *
 * Sections and themes interleave unlabelled. The words carry the distinction,
 * and the Quotes lens still owns it: a card's location links to
 * `section-<slug>` or `theme-<slug>`, so the cross-link is namespace-aware.
 */
export function groupSignalsByLocation(signals: UnifiedSignal[]): SignalPlace[] {
  const byLocation = new Map<string, UnifiedSignal[]>();
  for (const s of signals) {
    const bucket = byLocation.get(s.location);
    if (bucket) bucket.push(s);
    else byLocation.set(s.location, [s]);
  }
  return [...byLocation.entries()]
    .map(([location, cards]) => ({ location, cards }))
    .sort((a, b) => b.cards[0].compositeSignal - a.cards[0].compositeSignal);
}
