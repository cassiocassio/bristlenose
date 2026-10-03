/**
 * Toolbar — organism island composing search and the All / Starred view switcher.
 *
 * Connects to QuotesStore for shared filter state.
 *
 * Embedded (macOS) mode: renders nothing. Search and the starred filter are
 * native toolbar controls (wired via the bridge); tag filtering is the tag
 * sidebar. The tag-filter dropdown was removed entirely (v0.16) — superseded by
 * the tag sidebar on every surface.
 *
 * CSV/XLSX export actions moved to ExportDropdown in NavBar (v0.15).
 */

import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { SearchBox, type SearchCombo } from "../components/SearchBox";
import { applyNativeSearchAction, searchSuggestionsFor } from "../components/NativeSearchSync";
import { ViewSwitcher } from "../components/ViewSwitcher";
import { ToolbarButton } from "../components/ToolbarButton";
import {
  clearSearch,
  filterStateOf,
  getSearchPeople,
  removeSearchToken,
  setSearchPeople,
  setSearchTokenMode,
  useQuotesStore,
  setSearchQuery,
  setViewMode,
} from "../contexts/QuotesContext";
import { getPeople } from "../utils/api";
import { foldKey } from "../utils/searchMatch";
import { quoteTags } from "../utils/searchSuggest";
import type { PersonMode, TagMode } from "../utils/searchTokens";
import { useFocusMode, toggleFocusMode } from "../contexts/FocusModeStore";
import { filterQuotes } from "../utils/filter";
import { isEmbedded } from "../utils/embedded";
import { isActiveQuery } from "../utils/searchMatch";
import { useSearchAnnouncement } from "../hooks/useSearchAnnouncement";

// ── Component ─────────────────────────────────────────────────────────

export function Toolbar() {
  const { t } = useTranslation();
  const store = useQuotesStore();
  const focusMode = useFocusMode();

  // ── Derived state ─────────────────────────────────────────────────

  const filterState = filterStateOf(store);

  const visibleCount = useMemo(
    () => filterQuotes(store.quotes, filterState).length,
    [store.quotes, filterState],
  );

  // View switcher label (matches vanilla: shows count when filtered)
  const viewLabel = useMemo(() => {
    if (isActiveQuery(store.searchQuery) || store.searchTokens.length > 0) {
      return t("toolbar.matching", { count: visibleCount });
    }
    return undefined; // default label from ViewSwitcher
  }, [store.searchQuery, store.searchTokens, visibleCount, t]);

  useSearchAnnouncement(store, !isEmbedded());

  // ── Search suggestions and tokens (design-search §4–§6) ─────────────

  // The people list, once, so a person is offered by every name /people knows
  // (the export embeds it). Absent, people are offered by code and by the name
  // on their quotes — degraded, not broken.
  const [peopleLoaded, setPeopleLoaded] = useState(() => getSearchPeople() !== undefined);
  useEffect(() => {
    if (isEmbedded() || peopleLoaded) return;
    let cancelled = false;
    getPeople()
      .then((map) => {
        if (cancelled) return;
        setSearchPeople(map);
        setPeopleLoaded(true);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [peopleLoaded]);

  const combo = useMemo((): SearchCombo => {
    const colours = new Map<string, { colourSet: string; colourIndex: number }>();
    for (const q of store.quotes) {
      for (const tag of quoteTags(q, store.tags)) {
        const key = foldKey(tag.name);
        if (!colours.has(key) && tag.colour_set) {
          colours.set(key, { colourSet: tag.colour_set, colourIndex: tag.colour_index });
        }
      }
    }
    return {
      tokens: store.searchTokens,
      suggestions: isEmbedded() ? [] : searchSuggestionsFor(store),
      tagColour: (name) => colours.get(foldKey(name)) ?? null,
      onChoose: (id) => applyNativeSearchAction("applySearchSuggestion", { id }),
      onTokenMode: (token, mode) => setSearchTokenMode(token, mode as PersonMode | TagMode),
      onTokenRemove: removeSearchToken,
    };
    // peopleLoaded: the people list arrived after the store last changed.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [store, peopleLoaded]);

  // ── Render ────────────────────────────────────────────────────────

  // Embedded: search + starred live in the native toolbar, tags in the sidebar.
  // Nothing left to render in-report.
  if (isEmbedded()) return null;

  return (
    <div className="toolbar" data-testid="bn-toolbar">
      <SearchBox
        value={store.searchQuery}
        onChange={setSearchQuery}
        onClear={clearSearch}
        syncKey={store.searchTokens}
        combo={combo}
        data-testid="bn-toolbar-search"
      />
      <ViewSwitcher
        viewMode={store.viewMode}
        onViewModeChange={setViewMode}
        labelOverride={viewLabel}
        data-testid="bn-toolbar-view-switcher"
      />
      <ToolbarButton
        label={t("toolbar.focusMode")}
        icon={<MoonIcon />}
        className={focusMode ? "toolbar-btn-toggle active" : "toolbar-btn-toggle"}
        aria-pressed={focusMode}
        onClick={toggleFocusMode}
        data-testid="bn-toolbar-focus-mode"
      />
    </div>
  );
}

/**
 * Moon — the same glyph Apple uses for the identically-named feature in Mail's
 * View menu (`moon.circle`). Read as "quiet", not "dark mode": Focus never
 * touches the ground colour, and the button sits with view controls rather than
 * appearance ones.
 */
function MoonIcon() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z" />
    </svg>
  );
}
