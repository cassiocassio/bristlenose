/**
 * searchFuzz — adversarial and property tests for the search engine.
 *
 * Tries to BREAK searchMatch / searchSuggest / searchTokens / filter with
 * synthetic and hostile input. Everything is driven by a fixed-seed PRNG, so a
 * failure reproduces exactly; a failing sweep shrinks its counterexample and
 * prints it with invisible characters escaped.
 *
 * Conventions in this file:
 *   - A property that holds is a plain `it`.
 *   - A property that FAILED because of a real defect was `it.fails`, named
 *     "DEFECT Dn", over the full domain. D1–D9 were fixed on 3 Oct 2026 and
 *     are now plain `it`, named "FIXED Dn", so a regression turns the file red. Next to it, the same property runs
 *     over the domain minus that defect's trigger atoms (and only those), so a
 *     NEW failure of the same property still turns the file red.
 *   - Behaviour the contract (tests/fixtures/search-match-contract.json,
 *     `known_limits`) already accepts is excluded by name, never silently.
 *   - "UNDOCUMENTED LIMIT" marks behaviour that is plausibly intended but is
 *     not in the contract's known limits; it is `it.fails` so a change shows.
 *
 * No Node globals (no @types/node here, and `tsc -b` checks test files).
 */

import { describe, expect, it } from "vitest";
import type { QuotesState } from "../contexts/QuotesContext";
import { filterStateOf } from "../contexts/QuotesContext";
import { EMPTY_TAG_FILTER, filterQuotes, isQuoteVisible, type FilterState } from "./filter";
import {
  asPhrase,
  fold,
  foldKey,
  foldWithMap,
  isActiveQuery,
  markRanges,
  matchesAll,
  parseQuery,
  termMatches,
  wholeWordsTerm,
  type SearchTerm,
} from "./searchMatch";
import { quoteTags, suggest, type SearchPerson, type Suggestion } from "./searchSuggest";
import { syntheticProject } from "./searchSynthetic";
import {
  personToken,
  sameSubject,
  tagToken,
  tokenHighlightTerms,
  tokenMatches,
  type SearchToken,
} from "./searchTokens";
import type { QuoteResponse, TagResponse } from "./types";

// ── Deterministic randomness ─────────────────────────────────────────────

const SEED = 20261003;

/** mulberry32, the same small PRNG searchSynthetic uses. */
class Rng {
  private a: number;
  constructor(seed: number) {
    this.a = seed >>> 0;
  }
  next(): number {
    this.a = (this.a + 0x6d2b79f5) >>> 0;
    let t = this.a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  }
  int(n: number): number {
    return Math.floor(this.next() * n);
  }
  pick<T>(xs: readonly T[]): T {
    return xs[this.int(xs.length)];
  }
  chance(p: number): boolean {
    return this.next() < p;
  }
}

// ── Atoms: the hostile alphabet ──────────────────────────────────────────

const ASCII_WORDS = [
  "delivery", "Delivery", "DELIV", "price", "best", "st", "Storey", "Steppe", "the", "shelf",
  "than", "more", "O'Brien", "they're", "don`t", "e-mail", "foo_bar", "12:04", "p3", "a", "ab", "x",
];
const ASCII_SEPS = [" ", "  ", "\t", "\n", ".", ",", "(", ")", "-", "_", "'", "`", "\u0000", "\u007f", ":", "/"];

/** Double-quote marks the parser treats as phrase delimiters. Trigger for D2. */
const QUOTE_ATOMS = ['"', "“", "”", "„", "«", "»", "「", "」"];

/** Compatibility characters that decompose to an UPPERCASE letter or a typographic apostrophe. Trigger for D1. */
const COMPAT_UPPER_ATOMS = ["™", "℃", "𝐃𝐞𝐥", "ℍ", "㎒", "ŉ"];

/**
 * User-perceived characters spanning several code points that the matcher can
 * end inside: emoji with modifiers/ZWJ/flags/VS16, and a Devanagari conjunct
 * joined by a virama (क\u094Dष), and Hangul written as conjoining jamo (NFD 서울),
 * where one syllable is several code points. Trigger for D8.
 */
const EMOJI_CLUSTER_ATOMS = ["क\u094Dषम\u093E", "\u1109\u1165\u110B\u116E\u11AF", "👍\uD83C\uDFFD", "👩\u200D👩\u200D👧", "🇬🇧", "❤\uFE0F"];

/** U+FEFF: whitespace to the query side, invisible to the text side. Trigger for D6. */
const BOM_ATOMS = ["\uFEFF"];

/** Turkish dotless ı: a contract known limit. */
const DOTLESS_I_ATOMS = ["kırmızı", "ı"];

const BASE_ATOMS = [
  ...ASCII_WORDS,
  ...ASCII_SEPS,
  // regex metacharacters, control characters
  ".*+?^${}()|[]\\", "\u0001", "\u001f",
  // invisibles and Unicode spaces
  "\u00AD", "\u200B", "\uFEFF", "\u200C", "\u200D", "\u2060", "\u200E", "\u200F",
  "\u00A0", "\u2007", "\u202F", "\u3000", "\u0085", "\u2028", "\u1680",
  // accents, NFC and NFD
  "José", "Jose\u0301", "Müller", "Mu\u0308ller", "e\u0301", "\u0301", "\u0301\u0301", "ñ", "Ñ",
  // Turkish, German, Greek, Cyrillic
  "İstanbul", "İ", "Straße", "STRASSE", "ẞ", "ß", "ΟΔΟΣ", "οδός", "ς", "Σ", "Αθήνα", "ΐ",
  "ещё", "Алёна", "й", "и\u0306",
  // CJK, Japanese with voicing marks, half-width kana
  "東京", "我住在東京", "京", "山田", "花子", "パン", "ハ\u309Aン", "ハン", "ｶﾞｲﾄﾞ", "でい", "を",
  // Korean (the conjoining-jamo form is a D8 atom)
  "서울에서", "김민지가", "한",
  // Arabic, Hebrew, Thai, Hindi
  "م\u064Fح\u064Eم\u064E\u0651د", "أحمد", "ـ", "ש\u05B8\u05C1לו\u05B9ם", "ข\u0E48าวด\u0E35", "ข\u0E49าว", "กำ", "क\u093Eम", "ह\u094B",
  // fullwidth, ligatures, spacing accents
  "ＩＫＥＡ", "ａｂｃ", "１２３", "ﬁ", "ﬂ", "ﬀ", "ǅ", "¨", "˜", "¸",
  // emoji that are one code point
  "👍", "🙂", "❤",
  // lone surrogate halves
  "\uD83D", "\uDE00",
];

