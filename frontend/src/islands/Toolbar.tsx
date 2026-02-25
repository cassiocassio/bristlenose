/**
 * Toolbar — organism island composing search, tag filter, view switcher, and CSV export.
 *
 * Connects to QuotesStore for shared filter state.
 * Manages mutual exclusion of dropdowns.
 * Reuses organisms/toolbar.css (.toolbar).
 */

import { useCallback, useMemo, useState } from "react";
import { SearchBox } from "../components/SearchBox";
import { TagFilterDropdown } from "../components/TagFilterDropdown";
import { ViewSwitcher } from "../components/ViewSwitcher";
import { ToolbarButton } from "../components/ToolbarButton";
import {
  useQuotesStore,
  setSearchQuery,
  setViewMode,
  setTagFilter,
} from "../contexts/QuotesContext";
import { filterQuotes } from "../utils/filter";
import type { FilterState } from "../utils/filter";
import { toast } from "../utils/toast";

// ── Icons ─────────────────────────────────────────────────────────────

function CopyIcon() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <rect x="5" y="1" width="9" height="11" rx="1.5" />
      <path d="M3 5H2.5A1.5 1.5 0 0 0 1 6.5v8A1.5 1.5 0 0 0 2.5 16h8a1.5 1.5 0 0 0 1.5-1.5V14" />
    </svg>
  );
}

// ── CSV builder ───────────────────────────────────────────────────────

function csvEsc(v: string): string {
  if (v.includes(",") || v.includes('"') || v.includes("\n")) {
    return `"${v.replace(/"/g, '""')}"`;
  }
  return v;
}

function formatTimecode(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

// ── Component ─────────────────────────────────────────────────────────

type ActiveDropdown = "none" | "tagFilter" | "viewSwitcher";

export function Toolbar() {
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
      return `${visibleCount} matching`;
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

  // ── CSV export ────────────────────────────────────────────────────

  const handleCsvExport = useCallback(() => {
    const header = ["Timecode", "Quote", "Participant", "Topic", "Sentiment", "Tags"];
    const rows = visibleQuotes.map((q) => {
      const text = store.edits[q.dom_id] ?? q.text;
      const tags = (store.tags[q.dom_id] ?? q.tags).map((t) => t.name).join("; ");
      return [
        csvEsc(formatTimecode(q.start_timecode)),
        csvEsc(text),
        csvEsc(q.speaker_name),
        csvEsc(q.topic_label),
        csvEsc(q.sentiment ?? ""),
        csvEsc(tags),
      ].join(",");
    });

    const csv = [header.join(","), ...rows].join("\n");
    navigator.clipboard
      .writeText(csv)
      .then(() => toast(`${visibleQuotes.length} quotes copied as CSV`))
      .catch(() => toast("Could not copy to clipboard"));
  }, [visibleQuotes, store.edits, store.tags]);

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
      <ToolbarButton
        label="Copy CSV"
        icon={<CopyIcon />}
        onClick={handleCsvExport}
        data-testid="bn-toolbar-csv"
      />
    </div>
  );
}
