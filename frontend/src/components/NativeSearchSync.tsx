/**
 * NativeSearchSync — the Quotes search menu and tokens for the Mac app's
 * native search field (docs/design-search.md §7).
 *
 * In the Mac app the toolbar field is native and the web SearchBox is not
 * rendered. The native field sends keystrokes (`setSearchQuery`); this
 * component recognises them with the same `suggest()` the browser menu uses
 * and posts the rows back, and `applyNativeSearchAction` carries out what the
 * researcher picks. The SPA stays the source of truth for the query and the
 * tokens; native only draws.
 *
 * Renders `null` and does nothing outside the Mac app.
 */

import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";

import {
  addSearchToken,
  clearSearch,
  filterStateOf,
  getQuotesSnapshot,
  getSearchPeople,
  removeSearchToken,
  setSearchPeople,
  setSearchQuery,
  setSearchTokenMode,
  useQuotesStore,
  type QuotesState,
} from "../contexts/QuotesContext";
import { postSearchBadgeStyles, postSearchSuggestions } from "../shims/bridge";
import {
  probeBadgeStyles,
  type BadgeStyle,
  type BadgeStyles,
  type PersonBadgeStyle,
} from "../utils/badgeStyle";
import { foldKey } from "../utils/searchMatch";
import { getPeople } from "../utils/api";
import { isEmbedded } from "../utils/embedded";
import { isQuoteVisible } from "../utils/filter";
import {
  choiceForId,
  parseMode,
  parseSubject,
  subjectToken,
  suggestionsToWire,
  type ChoiceContext,
  type WireSuggestionRow,
} from "../utils/searchBridge";
import { quoteTags, suggest, type SearchPerson, type Suggestion } from "../utils/searchSuggest";
import type { TagResponse } from "../utils/types";
import { tabFromPath } from "./LensSubtitleSync";
import { useLocaleStore } from "../i18n/LocaleStore";
import { useSearchAnnouncement } from "../hooks/useSearchAnnouncement";

// The project's people, fetched once per mount, are held by the quotes store
// (setSearchPeople) so the menu actions, dispatched from AppLayout outside this
// component, and a code typed into the field ("p3 ") name a person the same way.

/** For tests: what `getPeople()` would have returned. */
export function _setNativeSearchPeople(map: Record<string, SearchPerson> | undefined): void {
  setSearchPeople(map);
}

/** What the menu offers for the store as it stands. Exported for tests. */
export function nativeSuggestions(store: QuotesState, knownPeople = getSearchPeople()) {
  return suggestionsToWire(store.searchQuery, searchSuggestionsFor(store, knownPeople));
}

/**
 * The suggestions for the store's query, under its tokens and filters: the
 * one computation both the Mac field (over the bridge) and the browser field
 * (the toolbar's SearchBox) draw, so they offer the same rows and counts.
 */
export function searchSuggestionsFor(store: QuotesState, knownPeople = getSearchPeople()): Suggestion[] {
  const f = filterStateOf(store);
  const visibleBefore = { ...f, searchQuery: "" };
  return suggest(
    store.searchQuery,
    {
      quotes: store.quotes,
      tags: store.tags,
      edits: store.edits,
      people: knownPeople,
      isVisible: (q) => isQuoteVisible(q, visibleBefore),
    },
    {
      excludeCodes: store.searchTokens.flatMap((t) => (t.kind === "person" ? [t.code] : [])),
      excludeTags: store.searchTokens.flatMap((t) => (t.kind === "tag" ? [t.name] : [])),
    },
  );
}

function choiceContext(store: QuotesState): ChoiceContext {
  const nameOnQuotes = (code: string): string | undefined =>
    store.quotes.find((q) => q.participant_id === code && q.speaker_name && q.speaker_name !== code)
      ?.speaker_name;
  const tags: TagResponse[] = [];
  for (const q of store.quotes) tags.push(...quoteTags(q, store.tags));
  return { people: getSearchPeople(), nameOnQuotes, tags };
}

/**
 * Carry out a search action from the native field. Returns false for an
 * action this module does not own, so the caller's switch can fall through.
 * A payload that does not parse (an unknown subject, a mode the subject can't
 * take, a tag that has since gone) is ignored: the native menu is a mirror,
 * and a stale click must not land on whatever now sits in its place.
 */