const ALL_ATOMS = [...BASE_ATOMS, ...QUOTE_ATOMS, ...COMPAT_UPPER_ATOMS, ...EMOJI_CLUSTER_ATOMS, ...DOTLESS_I_ATOMS];
const without = (xs: readonly string[], ...drop: (readonly string[])[]) =>
  xs.filter((a) => !drop.some((d) => d.includes(a)));

function randomString(r: Rng, atoms: readonly string[], maxAtoms = 8): string {
  const n = r.int(maxAtoms + 1);
  let s = "";
  for (let i = 0; i < n; i++) {
    s += r.pick(atoms);
    if (r.chance(0.4)) s += " ";
  }
  return s;
}

// ── Shrinking and reporting ──────────────────────────────────────────────

/** Escape everything outside printable ASCII, so invisibles show in a message. */
function show(s: string): string {
  let out = "";
  for (const ch of s) {
    const cp = ch.codePointAt(0) ?? 0;
    out += cp >= 0x20 && cp < 0x7f && ch !== "\\" ? ch : `\\u{${cp.toString(16)}}`;
  }
  return JSON.stringify(out);
}

/** Greedy delta-debugging over code points, field by field. */
function shrink(fields: string[], fails: (f: string[]) => boolean): string[] {
  const safe = (f: string[]) => {
    try {
      return fails(f);
    } catch {
      return true;
    }
  };
  let cur = fields.slice();
  let progress = true;
  while (progress) {
    progress = false;
    for (let fi = 0; fi < cur.length; fi++) {
      let cps = Array.from(cur[fi]);
      for (let size = Math.max(1, cps.length >> 1); size >= 1; size >>= 1) {
        for (let start = 0; start + size <= cps.length; ) {
          const cand = cps.slice(0, start).concat(cps.slice(start + size));
          const next = cur.slice();
          next[fi] = cand.join("");
          if (safe(next)) {
            cur = next;
            cps = cand;
            progress = true;
          } else start += size;
        }
        if (size === 1) break;
      }
    }
  }
  return cur;
}

/**
 * Run `n` random cases; the property returns null when it holds or a
 * description when it doesn't. On the first failure, shrink and throw.
 */
function sweep(
  label: string,
  n: number,
  seed: number,
  gen: (r: Rng) => string[],
  prop: (f: string[]) => string | null,
): void {
  const r = new Rng(seed);
  for (let i = 0; i < n; i++) {
    const fields = gen(r);
    let why: string | null;
    try {
      why = prop(fields);
    } catch (e) {
      why = `threw ${String(e)}`;
    }
    if (why !== null) {
      const min = shrink(fields, (f) => prop(f) !== null);
      throw new Error(
        `${label}: case ${i} (seed ${seed}) failed: ${why}\n  original: ${fields.map(show).join(", ")}` +
          `\n  shrunk:   ${min.map(show).join(", ")}\n  shrunk says: ${prop(min)}`,
      );
    }
  }
}

const eqRanges = (a: Array<[number, number]>, b: Array<[number, number]>) =>
  a.length === b.length && a.every((x, i) => x[0] === b[i][0] && x[1] === b[i][1]);

const matches = (text: string, query: string) => matchesAll([text], parseQuery(query));

// Intl.Segmenter is ES2022 (lib here is ES2020); typed by hand.
interface GraphemeSegmenter {
  segment(s: string): Iterable<{ index: number }>;
}
const Segmenter = (Intl as unknown as {
  Segmenter: new (l?: string, o?: { granularity: "grapheme" }) => GraphemeSegmenter;
}).Segmenter;
const graphemes = new Segmenter(undefined, { granularity: "grapheme" });
function graphemeBoundaries(s: string): Set<number> {
  const out = new Set<number>([s.length]);
  for (const seg of graphemes.segment(s)) out.add(seg.index);
  return out;
}

// ── 1. Nothing throws ────────────────────────────────────────────────────

const FIXED_HOSTILE = [
  "", " ", "   ", "\t\n", '"', 'a"b', '"""', '""', "“", "「", "''", "’’", "'s", "\u0000",
  "\u0000\u0000\u0000", ".*+?^${}()|[]\\", "\\", "\uD800", "\uDFFF", "\uDFFF\uD800", "\uFEFF",
  "\u200D\u200D", "\u0301", "\u0085\u0085", "ß".repeat(300), "a".repeat(10_000),
  "'".repeat(5_000) + "x", ("delivery " + "\u200B").repeat(1_200), "👍".repeat(3_000),
  "x" + "\u0301".repeat(5_000), "東".repeat(10_000), '"'.repeat(10_001),
];

describe("nothing throws, for any string", () => {
  it("fold, parse, activation, phrase, whole-word and marks survive the hostile set and 3000 random strings", () => {
    const r = new Rng(SEED);
    const inputs = [...FIXED_HOSTILE];
    for (let i = 0; i < 3000; i++) inputs.push(randomString(r, ALL_ATOMS, 12));
    for (const s of inputs) {
      const q = inputs[r.int(inputs.length)];
      expect(() => {
        fold(s);
        foldWithMap(s);
        const terms = parseQuery(q);
        isActiveQuery(s);
        asPhrase(s);
        wholeWordsTerm(s);
        markRanges(s, terms);
        matchesAll([s, "", q], terms);
        for (const t of terms) termMatches(s, t);
        const w = wholeWordsTerm(q);
        if (w) termMatches(s, w);
      }, show(s) + " / " + show(q)).not.toThrow();
    }
  });

  it("suggest, filter and tokens survive a project made of hostile strings", () => {
    const r = new Rng(SEED + 1);
    const quotes: QuoteResponse[] = [];
    const people: Record<string, SearchPerson> = {};
    for (let i = 0; i < 150; i++) {
      const code = r.chance(0.1) ? r.pick(["", "\u0000", "p1", "P1", " p1"]) : `p${r.int(12)}`;
      people[code] = { full_name: randomString(r, ALL_ATOMS, 3), short_name: randomString(r, ALL_ATOMS, 1) };
      const tags = Array.from({ length: r.int(3) }, () => mkTag(randomString(r, ALL_ATOMS, 2)));
      quotes.push(mkQuote(`h${i}`, code, randomString(r, ALL_ATOMS, 2), randomString(r, ALL_ATOMS, 10), tags));
    }
    for (let i = 0; i < 300; i++) {
      const query = i < FIXED_HOSTILE.length ? FIXED_HOSTILE[i] : randomString(r, ALL_ATOMS, 4);
      const q = r.pick(quotes);
      const tokens: SearchToken[] = [
        { ...personToken(q.participant_id, people[q.participant_id], q.speaker_name), mode: r.pick(["said", "mentions", "not"] as const) },
        { ...tagToken({ name: randomString(r, ALL_ATOMS, 2) }), mode: r.pick(["tagged", "contains", "not"] as const) },
      ];
      expect(() => {
        suggest(query, { quotes, people }, { cap: r.int(5), excludeTags: [query], excludeCodes: [query] });
        filterQuotes(quotes, { ...baseFilter(), searchQuery: query, searchTokens: tokens });
        for (const t of tokens) tokenHighlightTerms(t);
      }, show(query)).not.toThrow();
    }
  });
});

