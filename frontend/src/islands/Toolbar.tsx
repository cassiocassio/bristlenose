/**
 * Toolbar — organism island composing search, tag filter, and view switcher.
 *
 * Connects to QuotesStore for shared filter state.
 * Manages mutual exclusion of dropdowns.
 * Reuses organisms/toolbar.css (.toolbar).
 *
 * CSV/XLSX export actions moved to ExportDropdown in NavBar (v0.15).
 */

import { useCallback, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { SearchBox } from "../components/SearchBox";
import { TagFilterDropdown } from "../components/TagFilterDropdown";
import { ViewSwitcher } from "../components/ViewSwitcher";
import {
  useQuotesStore,
  setSearchQuery,
  setViewMode,
  setTagFilter,
} from "../contexts/QuotesContext";
import { filterQuotes } from "../utils/filter";
import type { FilterState } from "../utils/filter";

// ── Component ─────────────────────────────────────────────────────────

type ActiveDropdown = "none" | "tagFilter" | "viewSwitcher";

export function Toolbar() {
  const { t } = useTranslation();
  const store = useQuotesStore();
  const [activeDropdown, setActiveDropdown] = useState<ActiveDropdown>("none");

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

  const visibleQuotes = useMemo(
    () => filterQuotes(store.quotes, filterState),
    [store.quotes, filterState],
  );

  const visibleCount = visibleQuotes.length;

  // Tag counts: how many quotes have each tag (from all quotes, not just visible)
  const tagCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const q of store.quotes) {
      if (store.hidden[q.dom_id]) continue;
      const tags = store.tags[q.dom_id] ?? q.tags;
      for (const t of tags) {
        const lower = t.name.toLowerCase();
        counts[lower] = (counts[lower] || 0) + 1;
      }
    }
    return counts;
  }, [store.quotes, store.tags, store.hidden]);

  const noTagCount = useMemo(() => {
    let count = 0;
    for (const q of store.quotes) {
      if (store.hidden[q.dom_id]) continue;
      const tags = store.tags[q.dom_id] ?? q.tags;
      if (tags.length === 0) count++;
    }
    return count;
  }, [store.quotes, store.tags, store.hidden]);

  // View switcher label (matches vanilla: shows count when filtered)
  const viewLabel = useMemo(() => {
    if (store.searchQuery.length >= 3) {
      return t("toolbar.matching", { count: visibleCount });
    }
    return undefined; // default label from ViewSwitcher
  }, [store.searchQuery, visibleCount]);

  // ── Dropdown mutual exclusion ─────────────────────────────────────

  const handleTagFilterToggle = useCallback((open: boolean) => {
    setActiveDropdown(open ? "tagFilter" : "none");
  }, []);

  const handleViewSwitcherToggle = useCallback((open: boolean) => {
    setActiveDropdown(open ? "viewSwitcher" : "none");
  }, []);

  // ── Render ────────────────────────────────────────────────────────

  return (
    <div className="toolbar" data-testid="bn-toolbar">
      <SearchBox
        value={store.searchQuery}
        onChange={setSearchQuery}
        data-testid="bn-toolbar-search"
      />
      <TagFilterDropdown
        tagFilter={store.tagFilter}
        onTagFilterChange={setTagFilter}
        tagCounts={tagCounts}
        noTagCount={noTagCount}
        isOpen={activeDropdown === "tagFilter"}
        onToggle={handleTagFilterToggle}
        data-testid="bn-toolbar-tag-filter"
      />
      <ViewSwitcher
        viewMode={store.viewMode}
        onViewModeChange={setViewMode}
        isOpen={activeDropdown === "viewSwitcher"}
        onToggle={handleViewSwitcherToggle}
        labelOverride={viewLabel}
        data-testid="bn-toolbar-view-switcher"
      />
    </div>
  );
}
