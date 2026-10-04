/**
 * searchMatch — the one set of rules for "does this text match what was typed".
 *
 * Every search surface in the SPA goes through here: the quote filter, the
 * highlight marks, and the suggestion recognisers. The rules are pinned by
 * `tests/fixtures/search-match-contract.json` so the Python/SQLite search core,
 * when it lands, can be held to the same answers.
 *
 * The rules (docs/mockups/toolbar-search.html, decided 28 Sep 2026):
 *   - Words typed together match together, in order, from the START of a word
 *     ("st" finds "Storey" and "Steppe", not "best"; "want to go" finds
 *     "I want to go home", not "go … want … to"). It is a quote engine: a
 *     researcher typing several words is looking for something somebody said.
 *     (Decided 3 Oct 2026; until then each word matched on its own.)
 *   - A term in double quotes matches as exact text, anywhere: "boarding was"
 *     finds "onboarding was". Quoting is the way to search for a fragment, and
 *     what ⌘E (Use Selection for Find) sends.
 *   - Case, accents and width are folded: "Jose" finds "José", "ё" finds "е",
 *     "ＡＢＣ" finds "abc", "strasse" finds "Straße", "soren" finds "Søren".
 *     Nobody should have to type an accent to find a name. Latin letters that
 *     Unicode gives no decomposition (ø ł đ æ œ þ ı) fold by lodash's `deburr`
 *     table rather than one of our own. Curly and straight
 *     apostrophes are the same. Accents are stripped ONLY in scripts where they
 *     are optional marks (Latin, Greek, Cyrillic, Arabic, Hebrew); in Japanese,
 *     Thai or Hindi a combining mark changes the word (パン is not ハン), so it
 *     is kept, and a match may not end just before one.
 *   - Invisible characters (soft hyphen, zero-width space) are ignored.
 *   - Chinese and Japanese have no spaces, so a term written in those scripts
 *     matches anywhere, not only at a word start.
 *   - A query is active from 2 characters, or 1 Chinese/Japanese character.
 *   - Punctuation is whitespace, in text and query alike, so a run finds its
 *     words across a comma, hyphen or ellipsis ("yes it was" finds "Yes, it
 *     was"). Apostrophes at the edge of a word are dropped on both sides, so
 *     smart single quotes (‘than the’) and possessives (students’) behave like
 *     the plain words; one inside a word stays (don't).
 *   - Whether a run may start mid-word is decided by its first letter: a
 *     Chinese or Japanese run may, a Latin one may not ("ing 東京").
 *   - Decided 4 Oct 2026: # @ % & stay in the word (C#, #1, 50%, R&D);
 *     punctuation after the last typed word finishes it ("why?" is not a
 *     prefix); and a typed run also matches its joined form ("covid19" finds
 *     "COVID-19", "1000" finds "1,000") — see "Joined forms" below; and a
 *     typed plural or possessive also finds the singular ("dogs" finds "dog",
 *     "Mike's" finds "Mike") — see "Plurals and possessives".
 */

import deburr from "lodash.deburr";

// ── Folding ─────────────────────────────────────────────────────────────

/** The letters `deburr` folds: Latin-1 Supplement and Latin Extended-A, less
 *  × and ÷. Only these go through it, so its own mark stripping never reaches
 *  a script whose marks we keep. */
const DEBURR_LATIN = /[\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u017F]/u;

const MARK = /\p{M}/u;
/** Invisible: format characters (soft hyphen, zero-width space, BOM), emoji
 *  variation selectors (❤ and ❤️ are one heart) and skin tones (👍 finds 👍🏽).
 *  Dropped from text and query; a highlight still covers the whole emoji. */
const INVISIBLE = /[\p{Cf}\p{Variation_Selector}\p{Emoji_Modifier}]/u;
const INVISIBLE_G = /[\p{Cf}\p{Variation_Selector}\p{Emoji_Modifier}]/gu;
const SPACE = /[\s\u0085]/u;
const APOSTROPHES = /[\u2018\u2019\u02BC\u0060\u00B4]/g;
/** Letters, digits and marks. A kept symbol (# @ % &) is not one, so
 *  "hashtag" still starts a word in "#hashtag" and "sarah" in "@sarah". */
