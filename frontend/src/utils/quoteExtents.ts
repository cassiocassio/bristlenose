/**
 * Which of a transcript paragraph's drawn words belong to which quote.
 *
 * The server keeps no word range for a quote (the persisted anchor is future
 * work: docs/design-transcript-editing.md, "The keystone"). What it sends is
 * the quote's `verbatim_excerpt` and, per paragraph, the ids of the quotes that
 * overlap it in time. This matches the excerpt's words against the words the
 * page draws (`drawnTokens`), across consecutive paragraphs, ignoring case and
 * punctuation. Measured 17 Oct 2026 on 918 quotes in 10 projects: 76% located
 * (exact substring, the server's own test, found 69%), 68 of them spanning
 * paragraphs (docs/design-transcript-gutter.md, "The data").
 *
 * Where to look: the server's `quote_ids` list a paragraph only when it *starts* inside the
 * quote's time, so the paragraph a quote begins in, mid-paragraph, is missing from it (93 of
 * 10,022 local quotes; 214 matched no paragraph at all). So the words are looked for in every
 * paragraph that overlaps the quote in time, as well as those. Whoever the paragraph is
 * attributed to: diarisation puts a participant's words under the moderator's code often enough
 * (a 97-second quote in one QA project, 17 Oct 2026), and an exact match of the excerpt's word
 * sequence does not turn up under another speaker by chance.
 *
 * The model often tidies an excerpt a little (an "uh" dropped, a repeat removed), so when the
 * whole sequence is not there, the quote is anchored on its first and last few words and runs
 * between them, if that span is within half to twice the excerpt's length. Measured on the same
 * 918 quotes: exact 711, anchored 175 more, 32 (3.5%) left unlocated.
 *
 * A quote it cannot locate is its paragraphs' remaining words — the server's paragraphs, as its
 * whole-paragraph fallback is today, else the overlapping ones — and is reported as `approximate`.
 */

import { drawnTokens } from "./paragraphEdits";

export interface ExtentParagraph {
  text: string;
  words?: { text: string; start?: number }[] | null;
  quote_ids: string[];
  inaudible?: boolean;
  speaker_code?: string;
  start_time?: number;
  end_time?: number;
}

/** What the transcript knows of a quote: its words as extracted, its time, who said it. */
export interface ExtentQuote {
  excerpt: string;
  start?: number;
  end?: number;
  participant?: string;
}

export interface QuoteExtents {
  /** Per paragraph (by position), per drawn word: the quote id it belongs to, or null. */
  owners: (string | null)[][];
  /** Quotes whose words could not be located and stand for their paragraphs instead. */
  approximate: Set<string>;
}

/** A word reduced to what matching compares: lower case, letters and digits only. */
export function matchForm(word: string): string {
  return word.toLowerCase().normalize("NFKD").replace(/[^\p{L}\p{N}]+/gu, "");
}

