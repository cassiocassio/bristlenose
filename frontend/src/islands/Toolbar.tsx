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

import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { SearchBox } from "../components/SearchBox";
import { ViewSwitcher } from "../components/ViewSwitcher";
import { useQuotesStore, setSearchQuery, setViewMode } from "../contexts/QuotesContext";
import { filterQuotes } from "../utils/filter";
import type { FilterState } from "../utils/filter";
import { isEmbedded } from "../utils/embedded";

// ── Component ─────────────────────────────────────────────────────────

export function Toolbar() {
  const { t } = useTranslation();
  const store = useQuotesStore();

  // ── Derived state ─────────────────────────────────────────────────

  const filterState: FilterState = useMemo(
    () => ({
      searchQuery: store.searchQuery,
      viewMode: store.viewMode,
      tagFilter: store.tagFilter,
      hidden: store.hidden,
      starred: store.starred,
      tags: store.tags,
    }),
    [store.searchQuery, store.viewMode, store.tagFilter, store.hidden, store.starred, store.tags],
  );

  const visibleCount = useMemo(
    () => filterQuotes(store.quotes, filterState).length,
    [store.quotes, filterState],
  );

  // View switcher label (matches vanilla: shows count when filtered)
  const viewLabel = useMemo(() => {
    if (store.searchQuery.length >= 3) {
      return t("toolbar.matching", { count: visibleCount });
    }
    return undefined; // default label from ViewSwitcher
  }, [store.searchQuery, visibleCount, t]);

  // ── Render ────────────────────────────────────────────────────────

  // Embedded: search + starred live in the native toolbar, tags in the sidebar.
  // Nothing left to render in-report.
  if (isEmbedded()) return null;

  return (
    <div className="toolbar" data-testid="bn-toolbar">
      <SearchBox
        value={store.searchQuery}
        onChange={setSearchQuery}
        data-testid="bn-toolbar-search"
      />
      <ViewSwitcher
        viewMode={store.viewMode}
        onViewModeChange={setViewMode}
        labelOverride={viewLabel}
        data-testid="bn-toolbar-view-switcher"
      />
    </div>
  );
}
