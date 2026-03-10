/**
 * TagSidebar — tag filter tree for the Quotes tab right sidebar.
 *
 * Fetches the codebook API, groups tags by framework, renders
 * disclosure trees with eye toggles and tag checkboxes. Shares
 * QuotesStore.tagFilter with the toolbar TagFilterDropdown — changes
 * in either are immediately reflected in both.
 *
 * Eye toggle state (hiddenTagGroups) is persisted to SQLite via
 * SidebarStore. Framework-level hidden is derived: a framework is
 * hidden when ALL its groups are in hiddenTagGroups.
 *
 * @module TagSidebar
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { getCodebook, getHiddenTagGroups } from "../utils/api";
import { getGroupBg } from "../utils/colours";
import type { CodebookResponse, CodebookGroupResponse, CodebookTagResponse } from "../utils/types";
import { EMPTY_TAG_FILTER } from "../utils/filter";
import { useQuotesStore, setTagFilter } from "../contexts/QuotesContext";
import {
  initHiddenTagGroups,
  setTagGroupsHidden,
  toggleTagGroupHidden,
  useSidebarStore,
} from "../contexts/SidebarStore";
import { EyeToggle } from "./EyeToggle";
import { TagGroupCard } from "./TagGroupCard";

// ── Framework metadata (from codebook YAML files) ────────────────────────
// The codebook API returns framework_id on groups but no framework-level
// title/author. This static map provides display names for known frameworks.
// Falls back to capitalising the framework_id for unknown ones.

const FRAMEWORK_META: Record<string, { title: string; author: string }> = {
  sentiment: { title: "Sentiment", author: "" },
  norman:    { title: "The Design of Everyday Things", author: "Don Norman" },
  garrett:   { title: "The Elements of User Experience", author: "Jesse James Garrett" },
  plato:     { title: "Platonic Ontology & Epistemology", author: "Composite — Vlastos, Fine, Kraut, Sedley" },
  uxr:       { title: "Bristlenose UXR Codebook", author: "" },
};

function frameworkTitle(id: string): string {
  return FRAMEWORK_META[id]?.title ?? id.charAt(0).toUpperCase() + id.slice(1);
}

function frameworkAuthor(id: string): string {
  return FRAMEWORK_META[id]?.author ?? "";
}

// ── Framework grouping ────────────────────────────────────────────────────

interface FrameworkGroup {
  id: string;
  title: string;
  author: string;
  groups: CodebookGroupResponse[];
}

/** Group codebook groups by framework_id. Ungrouped → "User Tags". */
function groupByFramework(codebook: CodebookResponse): FrameworkGroup[] {
  const map = new Map<string, FrameworkGroup>();

  for (const g of codebook.groups) {
    const fwId = g.framework_id ?? "_user";
    if (!map.has(fwId)) {
      map.set(fwId, {
        id: fwId,
        title: fwId === "_user" ? "User Tags" : frameworkTitle(fwId),
        author: fwId === "_user" ? "" : frameworkAuthor(fwId),
        groups: [],
      });
    }
    map.get(fwId)!.groups.push(g);
  }

  // Add ungrouped tags as a synthetic group if present
  if (codebook.ungrouped.length > 0) {
    const syntheticGroup: CodebookGroupResponse = {
      id: -1,
      name: "Other",
      subtitle: "",
      colour_set: "",
      order: 9999,
      tags: codebook.ungrouped,
      total_quotes: codebook.ungrouped.reduce((s, t) => s + t.count, 0),
      is_default: false,
      framework_id: null,
    };
    if (map.has("_user")) {
      map.get("_user")!.groups.push(syntheticGroup);
    } else {
      map.set("_ungrouped", {
        id: "_ungrouped",
        title: "User Tags",
        author: "",
        groups: [syntheticGroup],
      });
    }
  }

  return Array.from(map.values());
}

// ── Chevron icon ──────────────────────────────────────────────────────────

function ChevronIcon() {
  return (
    <svg className="codebook-disclosure" width="14" height="14" viewBox="0 0 14 14" fill="currentColor">
      <path d="M5 2.5l5 4.5-5 4.5z" />
    </svg>
  );
}

// ── Component ─────────────────────────────────────────────────────────────

