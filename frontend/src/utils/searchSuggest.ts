/**
 * searchSuggest — what the search menu offers for a typed query.
 *
 * Pure: given the query and the project's data, returns the free-text row and
 * the people and tags the query recognises, each with a count. Nothing here
 * applies a filter; a recogniser only ever OFFERS (docs/design-search.md §4).
 * The UI (browser listbox, native Mac menu) only draws what this returns.
 *
 * Counts are "what would I see if I chose this now": quotes that pass
 * `isVisible` (hidden, starred, tag sidebar, existing tokens) and the row.
 */

import { foldKey, isActiveQuery, matchesAll, parseQuery, type SearchTerm } from "./searchMatch";
import type { QuoteResponse, TagResponse } from "./types";

/** A person as the people endpoint returns them, keyed by speaker code. */
export interface SearchPerson {
  full_name: string;
  short_name: string;
}

export interface SuggestSource {
  quotes: QuoteResponse[];
  /** The store's per-quote tags (QuotesStore.tags); falls back to `quote.tags`. */
  tags?: Record<string, TagResponse[]>;
  /** The store's text edits (QuotesStore.edits), made this session or loaded. */
  edits?: Record<string, string>;
  /** The project's people, keyed by speaker code (GET /people). */
  people?: Record<string, SearchPerson>;
  /** Quotes the researcher can see before this query. Default: all of them. */
  isVisible?: (q: QuoteResponse) => boolean;
}

export interface SuggestOptions {
  /** Most rows per group (default 3). */
  cap?: number;
  /** Speaker codes already present as tokens. */
  excludeCodes?: Iterable<string>;
  /** Tag names already present as tokens (any case). */
  excludeTags?: Iterable<string>;
}

export type Suggestion =
  | { kind: "text"; id: "text"; query: string; count: number }
  | { kind: "person"; id: string; code: string; name: string | null; count: number }
  | { kind: "tag"; id: string; tag: TagResponse; count: number };

// ── What a quote is searched by ─────────────────────────────────────────

/** A quote's current tags: the store's edits if any, else what the server sent. */
export function quoteTags(q: QuoteResponse, tags?: Record<string, TagResponse[]>): TagResponse[] {
  return tags?.[q.dom_id] ?? q.tags;
}

/** The text a researcher sees on the card: their edit if any, else the original. */
export function quoteDisplayText(q: QuoteResponse, edits?: Record<string, string>): string {
  return edits?.[q.dom_id] ?? q.edited_text ?? q.text;
}

/** The fields free text is matched against (spec §3.4). */
export function quoteSearchFields(
  q: QuoteResponse,
  tags?: Record<string, TagResponse[]>,
  edits?: Record<string, string>,
): string[] {
  return [
    quoteDisplayText(q, edits),
    q.speaker_name,
    ...quoteTags(q, tags).map((t) => t.name),
    q.sentiment ?? "",
  ];
}

export function quoteMatches(
  q: QuoteResponse,
  terms: SearchTerm[],
  tags?: Record<string, TagResponse[]>,
  edits?: Record<string, string>,
): boolean {
  return matchesAll(quoteSearchFields(q, tags, edits), terms);
}

// ── Suggest ─────────────────────────────────────────────────────────────

const byNatural = (a: string, b: string) => a.localeCompare(b, undefined, { numeric: true });

export function suggest(
  query: string,
  source: SuggestSource,
  options: SuggestOptions = {},
): Suggestion[] {
  const terms = parseQuery(query);
  if (terms.length === 0) return [];
  const cap = options.cap ?? 3;
  const typed = terms.map((t) => t.text).join(" ");
  const excludeCodes = new Set(options.excludeCodes ?? []);
  const excludeTags = new Set([...(options.excludeTags ?? [])].map(foldKey));
  const visible = source.isVisible ? source.quotes.filter(source.isVisible) : source.quotes;

  const out: Suggestion[] = [];

  // Free text: only once the query is long enough to filter by.
  if (isActiveQuery(query)) {
    let count = 0;
    for (const q of visible) if (quoteMatches(q, terms, source.tags, source.edits)) count++;
    out.push({ kind: "text", id: "text", query, count });
  }

  // One pass over the visible quotes for every count the recognisers need.
  const quotesByCode = new Map<string, number>();
  const nameOnQuotes = new Map<string, string>();
  const tagsByKey = new Map<string, { tag: TagResponse; count: number }>();
  for (const q of visible) {
    const code = q.participant_id;
    if (code) {
      quotesByCode.set(code, (quotesByCode.get(code) ?? 0) + 1);
      if (!nameOnQuotes.has(code) && q.speaker_name && q.speaker_name !== code) {
        nameOnQuotes.set(code, q.speaker_name);
      }
    }
    const seen = new Set<string>();
    for (const tag of quoteTags(q, source.tags)) {
      const key = foldKey(tag.name);
      if (seen.has(key)) continue;
      seen.add(key);
      const entry = tagsByKey.get(key);
      if (entry) entry.count++;
      else tagsByKey.set(key, { tag, count: 1 });
    }
  }

  // People: anyone with a visible quote whose code or name the query starts.
  const people: { s: Suggestion & { kind: "person" }; exact: boolean }[] = [];
  for (const [code, count] of quotesByCode) {
    if (excludeCodes.has(code)) continue;
    const person = source.people?.[code];
    const names = [person?.full_name, person?.short_name, nameOnQuotes.get(code)].filter(
      (n): n is string => Boolean(n),
    );
    if (!matchesAll([code, ...names], terms)) continue;
    const exact = [code, ...names].some((f) => foldKey(f) === typed);
    const name = person?.short_name || person?.full_name || nameOnQuotes.get(code) || null;
    people.push({ s: { kind: "person", id: `person:${code}`, code, name, count }, exact });
  }
  people.sort(
    (a, b) => Number(b.exact) - Number(a.exact) || b.s.count - a.s.count || byNatural(a.s.code, b.s.code),
  );
  out.push(...people.slice(0, cap).map((p) => p.s));

  // Tags: any tag on a visible quote whose name the query starts.
  const tags: { s: Suggestion & { kind: "tag" }; exact: boolean }[] = [];
  for (const [key, { tag, count }] of tagsByKey) {
    if (excludeTags.has(key)) continue;
    if (!matchesAll([tag.name], terms)) continue;
    tags.push({ s: { kind: "tag", id: `tag:${key}`, tag, count }, exact: key === typed });
  }
  tags.sort(
    (a, b) =>
      Number(b.exact) - Number(a.exact) || b.s.count - a.s.count || byNatural(a.s.tag.name, b.s.tag.name),
  );
  out.push(...tags.slice(0, cap).map((t) => t.s));

  return out;
}