const WORD_CHAR = /[\p{L}\p{N}\p{M}]/u;
/** Scripts whose combining marks are optional accents, safe to fold away. */
const ACCENTED_SCRIPT = /[\p{Script=Latin}\p{Script=Greek}\p{Script=Cyrillic}\p{Script=Arabic}\p{Script=Hebrew}]/u;
/** Scripts written without spaces between words: a term may match mid-word. */
const UNSPACED = /[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Thai}]/u;
/** Korean: particles attach to the word they follow, so a name ends mid-"word". */
const HANGUL = /\p{Script=Hangul}/u;
/** Hangul jamo that continue a syllable (vowels, final consonants): a match
 *  ending before one ends inside a syllable. Folding decomposes syllables. */
const HANGUL_CONTINUES = /[\u1160-\u11FF\uD7B0-\uD7FF]/u;
/** Scripts where one character is already a word. */
const ONE_CHAR_WORD = /[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}]/u;
const QUOTE_MARKS = /["\u201C\u201D\u201E\u00AB\u00BB\u300C\u300D]/gu;
/** Double quote marks in text fold to a space: they are punctuation around
 *  speech, and a quoted phrase in the query cannot contain one. */
const QUOTE_MARK = /["\u201C\u201D\u201E\u00AB\u00BB\u300C\u300D]/u;
/** Punctuation folds to a space, on both sides, so a run of typed words finds
 *  them across a comma, a hyphen or an ellipsis: "yes it was" finds "Yes, it
 *  was", "well known" finds "well-known". Apostrophes are kept (don't, Tom's);
 *  the single quote marks are apostrophes here. */
const PUNCT = /\p{P}/u;
const APOSTROPHE_LIKE = /['\u2018\u2019]/u;
/** Punctuation that carries meaning inside a word rather than separating
 *  words: C#, #1, @sarah, 50%, R&D. Kept, full-width forms included (they
 *  fold to these), so "C#" is not the letter c and "#1" is not 1. Decided
 *  4 Oct 2026; the cost is that "R&D" no longer finds "R & D". */
const WORD_SYMBOL = /[#@%&\uFF03\uFF20\uFF05\uFF06\uFE5F\uFE6B\uFE6A\uFE60]/u;
const isPunct = (c: string) => PUNCT.test(c) && !APOSTROPHE_LIKE.test(c) && !WORD_SYMBOL.test(c);

// ── Joined forms ────────────────────────────────────────────────────────
//
// A word written with a mark inside it is also found written without it:
// "covid19" finds "COVID-19", "coop" finds "co-op", "1000" finds "1,000",
// "collecció" finds "col·lecció" — and the reverse, "co-op" finds "coop".
// Lucene's WordDelimiterGraphFilter does this with its catenate options: the
// split form and the joined form both match. Here the text is folded a second
// way, with those marks dropped instead of turned into a space, and a typed run
// is tried against both. Only marks INSIDE a word join: a hyphen or dash
// between letters or digits; a middle dot, or a full stop, between letters;
// and a thousands separator — a full stop, comma or narrow space followed by
// exactly three digits — so "3.5" never becomes "35". Decided 4 Oct 2026.

const DASH = /\p{Pd}/u;
const LETTERISH = /[\p{L}\p{M}]/u;
const LETTER_OR_DIGIT = /[\p{L}\p{N}\p{M}]/u;
const DIGIT = /\p{Nd}/u;
const LETTER_JOINERS = /[.\u00B7\u2027]/u;
const THOUSANDS = /[.,\u00A0\u202F\u2009]/u;
/** Could this text have a joined form at all? The in-word patterns themselves
 *  (invisible characters allowed between), not just their marks: commas and
 *  full stops are in nearly every quote, and testing for those alone folded
 *  almost every quote twice on every keystroke (p95 57 ms on 10,000 quotes). */
const INV = "[\\p{Cf}\\p{Variation_Selector}\\p{Emoji_Modifier}]*";
const MAY_JOIN = new RegExp(
  `[\\p{L}\\p{N}\\p{M}]${INV}\\p{Pd}${INV}[\\p{L}\\p{N}\\p{M}]` +
    `|[\\p{L}\\p{M}]${INV}[.\\u00B7\\u2027]${INV}\\p{L}` +
    `|\\p{Nd}${INV}[.,\\u00A0\\u202F\\u2009]${INV}\\p{Nd}`,
  "u",
);

/** True when the code point at `k` is a mark inside a word, by its raw
 *  neighbours (invisible characters skipped). */
function joinsAt(cps: string[], k: number): boolean {
  const c = cps[k];
  let a = k - 1;
  while (a >= 0 && INVISIBLE.test(cps[a])) a--;
  let b = k + 1;
  while (b < cps.length && INVISIBLE.test(cps[b])) b++;
  const prev = a >= 0 ? cps[a] : "";
  const next = b < cps.length ? cps[b] : "";
  if (!prev || !next) return false;
  if (DASH.test(c)) return LETTER_OR_DIGIT.test(prev) && LETTER_OR_DIGIT.test(next);
  if (THOUSANDS.test(c) && DIGIT.test(prev)) {
    let n = 0;
    while (b + n < cps.length && DIGIT.test(cps[b + n])) n++;
    if (n === 3) return true;
  }
  return LETTER_JOINERS.test(c) && LETTERISH.test(prev) && LETTERISH.test(next);
}

/** Folded text plus, for every folded UTF-16 unit, its index in the original. */
export interface Folded {
  text: string;
  /** map[i] = index in the original string of folded unit i; one extra end sentinel. */
  map: number[];
}

/**
 * The one folding walk, per code point:
 *   - invisible characters (format characters, emoji variation selectors) vanish;
 *   - whitespace and double quote marks become one space, runs collapse;
 *   - apostrophes unify, compatibility forms decompose (NFKD) and then case
 *     folds, so "™" is "tm" and folding twice changes nothing;
 *   - a combining mark is dropped only after a letter of an ACCENTED_SCRIPT,
 *     which also covers marks written as separate characters ("e" + U+0301);
 *   - ß → ss and final ς → σ, as Python's casefold does.
 */
function foldCore(s: string, map: number[] | null, joined = false): string {
  let text = "";
  let i = 0;
  let stripMarks = false;
  const cps = joined ? Array.from(s) : null;
  let k = -1;
  const emit = (unit: string) => {
    if (unit === " " && (text.length === 0 || text[text.length - 1] === " ")) return;
    map?.push(i);
    text += unit;
  };
  for (const ch of s) {
    k++;
    if (INVISIBLE.test(ch) || (cps !== null && joinsAt(cps, k))) {
      // invisible, or a mark inside a word in the joined fold: no output
    } else if (SPACE.test(ch) || QUOTE_MARK.test(ch) || isPunct(ch)) {
      emit(" ");
      stripMarks = false;
    } else {
      // Apostrophes before NFKD (U+00B4 decomposes to a space and an accent)
      // and after it (U+0149 decomposes to U+02BC + n); case after NFKD, so a
      // compatibility capital ("™" → "TM", "𝐃" → "D") is lowered too.
      const decomposed = (DEBURR_LATIN.test(ch) ? deburr(ch) : ch)
        .replace(APOSTROPHES, "'")
        .normalize("NFKD")
        .replace(APOSTROPHES, "'")
        .toLowerCase()
        .normalize("NFKD");
      for (const cp of decomposed) {
        if (INVISIBLE.test(cp)) continue;
        if (MARK.test(cp)) {
          if (stripMarks) continue;
        } else {
          stripMarks = ACCENTED_SCRIPT.test(cp);
        }
        const out =
          cp === "ß"
            ? "ss"
            : cp === "ς"
              ? "σ"
              : SPACE.test(cp) || QUOTE_MARK.test(cp) || isPunct(cp)
                ? " "
                : cp;
        // UTF-16 units, so the map stays one entry per unit of `text`.
        for (let k = 0; k < out.length; k++) emit(out[k]);
      }
    }
    i += ch.length;
  }
  map?.push(i);
  return dropEdgeApostrophes(text, map);
}

/**
 * Drop apostrophes at the edge of a word, in text and query alike, so single
 * quote marks used as quotation (‘than the’) and possessive plurals
 * (students’) match the plain words. One inside a word stays (don't, Tom's).
 * Spaces left doubled or leading by a drop collapse, as `emit` keeps them.
 */
function dropEdgeApostrophes(text: string, map: number[] | null): string {
  if (!text.includes("'")) return text;
  let out = "";
  const kept: number[] = [];
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (c === "'") {
      let j = i + 1;
      while (j < text.length && text[j] === "'") j++;
      const prev = out.length > 0 ? out[out.length - 1] : " ";
      const next = j < text.length ? text[j] : " ";
      if (prev === " " || next === " ") continue;
    } else if (c === " " && (out.length === 0 || out[out.length - 1] === " ")) {
      continue;
    }
    out += c;
    if (map) kept.push(map[i]);
  }
  if (map) {
    kept.push(map[text.length]);
    map.length = 0;
    map.push(...kept);
  }
  return out;
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

/**
 * A folded string used as a KEY (a tag's identity, a style key, a row id):
 * folded and trimmed, since a quote mark at either end folds to a space.
 */
export function foldKey(s: string): string {
  return fold(s).trim();
}

const joinedCache = new Map<string, string>();
const joinedMapCache = new Map<string, Folded>();

/** The joined fold (see "Joined forms"): the plain fold itself (the same
 *  string) when nothing joins, decided once per text and cached. */
function foldJoined(s: string): string {
  const hit = joinedCache.get(s);
  if (hit !== undefined) return hit;
  const text = MAY_JOIN.test(s) ? foldCore(s, null, true) : fold(s);
  if (joinedCache.size >= TEXT_CACHE_MAX) joinedCache.clear();
  joinedCache.set(s, text);
  return text;
}

function foldJoinedWithMap(s: string): Folded {
  if (foldJoined(s) === fold(s)) return foldWithMap(s);
  const hit = joinedMapCache.get(s);
  if (hit) return hit;
  const map: number[] = [];
  const folded = { text: foldCore(s, map, true), map };
  if (joinedMapCache.size >= MAP_CACHE_MAX) joinedMapCache.clear();
  joinedMapCache.set(s, folded);
  return folded;
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
  /** A typed run's joined form, when it differs ("co-op" → "coop"). Runs are
   *  also tried against the text's joined form (see "Joined forms"). */
  joined?: string;
  /** A typed run's singular form, when it differs ("dogs" → "dog", "Mike's" →
   *  "mike"), matched as whole words (see "Plurals"). */
  singular?: string;
}

// ── Plurals and possessives ─────────────────────────────────────────────
//
// "dogs" also finds "dog", "Mike's" also finds "Mike". Harman's S-stemmer
// (Harman 1991, "How effective is suffixing?", JASIS 42:7), the library-science
// classic: -ies → -y (not -eies, -aies), -es → -e (not -aes, -ees, -oes), -s →
// "" (not -us, -ss); and a possessive 's is dropped. Applied to each word of
// a typed run in Latin script, four letters or more, and only as an EXTRA
// form matched as whole words — so it can add matches and never removes one,
// and a stem that is not a word ("thi" from "this") finds nothing. Decided
// 4 Oct 2026.

const LATIN_WORD = /^[\p{Script=Latin}]+$/u;

/** One word's singular by Harman's rules, or the word itself. */
export function singularOf(word: string): string {
  if (word.endsWith("'s")) return word.slice(0, -2);
  if (word.length < 4 || !LATIN_WORD.test(word)) return word;
  if (word.endsWith("ies") && !word.endsWith("eies") && !word.endsWith("aies")) return `${word.slice(0, -3)}y`;
  if (word.endsWith("es") && !/(?:aes|ees|oes)$/.test(word)) return word.slice(0, -1);
  if (word.endsWith("s") && !word.endsWith("us") && !word.endsWith("ss")) return word.slice(0, -1);
  return word;
}

const OPEN_QUOTES = new Set(['"', "“", "”", "„", "«", "»", "「", "」"]);

/** A mark that opens or closes a quoted phrase in a query. */
export function isPhraseQuote(ch: string): boolean {
  return OPEN_QUOTES.has(ch);
}

/** Split a typed query into word and "quoted phrase" terms. */
export function parseQuery(query: string): SearchTerm[] {
  const terms: SearchTerm[] = [];
  let buf = "";
  let inPhrase = false;
  const flush = (kind: "word" | "phrase") => {
    const text = fold(buf).trim();
    const raw = buf;
    buf = "";
    if (!text) return;
    if (kind === "word") {
      // Words typed together are a phrase: "want to go" finds those words in
      // that order, never want, to and go scattered through a quote. It starts
      // at a word start, so the last word may still be being typed — unless
      // punctuation follows it: "why?" is a finished word and does not find
      // "whyever".
      const w = trimApostrophes(text);
      if (!w) return;
      const term = makeTerm("word", w);
      if (endsInPunctuation(raw)) term.whole = true;
      const j = trimApostrophes(foldJoined(raw).trim());
      if (j && j !== w) term.joined = j;
      const sg = w.split(" ").map(singularOf).join(" ");
      if (sg !== w) term.singular = sg;
      terms.push(term);
    } else {
      terms.push(makeTerm("phrase", text));
    }
  };
  for (const ch of query) {
    if (INVISIBLE.test(ch)) continue; // as fold does, so a BOM can't split a word
    if (OPEN_QUOTES.has(ch)) {
      flush(inPhrase ? "phrase" : "word");
      inPhrase = !inPhrase;
    } else {
      buf += ch;
    }
  }
  flush(inPhrase ? "phrase" : "word");
  return terms;
}

/** True when the last visible character typed is punctuation (not an
 *  apostrophe, not a word symbol): the word before it is finished. */
function endsInPunctuation(raw: string): boolean {
  const chars = [...raw.replace(INVISIBLE_G, "").trimEnd()];
  const last = chars[chars.length - 1];
  return last !== undefined && isPunct(last);
}

/** Trim apostrophes from the edges of a run, and the spaces they leave
 *  behind ("` ¨" folds to an apostrophe, a space and a mark). */
function trimApostrophes(w: string): string {
  let a = 0;
  let b = w.length;
  while (a < b && (w[a] === "'" || w[a] === " ")) a++;
  while (b > a && (w[b - 1] === "'" || w[b - 1] === " ")) b--;
  return w.slice(a, b);
}

function makeTerm(kind: "word" | "phrase", text: string): SearchTerm {
  // Where a run may start is decided by its first letter: "東京 tokyo" may
  // start mid-text, "ing 東京" must start a word.
  const first = String.fromCodePoint(text.codePointAt(0) ?? 0);
  return { kind, text, anywhere: kind === "phrase" || UNSPACED.test(first) };
}

/**
 * A term for a known name or label, matched as whole words: "Tom" finds
 * "Tom said" and "Tom's", never "Tomorrow". Used by the tokens that look for a
 * person's name or a tag's name in quote text (docs/design-search.md §5).
 * Unspaced scripts match anywhere. A Korean name may be followed directly by
 * a particle (김민지가) but not by the rest of its own last syllable (김민직).
 * A switch into Chinese, Japanese or Thai also ends a word (Tomさん, 我和Tom说).
 */
export function wholeWordsTerm(text: string): SearchTerm | null {
  const folded = fold(text).trim();
  if (!folded) return null;
  const unspaced = UNSPACED.test(folded);
  return { kind: "phrase", text: folded, anywhere: unspaced, whole: !unspaced };
}

/**
 * Turn selected text into a query that finds it exactly: a quoted phrase,
 * with any double quotes inside it removed so they can't end it early.
 */
export function asPhrase(text: string): string {
  const inner = text.replace(INVISIBLE_G, "").replace(QUOTE_MARKS, " ").replace(/\s+/gu, " ").trim();
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
  // Marks ride on a letter: Thai ำ decomposes to a mark and a vowel, one letter.
  return [...compact].filter((c) => !MARK.test(c)).length >= 2;
}

// ── Matching ────────────────────────────────────────────────────────────

/** The whole code point ending at `i` (exclusive), or "" at the start. */
function codePointBefore(s: string, i: number): string {
  if (i <= 0) return "";
  const low = s.charCodeAt(i - 1);
  if (low >= 0xdc00 && low <= 0xdfff && i >= 2) {
    const high = s.charCodeAt(i - 2);
    if (high >= 0xd800 && high <= 0xdbff) return s.slice(i - 2, i);
  }
  return s[i - 1];
}

/** The whole code point starting at `i`, or "" at the end. */
function codePointAt(s: string, i: number): string {
  const cp = s.codePointAt(i);
  return cp === undefined ? "" : String.fromCodePoint(cp);
}

/**
 * A word starts here when what comes before is not part of a word: the start,
 * a space or punctuation, or a letter of an unspaced script (a Latin brand in
 * Chinese text, 我用iPhone). Marks belong to the letter they follow.
 */
function isWordStart(folded: string, at: number): boolean {
  let i = at;
  let prev = codePointBefore(folded, i);
  while (prev && MARK.test(prev)) {
    i -= prev.length;
    prev = codePointBefore(folded, i);
  }
  if (!prev) return true;
  if (i < at) return UNSPACED.test(prev); // marks after a base: a word char unless unspaced
  return !WORD_CHAR.test(prev) || UNSPACED.test(prev);
}

/** A whole-words term must also end here (see wholeWordsTerm). */
function endsWord(folded: string, end: number, term: SearchTerm): boolean {
  if (!term.whole || end >= folded.length) return true;
  const next = codePointAt(folded, end);
  if (HANGUL_CONTINUES.test(next)) return false; // inside a Korean syllable
  if (UNSPACED.test(next)) return true; // Tomさん, 我和Tom说过
  if (HANGUL.test(next) && HANGUL.test(term.text)) return true; // a particle after a Korean name
  return !WORD_CHAR.test(next);
}

/** Folded start indexes where `term` matches; stops at the first if `firstOnly`. */
function termPositions(folded: string, term: SearchTerm, firstOnly = false): number[] {
  const out: number[] = [];
  let from = 0;
  for (;;) {
    const at = folded.indexOf(term.text, from);
    if (at < 0) break;
    const end = at + term.text.length;
    // A kept combining mark belongs to the letter it follows: a match may not
    // end before one ("ハ" is not the first half of "パ") or begin with one that
    // has a letter before it ("゚ン" is not inside "パン"). A mark with nothing
    // before it, at the start or after a space ("¸" is a space and a cedilla),
    // is not inside a letter.
    const beginsInsideLetter = MARK.test(folded[at]) && at > 0 && folded[at - 1] !== " ";
    const splitsLetter = (end < folded.length && MARK.test(folded[end])) || beginsInsideLetter;
    if ((term.anywhere || isWordStart(folded, at)) && !splitsLetter && endsWord(folded, end, term)) {
      out.push(at);
      if (firstOnly) break;
    }
    from = at + 1;
  }
  return out;
}

/** The term's forms: as typed, joined when it differs, and singular (whole
 *  words) when it differs. */
function forms(term: SearchTerm): SearchTerm[] {
  const out = [term];
  if (term.joined) out.push({ ...term, text: term.joined });
  if (term.singular) out.push({ ...term, text: term.singular, whole: true });
  return out;
}

/** The ways `text` is folded for `term`: a typed run also tries the joined fold. */
function foldsFor(text: string, term: SearchTerm, withMap: true): Folded[];
function foldsFor(text: string, term: SearchTerm, withMap: false): string[];
function foldsFor(text: string, term: SearchTerm, withMap: boolean): Array<Folded | string> {
  const plain = fold(text);
  if (term.kind !== "word") return [withMap ? foldWithMap(text) : plain];
  const joined = foldJoined(text);
  if (joined === plain) return [withMap ? foldWithMap(text) : plain];
  return withMap ? [foldWithMap(text), foldJoinedWithMap(text)] : [plain, joined];
}

/** True when `term` matches somewhere in `text`. */
export function termMatches(text: string, term: SearchTerm): boolean {
  for (const folded of foldsFor(text, term, false)) {
    for (const f of forms(term)) if (termPositions(folded, f, true).length > 0) return true;
  }
  return false;
}

/**
 * True when every term matches in at least one of `fields` (each term may
 * match a different field: `tom "delivery"` finds Tom's quote about delivery;
 * typed together, "tom delivery" is one run and must be said).
 */
export function matchesAll(fields: string[], terms: SearchTerm[]): boolean {
  return terms.every((term) => fields.some((f) => f && termMatches(f, term)));
}

/** Character ranges [start, end) in the ORIGINAL text to mark, merged and sorted. */
export function markRanges(text: string, terms: SearchTerm[]): Array<[number, number]> {
  const ranges: Array<[number, number]> = [];
  for (const term of terms) {
    for (const { text: folded, map } of foldsFor(text, term, true)) {
      for (const f of forms(term)) {
        for (const at of termPositions(folded, f)) {
          // A match can end inside one original character that folded to several
          // units ("ﬁ" → "fi"): extend to that character's end, never a zero width.
          let end = at + f.text.length;
          while (end < folded.length && map[end] === map[end - 1]) end++;
          ranges.push([map[at], map[end]]);
        }
      }
    }
  }
  widenToGraphemes(text, ranges);
  ranges.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const merged: Array<[number, number]> = [];
  for (const r of ranges) {
    const last = merged[merged.length - 1];
    if (last && r[0] <= last[1]) last[1] = Math.max(last[1], r[1]);
    else merged.push([r[0], r[1]]);
  }
  return merged;
}

/**
 * Widen each range to whole user-perceived characters, so a mark never splits
 * an emoji and its skin tone, a flag, or a Devanagari conjunct. A no-op where
 * Intl.Segmenter is missing (it ships in every engine we target).
 */
function widenToGraphemes(text: string, ranges: Array<[number, number]>): void {
  // `lib` is ES2020 here and Intl.Segmenter is ES2022's: typed by hand.
  const Segmenter = (
    Intl as unknown as {
      Segmenter?: new (
        locale: undefined,
        options: { granularity: "grapheme" },
      ) => { segment(s: string): Iterable<{ index: number }> };
    }
  ).Segmenter;
  if (ranges.length === 0 || !Segmenter) return;
  const bounds: number[] = [];
  for (const seg of new Segmenter(undefined, { granularity: "grapheme" }).segment(text)) {
    bounds.push(seg.index);
  }
  bounds.push(text.length);
  const floor = (x: number) => {
    let lo = 0;
    let hi = bounds.length - 1;
    while (lo < hi) {
      const mid = (lo + hi + 1) >> 1;
      if (bounds[mid] <= x) lo = mid;
      else hi = mid - 1;
    }
    return bounds[lo];
  };
  const ceil = (x: number) => {
    let lo = 0;
    let hi = bounds.length - 1;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (bounds[mid] >= x) hi = mid;
      else lo = mid + 1;
    }
    return bounds[lo];
  };
  for (const r of ranges) {
    r[0] = floor(r[0]);
    r[1] = ceil(r[1]);
  }
}