export function TagSidebar() {
  const [codebook, setCodebook] = useState<CodebookResponse | null>(null);
  const [search, setSearch] = useState("");

  const store = useQuotesStore();
  const tagFilter = store.tagFilter;

  const { hiddenTagGroups } = useSidebarStore();

  // Fetch codebook
  useEffect(() => {
    getCodebook().then(setCodebook).catch(() => {});
  }, []);

  // Hydrate hidden tag groups from API on mount
  useEffect(() => {
    getHiddenTagGroups()
      .then((groups) => initHiddenTagGroups(groups))
      .catch(() => {});
  }, []);

  // Re-fetch on autocode tag changes
  useEffect(() => {
    const handler = () => {
      getCodebook().then(setCodebook).catch(() => {});
    };
    document.addEventListener("bn:tags-changed", handler);
    return () => document.removeEventListener("bn:tags-changed", handler);
  }, []);

  // ── Derived data ────────────────────────────────────────────────────

  const frameworks = useMemo(
    () => (codebook ? groupByFramework(codebook) : []),
    [codebook],
  );

  // Derive framework-level hidden from group-level hidden:
  // a framework is hidden when ALL its groups are in hiddenTagGroups.
  const hiddenFrameworks = useMemo(() => {
    const hidden = new Set<string>();
    for (const fw of frameworks) {
      if (
        fw.groups.length > 0 &&
        fw.groups.every((g) => hiddenTagGroups.has(g.name))
      ) {
        hidden.add(fw.id);
      }
    }
    return hidden;
  }, [frameworks, hiddenTagGroups]);

  // Tag counts from QuotesStore (same logic as Toolbar)
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

  const uncheckedSet = useMemo(
    () => new Set(tagFilter.unchecked.map((t) => t.toLowerCase())),
    [tagFilter.unchecked],
  );

  // All tag names for bulk actions
  const allTagNames = useMemo(() => {
    if (!codebook) return [];
    const names: string[] = [];
    for (const g of codebook.groups) {
      for (const t of g.tags) names.push(t.name);
    }
    for (const t of codebook.ungrouped) names.push(t.name);
    return names;
  }, [codebook]);

  // Stats for subtitle
  const totalTags = allTagNames.length;
  const totalFrameworks = frameworks.length;

  // ── Search filter ───────────────────────────────────────────────────

  const searchLower = search.toLowerCase();

  function tagMatchesSearch(t: CodebookTagResponse): boolean {
    return !search || t.name.toLowerCase().includes(searchLower);
  }

  function groupMatchesSearch(g: CodebookGroupResponse): boolean {
    if (!search) return true;
    if (g.name.toLowerCase().includes(searchLower)) return true;
    return g.tags.some(tagMatchesSearch);
  }

  // ── Actions ─────────────────────────────────────────────────────────

  const handleToggleTag = useCallback(
    (tagName: string, checked: boolean) => {
      const lower = tagName.toLowerCase();
      let unchecked: string[];
      if (checked) {
        unchecked = tagFilter.unchecked.filter((t) => t.toLowerCase() !== lower);
      } else {
        unchecked = [...tagFilter.unchecked, tagName];
      }
      setTagFilter({
        unchecked,
        noTagsUnchecked: tagFilter.noTagsUnchecked,
        clearAll: false,
      });
    },
    [tagFilter],
  );

  const handleSelectAll = useCallback(() => {
    setTagFilter(EMPTY_TAG_FILTER);
  }, []);

  const handleClear = useCallback(() => {
    setTagFilter({
      unchecked: allTagNames,
      noTagsUnchecked: true,
      clearAll: true,
    });
  }, [allTagNames]);

  const handleToggleFrameworkEye = useCallback((fw: FrameworkGroup, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const willHide = !hiddenFrameworks.has(fw.id);
    setTagGroupsHidden(fw.groups.map((g) => g.name), willHide);
  }, [hiddenFrameworks]);

  // ── Render ──────────────────────────────────────────────────────────

  if (!codebook) return null;

  return (
    <>
      {/* Subtitle */}
      <div className="tag-sidebar-subtitle">
        {totalTags} tag{totalTags !== 1 ? "s" : ""} across{" "}
        {totalFrameworks} framework{totalFrameworks !== 1 ? "s" : ""}
      </div>

      {/* Actions bar */}
      <div className="tag-sidebar-actions">
        <button type="button" className="tag-filter-action" onClick={handleSelectAll}>
          Select all
        </button>
        <span className="tag-filter-separator">|</span>
        <button type="button" className="tag-filter-action" onClick={handleClear}>
          Clear
        </button>
      </div>

      {/* Search */}
      {totalTags > 8 && (
        <div className="tag-search-container">
          <input
            type="text"
            className="tag-search-input"
            placeholder="Search tags\u2026"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            autoComplete="off"
          />
        </div>
      )}

      {/* Framework tree */}
      <div className="tag-sidebar-body">
        {frameworks.map((fw) => {
          const matchingGroups = fw.groups.filter(groupMatchesSearch);
          if (matchingGroups.length === 0) return null;
          const isFrameworkHidden = hiddenFrameworks.has(fw.id);

          return (
            <details
              key={fw.id}
              className={`codebook-framework${isFrameworkHidden ? " eye-hidden" : ""}`}
              open
            >
              <summary>
                <ChevronIcon />
                <div className="codebook-info">
                  <div className="codebook-title">{fw.title}</div>
                  {fw.author && <div className="codebook-author">{fw.author}</div>}
                </div>
                <EyeToggle
                  open={!isFrameworkHidden}
                  onClick={(e) => handleToggleFrameworkEye(fw, e)}
                  className="codebook-eye"
                  aria-label={isFrameworkHidden ? `Show ${fw.title}` : `Hide ${fw.title}`}
                />
              </summary>
              {!isFrameworkHidden && (
                <div className="codebook-body">
                  {matchingGroups.map((group) => (
                    <TagGroupCard
                      key={group.id}
                      name={group.name}
                      subtitle={group.subtitle}
                      colourSet={group.colour_set}
                      tags={search ? group.tags.filter(tagMatchesSearch) : group.tags}
                      groupBg={getGroupBg(group.colour_set)}
                      tagCounts={tagCounts}
                      uncheckedSet={uncheckedSet}
                      clearAll={tagFilter.clearAll}
                      onToggleTag={handleToggleTag}
                      onToggleEye={() => toggleTagGroupHidden(group.name)}
                      hideGroupHeader={fw.groups.length === 1}
                    />
                  ))}
                </div>
              )}
            </details>
          );
        })}
      </div>
    </>
  );
}