// ── 2. markRanges ───────────────────────────────────────────────────────

describe("markRanges", () => {
  const gen = (atoms: readonly string[]) => (r: Rng): string[] => {
    const text = randomString(r, atoms, 10);
    // Half the queries are cut from the text itself, so they actually match.
    const cps = Array.from(text);
    const a = r.int(cps.length + 1);
    const query = r.chance(0.5) ? cps.slice(a, a + 1 + r.int(4)).join("") : randomString(r, atoms, 3);
    return [text, r.chance(0.3) ? `"${query}"` : query];
  };

  it("ranges are in bounds, non-empty, sorted, separated, and never split a surrogate pair", () => {
    sweep("markRanges structure", 4000, SEED + 2, gen(ALL_ATOMS), ([text, query]) => {
      const ranges = markRanges(text, parseQuery(query));
      let prevEnd = -1;
      for (const [s, e] of ranges) {
        if (!(s >= 0 && e <= text.length)) return `out of bounds [${s},${e}) in length ${text.length}`;
        if (!(s < e)) return `empty range [${s},${e})`;
        if (!(s > prevEnd)) return `not sorted/separated: starts at ${s} after ${prevEnd}`;
        for (const x of [s, e]) {
          const c = text.charCodeAt(x);
          const p = text.charCodeAt(x - 1);
          if (x > 0 && x < text.length && p >= 0xd800 && p <= 0xdbff && c >= 0xdc00 && c <= 0xdfff) {
            return `boundary ${x} splits a surrogate pair`;
          }
        }
        prevEnd = e;
      }
      return null;
    });
  });

  it("every marked range contains a match of some term, and a term matches iff it marks something", () => {
    sweep("markRanges soundness", 4000, SEED + 3, gen(ALL_ATOMS), ([text, query]) => {
      const terms = parseQuery(query);
      for (const [s, e] of markRanges(text, terms)) {
        const slice = text.slice(s, e);
        if (!terms.some((t) => termMatches(slice, t))) return `range ${show(slice)} matches no term`;
      }
      for (const t of terms) {
        if (termMatches(text, t) !== markRanges(text, [t]).length > 0) {
          return `termMatches and markRanges disagree on ${show(t.text)}`;
        }
      }
      return null;
    });
  });

  it("FIXED D8: a mark can split one user-perceived character (emoji with skin tone, ZWJ family)", () => {
    // Minimal: text "👍\uD83C\uDFFD great", query "👍 great" → [[0,2],[5,10]]: the mark
    // ends between the thumbs-up and its skin-tone modifier.
    sweep("markRanges graphemes, full domain", 3000, SEED + 4, gen(ALL_ATOMS), graphemeProp);
  });

  it("…and over the domain without multi-code-point emoji or bare marks, marks fall on grapheme boundaries", () => {
    sweep("markRanges graphemes, minus D8, D9", 3000, SEED + 4, gen(without(ALL_ATOMS, EMOJI_CLUSTER_ATOMS)), (f) =>
      // D9's trigger is a term whose FOLDED text begins with a mark, which a
      // query can reach by decomposition (Thai ำ → U+0E4D U+0E32), not only by
      // typing a bare mark; so it is excluded by that predicate.
      parseQuery(f[1]).some((t) => /^\p{M}/u.test(t.text)) ? null : graphemeProp(f),
    );
  });

  it("FIXED D9: a term that BEGINS with a combining mark matches inside a letter", () => {
    // The start-side twin of the contract's "a match may not end inside a
    // letter": termPositions checks the end, never the start.
    // On a symbol that stays a character ("+"; ")" is punctuation and folds to
    // a space now, after which a mark stands alone and may match).
    expect(matches("+\u0301\u0301", "\u0301\u0301")).toBe(false);
  });
  it("FIXED D9: Thai — the vowel ำ alone decomposes to a mark first, and marks half of กำ", () => {
    expect(markRanges("\u0E01\u0E33", parseQuery("\u0E33"))).toEqual([]);
  });
  it("FIXED D9 side effect: one Thai vowel ำ is an active query, though one Thai letter is not", () => {
    // isActiveQuery recomposes with NFC, but ำ's decomposition is compatibility-only.
    expect(isActiveQuery("\u0E33")).toBe(false);
  });
  it("FIXED D9: Japanese — a quoted fragment starting with the semi-voiced mark finds パン", () => {
    expect(matches("パン", '"\u309Aン"')).toBe(false);
  });

  function graphemeProp([text, query]: string[]): string | null {
    const ranges = markRanges(text, parseQuery(query));
    if (ranges.length === 0) return null;
    const ok = graphemeBoundaries(text);
    for (const [s, e] of ranges) {
      if (!ok.has(s) || !ok.has(e)) return `range [${s},${e}) of ${show(text)} splits a grapheme`;
    }
    return null;
  }

  it("FIXED D8, Devanagari: the half-letter क\u094D marks the whole conjunct क\u094Dष", () => {
    expect(markRanges("\u0915\u094D\u0937\u092E\u093E", parseQuery("\u0915\u094D"))).toEqual([[0, 3]]);
  });

  it("FIXED D8: the mark covers the whole emoji, skin tone included", () => {
    // A skin tone folds away, so the run "👍 great" is one mark over all of it.
    expect(markRanges("👍\uD83C\uDFFD great", parseQuery("👍 great"))).toEqual([[0, 10]]);
  });
});

// ── 3. An independent oracle for the ASCII domain ───────────────────────

/**
 * In ASCII, folding (written from the spec, not the code): lower case; letters
 * and digits are word characters; whitespace and punctuation (\\p{P}, except
 * the apostrophe) are one space, runs collapsed, none leading; a backtick is
 * an apostrophe, kept only between two word characters (don't), dropped at a
 * word's edge (‘than the’, students'); other symbols ($ + < = > ^ | ~) stay.
 * Returns the folded text and, per folded character, its index in `s`.
 */
