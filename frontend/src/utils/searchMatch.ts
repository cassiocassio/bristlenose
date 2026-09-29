/**
 * searchMatch — the one set of rules for "does this text match what was typed".
 *
 * Every search surface in the SPA goes through here: the quote filter, the
 * highlight marks, and the suggestion recognisers. The rules are pinned by
 * `tests/fixtures/search-match-contract.json` so the Python/SQLite search core,
 * when it lands, can be held to the same answers.
 *
 * The rules (docs/mockups/toolbar-search.html, decided 28 Sep 2026):
 *   - Each typed word matches on its own, in any order, as the START of a word
 *     ("st" finds "Storey" and "Steppe", not "best").
 *   - A term in double quotes matches as an exact phrase (still word-initial).
 *   - Case, accents and width are folded: "Jose" finds "José", "ё" finds "е",
 *     "ＡＢＣ" finds "abc". Curly and straight apostrophes are the same.
 *   - Chinese and Japanese have no spaces, so a term written in those scripts
 *     matches anywhere, not only at a word start.
 *   - A query is active from 2 characters, or 1 Chinese/Japanese character.
 */

// ── Folding ─────────────────────────────────────────────────────────────

const COMBINING = /\p{M}/gu;
const APOSTROPHES = /[‘’ʼ`´]/g;
const WORD_CHAR = /[\p{L}\p{N}]/u;
/** Scripts written without spaces between words. */
const UNSPACED = /[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Thai}]/u;

function foldChar(ch: string): string {
  return ch.toLowerCase().normalize("NFKD").replace(COMBINING, "").replace(APOSTROPHES, "'");
}

/** Folded text plus, for every folded UTF-16 unit, its index in the original. */
export interface Folded {
  text: string;
  /** map[i] = index in the original string of folded unit i; one extra end sentinel. */
  map: number[];
}

const cache = new Map<string, Folded>();
const CACHE_MAX = 20_000;

/**
 * Fold a string for matching, keeping a map back to the original so marks can
 * be drawn on the unfolded text. Whitespace runs collapse to one space.
 */
export function foldWithMap(s: string): Folded {
  const hit = cache.get(s);
  if (hit) return hit;
  let text = "";
  const map: number[] = [];
  let i = 0;
  for (const ch of s) {
    if (/\s/u.test(ch)) {
      if (text.length > 0 && text[text.length - 1] !== " ") {
        text += " ";
        map.push(i);
      }
    } else {
      const f = foldChar(ch);
      for (let k = 0; k < f.length; k++) map.push(i);
      text += f;
    }
    i += ch.length;
  }
  map.push(i);
  if (cache.size >= CACHE_MAX) cache.clear();
  const folded = { text, map };
  cache.set(s, folded);
  return folded;
}

export function fold(s: string): string {
  return foldWithMap(s).text;
}

// ── Query parsing ───────────────────────────────────────────────────────

export interface SearchTerm {
  kind: "word" | "phrase";
  /** Folded text of the term. */
  text: string;
  /** True when the term may match mid-word (unspaced scripts). */
  anywhere: boolean;
}

const OPEN_QUOTES = new Set(['"', "“", "”", "„", "«", "»", "「", "」"]);

/** Split a typed query into word and "quoted phrase" terms. */
export function parseQuery(query: string): SearchTerm[] {
  const terms: SearchTerm[] = [];
  let buf = "";
  let inPhrase = false;
  const flush = (kind: "word" | "phrase") => {
    const text = fold(buf).trim();
    buf = "";
    if (!text) return;
    if (kind === "word") {
      for (const w of text.split(" ")) if (w) terms.push(makeTerm("word", w));
    } else {
      terms.push(makeTerm("phrase", text));
    }
  };
  for (const ch of query) {
    if (OPEN_QUOTES.has(ch)) {
      flush(inPhrase ? "phrase" : "word");
      inPhrase = !inPhrase;
    } else if (!inPhrase && /\s/u.test(ch)) {
      flush("word");
    } else {
      buf += ch;
    }
  }
  flush(inPhrase ? "phrase" : "word");
  return terms;
}

function makeTerm(kind: "word" | "phrase", text: string): SearchTerm {
  return { kind, text, anywhere: UNSPACED.test(text) };
}

/** True once the query is long enough to filter by. */
export function isActiveQuery(query: string): boolean {
  const compact = query.replace(/[\s"“”„«»「」]/gu, "");
  if (UNSPACED.test(compact)) return compact.length >= 1;
  return [...compact].length >= 2;
}

// ── Matching ────────────────────────────────────────────────────────────

function isWordStart(folded: string, at: number): boolean {
  if (at === 0) return true;
  return !WORD_CHAR.test(folded[at - 1]);
}

/** Every folded start index where `term` matches in `folded`. */
function termPositions(folded: string, term: SearchTerm): number[] {
  const out: number[] = [];
  let from = 0;
  for (;;) {
    const at = folded.indexOf(term.text, from);
    if (at < 0) break;
    if (term.anywhere || isWordStart(folded, at)) out.push(at);
    from = at + 1;
  }
  return out;
}

/** True when `term` matches somewhere in `text`. */
export function termMatches(text: string, term: SearchTerm): boolean {
  return termPositions(fold(text), term).length > 0;
}

/**
 * True when every term matches in at least one of `fields` (each term may
 * match a different field: "tom delivery" finds Tom's quote about delivery).
 */
export function matchesAll(fields: string[], terms: SearchTerm[]): boolean {
  return terms.every((term) => fields.some((f) => f && termMatches(f, term)));
}

/** Character ranges [start, end) in the ORIGINAL text to mark, merged and sorted. */
export function markRanges(text: string, terms: SearchTerm[]): Array<[number, number]> {
  const { text: folded, map } = foldWithMap(text);
  const ranges: Array<[number, number]> = [];
  for (const term of terms) {
    for (const at of termPositions(folded, term)) {
      ranges.push([map[at], map[at + term.text.length]]);
    }
  }
  ranges.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const merged: Array<[number, number]> = [];
  for (const r of ranges) {
    const last = merged[merged.length - 1];
    if (last && r[0] <= last[1]) last[1] = Math.max(last[1], r[1]);
    else merged.push([r[0], r[1]]);
  }
  return merged;
}
