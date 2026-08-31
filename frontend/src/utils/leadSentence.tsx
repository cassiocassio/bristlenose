/**
 * leadSentence — split a description into its leading claim and the remainder.
 *
 * THE PATTERN. One paragraph, two ranks: a leading sentence in normal ink and
 * the sentences after it in a tint. Nothing is truncated — the whole text is
 * there for anyone who reads it, and a skimmer gets the claim without deciding
 * to skip anything. That is the answer to a description being "good but too
 * long": the length is fine, the *rank* was missing.
 *
 * THE TREATMENT IS COLOUR, NOT WEIGHT — variant A, chosen 31 Aug 2026. This
 * module only decides *where* the break falls; what the two halves look like
 * belongs to `bristlenose/theme/atoms/lead-paragraph.css`, which carries the
 * reasoning and the tokens. To revisit the look, open
 * `docs/mockups/lead-sentence-playground.html`: eight combinations of weight
 * and tint against this exact text, in both palettes and both appearances.
 *
 * WE ALREADY DID THIS ONCE. The analysis signal cards split their elaboration
 * on a literal `||` the model writes into the text, then `<strong>` the part
 * before it. This module is that mechanism, extracted, so the two surfaces
 * cannot drift — and so the next one gets it for free rather than reinventing
 * the split.
 *
 * TWO WAYS TO FIND THE BREAK, and the caller chooses:
 *
 *   - **`||`** — the author placed it. Always wins, because a human (or a
 *     model told to) decided where the claim ends, and no heuristic beats
 *     that. This is what the signal cards pass.
 *   - **first sentence** — `autoSplit`, for prose carrying no marker. Codebook
 *     descriptions are hand-written YAML with no `||` in them, and waiting for
 *     all nine to be re-authored would mean shipping no treatment at all in
 *     the meantime.
 *
 * @module leadSentence
 */

/** The author's explicit break. */
const MARKER = "||";

/**
 * End of the first sentence, or -1.
 *
 * Deliberately conservative. `.` is not a sentence end when it is an
 * abbreviation ("e.g.", "Dr.", "U.S."), a decimal, or an ellipsis — and a
 * split in the wrong place is worse than no split, because it ranks half a
 * clause and reads as a bug rather than as design. So: require the stop to be
 * followed by whitespace and something that opens a sentence, and refuse the
 * common abbreviation shapes before it.
 */
function firstSentenceEnd(text: string): number {
  const ABBREV =
    /(?:\b[A-Z]\.|\be\.g\.|\bi\.e\.|\betc\.|\bvs\.|\bDr\.|\bMr\.|\bMs\.|\bMrs\.|\bSt\.|\bNo\.)$/;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (ch !== "." && ch !== "!" && ch !== "?") continue;
    // An ellipsis is not a sentence end.
    if (text.slice(i, i + 3) === "...") {
      i += 2;
      continue;
    }
    // A decimal point: digit either side.
    if (ch === "." && /\d/.test(text[i - 1] ?? "") && /\d/.test(text[i + 1] ?? "")) continue;
    if (ABBREV.test(text.slice(0, i + 1))) continue;

    const rest = text.slice(i + 1);
    // Must be followed by space then something that starts a sentence. A stop
    // at the very end means the whole text is one sentence — nothing to split.
    if (!/^\s+["'“‘(]?[A-Z0-9]/.test(rest)) continue;
    return i + 1;
  }
  return -1;
}

export interface LeadSplit {
  /** The claim. */
  lead: string;
  /** Everything after it, or "" when there is nothing to recede. */
  rest: string;
}

/**
 * Split text into its leading claim and the remainder.
 *
 * Exported separately from the renderer so the rule is testable without a DOM,
 * and so a caller needing the strings (a tooltip, an export, a plain-text
 * surface) is not forced through JSX.
 */
export function splitLead(text: string, opts: { autoSplit?: boolean } = {}): LeadSplit {
  const marked = text.indexOf(MARKER);
  if (marked !== -1) {
    return {
      lead: text.slice(0, marked).trimEnd(),
      rest: text.slice(marked + MARKER.length).trimStart(),
    };
  }
  if (!opts.autoSplit) return { lead: text, rest: "" };

  const end = firstSentenceEnd(text);
  if (end === -1) return { lead: text, rest: "" };
  return { lead: text.slice(0, end).trimEnd(), rest: text.slice(end).trimStart() };
}

/**
 * Render the split: `<strong>` on the claim, the remainder as a sibling.
 *
 * **A one-rank paragraph gets no markup at all.** With nothing after it there
 * is nothing to rank against, so wrapping the whole text in `<strong>` would
 * announce every word as emphasised to a screen reader in exchange for no
 * visual difference whatsoever — the atom resets `<strong>` to the same weight
 * the paragraph already has.
 *
 * The remainder is a plain text node rather than a wrapping element on
 * purpose: it inherits the paragraph's colour, so the container carries the
 * treatment (`.bn-lead-para`) and this function stays about the split.
 */
export function renderLead(text: string, opts: { autoSplit?: boolean } = {}): React.ReactNode {
  const { lead, rest } = splitLead(text, opts);
  if (!rest) return lead;
  return (
    <>
      <strong>{lead}</strong> {rest}
    </>
  );
}