const isWordA = (c: string | undefined) => c !== undefined && /[a-z0-9]/i.test(c);
const isApostropheA = (c: string) => c === "'" || c === "`";
const isSepA = (c: string) => /\s/.test(c) || (/\p{P}/u.test(c) && c !== "'");
function foldA(s: string): { text: string; map: number[] } {
  let text = "";
  const map: number[] = [];
  for (let i = 0; i < s.length; i++) {
    const c = s[i];
    if (isApostropheA(c)) {
      let j = i + 1;
      while (j < s.length && isApostropheA(s[j])) j++;
      const prev = text[text.length - 1];
      const inside = prev !== undefined && prev !== " " && j < s.length && !isSepA(s[j]);
      if (inside) {
        text += "'";
        map.push(i);
      }
    } else if (isSepA(c)) {
      if (text.length > 0 && text[text.length - 1] !== " ") {
        text += " ";
        map.push(i);
      }
    } else {
      text += c.toLowerCase();
      map.push(i);
    }
  }
  return { text, map };
}

function oracleParse(q: string): { kind: string; text: string }[] {
  const terms: { kind: string; text: string }[] = [];
  let buf = "";
  let inPhrase = false;
  const flush = (kind: "word" | "phrase") => {
    const t = foldA(buf).text.trim();
    buf = "";
    if (!t) return;
    // Words typed together are one run (decided 3 Oct 2026).
    terms.push({ kind, text: t });
  };
  for (const ch of q) {
    if (ch === '"') {
      flush(inPhrase ? "phrase" : "word");
      inPhrase = !inPhrase;
    } else buf += ch;
  }
  flush(inPhrase ? "phrase" : "word");
  return terms;
}

/** Every [start, end) in `text` where the folded term matches, written from the spec, not the code. */
function oracleRanges(text: string, term: { kind: string; text: string }, whole = false): Array<[number, number]> {
  const out: Array<[number, number]> = [];
  const { text: f, map } = foldA(text);
  for (let i = 0; i + term.text.length <= f.length; i++) {
    if (f.slice(i, i + term.text.length) !== term.text) continue;
    if ((term.kind === "word" || whole) && i > 0 && isWordA(f[i - 1])) continue;
    const j = i + term.text.length;
    if (whole && j < f.length && isWordA(f[j])) continue;
    // A mark runs to where the next folded character starts, so it takes in
    // what folding dropped after the match (a word-edge apostrophe), as it
    // takes in an accent dropped from a letter.
    out.push([map[i], j < f.length ? map[j] : text.length]);
  }
  return out;
}

function mergeRanges(rs: Array<[number, number]>): Array<[number, number]> {
  const sorted = rs.slice().sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const merged: Array<[number, number]> = [];
  for (const r of sorted) {
    const last = merged[merged.length - 1];
    if (last && r[0] <= last[1]) last[1] = Math.max(last[1], r[1]);
    else merged.push([r[0], r[1]]);
  }
  return merged;
}

describe("ASCII oracle (independently written from docs/design-search.md §3)", () => {
  const ASCII_TEXT = [...ASCII_WORDS, ...ASCII_SEPS];
  const ASCII_QUERY = [...ASCII_WORDS.map((w) => w.slice(0, 1 + (w.length >> 1))), ...ASCII_WORDS, " ", '"', "'", "`", "\t"];
  const genA = (r: Rng) => [randomString(r, ASCII_TEXT, 10), randomString(r, ASCII_QUERY, 4)];

  it("parseQuery splits, quotes, folds and strips edge apostrophes as specified", () => {
    sweep("ascii parse", 3000, SEED + 5, genA, ([, q]) => {
      const got = parseQuery(q).map((t) => ({ kind: t.kind, text: t.text }));
      const want = oracleParse(q);
      if (JSON.stringify(got) !== JSON.stringify(want)) return `got ${JSON.stringify(got)} want ${JSON.stringify(want)}`;
      for (const t of parseQuery(q)) if (t.anywhere !== (t.kind === "phrase")) return `anywhere wrong on ${t.text}`;
      return null;
    });
  });

  it("matchesAll and markRanges equal the oracle exactly", () => {
    sweep("ascii match+marks", 4000, SEED + 6, genA, ([text, q]) => {
      const terms = parseQuery(q);
      const per = terms.map((t) => oracleRanges(text, t));
      const want = terms.every((_, i) => per[i].length > 0);
      if (matchesAll([text], terms) !== want) return `match ${!want}, oracle says ${want}`;
      const got = markRanges(text, terms);
      const wantR = mergeRanges(per.flat());
      if (!eqRanges(got, wantR)) return `marks ${JSON.stringify(got)} oracle ${JSON.stringify(wantR)}`;
      return null;
    });
  });

  it("whole-word terms (the mentions / contains tokens) equal the oracle exactly", () => {
    sweep("ascii whole", 3000, SEED + 7, (r) => [randomString(r, ASCII_TEXT, 10), randomString(r, ASCII_WORDS, 2)], ([text, name]) => {
      const term = wholeWordsTerm(name);
      if (!term) return name.trim() ? "null term for a non-empty name" : null;
      const want = oracleRanges(text, { kind: "phrase", text: term.text }, true).length > 0;
      return termMatches(text, term) === want ? null : `whole match ${!want}, oracle ${want}`;
    });
  });
});

// ── 4. Folding laws ─────────────────────────────────────────────────────

