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
  filterStateOf,
  getQuotesSnapshot,
  removeSearchToken,
  setSearchQuery,
  setSearchTokenMode,
  useQuotesStore,
  type QuotesState,
} from "../contexts/QuotesContext";
import { postSearchSuggestions } from "../shims/bridge";
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
} from "../utils/searchBridge";
import { quoteTags, suggest, type SearchPerson } from "../utils/searchSuggest";
import type { TagResponse } from "../utils/types";
import { tabFromPath } from "./LensSubtitleSync";

// The project's people, fetched once per mount. Module-level so the menu
// actions (dispatched from AppLayout, outside this component) see the same map.
let people: Record<string, SearchPerson> | undefined;

/** For tests: what `getPeople()` would have returned. */
export function _setNativeSearchPeople(map: Record<string, SearchPerson> | undefined): void {
  people = map;
}

/** What the menu offers for the store as it stands. Exported for tests. */
export function nativeSuggestions(store: QuotesState, knownPeople = people) {
  const f = filterStateOf(store);
  const visibleBefore = { ...f, searchQuery: "" };
  const rows = suggest(
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
  return suggestionsToWire(store.searchQuery, rows);
}

function choiceContext(store: QuotesState): ChoiceContext {
  const nameOnQuotes = (code: string): string | undefined =>
    store.quotes.find((q) => q.participant_id === code && q.speaker_name && q.speaker_name !== code)
      ?.speaker_name;
  const tags: TagResponse[] = [];
  for (const q of store.quotes) tags.push(...quoteTags(q, store.tags));
  return { people, nameOnQuotes, tags };
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
    default:
      return false;
  }
}

export function NativeSearchSync(): null {
  const { pathname } = useLocation();
  const onQuotes = tabFromPath(pathname) === "quotes";
  const store = useQuotesStore();
  const [peopleLoaded, setPeopleLoaded] = useState(0);
  const lastPosted = useRef<string | null>(null);

  useEffect(() => {
    if (!isEmbedded()) return;
    let cancelled = false;
    getPeople()
      .then((map) => {
        if (cancelled) return;
        people = map;
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
  }, []);

  useEffect(() => {
    if (!isEmbedded() || !onQuotes) return;
    const wire = nativeSuggestions(store);
    // The store changes far more often than the menu does (stars, tags,
    // hides): only post when what the native menu would draw has changed.
    const key = JSON.stringify(wire);
    if (key === lastPosted.current) return;
    lastPosted.current = key;
    postSearchSuggestions(wire);
  }, [onQuotes, store, peopleLoaded]);

  return null;
}