export function quoteExtents(
  paragraphs: ExtentParagraph[],
  quotes: Record<string, ExtentQuote>,
): QuoteExtents {
  const tokens = paragraphs.map((p) => (p.inaudible ? [] : drawnTokens(p.text, p.words)));
  // Each paragraph's words reduced once, and their times where Whisper gave them.
  const forms = tokens.map((t) => t.map(matchForm));
  const times = paragraphs.map((p, i) =>
    p.words && p.words.length === tokens[i].length ? p.words.map((w) => w.start) : null);
  const owners: (string | null)[][] = tokens.map((t) => t.map(() => null));
  const approximate = new Set<string>();

  // Each quote's paragraphs, in reading order, as the server matched them by time…
  const serverParagraphs = new Map<string, number[]>();
  paragraphs.forEach((p, i) => {
    for (const q of p.quote_ids) {
      const list = serverParagraphs.get(q);
      if (list) list.push(i);
      else serverParagraphs.set(q, [i]);
    }
  });
  // …and where to look for its words: those, and every paragraph overlapping its time.
  const searchIn = new Map<string, number[]>();
  for (const [quoteId, q] of Object.entries(quotes)) {
    const set = new Set(serverParagraphs.get(quoteId) ?? []);
    if (q.start !== undefined && q.end !== undefined) {
      paragraphs.forEach((p, i) => {
        if (p.start_time !== undefined && p.end_time !== undefined
            && p.start_time <= q.end! && p.end_time >= q.start!) set.add(i);
      });
    }
    if (set.size > 0) searchIn.set(quoteId, [...set].sort((a, b) => a - b));
  }

  const unlocated: string[] = [];
  for (const [quoteId, paras] of searchIn) {
    const q = quotes[quoteId];
    const wanted = (q?.excerpt ?? "").split(/\s+/).map(matchForm).filter(Boolean);
    // First the quote's own speaker's paragraphs, so a moderator's "mm-hm" in the middle of it
    // does not break the run; then every overlapping paragraph, for words filed under someone else.
    const own = q?.participant ? paras.filter((i) => paragraphs[i].speaker_code === q.participant) : paras;
    const tries = own.length > 0 && own.length < paras.length ? [own, paras] : [paras];
    let claimed = false;
    for (const tryParas of tries) {
      // The words of those paragraphs as one run, skipping words that reduce to nothing (a dash,
      // an ellipsis), each remembering where it is drawn and, if timed, when it was said.
      const run: { form: string; para: number; word: number; t?: number }[] = [];
      for (const i of tryParas) {
        forms[i].forEach((form, j) => {
          if (form) run.push({ form, para: i, word: j, t: times[i]?.[j] });
        });
      }
      const spans = locateAll(run.map((r) => r.form), wanted);
      if (spans.length === 0) continue;
      // Of every place the words occur, the first whose words no other quote has taken and, where
      // the words are timed, that was said within the quote's own time: two quotes with the same
      // words ("yes, I love it") land on their own occurrences (review, 17 Oct 2026).
      const free = ([a, b]: [number, number]) =>
        run.slice(a, b + 1).some((r) => owners[r.para][r.word] === null);
      const inTime = ([a]: [number, number]) =>
        run[a].t === undefined || q?.start === undefined || q.end === undefined
          || (run[a].t! >= q.start - 2 && run[a].t! <= q.end + 2);
      const span = spans.find((sp) => free(sp) && inTime(sp)) ?? spans.find(free);
      if (!span) continue;
      // Claim from the first matched word to the last, so punctuation drawn as its own word
      // inside the quote belongs to it. A word another quote claimed first stays its.
      const first = run[span[0]], last = run[span[1]];
      let took = 0;
      for (const i of tryParas) {
        if (i < first.para || i > last.para) continue;
        const from = i === first.para ? first.word : 0;
        const to = i === last.para ? last.word : tokens[i].length - 1;
        for (let j = from; j <= to; j++) {
          if (owners[i][j] === null) {
            owners[i][j] = quoteId;
            took += 1;
          }
        }
      }
      claimed = took > 0;
      break;
    }
    if (!claimed) unlocated.push(quoteId);
  }
  // An unlocated quote is whatever its paragraphs have left over: the server's, else its own
  // speaker's that truly overlap it — never a neighbour that only touches its time, which is often
  // the moderator's question just before it.
  for (const quoteId of unlocated) {
    approximate.add(quoteId);
    const q = quotes[quoteId];
    const fallback = serverParagraphs.get(quoteId) ?? paragraphs.flatMap((p, i) =>
      q?.start !== undefined && q.end !== undefined && p.speaker_code === q.participant
        && p.start_time !== undefined && p.end_time !== undefined && p.start_time < q.end && p.end_time > q.start
        ? [i] : []);
    for (const i of fallback) {
      for (let j = 0; j < owners[i].length; j++) owners[i][j] ??= quoteId;
    }
  }
  return { owners, approximate };
}

/** Every place `wanted` runs in `forms`, as [first, last] indices: each occurrence of the whole
 *  sequence; failing any, each place its first ANCHOR words occur with its last ANCHOR words after
 *  them, the nearest such that the span is half to twice the excerpt's length. */
const ANCHOR = 4;
function locateAll(forms: string[], wanted: string[]): [number, number][] {
  if (wanted.length === 0) return [];
  const exact: [number, number][] = [];
  for (let k = findRun(forms, wanted, 0); k >= 0; k = findRun(forms, wanted, k + 1)) {
    exact.push([k, k + wanted.length - 1]);
  }
  if (exact.length > 0 || wanted.length <= ANCHOR) return exact;
  const head = wanted.slice(0, ANCHOR), tail = wanted.slice(-ANCHOR);
  const anchored: [number, number][] = [];
  for (let a = findRun(forms, head, 0); a >= 0; a = findRun(forms, head, a + 1)) {
    const from = a + Math.max(ANCHOR, Math.ceil(wanted.length / 2)) - ANCHOR;
    const to = Math.min(forms.length - ANCHOR, a + wanted.length * 2 - ANCHOR);
    for (let b = from; b <= to; b++) {
      if (tail.every((w, m) => forms[b + m] === w)) {
        anchored.push([a, b + ANCHOR - 1]);
        break;
      }
    }
  }
  return anchored;
}

function findRun(haystack: string[], needle: string[], from: number): number {
  outer: for (let k = from; k + needle.length <= haystack.length; k++) {
    for (let m = 0; m < needle.length; m++) if (haystack[k + m] !== needle[m]) continue outer;
    return k;
  }
  return -1;
}
