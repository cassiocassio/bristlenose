/**
 * searchBridge — the search menu and tokens as they cross to the Mac app
 * (docs/design-search.md §7, the bridge contract).
 *
 * The SPA stays the source of truth: it recognises, counts and labels, and the
 * native side only draws what arrives here and sends back what was chosen. So
 * every label is localised on this side, and the native app adds no locale
 * keys. Pure: no store access, no posting — the caller supplies the data and
 * does the I/O, which is what lets one fixture pin both ends of the wire
 * (tests/fixtures/search-bridge-contract.json).
 *
 * Offsets in `typed` are UTF-16 code units, the unit of a JS string and of an
 * `NSString`/`NSRange`, so Swift must index with `utf16`, not `Character`s.
 *
 * Copy: the English below is the spec's (§8) and renders through
 * `defaultValue`; the locale keys are added with the browser UI (P4), once the
 * owner has settled the wording, so they are not seeded into 21 files twice.
 */

import i18n from "../i18n";
import { foldKey, markRanges, parseQuery } from "./searchMatch";
import type { SearchPerson, Suggestion } from "./searchSuggest";
import {
  canMention,
  PERSON_MODES,
  personToken,
  TAG_MODES,
  tagToken,
  type PersonMode,
  type SearchToken,
  type TagMode,
} from "./searchTokens";
import type { TagResponse } from "./types";

// ── The wire ────────────────────────────────────────────────────────────

/** A person or a tag, as the store addresses tokens: never by position. */
export type WireSubject = { kind: "person"; code: string } | { kind: "tag"; name: string };

export interface WireSuggestionRow {
  /** Stable for the subject: `text`, `person:<code>`, `tag:<folded name>`. */
  id: string;
  kind: "text" | "person" | "tag";
  /** Localised, ready to draw. */
  label: string;
  /** Where the typed words fall in `label`, as UTF-16 [start, end) offsets. */
  typed: Array<[number, number]>;
  count: number;
  /** Person rows only: the speaker code the badge shows. */
  code?: string;
}

export interface WireSuggestions {
  query: string;
  rows: WireSuggestionRow[];
}

export interface WireTokenMode {
  id: string;
  /** The menu item: "Said by Priya Shah". */
  label: string;
  /** The word the chip shows before the badge while this meaning is chosen:
   *  "said by". Lower case, as it reads inside the field (§5). */
  word: string;
  enabled: boolean;
}

export interface WireToken {
  kind: "person" | "tag";
  subject: WireSubject;
  /** Key into `search-badge-styles`: the speaker code, or the folded tag
   *  name — folded here so Swift never has to reproduce `fold`. A row's key
   *  is its id after the `person:`/`tag:` prefix. */
  styleKey: string;
  /** The person's name (or code) or the tag's name. */
  label: string;
  /** The last item of the chip's menu. */
  removeLabel: string;
  mode: string;
  modes: WireTokenMode[];
}

// ── Web → native ────────────────────────────────────────────────────────

const t = (key: string, defaultValue: string, vars: Record<string, string> = {}) =>
  i18n.t(key, { defaultValue, ...vars });

const SENTINEL = "\u0000";

/**
 * The free-text row's label and where the typed query sits in it. The label is
 * rendered once with a sentinel to find the placeholder, so the range lands on
 * the query and never on the template's own words ("containing", "Quotes"), in
 * any language. Values are not escaped (i18n escapeValue: false), so offsets
 * before the placeholder are the same in both renderings.
 */
function textRowLabel(query: string): { label: string; typed: Array<[number, number]> } {
  const key = "search.suggest.textRow";
  const fallback = "Quotes containing “{{query}}”";
  const at = t(key, fallback, { query: SENTINEL }).indexOf(SENTINEL);
  const label = t(key, fallback, { query });
  return { label, typed: at < 0 || !query ? [] : [[at, at + query.length]] };
}

/** The suggestion rows as the native menu draws them. */
/** What a screen reader hears for a row: the label (a person with their code
 *  first, as the badge shows it), then the count after a pause. The same
 *  string the Mac list speaks (`SuggestionLabel.spoken`). */
export function spokenRow(row: WireSuggestionRow): string {
  const label =
    row.kind === "person" && row.code && row.label !== row.code ? `${row.code} ${row.label}` : row.label;
  return `${label}, ${row.count.toLocaleString()}`;
}

export function suggestionsToWire(query: string, suggestions: Suggestion[]): WireSuggestions {
  const terms = parseQuery(query);
  const rows = suggestions.map((s): WireSuggestionRow => {
    switch (s.kind) {
      case "text": {
        const { label, typed } = textRowLabel(s.query);
        return { id: s.id, kind: "text", label, typed, count: s.count };
      }
      case "person": {
        const label = s.name ?? s.code;
        return {
          id: s.id, kind: "person", label, typed: markRanges(label, terms), count: s.count,
          code: s.code,
        };
      }
      case "tag": {
        const label = s.tag.name;
        return { id: s.id, kind: "tag", label, typed: markRanges(label, terms), count: s.count };
      }
    }
  });
  return { query, rows };
}

const PERSON_MODE_COPY: Record<PersonMode, [string, string]> = {
  said: ["search.token.person.said", "Said by {{name}}"],
  mentions: ["search.token.person.mentions", "Mentions {{name}}"],
  not: ["search.token.person.not", "Not {{name}}"],
};