export function applyNativeSearchAction(action: string, payload: unknown): boolean {
  const p = (payload ?? {}) as Record<string, unknown>;
  switch (action) {
    case "applySearchSuggestion": {
      const choice = choiceForId(p.id, choiceContext(getQuotesSnapshot()));
      if (choice?.kind === "add-token") {
        addSearchToken(choice.token);
        // A chosen person or tag replaces what was typed to find it (§6).
        setSearchQuery("");
      }
      // "commit-text": the query is already in the store — the native field
      // set it as it was typed — so there is nothing more to apply.
      return true;
    }
    case "setSearchTokenMode": {
      const subject = parseSubject(p.subject);
      const mode = subject && parseMode(subject, p.mode);
      if (subject && mode) setSearchTokenMode(subjectToken(subject), mode);
      return true;
    }
    case "removeSearchToken": {
      const subject = parseSubject(p.subject);
      if (subject) removeSearchToken(subjectToken(subject));
      return true;
    }
    case "clearSearch":
      // The native field's clear button and Esc: the text and every token.
      clearSearch();
      return true;
    default:
      return false;
  }
}

// ── Badge styles for the native menu and chips (§7a) ─────────────────────

/** The badges to measure: a tag by its colour, a person by whether a name shows. */
export interface BadgeSubjects {
  tags: Pick<TagResponse, "name" | "colour_set" | "colour_index">[];
  people: { code: string; name: string | null }[];
}

/**
 * Every badge the native side can draw right now: the people and tags in the
 * menu's rows and in the tokens. A tag carries its colour from the quotes it
 * is on, so a recolour shows. Exported for tests.
 */
export function badgeSubjects(store: QuotesState, rows: WireSuggestionRow[]): BadgeSubjects {
  const known = new Map<string, TagResponse>();
  for (const q of store.quotes) {
    for (const t of quoteTags(q, store.tags)) {
      const key = foldKey(t.name);
      if (!known.has(key)) known.set(key, t);
    }
  }
  const tags = new Map<string, BadgeSubjects["tags"][number]>();
  const people = new Map<string, string | null>();
  const addTag = (key: string, name: string) =>
    tags.set(key, known.get(key) ?? { name, colour_set: "", colour_index: 0 });
  for (const r of rows) {
    if (r.kind === "tag") addTag(r.id.slice("tag:".length), r.label);
    else if (r.kind === "person" && r.code) people.set(r.code, r.label !== r.code ? r.label : null);
  }
  for (const t of store.searchTokens) {
    if (t.kind === "tag") addTag(foldKey(t.name), t.name);
    else if (!people.has(t.code)) people.set(t.code, t.names[0] ?? null);
  }
  return {
    tags: [...tags.values()],
    people: [...people].map(([code, name]) => ({ code, name })),
  };
}

const tagCacheKey = (t: BadgeSubjects["tags"][number]) =>
  `${foldKey(t.name)}|${t.colour_set}|${t.colour_index}`;
const personCacheKey = (p: BadgeSubjects["people"][number]) => `${p.code}|${p.name === null ? 0 : 1}`;

/** Measured styles for one appearance. Cleared when the appearance changes. */
export interface BadgeStyleCache {
  appearance: string;
  tags: Map<string, BadgeStyle>;
  people: Map<string, PersonBadgeStyle>;
}

export function emptyBadgeStyleCache(): BadgeStyleCache {
  return { appearance: "", tags: new Map(), people: new Map() };
}

/**
 * The styles for these subjects, measuring only what this appearance has not
 * measured before. Keyed as the wire's `styleKey`: a folded tag name, a code.
 * A badge that could not be measured is left out, not guessed. Exported for
 * tests, which pass their own `probe`.
 */
export function badgeStylesFor(
  subjects: BadgeSubjects,
  appearance: string,
  cache: BadgeStyleCache,
  probe: (s: BadgeSubjects) => BadgeStyles,
): BadgeStyles {
  if (cache.appearance !== appearance) {
    cache.appearance = appearance;
    cache.tags.clear();
    cache.people.clear();
  }
  const missing: BadgeSubjects = {
    tags: subjects.tags.filter((t) => !cache.tags.has(tagCacheKey(t))),
    people: subjects.people.filter((p) => !cache.people.has(personCacheKey(p))),
  };
  if (missing.tags.length > 0 || missing.people.length > 0) {
    const measured = probe(missing);
    for (const t of missing.tags) {
      const style = measured.tags[foldKey(t.name)];
      if (style) cache.tags.set(tagCacheKey(t), style);
    }
    for (const p of missing.people) {
      const style = measured.people[p.code];
      if (style) cache.people.set(personCacheKey(p), style);
    }
  }
  const out: BadgeStyles = { tags: {}, people: {} };
  for (const t of subjects.tags) {
    const style = cache.tags.get(tagCacheKey(t));
    if (style) out.tags[foldKey(t.name)] = style;
  }
  for (const p of subjects.people) {
    const style = cache.people.get(personCacheKey(p));
    if (style) out.people[p.code] = style;
  }
  return out;
}

