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
 *   - A term in double quotes matches as exact text, anywhere: "boarding was"
 *     finds "onboarding was". Quoting is the way to search for a fragment, and
 *     what ⌘E (Use Selection for Find) sends.
 *   - Case, accents and width are folded: "Jose" finds "José", "ё" finds "е",
 *     "ＡＢＣ" finds "abc", "strasse" finds "Straße". Curly and straight
 *     apostrophes are the same. Accents are stripped ONLY in scripts where they
 *     are optional marks (Latin, Greek, Cyrillic, Arabic, Hebrew); in Japanese,
 *     Thai or Hindi a combining mark changes the word (パン is not ハン), so it
 *     is kept, and a match may not end just before one.
 *   - Invisible characters (soft hyphen, zero-width space) are ignored.
 *   - Chinese and Japanese have no spaces, so a term written in those scripts
 *     matches anywhere, not only at a word start.
 *   - A query is active from 2 characters, or 1 Chinese/Japanese character.
 *   - Apostrophes at the edge of a typed word are ignored, so smart single
 *     quotes (‘than the’) behave like the plain words.
 */

// ── Folding ─────────────────────────────────────────────────────────────

const MARK = /\p{M}/u;
const FORMAT = /\p{Cf}/u;
const SPACE = /[\s\u0085]/u;
const APOSTROPHES = /[\u2018\u2019\u02BC\u0060\u00B4]/g;
const WORD_CHAR = /[\p{L}\p{N}\p{M}]/u;
/** Scripts whose combining marks are optional accents, safe to fold away. */
const ACCENTED_SCRIPT = /[\p{Script=Latin}\p{Script=Greek}\p{Script=Cyrillic}\p{Script=Arabic}\p{Script=Hebrew}]/u;
/** Scripts written without spaces between words: a term may match mid-word. */
const UNSPACED = /[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Thai}]/u;
/** Korean: particles attach to the word they follow, so a name ends mid-"word". */
const HANGUL = /\p{Script=Hangul}/u;
/** Scripts where one character is already a word. */
const ONE_CHAR_WORD = /[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}]/u;
const QUOTE_MARKS = /["\u201C\u201D\u201E\u00AB\u00BB\u300C\u300D]/gu;

/** Folded text plus, for every folded UTF-16 unit, its index in the original. */
export interface Folded {
  text: string;
  /** map[i] = index in the original string of folded unit i; one extra end sentinel. */
  map: number[];
}

/**
 * The one folding walk, per code point:
 *   - format characters (soft hyphen, zero-width space, BOM) vanish;
 *   - whitespace becomes one space, runs collapse;
 *   - apostrophes unify, case folds, compatibility forms decompose (NFKD);
 *   - a combining mark is dropped only after a letter of an ACCENTED_SCRIPT,
 *     which also covers marks written as separate characters ("e" + U+0301);
 *   - ß → ss and final ς → σ, as Python's casefold does.
 */
function foldCore(s: string, map: number[] | null): string {
  let text = "";
  let i = 0;
  let stripMarks = false;
  const emit = (unit: string) => {
    if (unit === " " && (text.length === 0 || text[text.length - 1] === " ")) return;
    map?.push(i);
    text += unit;
  };
  for (const ch of s) {
    if (FORMAT.test(ch)) {
      // invisible: no output, no boundary
    } else if (SPACE.test(ch)) {
      emit(" ");
      stripMarks = false;
    } else {
      const decomposed = ch.replace(APOSTROPHES, "'").toLowerCase().normalize("NFKD");
      for (const cp of decomposed) {
        if (MARK.test(cp)) {
          if (stripMarks) continue;
        } else {
          stripMarks = ACCENTED_SCRIPT.test(cp);
        }
        const out = cp === "ß" ? "ss" : cp === "ς" ? "σ" : SPACE.test(cp) ? " " : cp;
        // UTF-16 units, so the map stays one entry per unit of `text`.
        for (let k = 0; k < out.length; k++) emit(out[k]);
      }
    }
    i += ch.length;
  }
  map?.push(i);
  return text;
}

// Two caches. Matching folds every quote on every keystroke, so its cache must
// hold a whole project's fields; it stores only the folded string. Highlighting
// needs the index map too, but only for the few quotes on screen.
const textCache = new Map<string, string>();
const TEXT_CACHE_MAX = 200_000;
const mapCache = new Map<string, Folded>();
const MAP_CACHE_MAX = 2_000;

/** Fold a string for matching (case, accents, width, apostrophes, whitespace). */
export function fold(s: string): string {
  const hit = textCache.get(s);
  if (hit !== undefined) return hit;
  const text = foldCore(s, null);
  if (textCache.size >= TEXT_CACHE_MAX) textCache.clear();
  textCache.set(s, text);
  return text;
}

/** Fold a string and keep a map back to the original, for drawing marks. */
export function foldWithMap(s: string): Folded {
  const hit = mapCache.get(s);
  if (hit) return hit;
  const map: number[] = [];
  const folded = { text: foldCore(s, map), map };
  if (mapCache.size >= MAP_CACHE_MAX) mapCache.clear();
  mapCache.set(s, folded);
  return folded;
}

// ── Query parsing ───────────────────────────────────────────────────────

export interface SearchTerm {
  kind: "word" | "phrase";
  /** Folded text of the term. */
  text: string;
  /** True when the term may match mid-word (unspaced scripts). */
  anywhere: boolean;
  /** True when the term must also END at a word boundary (see wholeWordsTerm). */
  whole?: boolean;
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
      for (const raw of text.split(" ")) {
        const w = raw.replace(/^'+|'+$/g, "");
        if (w) terms.push(makeTerm("word", w));
      }
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
  return { kind, text, anywhere: kind === "phrase" || UNSPACED.test(text) };
}

/**
 * A term for a known name or label, matched as whole words: "Tom" finds
 * "Tom said" and "Tom's", never "Tomorrow". Used by the tokens that look for a
 * person's name or a tag's name in quote text (docs/design-search.md §5).
 * Unspaced scripts match anywhere; Korean need not end at a word boundary,
 * because a particle follows the name directly (김민지가).
 */
export function wholeWordsTerm(text: string): SearchTerm | null {
  const folded = fold(text).trim();
  if (!folded) return null;
  const unspaced = UNSPACED.test(folded);
  return { kind: "phrase", text: folded, anywhere: unspaced, whole: !unspaced && !HANGUL.test(folded) };
}

/**
 * Turn selected text into a query that finds it exactly: a quoted phrase,
 * with any double quotes inside it removed so they can't end it early.
 */
export function asPhrase(text: string): string {
  const inner = text.replace(QUOTE_MARKS, " ").replace(/\s+/gu, " ").trim();
  return inner ? `"${inner}"` : "";
}

/**
 * True once the query is long enough to filter by: its parsed terms hold at
 * least 2 characters, or 1 Chinese or Japanese character. Counted after
 * parsing, so quote marks and edge apostrophes don't count ("'s" is one
 * letter), and recomposed (NFC) so a Korean syllable or "e" + accent counts
 * once and a ligature counts as its letters.
 */
export function isActiveQuery(query: string): boolean {
  const compact = parseQuery(query)
    .map((t) => t.text)
    .join("")
    .replace(/ /g, "")
    .normalize("NFC");
  if (!compact) return false;
  if (ONE_CHAR_WORD.test(compact)) return true;
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
    const end = at + term.text.length;
    // A kept combining mark belongs to the letter before it: "ハ" must not
    // match the first half of "パ".
    const splitsLetter = end < folded.length && MARK.test(folded[end]);
    const endsWord = !term.whole || end === folded.length || !WORD_CHAR.test(folded[end]);
    if ((term.anywhere || isWordStart(folded, at)) && !splitsLetter && endsWord) out.push(at);
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
      // A match can end inside one original character that folded to several
      // units ("ﬁ" → "fi"): extend to that character's end, never a zero width.
      let end = at + term.text.length;
      while (end < folded.length && map[end] === map[end - 1]) end++;
      ranges.push([map[at], map[end]]);
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
