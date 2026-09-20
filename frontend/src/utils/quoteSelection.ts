/**
 * Which quotes a card shows, and why those.
 *
 * **Selection and ordering are separable, and that is the whole idea.** The
 * shipped order is `(participant_id, start_seconds)` — alphabetical by
 * participant, then chronological — which makes the lead quote *whatever the
 * lowest-numbered participant said earliest*. That is a byproduct, not a
 * choice, and it caused two visible defects: sibling cards at one location
 * systematically opened with the same quote, and on a 56-quote card the first
 * four said nothing about the whole.
 *
 * The order is also **load-bearing**: `detectSequences` fuses same-participant
 * quotes within 17.5s into a visual run, which needs them adjacent in the
 * array. Re-sorting by strength would scatter them, and worse, could
 * manufacture a false sequence — the check is pid/session/gap and never that
 * the order is chronological.
 *
 * So this module picks WHICH quotes, and the caller keeps the existing sort.
 *
 * MEASURED over the 20 corpus cards where selection matters: cards showing no
 * supporting quote fall 3 → 0, and cards showing a dissenting voice RISE,
 * 13 → 16. Better grounded and more argumentative at once.
 *
 * The reserved slot is deliberate and is not a statistical correction: *"a
 * very strong one in five, said clearly and with feeling, has earned the right
 * to be seen."* A card that only ever agrees with itself is one you stop
 * reading.
 *
 * @module quoteSelection
 */
import type { UnifiedQuote, UnifiedSignal } from "./types";

/** The seven, and their direction. Mirrors `analysis/sentiment_label.py`. */
const VALENCE: Record<string, string> = {
  frustration: "neg",
  confusion: "neg",
  doubt: "neg",
  surprise: "neu",
  satisfaction: "pos",
  delight: "pos",
  confidence: "pos",
};

/**
 * Forcefulness a dissenting quote must reach to take the reserved slot.
 *
 * On a 1–3 scale this is "said with some feeling" — a passing remark does not
 * take it, a clear one does. **Intensity is a proxy for the real criterion,
 * which is clarity AND intensity**, and no clarity signal exists per quote, so
 * this will sometimes surface something loud and muddy over something quiet
 * and sharp. Tracked as a Value/Could item.
 */
const DISSENT_MIN_INTENSITY = 2;

/**
 * Does this quote carry the thing the card's label claims?
 *
 * A codebook card has no sentiment label, so it supports its **pattern**:
 * `success` and `recovery` want quotes satisfying their tag, `gap` wants ones
 * violating it, `tension` is mixed by definition and supports everything.
 * Step 2 of the elaboration prompt already classifies each quote that way, so
 * this needs no new model output.
 */
function supports(q: UnifiedQuote, signal: UnifiedSignal): boolean {
  const kind = signal.labelKind;
  const label = signal.label ?? signal.columnLabel;

  if (kind === "value") return q.tagNames.includes(label);
  if (kind === "valence") {
    const want = label === "Positive" ? "pos" : "neg";
    return q.tagNames.some((t) => VALENCE[t] === want);
  }
  // "mixed" says the card is divided, so nothing is the dissenting voice —
  // and a codebook card with no pattern has nothing to support either.
  return true;
}

/**
 * Up to `cap` quotes: the strongest that carry the finding, plus one held back
 * for the voice that argues with it.
 *
 * Returns them in the caller's order — `(participant, time)` — so the sequence
 * treatment is untouched. `dissenting` names the reserved quote so the card
 * can mark it.
 */
export function selectQuotes(
  signal: UnifiedSignal,
  cap: number,
): { shown: UnifiedQuote[]; dissenting: UnifiedQuote | null } {
  const inOrder = (qs: UnifiedQuote[]) =>
    [...qs].sort((a, b) => a.pid.localeCompare(b.pid) || a.startSeconds - b.startSeconds);

  if (signal.quotes.length <= cap) {
    return { shown: inOrder(signal.quotes), dissenting: null };
  }

  const supporting = signal.quotes.filter((q) => supports(q, signal));
  const others = signal.quotes.filter((q) => !supports(q, signal));

  // Nothing identifiably supports the label — fall back to forcefulness rather
  // than inventing a preference.
  const pool = supporting.length ? supporting : signal.quotes;
  const byForce = (a: UnifiedQuote, b: UnifiedQuote) => b.intensity - a.intensity;

  const ranked = [...pool].sort(byForce);
  const dissenters = [...others].sort(byForce);

  const picked = ranked.slice(0, cap - 1);
  let dissenting: UnifiedQuote | null = null;
  if (dissenters.length && dissenters[0].intensity >= DISSENT_MIN_INTENSITY) {
    dissenting = dissenters[0];
    picked.push(dissenting);
  }
  // Fill any spare slot from the supporting pool rather than leaving it empty.
  const shown = [...picked, ...ranked.slice(cap - 1)].slice(0, cap);
  return { shown: inOrder(shown), dissenting };
}