const TAG_MODE_COPY: Record<TagMode, [string, string]> = {
  tagged: ["search.token.tag.tagged", "Tagged “{{tag}}”"],
  contains: ["search.token.tag.contains", "Text contains “{{tag}}”"],
  not: ["search.token.tag.not", "Not tagged “{{tag}}”"],
};

/** The chip's word for each meaning, shown before the badge. */
const PERSON_MODE_WORD: Record<PersonMode, [string, string]> = {
  said: ["search.token.person.saidWord", "said by"],
  mentions: ["search.token.person.mentionsWord", "mentions"],
  not: ["search.token.person.notWord", "not"],
};

const TAG_MODE_WORD: Record<TagMode, [string, string]> = {
  tagged: ["search.token.tag.taggedWord", "tagged"],
  contains: ["search.token.tag.containsWord", "contains"],
  not: ["search.token.tag.notWord", "not tagged"],
};

/** How a token is named in its menu: the person's first known name, else
 *  their code; the tag's name. */
export function tokenLabel(token: SearchToken): string {
  return token.kind === "person" ? (token.names[0] ?? token.code) : token.name;
}

/** A token's key into `search-badge-styles` (see `WireToken.styleKey`). */
export function styleKeyOf(token: SearchToken): string {
  return token.kind === "person" ? token.code : foldKey(token.name);
}

export function subjectOf(token: SearchToken): WireSubject {
  return token.kind === "person"
    ? { kind: "person", code: token.code }
    : { kind: "tag", name: token.name };
}

/** The tokens as the native chips and their meaning menus draw them. */
export function tokensToWire(tokens: SearchToken[]): WireToken[] {
  return tokens.map((token) => {
    const label = tokenLabel(token);
    const modes: WireTokenMode[] =
      token.kind === "person"
        ? PERSON_MODES.map((id) => ({
            id,
            label: t(PERSON_MODE_COPY[id][0], PERSON_MODE_COPY[id][1], { name: label }),
            word: t(PERSON_MODE_WORD[id][0], PERSON_MODE_WORD[id][1]),
            enabled: id !== "mentions" || canMention(token),
          }))
        : TAG_MODES.map((id) => ({
            id,
            label: t(TAG_MODE_COPY[id][0], TAG_MODE_COPY[id][1], { tag: label }),
            word: t(TAG_MODE_WORD[id][0], TAG_MODE_WORD[id][1]),
            enabled: true,
          }));
    return {
      kind: token.kind, subject: subjectOf(token), styleKey: styleKeyOf(token), label,
      removeLabel: t("search.token.remove", "Remove"),
      mode: token.mode, modes,
    };
  });
}

// ── Native → web ────────────────────────────────────────────────────────
//
// Payloads arrive from Swift, so each is checked rather than trusted: an
// unknown kind or a missing field is "nothing to do", never a throw inside the
// menu-action switch.

export function parseSubject(raw: unknown): WireSubject | null {
  if (!raw || typeof raw !== "object") return null;
  const r = raw as Record<string, unknown>;
  if (r.kind === "person" && typeof r.code === "string" && r.code) {
    return { kind: "person", code: r.code };
  }
  if (r.kind === "tag" && typeof r.name === "string" && r.name) {
    return { kind: "tag", name: r.name };
  }
  return null;
}

/** A store token with this subject and a placeholder meaning, for the store's
 *  subject-addressed actions (which compare person by code, tag by folded name). */
export function subjectToken(subject: WireSubject): SearchToken {
  return subject.kind === "person"
    ? { kind: "person", code: subject.code, names: [], mode: "said" }
    : { kind: "tag", name: subject.name, mode: "tagged" };
}

/** The mode, if it is one this subject can take. */
export function parseMode(subject: WireSubject, raw: unknown): PersonMode | TagMode | null {
  if (typeof raw !== "string") return null;
  const modes: readonly string[] = subject.kind === "person" ? PERSON_MODES : TAG_MODES;
  return modes.includes(raw) ? (raw as PersonMode | TagMode) : null;
}

/** What applying a suggestion does to the store. */
export type SuggestionChoice =
  | { kind: "commit-text" }
  | { kind: "add-token"; token: SearchToken };

export interface ChoiceContext {
  /** The project's people, keyed by speaker code. */
  people?: Record<string, SearchPerson>;
  /** The name quotes carry for each code, when the people list has none. */
  nameOnQuotes?: (code: string) => string | undefined;
  /** Every tag the project knows (any quote's, any spelling). */
  tags: Iterable<Pick<TagResponse, "name">>;
}

/**
 * Turn a row id from the native menu into a choice. The id names its subject,
 * so a click that lands after the query has changed still adds the person or
 * tag the researcher saw — never whatever now sits in that row.
 */
export function choiceForId(id: unknown, ctx: ChoiceContext): SuggestionChoice | null {
  if (id === "text") return { kind: "commit-text" };
  if (typeof id !== "string") return null;
  if (id.startsWith("person:")) {
    const code = id.slice("person:".length);
    if (!code) return null;
    return {
      kind: "add-token",
      token: personToken(code, ctx.people?.[code], ctx.nameOnQuotes?.(code)),
    };
  }
  if (id.startsWith("tag:")) {
    const key = id.slice("tag:".length);
    if (!key) return null;
    for (const tag of ctx.tags) {
      if (foldKey(tag.name) === key) return { kind: "add-token", token: tagToken(tag) };
    }
    return null; // the tag has gone since the menu was drawn
  }
  return null;
}