describe("folding laws", () => {
  const foldIdem = ([s]: string[]) => (fold(fold(s)) === fold(s) ? null : `${show(fold(s))} → ${show(fold(fold(s)))}`);

  it("FIXED D1: fold is not idempotent — compatibility forms decompose AFTER lower-casing", () => {
    // Minimal: fold("™") === "TM", fold("TM") === "tm". Same root: "℃" → "°C",
    // "𝐃" → "D", "ŉ" → "ʼn" (U+02BC escapes the apostrophe mapping).
    sweep("fold idempotent, full domain", 4000, SEED + 8, (r) => [randomString(r, ALL_ATOMS, 10)], foldIdem);
  });

  it("…fold is idempotent over the domain minus D1's compatibility atoms", () => {
    sweep("fold idempotent, minus D1", 4000, SEED + 8, (r) => [randomString(r, without(ALL_ATOMS, COMPAT_UPPER_ATOMS), 10)], foldIdem);
  });

  const normInvariant = (form: "NFC" | "NFD" | "NFKC") => ([text, query]: string[]) => {
    const terms = parseQuery(query);
    const a = matchesAll([text], terms);
    const b = matchesAll([text.normalize(form)], terms);
    const c = matchesAll([text], parseQuery(query.normalize(form)));
    if (a !== b) return `text ${form} changes the answer (${a} → ${b})`;
    if (a !== c) return `query ${form} changes the answer (${a} → ${c})`;
    return null;
  };
  const genTQ = (atoms: readonly string[]) => (r: Rng) => {
    const text = randomString(r, atoms, 8);
    const cps = Array.from(text.normalize(r.chance(0.5) ? "NFC" : "NFD"));
    const a = r.int(cps.length + 1);
    return [text, r.chance(0.6) ? cps.slice(a, a + 1 + r.int(5)).join("") : randomString(r, atoms, 2)];
  };

  it("matching is invariant under NFC and NFD of the text and the query", () => {
    sweep("NFC", 3000, SEED + 9, genTQ(ALL_ATOMS), normInvariant("NFC"));
    sweep("NFD", 3000, SEED + 10, genTQ(ALL_ATOMS), normInvariant("NFD"));
  });

  it("FIXED D1 again: matching is not invariant under NFKC (compatibility forms are claimed to fold)", () => {
    // Minimal: text "™", query "tm" → no match; text "TM", query "tm" → match.
    sweep("NFKC, full domain", 3000, SEED + 11, genTQ(ALL_ATOMS), normInvariant("NFKC"));
  });

  it("…NFKC invariance holds over the domain minus D1's atoms", () => {
    sweep("NFKC, minus D1", 3000, SEED + 11, genTQ(without(ALL_ATOMS, COMPAT_UPPER_ATOMS)), normInvariant("NFKC"));
  });

  it("matching is invariant under upper- and lower-casing the text (dotless ı excluded: contract known limit)", () => {
    const atoms = without(ALL_ATOMS, COMPAT_UPPER_ATOMS, DOTLESS_I_ATOMS);
    sweep("case", 4000, SEED + 12, genTQ(atoms), ([text, query]) => {
      const terms = parseQuery(query);
      const a = matchesAll([text], terms);
      for (const t of [text.toUpperCase(), text.toLowerCase()]) {
        if (matchesAll([t], terms) !== a) return `casing the text to ${show(t)} changes the answer`;
      }
      return null;
    });
  });

  it("FIXED D1 minimal repros", () => {
    expect(fold("™")).toBe("tm");
    expect(matches("Brand ™", "tm")).toBe(true);
    expect(matches("𝐃𝐞𝐥𝐢𝐯𝐞𝐫𝐲 was late", "delivery")).toBe(true);
    expect(matches("it was 30℃", '"30°c"')).toBe(true);
  });
});

// ── 5. Parsing, activation and ⌘E ───────────────────────────────────────

describe("query parsing and ⌘E (Use Selection for Find)", () => {
  /** Pick a selection on grapheme boundaries, as a browser selection is. */
  const genSel = (atoms: readonly string[]) => (r: Rng) => {
    const text = randomString(r, atoms, 10);
    const b = [...graphemeBoundaries(text)].sort((x, y) => x - y);
    const i = r.int(b.length);
    const j = i + r.int(b.length - i);
    return [text, text.slice(b[i], b[j])];
  };
  const roundTrip = ([text, sel]: string[]) => {
    // Domain: the selection occurs in the text on grapheme boundaries (keeps shrinking honest).
    const b = graphemeBoundaries(text);
    let at = text.indexOf(sel);
    while (at >= 0 && !(b.has(at) && b.has(at + sel.length))) at = text.indexOf(sel, at + 1);
    if (at < 0) return null;
    const q = asPhrase(sel);
    if (!q) return null; // whitespace-only selection: nothing to find
    return matchesAll([text], parseQuery(q)) ? null : `${show(q)} does not find its own source`;
  };

  it("FIXED D2: a selection containing a double quote mark does not find the quote it came from", () => {
    // Minimal: text 'said "no"', selection 'said "no' → asPhrase gives
    // '"said no"', which needs a space where the text has a quote mark.
    // Japanese 「」 and French « » quoted speech hit the same thing.
    sweep("⌘E round trip, full domain", 4000, SEED + 13, genSel(ALL_ATOMS), roundTrip);
  });

  it("…the round trip holds for any selection without a double quote mark (D2) or a byte-order mark (D6) inside it", () => {
    sweep("⌘E round trip, minus D2, D6", 4000, SEED + 13, genSel(without(ALL_ATOMS, QUOTE_ATOMS, BOM_ATOMS)), roundTrip);
  });

  it("FIXED D6 (⌘E face): a selection containing U+FEFF does not find its source", () => {
    // asPhrase's /\s+/ turns the BOM into a space; fold makes it vanish in the text.
    expect(matches("ab\uFEFFcd", asPhrase("ab\uFEFFcd"))).toBe(true);
  });

  it("FIXED D2 minimal repros", () => {
    expect(matches('she said "no" twice', asPhrase('said "no"'))).toBe(true);
    expect(matches("彼は「はい」と言った", asPhrase("「はい」と"))).toBe(true);
    expect(matches("il a dit « non » hier", asPhrase("dit « non"))).toBe(true);
  });

  it("asPhrase always yields exactly one phrase term (or nothing), whatever is selected", () => {
    sweep("asPhrase shape", 4000, SEED + 14, (r) => [randomString(r, ALL_ATOMS, 8)], ([sel]) => {
      const q = asPhrase(sel);
      const terms = parseQuery(q);
      if (!q) return terms.length === 0 ? null : "empty phrase parsed to terms";
      if (terms.length > 1 || (terms.length === 1 && terms[0].kind !== "phrase")) {
        return `parsed to ${JSON.stringify(terms.map((t) => [t.kind, t.text]))}`;
      }
      return null;
    });
  });

  it("isActiveQuery is monotone: adding a word to an active query keeps it active", () => {
    sweep("active monotone", 3000, SEED + 15, (r) => [randomString(r, ALL_ATOMS, 3), randomString(r, ALL_ATOMS, 2)], ([q, w]) => {
      if (!isActiveQuery(q)) return null;
      return isActiveQuery(`${q} ${w}`) ? null : "became inactive";
    });
  });

  it("FIXED D6: a byte-order mark inside a typed word splits it, though the text side treats it as invisible", () => {
    // parseQuery splits on /\s/u, which includes U+FEFF; fold drops it.
    expect(matches("a\uFEFFb", "a\uFEFFb")).toBe(true);
  });
});

// ── 6. Script-boundary defects (minimal repros) ─────────────────────────

