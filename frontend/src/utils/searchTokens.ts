/**
 * searchTokens — the person and tag tokens a search can hold, and what each of
 * their meanings lets through (docs/design-search.md §5).
 *
 * A token is chosen from a suggestion (searchSuggest.ts) and then narrows the
 * Quotes lens alongside the typed text, AND-ed with everything else. Its
 * meaning can change without retyping: a person is "said by", "mentions" or
 * "not"; a tag is "tagged", "text contains" or "not tagged".
 */

import { foldKey, isPhraseQuote, termMatches, wholeWordsTerm, type SearchTerm } from "./searchMatch";
import { quoteDisplayText, quoteTags, type SearchPerson } from "./searchSuggest";
import type { QuoteResponse, TagResponse } from "./types";

export type PersonMode = "said" | "mentions" | "not";
export type TagMode = "tagged" | "contains" | "not";

export interface PersonToken {
  kind: "person";
  code: string;
  /** Names to look for when the mode is "mentions" (full, short). May be empty. */
  names: string[];
  mode: PersonMode;
}

export interface TagToken {
  kind: "tag";
  name: string;
  mode: TagMode;
}

export type SearchToken = PersonToken | TagToken;

export const PERSON_MODES: readonly PersonMode[] = ["said", "mentions", "not"];
export const TAG_MODES: readonly TagMode[] = ["tagged", "contains", "not"];

// ── Building tokens ──────────────────────────────────────────────────────

/** A person token, said-by by default, carrying every name we know them by. */
export function personToken(
  code: string,
  person?: SearchPerson,
  nameOnQuotes?: string,
): PersonToken {
  const names = [person?.full_name, person?.short_name, nameOnQuotes]
    .map((n) => n?.trim() ?? "")
    .filter((n) => n && n !== code);
  return { kind: "person", code, names: [...new Set(names)], mode: "said" };
}

/**
 * Take speaker codes typed as whole words out of the query, so they can become
 * person tokens. A code counts once a space (or more typing) follows it, since
 * "m1" on its own may be the start of "m11"; a code inside a quoted phrase is
 * text. Returns the query without those words, and the codes in typed order.
 * `codeOf` answers the project's code for a typed word ("P3" → "p3"), or null.
 */
export function takeCodeTokens(
  query: string,
  codeOf: (word: string) => string | null,
): { query: string; codes: string[] } {
  const codes: string[] = [];
  let out = "";
  let inPhrase = false;
  let i = 0;
  const chars = [...query];
  while (i < chars.length) {
    const ch = chars[i];
    if (isPhraseQuote(ch)) {
      inPhrase = !inPhrase;
      out += ch;
      i++;
      continue;
    }
    if (inPhrase || /\s/u.test(ch)) {
      out += ch;
      i++;
      continue;
    }
    // A word outside a phrase: up to the next space or quote mark.
    let j = i;
    while (j < chars.length && !/\s/u.test(chars[j]) && !isPhraseQuote(chars[j])) j++;
    const word = chars.slice(i, j).join("");
    const followedBySpace = j < chars.length && /\s/u.test(chars[j]);
    const code = followedBySpace ? codeOf(word) : null;
    if (code !== null) {
      if (!codes.includes(code)) codes.push(code);
      while (j < chars.length && /\s/u.test(chars[j])) j++; // and its space
    } else {
      out += word;
    }
    i = j;
  }
  return codes.length === 0 ? { query, codes } : { query: out, codes };
}

/** A tag token, tagged by default. */
export function tagToken(tag: Pick<TagResponse, "name">): TagToken {
  return { kind: "tag", name: tag.name, mode: "tagged" };
}

/** Two tokens name the same person or the same tag (meaning aside). */
export function sameSubject(a: SearchToken, b: SearchToken): boolean {
  if (a.kind === "person" && b.kind === "person") return a.code === b.code;
  if (a.kind === "tag" && b.kind === "tag") return foldKey(a.name) === foldKey(b.name);
  return false;
}

/** "Mentions" needs a name to look for; a code-only person cannot offer it. */
export function canMention(token: SearchToken): boolean {
  return token.kind === "person" && token.names.length > 0;
}

// ── What a token lets through ────────────────────────────────────────────

// Tokens are immutable values in the store, so their terms can be cached by
// identity: the filter asks once per quote.
const termCache = new WeakMap<SearchToken, SearchTerm[]>();

function termsOf(token: SearchToken): SearchTerm[] {
  let terms = termCache.get(token);
  if (!terms) {
    const texts = token.kind === "person" ? token.names : [token.name];
    terms = texts.map(wholeWordsTerm).filter((t): t is SearchTerm => t !== null);
    termCache.set(token, terms);
  }
  return terms;
}

function carriesTag(q: QuoteResponse, name: string, tags?: Record<string, TagResponse[]>): boolean {
  const key = foldKey(name);
  return quoteTags(q, tags).some((t) => foldKey(t.name) === key);
}

/** True when the quote passes this token under its current meaning. */
export function tokenMatches(
  q: QuoteResponse,
  token: SearchToken,
  tags?: Record<string, TagResponse[]>,
  edits?: Record<string, string>,
): boolean {
  if (token.kind === "person") {
    switch (token.mode) {
      case "said":
        return q.participant_id === token.code;
      case "not":
        return q.participant_id !== token.code;
      case "mentions": {
        const text = quoteDisplayText(q, edits);
        return termsOf(token).some((t) => termMatches(text, t));
      }
    }
  }
  switch (token.mode) {
    case "tagged":
      return carriesTag(q, token.name, tags);
    case "not":
      return !carriesTag(q, token.name, tags);
    case "contains": {
      const text = quoteDisplayText(q, edits);
      return termsOf(token).some((t) => termMatches(text, t));
    }
  }
}

/**
 * Terms to highlight in quote text because of this token: a "mentions" or
 * "text contains" token marks what it found, so a quote that doesn't contain
 * the typed word still shows why it is there. Other meanings mark nothing.
 */
export function tokenHighlightTerms(token: SearchToken): SearchTerm[] {
  return token.mode === "mentions" || token.mode === "contains" ? termsOf(token) : [];
}
