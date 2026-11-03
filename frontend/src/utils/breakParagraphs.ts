/**
 * Break long paragraphs: where a long quote is split into blocks for display.
 *
 * The v1 display setting (`docs/design-display-preferences.md` §4). A pure
 * function of the quote's text: nothing is stored, the same text always gives
 * the same blocks, and editing a quote re-places its breaks. A block is a
 * "thought": the caller separates blocks with a half-line gap and lets the
 * lines wrap on their own inside each.
 *
 * The choice is the line-breaking problem Knuth and Plass solved for TeX:
 * pick break sites so each block sits near a target length, with a small cost
 * per break. Candidate sites are a sentence end, a cut (`...`, where the
 * pipeline removed filler) and the point before a conjunction. Dynamic
 * programming over the sites finds the cheapest set.
 *
 * Rules that never bend, because they protect what the speaker said:
 *  - the words are never changed (blocks differ only in where whitespace falls);
 *  - a `...` stays with the phrase it ends, and is never alone on a line;
 *  - a leading `...` stays with the words after it;
 *  - a block never ends on a small word (the, a, of, to, and, ...).
 *
 * English-tuned: the small-word and conjunction lists are English. Other
 * languages get breaks at sentence ends and cuts only, and text with no spaces
 * (CJK) is left whole. The constants are starting points to keep tuning in the
 * line-break lab (`docs/mockups/quotes-display-options.html`), not decisions.
 * Evidence: `docs/research-paragraph-length-benchmark.md`.
 *
 * @module breakParagraphs
 */

/** Words per thought: between a tabloid paragraph (about 28) and a broadsheet's (about 49). */
export const THOUGHT_TARGET_WORDS = 35;

export interface BreakOptions {
  /** Target words per block. Defaults to {@link THOUGHT_TARGET_WORDS}. */
  target?: number;
}

/** A word a block never ends on: it belongs with what follows. */
const SMALL = new Set([
  "the", "a", "an", "of", "to", "in", "on", "at", "for", "with", "and", "but", "or", "so",
  "i", "it", "that", "my", "your", "this", "is", "was", "be", "by", "as", "if", "not", "then",
  "than", "from",
]);

/** A word a break may come before: it opens a new clause. */
const BEFORE = new Set(["but", "because", "so", "and", "which", "though", "although", "whereas"]);

/** Cost of a break, by what it follows: a sentence end is the cheapest. */
const COST_SENTENCE = 0.15;
const COST_CUT = 0.25;
const COST_CONJUNCTION = 0.3;

/** A block over this many targets is penalised hard; one under MIN_WORDS a little. */
const CAP_FACTOR = 1.7;
const CAP_PENALTY = 3;
const MIN_WORDS = 5;
const MIN_PENALTY = 0.8;

const bare = (s: string): string => s.toLowerCase().replace(/[^a-z']/g, "");
const isCut = (t: string): boolean => /\.\.\.$/.test(t);
const isSentenceEnd = (t: string): boolean => /[.?!]["”)\]]?$/.test(t) && !isCut(t);

interface Site {
  /** The break falls after word `i`. */
  i: number;
  cost: number;
}

function sitesOf(w: string[]): Site[] {
  const out: Site[] = [];
  for (let i = 0; i < w.length - 1; i++) {
    const cur = w[i];
    const nxt = w[i + 1];
    if (nxt.startsWith("...")) continue; // a cut stays with the phrase it ends
    if (i === 0 && cur === "...") continue; // a leading cut stays with the words after it
    const cut = isCut(cur);
    const sentence = isSentenceEnd(cur);
    if (SMALL.has(bare(cur)) && !sentence && !cut) continue; // never end a block on a small word
    const cost = sentence
      ? COST_SENTENCE
      : cut
        ? COST_CUT
        : BEFORE.has(bare(nxt))
          ? COST_CONJUNCTION
          : -1;
    if (cost >= 0) out.push({ i, cost });
  }
  return out;
}

/** The cheapest set of breaks (indices of the word each falls after), by dynamic programming. */
function chooseCuts(sites: Site[], n: number, target: number): number[] {
  const pts = [-1, ...sites.map((s) => s.i), n - 1];
  const pen = [0, ...sites.map((s) => s.cost), 0];
  const best: number[] = [0];
  const back: number[] = [0];
  for (let j = 1; j < pts.length; j++) {
    let bestCost = Infinity;
    let bestFrom = 0;
    for (let a = 0; a < j; a++) {
      const len = pts[j] - pts[a];
      const cost =
        ((len - target) / target) ** 2 +
        (len > CAP_FACTOR * target ? CAP_PENALTY : 0) +
        (len < MIN_WORDS ? MIN_PENALTY : 0) +
        (a > 0 ? pen[a] : 0);
      if (best[a] + cost < bestCost) {
        bestCost = best[a] + cost;
        bestFrom = a;
      }
    }
    best[j] = bestCost;
    back[j] = bestFrom;
  }
  const cuts: number[] = [];
  for (let j = pts.length - 1; j > 0; ) {
    const a = back[j];
    if (a > 0) cuts.push(pts[a]);
    j = a;
  }
  return cuts.reverse();
}

/**
 * Split `text` into blocks. Returns `[text]` untouched when it needs no
 * breaks (a short quote, or no usable site), so a caller can render the
 * original string as it is. Otherwise each block is its words joined by single
 * spaces, and the blocks joined by a space equal the text with its whitespace
 * collapsed.
 */
export function breakIntoBlocks(text: string, options: BreakOptions = {}): string[] {
  const target = options.target ?? THOUGHT_TARGET_WORDS;
  const words = text.split(/\s+/).filter(Boolean);
  if (words.length < 2) return [text];
  const cuts = chooseCuts(sitesOf(words), words.length, target);
  if (cuts.length === 0) return [text];
  const blocks: string[] = [];
  let from = 0;
  for (const c of cuts) {
    blocks.push(words.slice(from, c + 1).join(" "));
    from = c + 1;
  }
  blocks.push(words.slice(from).join(" "));
  return blocks;
}
