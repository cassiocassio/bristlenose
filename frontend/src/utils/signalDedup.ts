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
 * HISTORY, because this comment described the wrong rule for four days.
 *
 * The rule shipped on 13 Sep DELETED: measured over nine trial projects, 74
 * locations and 106 cards, it hid 21 and was said to cost no evidence, since
 * every quote kept a card pointing at it. That last part was true of the
 * QUOTES and false of the READINGS — 11 of the 19 cards it hid matched no
 * single kept card at all, so it was destroying interpretations while claiming
 * to remove repeats.
 *
 * Since 20 Sep the loser FOLDS instead: it is attached to the winner as an
 * alternate and stays reachable. Two tests fire it — pairwise quote-set
 * Jaccard at FOLD_THRESHOLD, or union coverage — and the Sentiment exemption
 * that the delete rule needed is gone by construction, because nothing is
 * deleted to be exempt from.
 *
 * Decision trail: docs/mockups/signals-sidebar-row-layouts.html §R;
 * docs/design-decisions.md § Near-duplicate cards fold, they do not disappear.
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

/*
 * `isSentimentSignal` lived here until 20 Sep 2026 and is deliberately gone.
 *
 * It gave the Sentiment card a standing exemption from being hidden, because a
 * one-group framework has concentration structurally 1.00 and was handicapped
 * against every codebook card — unguarded, the old rule deleted it in 5 of 74
 * locations. The fold rule below removed the need: nothing is deleted, so there
 * is nothing to be exempt from.
 *
 * It is recorded rather than silently dropped because the function outlived its
 * caller by four days while its comment went on asserting the exemption was
 * live, and the only thing still importing it was its own test — the exact tell
 * CLAUDE.md files under "an exported function whose only remaining callers are
 * tests is usually a contract that has quietly lost its guard".
 *
 * `isFromSentimentLens` below is a different question (which ROUTE served this
 * card) and is alive: AnalysisPage.tsx reads it for `allPids` and `isSentiment`.
 */

/**
 * Did this card come from the /signals/sentiment lens rather than a codebook?
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
/**
 * How much two cards at one location are the same evidence.
 *
 * Pairwise, not union-based. The shipped rule walked a location strongest-first
 * and dropped any card whose quotes were all covered by the cards already
 * kept — which MEASURED over the corpus hid 14 cards, and **11 of the 19 hidden
 * on the as-shipped label set matched no single kept card at all**: they were
 * killed by the *union* of several others. One was sharing a quarter of its
 * quotes with its nearest neighbour. A finding that spans several other
 * findings is arguably the most interesting one at that location, not the
 * least.
 */
function jaccard(a: UnifiedSignal, b: UnifiedSignal): number {
  const A = new Set(a.quotes.map(quoteKey));
  const B = new Set(b.quotes.map(quoteKey));
  if (!A.size || !B.size) return 0;
  let shared = 0;
  for (const k of A) if (B.has(k)) shared += 1;
  return shared / (A.size + B.size - shared);
}

/**
 * Share of quotes two cards must have in common before one folds into the
 * other.
 *
 * The spike read **0.8** off a genuinely empty band at 0.7–0.9 in the corpus —
 * card pairs are either near-disjoint or literally identical, with almost
 * nothing between — and in the abstract that is the better-evidenced number.
 *
 * It is 0.6 because **both pairs raised in review sat at 0.67**, under that
 * cut, and would have stayed as two cards saying the same thing. Measured, 0.6
 * folds 13 cards where 0.8 folds 7. Nothing is lost either way: the loser
 * becomes an alternate reading on the card that beat it.
 */
const FOLD_THRESHOLD = 0.6;

export function dedupeSignals(signals: UnifiedSignal[]): UnifiedSignal[] {
  const byLocation = new Map<string, UnifiedSignal[]>();
  for (const s of signals) {
    const bucket = byLocation.get(s.location);
    if (bucket) bucket.push(s);
    else byLocation.set(s.location, [s]);
  }

  // Folded readings are collected SEPARATELY and attached to copies at the
  // end. Pushing onto the caller's objects would work once and then keep
  // working — `useMemo` is a hint, not a guarantee, and React 18 invokes it
  // twice in StrictMode, so a second pass over the same objects would append
  // every alternate again. A pure function cannot have that bug.
  const kept: UnifiedSignal[] = [];
  const folded = new Map<UnifiedSignal, NonNullable<UnifiedSignal["alternates"]>>();

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

      // TWO tests, and a card failing either folds.
      //
      // The near-twin test is pairwise: it catches a card citing essentially
      // the same evidence as one already kept. The novel-quote test is
      // union-based: it catches a card bringing nothing at all that is not
      // already on screen, even when no single kept card resembles it.
      //
      // They are not interchangeable. Pairwise alone keeps a card whose quotes
      // are split across two stronger ones — nothing new either way. Union
      // alone deletes a card sharing a quarter of its quotes with its nearest
      // neighbour, which MEASURED was 11 of the 19 the shipped rule hid.
      const twin = kept.find(
        (k) => k.location === s.location && jaccard(k, s) >= FOLD_THRESHOLD,
      );
      const bringsNothing = keys.length > 0 && keys.every((k) => covered.has(k));

      if (twin || bringsNothing) {
        // FOLDED, not deleted — the distinction the whole rule turns on. The
        // losing card is usually the same finding in another codebook's
        // language, and that reading exists nowhere else, so it rides along on
        // the card that beat it. Nothing can be lost, which is why the
        // Sentiment card no longer needs a standing exemption: MEASURED, in 9
        // of 9 locations where one sat beside codebook cards they covered
        // 100% of its quotes, so it could survive only by ranking first.
        const winner = twin ?? kept.find((k) => k.location === s.location);
        if (winner) {
          const list = folded.get(winner) ?? [];
          list.push({
            label: s.label ?? s.columnLabel,
            codebookName: s.codebookName,
            signalName: s.signalName ?? null,
            elaboration: s.elaboration ?? null,
          });
          folded.set(winner, list);
          continue;
        }
      }
      kept.push(s);
      for (const k of keys) covered.add(k);
    }
  }

  // Preserve the caller's order — the ranking is theirs to decide, not ours.
  const keptSet = new Set(kept);
  return signals
    .filter((s) => keptSet.has(s))
    .map((s) => (folded.has(s) ? { ...s, alternates: folded.get(s) } : s));
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
