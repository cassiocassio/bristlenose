/**
 * One screen-reader announcement per settled search (docs/design-search.md
 * §6): what a VoiceOver user cannot see is how many quotes the search left.
 * Said 700 ms after the query or tokens last changed, so typing produces one
 * announcement, not one per keystroke. Reuses the translated
 * `toolbar.matching` ("N matching").
 *
 * Used by the browser toolbar and, in the Mac app (where the toolbar is
 * native and the web one renders nothing), by NativeSearchSync.
 */

import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { filterStateOf, type QuotesState } from "../contexts/QuotesContext";
import { announce } from "../utils/announce";
import { filterQuotes } from "../utils/filter";
import { isActiveQuery } from "../utils/searchMatch";

export const SEARCH_ANNOUNCE_DELAY_MS = 700;

export function useSearchAnnouncement(store: QuotesState, enabled: boolean): void {
  const { t } = useTranslation();
  const storeRef = useRef(store);
  storeRef.current = store;
  const searching = isActiveQuery(store.searchQuery) || store.searchTokens.length > 0;
  useEffect(() => {
    if (!enabled || !searching) return;
    const timer = setTimeout(() => {
      const s = storeRef.current;
      announce(t("toolbar.matching", { count: filterQuotes(s.quotes, filterStateOf(s)).length }));
    }, SEARCH_ANNOUNCE_DELAY_MS);
    return () => clearTimeout(timer);
  }, [store.searchQuery, store.searchTokens, searching, enabled, t]);
}