/** Light or dark and the palette: what a badge's colours depend on. */
function appearanceSignature(): string {
  const html = document.documentElement;
  const dark =
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-color-scheme: dark)").matches;
  return [
    html.getAttribute("data-theme") ?? "",
    html.getAttribute("data-color-theme") ?? "",
    // Hides a person badge's name half (person-badge.css). Only the static
    // renderer writes it today, so it is watched for the day the SPA does.
    html.getAttribute("data-person-display") ?? "",
    dark ? "dark" : "light",
  ].join("|");
}

/** Re-renders when the appearance changes: the theme, palette or person-display
 *  attribute on <html>, or the system's light/dark (which the Mac app's web view
 *  follows). */
function useAppearanceSignature(enabled: boolean): string {
  const [signature, setSignature] = useState(appearanceSignature);
  useEffect(() => {
    if (!enabled) return;
    const update = () => setSignature(appearanceSignature());
    const observer = new MutationObserver(update);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme", "data-color-theme", "data-person-display"],
    });
    const media =
      typeof window.matchMedia === "function" ? window.matchMedia("(prefers-color-scheme: dark)") : null;
    media?.addEventListener?.("change", update);
    update();
    return () => {
      observer.disconnect();
      media?.removeEventListener?.("change", update);
    };
  }, [enabled]);
  return signature;
}

export function NativeSearchSync(): null {
  const { pathname } = useLocation();
  const onQuotes = tabFromPath(pathname) === "quotes";
  const store = useQuotesStore();
  // Labels come from i18n: a language change must re-post the menu.
  const { locale } = useLocaleStore();
  const [peopleLoaded, setPeopleLoaded] = useState(0);
  const lastPosted = useRef<string | null>(null);
  const lastStyles = useRef<string | null>(null);
  const styleCache = useRef<BadgeStyleCache>(emptyBadgeStyleCache());
  const active = isEmbedded() && onQuotes;
  const appearance = useAppearanceSignature(active);
  // The web toolbar renders nothing in the Mac app, so the count is said here.
  useSearchAnnouncement(store, active);

  // Fetched each time the Quotes lens is entered: a person is renamed in the
  // Sessions lens, and nothing announces it, so the names offered (and the
  // names a "mentions" token looks for) would otherwise be the old ones.
  useEffect(() => {
    if (!isEmbedded() || !onQuotes) return;
    let cancelled = false;
    getPeople()
      .then((map) => {
        if (cancelled) return;
        setSearchPeople(map);
        setPeopleLoaded((n) => n + 1);
      })
      .catch((err) => {
        // Degraded, not broken: people are still offered by code and by the
        // name on their quotes, just not by a name only /people knows.
        console.warn("NativeSearchSync: /people failed; people offered by code", err);
      });
    return () => {
      cancelled = true;
    };
  }, [onQuotes]);

  useEffect(() => {
    if (!active) return;
    const wire = nativeSuggestions(store);
    // The store changes far more often than the menu does (stars, tags,
    // hides): only post when what the native menu would draw has changed.
    const key = JSON.stringify(wire);
    if (key !== lastPosted.current) {
      lastPosted.current = key;
      postSearchSuggestions(wire);
    }

    // The badges those rows and the tokens show, measured off the render
    // (probeBadgeStyles renders a hidden React root of its own, which must not
    // happen inside this commit) and posted only when they change.
    const subjects = badgeSubjects(store, wire.rows);
    const timer = window.setTimeout(() => {
      const host = document.getElementById("bn-app-root") ?? document.body;
      const styles = badgeStylesFor(subjects, appearance, styleCache.current, (s) =>
        probeBadgeStyles(host, s),
      );
      const styleKey = JSON.stringify(styles);
      if (styleKey === lastStyles.current) return;
      lastStyles.current = styleKey;
      postSearchBadgeStyles(styles);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [active, store, peopleLoaded, locale, appearance]);

  return null;
}