describe("script boundaries", () => {
  it("FIXED D3: a Latin word or number written inside Chinese/Japanese text cannot be found", () => {
    // The term is Latin, so it must start a word; the preceding Han/kana
    // letter is a word character, so it never does.
    expect(matches("我用iPhone拍照", "iphone")).toBe(true);
  });
  it("FIXED D3: a price in Chinese text", () => {
    expect(matches("我花了500元", "500")).toBe(true);
  });
  it("FIXED D3: a brand in Japanese text", () => {
    expect(matches("家具はIKEAで買った", "ikea")).toBe(true);
  });

  it("FIXED D4: 'mentions' misses a Latin name followed by a Japanese honorific or Chinese verb", () => {
    const tom = wholeWordsTerm("Tom") as SearchTerm;
    expect(termMatches("Tomさんが言った", tom)).toBe(true);
  });
  it("FIXED D4: Latin name preceded and followed by Han", () => {
    const tom = wholeWordsTerm("Tom") as SearchTerm;
    expect(termMatches("我和Tom说过", tom)).toBe(true);
  });

  it("FIXED D5: a Korean whole-word name matches into the last syllable of a DIFFERENT name", () => {
    // 김민지 folds to jamo, and 김민직 begins with the same jamo, so
    // "mentions 김민지" finds 김민직 (particle allowance applied mid-syllable).
    const kim = wholeWordsTerm("김민지") as SearchTerm;
    expect(termMatches("김민직이 왔다", kim)).toBe(false);
  });

  it("FIXED D7: an emoji with VS16 (❤\uFE0F) does not find the same emoji without it (❤)", () => {
    // U+FE0F is a mark (Mn), not a format character, so it is kept and must match.
    expect(matches("I ❤ it", "❤\uFE0F it")).toBe(true);
  });

  it("FIXED: stroke and ligature letters fold (ø, ł, æ, œ, đ), by lodash's deburr table", () => {
    // Bristlenose ships da, nb and pl locales; nobody should have to type ø.
    expect(matches("Søren said", "soren")).toBe(true);
    expect(matches("Łódź store", "lodz")).toBe(true);
    expect(matches("Ærø ferry", "aero")).toBe(true);
    expect(matches("the œuvre of", "oeuvre")).toBe(true);
    expect(matches("Đorđe called", "dorde")).toBe(true);
    // Typed with the letter, it still finds itself.
    expect(matches("Søren said", "søren")).toBe(true);
  });
  it("deburr reaches only Latin letters: a mark Hindi keeps is not stripped by it", () => {
    // deburr strips U+0300–U+036F wherever it sees them; applied outside Latin
    // it would turn क́ into क and let a match end before a kept mark.
    expect(matches("\u0915\u0301", "\u0915")).toBe(false);
  });
});

// ── 7. Project-level properties: monotonicity, tokens, suggest ──────────

function mkTag(name: string): TagResponse {
  return { name, codebook_group: "g", colour_set: "ux", colour_index: 0 };
}
function mkQuote(id: string, code: string, speaker: string, text: string, tags: TagResponse[]): QuoteResponse {
  return {
    dom_id: id, text, verbatim_excerpt: text, participant_id: code, session_id: "s1", speaker_name: speaker,
    start_timecode: 0, end_timecode: 1, sentiment: null, intensity: 1, researcher_context: null,
    quote_type: "screen_specific", topic_label: "", is_starred: false, is_hidden: false, edited_text: null,
    tags, deleted_badges: [], proposed_tags: [], segment_index: 0,
  };
}
function baseFilter(): FilterState {
  return {
    searchQuery: "", searchTokens: [], viewMode: "all", tagFilter: EMPTY_TAG_FILTER,
    hidden: {}, starred: {}, tags: {}, edits: {},
  };
}

interface World {
  quotes: QuoteResponse[];
  people: Record<string, SearchPerson>;
  f: FilterState;
  vocab: string[];
}

/** The synthetic project plus hostile quotes, edits, store tags and random filter state. */
function world(seed: number): World {
  const r = new Rng(seed);
  const p = syntheticProject({ seed, sessions: 24, quotesPerSession: 6, extraTags: 6 });
  const quotes = p.quotes.slice();
  const people = { ...p.people };
  // A moderator, a code-only speaker, look-alike tags and hostile text.
  const hostileTags = ["Price", "price ", "prïce", "\u00ADprice", "Delivery Time", "ﬁx", "fix"].map(mkTag);
  for (let i = 0; i < 30; i++) {
    const code = r.pick(["m1", "p99", "p1", "p10", "p2"]);
    const tags = Array.from({ length: r.int(3) }, () => r.pick([...hostileTags, ...p.tags]));
    quotes.push(mkQuote(`x${i}`, code, code === "p99" ? "p99" : r.pick(["Sam", "Tom", "José", ""]), randomString(r, ALL_ATOMS, 8), tags));
  }
  const f = baseFilter();
  for (const q of quotes) {
    if (r.chance(0.05)) f.hidden[q.dom_id] = true;
    if (r.chance(0.3)) f.starred[q.dom_id] = true;
    if (r.chance(0.05)) f.edits[q.dom_id] = randomString(r, ALL_ATOMS, 6);
    if (r.chance(0.05)) f.tags[q.dom_id] = [r.pick(hostileTags)];
  }
  if (r.chance(0.3)) f.viewMode = "starred";
  if (r.chance(0.3)) f.tagFilter = { unchecked: [r.pick(p.tags).name], noTagsUnchecked: r.chance(0.5), clearAll: false };
  const vocab = [
    ...Object.keys(people), ...Object.values(people).flatMap((x) => [x.full_name, x.short_name]),
    ...p.tags.map((t) => t.name), ...hostileTags.map((t) => t.name),
    "delivery", "deliv", "price", "the", "東京", "配送", "서우", "джо", "“than the", "'s", "tom delivery",
  ].filter(Boolean);
  return { quotes, people, f, vocab };
}

function randomToken(r: Rng, w: World): SearchToken {
  if (r.chance(0.5)) {
    const code = r.pick(Object.keys(w.people));
    return { ...personToken(code, w.people[code]), mode: r.pick(["said", "mentions", "not"] as const) };
  }
  const q = r.pick(w.quotes);
  const tags = quoteTags(q, w.f.tags);
  const name = tags.length && r.chance(0.8) ? r.pick(tags).name : r.pick(["absent tag", "PRICE", "Hidden Costs"]);
  return { ...tagToken({ name }), mode: r.pick(["tagged", "contains", "not"] as const) };
}

const ids = (qs: QuoteResponse[]) => qs.map((q) => q.dom_id).join(",");

describe("filter monotonicity", () => {
  it("adding a word to an active query never lets more quotes through", () => {
    for (let s = 0; s < 6; s++) {
      const w = world(SEED + 100 + s);
      const r = new Rng(SEED + 200 + s);
      for (let i = 0; i < 150; i++) {
        const q = r.pick(w.vocab).slice(0, 2 + r.int(6));
        if (!isActiveQuery(q)) continue;
        const extra = r.pick([...w.vocab, ...ALL_ATOMS]);
        const a = new Set(filterQuotes(w.quotes, { ...w.f, searchQuery: q }).map((x) => x.dom_id));
        const b = filterQuotes(w.quotes, { ...w.f, searchQuery: `${q} ${extra}` });
        const leaked = b.filter((x) => !a.has(x.dom_id));
        expect(leaked.map((x) => x.dom_id), `${show(q)} + ${show(extra)}`).toEqual([]);
      }
    }
  });

  it("a single typed word's matches are a subset of the same word quoted (phrases match anywhere)", () => {
    sweep("word ⊆ phrase", 4000, SEED + 16, (r) => {
      const text = randomString(r, ALL_ATOMS, 8);
      const cps = Array.from(text);
      const a = r.int(cps.length + 1);
      return [text, cps.slice(a, a + 1 + r.int(4)).join("")];
    }, ([text, word]) => {
      const wt = parseQuery(word);
      // Domain: a query with no quote mark that parses to exactly one word,
      // nothing stripped (an edge apostrophe is dropped from a word and kept
      // in a phrase, by design).
      if ([...word].some((c) => QUOTE_ATOMS.includes(c))) return null;
      if (wt.length !== 1 || wt[0].kind !== "word" || wt[0].text !== fold(word).trim()) return null;
      const pt = parseQuery(`"${word}"`);
      if (pt.length !== 1 || pt[0].text !== wt[0].text) return `quoting changed the term: ${show(wt[0].text)} vs ${pt.map((t) => show(t.text))}`;
      if (termMatches(text, wt[0]) && !termMatches(text, pt[0])) return "word matched, phrase did not";
      return null;
    });
  });
});

describe("tokens", () => {
  it("said/not and tagged/not partition the quotes exactly; tokens commute; a repeated token is a no-op", () => {
    for (let s = 0; s < 6; s++) {
      const w = world(SEED + 300 + s);
      const r = new Rng(SEED + 400 + s);
      for (let i = 0; i < 60; i++) {
        const t = randomToken(r, w);
        const pos = t.kind === "person" ? { ...t, mode: "said" as const } : { ...t, mode: "tagged" as const };
        const neg = { ...t, mode: "not" as const };
        for (const q of w.quotes) {
          const a = tokenMatches(q, pos, w.f.tags, w.f.edits);
          const b = tokenMatches(q, neg, w.f.tags, w.f.edits);
          expect(a !== b, `${q.dom_id} ${JSON.stringify(t)}`).toBe(true);
        }
        const others = [randomToken(r, w), randomToken(r, w)];
        const run = (tokens: SearchToken[]) => ids(filterQuotes(w.quotes, { ...w.f, searchTokens: tokens }));
        const forward = run([t, ...others]);
        expect(run([...others].reverse().concat(t))).toBe(forward);
        expect(run([t, t, ...others, t])).toBe(forward);
        expect(sameSubject(t, { ...t })).toBe(true);
      }
    }
  });

  it("a tag token is case/accent-folded, so 'tagged Price' passes a quote tagged 'prïce' (consistent with suggest; not with the sidebar)", () => {
    // Recorded, not a verdict: the tag SIDEBAR compares with toLowerCase()
    // (filter.ts passesTagFilter), the token and suggest with fold().
    const q = mkQuote("t", "p1", "Tom", "x", [mkTag("prïce")]);
    expect(tokenMatches(q, tagToken({ name: "Price" }))).toBe(true);
    expect(isQuoteVisible(q, { ...baseFilter(), tagFilter: { unchecked: ["price"], noTagsUnchecked: false, clearAll: false } })).toBe(true);
  });
});

describe("suggest", () => {
  const byNatural = (a: string, b: string) => a.localeCompare(b, undefined, { numeric: true });

  it("every row's count is what its token or the typed text would let through; caps, exclusions, ordering, determinism", () => {
    let checked = 0;
    for (let s = 0; s < 8; s++) {
      const w = world(SEED + 500 + s);
      const r = new Rng(SEED + 600 + s);
      for (let i = 0; i < 60; i++) {
        const tokens = Array.from({ length: r.int(3) }, () => randomToken(r, w));
        const f: FilterState = { ...w.f, searchTokens: tokens };
        const before = { ...f, searchQuery: "" };
        const isVisible = (q: QuoteResponse) => isQuoteVisible(q, before);
        const visible = w.quotes.filter(isVisible);
        const raw = r.pick(w.vocab);
        const query = r.chance(0.2) ? randomString(r, ALL_ATOMS, 2) : raw.slice(0, 1 + r.int(raw.length + 1));
        const cap = r.pick([1, 2, 3, 5]);
        const excludeCodes = tokens.flatMap((t) => (t.kind === "person" ? [t.code] : []));
        const excludeTags = tokens.flatMap((t) => (t.kind === "tag" ? [t.name] : []));
        const src = { quotes: w.quotes, tags: f.tags, edits: f.edits, people: w.people, isVisible };
        const rows = suggest(query, src, { cap, excludeCodes, excludeTags });
        const where = `${show(query)} (world ${s}, case ${i})`;

        expect(suggest(query, src, { cap, excludeCodes, excludeTags }), "deterministic " + where).toEqual(rows);
        expect(new Set(rows.map((x) => x.id)).size, "unique ids " + where).toBe(rows.length);

        // Free text: first, present iff active, counts what the filter shows.
        const text = rows.filter((x) => x.kind === "text");
        expect(text.length, "text row iff active " + where).toBe(isActiveQuery(query) ? 1 : 0);
        if (text.length) {
          expect(rows[0].kind).toBe("text");
          expect(text[0].count, "text count " + where).toBe(filterQuotes(w.quotes, { ...f, searchQuery: query }).length);
        }

        const terms = parseQuery(query);
        const typed = terms.map((t) => t.text).join(" ");
        const persons = rows.filter((x): x is Extract<Suggestion, { kind: "person" }> => x.kind === "person");
        const tagRows = rows.filter((x): x is Extract<Suggestion, { kind: "tag" }> => x.kind === "tag");
        expect(rows.map((x) => x.kind).join(), "group order " + where).toBe(
          [...text.map(() => "text"), ...persons.map(() => "person"), ...tagRows.map(() => "tag")].join(),
        );

        // People: count = said-by under current tokens; > 0; not excluded; complete up to cap; ordered.
        const personCands = new Map<string, { count: number; exact: boolean }>();
        for (const q of visible) {
          const code = q.participant_id;
          if (!code || excludeCodes.includes(code) || personCands.has(code)) continue;
          const onQuote = visible.find((v) => v.participant_id === code && v.speaker_name && v.speaker_name !== code)?.speaker_name;
          const names = [w.people[code]?.full_name, w.people[code]?.short_name, onQuote].filter((n): n is string => Boolean(n));
          if (terms.length === 0 || !matchesAll([code, ...names], terms)) continue;
          const tok = personToken(code, w.people[code], onQuote);
          personCands.set(code, {
            count: visible.filter((v) => tokenMatches(v, tok, f.tags, f.edits)).length,
            exact: [code, ...names].some((n) => fold(n) === typed),
          });
        }
        for (const p of persons) {
          const c = personCands.get(p.code);
          expect(c, `person ${p.code} offered but not a candidate ` + where).toBeDefined();
          expect(p.count, `person ${p.code} count ` + where).toBe(c?.count);
          expect(p.count).toBeGreaterThan(0);
        }
        const rankP = [...personCands.entries()].sort(
          (a, b) => Number(b[1].exact) - Number(a[1].exact) || b[1].count - a[1].count || byNatural(a[0], b[0]),
        );
        expect(persons.map((p) => p.code), "people = top cap " + where).toEqual(rankP.slice(0, cap).map((x) => x[0]));

        // Tags: count = tagged under current tokens; > 0; not excluded; complete up to cap; ordered.
        const excludedKeys = new Set(excludeTags.map(foldKey));
        const tagCands = new Map<string, { name: string; count: number }>();
        for (const q of visible) {
          for (const t of quoteTags(q, f.tags)) {
            const key = foldKey(t.name);
            if (excludedKeys.has(key) || tagCands.has(key)) continue;
            if (terms.length === 0 || !matchesAll([t.name], terms)) continue;
            const tok = tagToken(t);
            tagCands.set(key, { name: t.name, count: visible.filter((v) => tokenMatches(v, tok, f.tags, f.edits)).length });
          }
        }
        for (const t of tagRows) {
          const c = tagCands.get(foldKey(t.tag.name));
          expect(c, `tag ${t.tag.name} offered but not a candidate ` + where).toBeDefined();
          expect(t.count, `tag ${t.tag.name} count ` + where).toBe(c?.count);
          expect(t.count).toBeGreaterThan(0);
        }
        const rankT = [...tagCands.entries()].sort(
          (a, b) => Number(b[0] === typed) - Number(a[0] === typed) || b[1].count - a[1].count || byNatural(a[1].name, b[1].name),
        );
        expect(tagRows.map((t) => foldKey(t.tag.name)), "tags = top cap " + where).toEqual(rankT.slice(0, cap).map((x) => x[0]));
        checked++;
      }
    }
    expect(checked).toBe(480);
  });
});

describe("filterStateOf", () => {
  it("returns the same object while the fields it reads are unchanged, and a new one when any changes", () => {
    const store = {
      searchQuery: "ab", searchTokens: [], viewMode: "all", tagFilter: EMPTY_TAG_FILTER,
      hidden: {}, starred: {}, tags: {}, edits: {},
    } as unknown as QuotesState;
    const a = filterStateOf(store);
    expect(filterStateOf({ ...store })).toBe(a);
    const b = filterStateOf({ ...store, searchQuery: "abc" });
    expect(b).not.toBe(a);
    expect(b.searchQuery).toBe("abc");
    expect(filterStateOf({ ...store, hidden: {} })).not.toBe(b);
  });
});

// ── 8. Performance (reports; warns rather than fails) ───────────────────

describe("performance", () => {
  it("10k quotes, 200 keystroke-prefix queries: suggest + filter per keystroke", () => {
    const p = syntheticProject({ seed: SEED, sessions: 1000, quotesPerSession: 10, extraTags: 40 });
    expect(p.quotes.length).toBe(10_000);
    const r = new Rng(SEED + 700);
    const targets = [
      ...Object.values(p.people).flatMap((x) => [x.full_name, x.short_name]),
      ...p.tags.map((t) => t.name), "delivery was", "“than the shelf”", "東京", "配送料", "서울", "p10",
    ].filter(Boolean);
    const times: number[] = [];
    while (times.length < 200) {
      const target = r.pick(targets);
      const cps = Array.from(target);
      for (let k = 1; k <= Math.min(5, cps.length) && times.length < 200; k++) {
        const q = cps.slice(0, k).join("");
        const t0 = performance.now();
        suggest(q, { quotes: p.quotes, people: p.people });
        filterQuotes(p.quotes, { ...baseFilter(), searchQuery: q });
        times.push(performance.now() - t0);
      }
    }
    const sorted = times.slice().sort((a, b) => a - b);
    const pct = (x: number) => sorted[Math.min(sorted.length - 1, Math.floor(x * sorted.length))];
    const report = `search perf: ${times.length} keystrokes over 10k quotes — p50 ${pct(0.5).toFixed(1)} ms, p95 ${pct(0.95).toFixed(1)} ms, max ${sorted[sorted.length - 1].toFixed(1)} ms (first ${times[0].toFixed(1)} ms, cold cache)`;
    console.warn(report);
    if (pct(0.95) > 50) console.warn(`PERF WARNING: p95 above the 50 ms keystroke budget`);
    expect(times.length).toBeGreaterThan(0);
  });

  it("hostile sizes: long text marks, long queries, apostrophe runs", () => {
    const big = ("the delivery was late and the price ".repeat(300) + "ﬁ".repeat(500)).slice(0, 12_000);
    const timeIt = (label: string, fn: () => void) => {
      const t0 = performance.now();
      fn();
      const ms = performance.now() - t0;
      console.warn(`search perf: ${label} ${ms.toFixed(1)} ms`);
      if (ms > 100) console.warn(`PERF WARNING: ${label} over 100 ms`);
    };
    timeIt("markRanges on 12k chars, 3 terms", () => markRanges(big, parseQuery("the de f")));
    timeIt("parse 20k-apostrophe word (x'''…'x)", () => parseQuery("x" + "'".repeat(20_000) + "x"));
    // termMatches collects EVERY position before testing for one, so a
    // many-term query against a repetitive field is (terms × occurrences).
    timeIt("5000-term query against one 2000-char field", () =>
      matchesAll(["a".repeat(2_000)], parseQuery("a ".repeat(5_000))),
    );
    timeIt("fold 200k chars", () => fold("José straße ".repeat(16_000)));
  });
});
