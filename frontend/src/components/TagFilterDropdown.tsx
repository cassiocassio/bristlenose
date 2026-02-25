/**
 * TagFilterDropdown — codebook-grouped tag filter for the toolbar.
 *
 * Displays checkboxes for each tag, grouped by codebook group,
 * with group header colours and per-tag quote counts.
 * Includes in-menu search, "Select all" / "Clear" actions.
 *
 * Controlled: receives tagFilter state and fires onTagFilterChange.
 * Uses useDropdown hook for dismiss behaviour.
 *
 * Reuses molecules/tag-filter.css.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { ToolbarButton } from "./ToolbarButton";
import { useDropdown } from "../hooks/useDropdown";
import { getTagBg, getGroupBg } from "../utils/colours";
import { getCodebook } from "../utils/api";
import type { CodebookResponse, CodebookGroupResponse, CodebookTagResponse } from "../utils/types";
import type { TagFilterState } from "../utils/filter";
import { EMPTY_TAG_FILTER } from "../utils/filter";

// ── Icons (inline SVGs matching toolbar.html) ─────────────────────────

function FilterIcon() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
    >
      <line x1="1" y1="3" x2="15" y2="3" />
      <line x1="3" y1="8" x2="13" y2="8" />
      <line x1="5.5" y1="13" x2="10.5" y2="13" />
    </svg>
  );
}

// ── Props ─────────────────────────────────────────────────────────────

export interface TagFilterDropdownProps {
  tagFilter: TagFilterState;
  onTagFilterChange: (filter: TagFilterState) => void;
  /** Tag counts keyed by lowercase tag name. */
  tagCounts: Record<string, number>;
  /** Total number of quotes with no user tags. */
  noTagCount: number;
  /** Controlled open state from parent. */
  isOpen?: boolean;
  onToggle?: (open: boolean) => void;
  "data-testid"?: string;
}

export function TagFilterDropdown({
  tagFilter,
  onTagFilterChange,
  tagCounts,
  noTagCount,
  isOpen,
  onToggle,
  "data-testid": testId,
}: TagFilterDropdownProps) {
  const { open, toggle, containerRef } = useDropdown({ isOpen, onToggle });
  const [codebook, setCodebook] = useState<CodebookResponse | null>(null);
  const [menuSearch, setMenuSearch] = useState("");

  // Fetch codebook on first open
  useEffect(() => {
    if (open && !codebook) {
      getCodebook().then(setCodebook).catch(() => {});
    }
  }, [open, codebook]);

  // Flatten all tag names for counting
  const allTagNames = useMemo(() => {
    if (!codebook) return [];
    const names: string[] = [];
    for (const g of codebook.groups) {
      for (const t of g.tags) names.push(t.name);
    }
    for (const t of codebook.ungrouped) names.push(t.name);
    return names;
  }, [codebook]);

  const uncheckedSet = useMemo(
    () => new Set(tagFilter.unchecked.map((t) => t.toLowerCase())),
    [tagFilter.unchecked],
  );

  const checkedCount = useMemo(() => {
    if (tagFilter.clearAll) return 0;
    return allTagNames.filter((n) => !uncheckedSet.has(n.toLowerCase())).length;
  }, [allTagNames, uncheckedSet, tagFilter.clearAll]);

  const totalTags = allTagNames.length;

  // ── Actions ───────────────────────────────────────────────────────

  const handleToggleTag = useCallback(
    (tagName: string, checked: boolean) => {
      const lower = tagName.toLowerCase();
      let unchecked: string[];
      if (checked) {
        unchecked = tagFilter.unchecked.filter((t) => t.toLowerCase() !== lower);
      } else {
        unchecked = [...tagFilter.unchecked, tagName];
      }
      onTagFilterChange({
        unchecked,
        noTagsUnchecked: tagFilter.noTagsUnchecked,
        clearAll: false,
      });
    },
    [tagFilter, onTagFilterChange],
  );

  const handleToggleNoTags = useCallback(
    (checked: boolean) => {
      onTagFilterChange({
        ...tagFilter,
        noTagsUnchecked: !checked,
        clearAll: false,
      });
    },
    [tagFilter, onTagFilterChange],
  );

  const handleSelectAll = useCallback(() => {
    onTagFilterChange(EMPTY_TAG_FILTER);
  }, [onTagFilterChange]);

  const handleClear = useCallback(() => {
    onTagFilterChange({
      unchecked: allTagNames,
      noTagsUnchecked: true,
      clearAll: true,
    });
  }, [onTagFilterChange, allTagNames]);

  // ── Label ─────────────────────────────────────────────────────────

  const label = useMemo(() => {
    if (tagFilter.clearAll) return "No tags";
    // If nothing is unchecked and noTags is included → generic label
    if (tagFilter.unchecked.length === 0 && !tagFilter.noTagsUnchecked) return "Tags";
    // Show checked count (codebook loaded) or indicate active filter (not yet loaded)
    if (totalTags > 0) return `${checkedCount} tags`;
    return `${tagFilter.unchecked.length} hidden`;
  }, [checkedCount, totalTags, tagFilter.clearAll, tagFilter.noTagsUnchecked, tagFilter.unchecked]);

  // ── Filtering within menu ─────────────────────────────────────────

  const menuSearchLower = menuSearch.toLowerCase();

  function tagMatchesMenuSearch(t: CodebookTagResponse) {
    return !menuSearch || t.name.toLowerCase().includes(menuSearchLower);
  }

  function groupHasMatchingTags(g: CodebookGroupResponse) {
    return g.tags.some(tagMatchesMenuSearch);
  }

  // ── Render ────────────────────────────────────────────────────────

  return (
    <div className="tag-filter" ref={containerRef} data-testid={testId}>
      <ToolbarButton
        label={<span className="tag-filter-label">{label}</span>}
        icon={<FilterIcon />}
        arrow
        expanded={open}
        onClick={toggle}
        className="tag-filter-btn"
        data-testid={testId ? `${testId}-btn` : undefined}
      />
      {open && codebook && (
        <div
          className="tag-filter-menu open"
          data-testid={testId ? `${testId}-menu` : undefined}
        >
          {/* Actions bar */}
          <div className="tag-filter-actions">
            <button
              type="button"
              className="tag-filter-action"
              onClick={handleSelectAll}
              data-testid={testId ? `${testId}-select-all` : undefined}
            >
              Select all
            </button>
            <span className="tag-filter-separator">|</span>
            <button
              type="button"
              className="tag-filter-action"
              onClick={handleClear}
              data-testid={testId ? `${testId}-clear` : undefined}
            >
              Clear
            </button>
          </div>

          {/* In-menu search */}
          {totalTags > 8 && (
            <div className="tag-filter-search">
              <input
                type="text"
                className="tag-filter-search-input"
                placeholder="Search tags\u2026"
                value={menuSearch}
                onChange={(e) => setMenuSearch(e.target.value)}
                autoComplete="off"
                data-testid={testId ? `${testId}-search` : undefined}
              />
            </div>
          )}

          {/* "(No tags)" option */}
          {(!menuSearch || "(no tags)".includes(menuSearchLower)) && (
            <label className="tag-filter-item tag-filter-item-muted">
              <input
                type="checkbox"
                checked={!tagFilter.noTagsUnchecked && !tagFilter.clearAll}
                onChange={(e) => handleToggleNoTags(e.target.checked)}
              />
              <span>(No tags)</span>
              <span className="tag-filter-count">{noTagCount}</span>
            </label>
          )}

          {/* Grouped tags */}
          {codebook.groups
            .filter(groupHasMatchingTags)
            .map((group) => (
              <div
                key={group.id}
                className="tag-filter-group"
                style={{ background: getGroupBg(group.colour_set) }}
              >
                <div className="tag-filter-group-header">{group.name}</div>
                {group.tags.filter(tagMatchesMenuSearch).map((tag) => {
                  const isChecked =
                    !tagFilter.clearAll &&
                    !uncheckedSet.has(tag.name.toLowerCase());
                  return (
                    <label key={tag.id} className="tag-filter-item">
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={(e) => handleToggleTag(tag.name, e.target.checked)}
                      />
                      <span
                        className="tag-filter-badge badge badge-user"
                        style={{ backgroundColor: getTagBg(group.colour_set, tag.colour_index) }}
                      >
                        {tag.name}
                      </span>
                      <span className="tag-filter-count">
                        {tagCounts[tag.name.toLowerCase()] ?? 0}
                      </span>
                    </label>
                  );
                })}
              </div>
            ))}

          {/* Ungrouped tags */}
          {codebook.ungrouped.filter(tagMatchesMenuSearch).length > 0 && (
            <>
              <div className="tag-filter-divider" />
              {codebook.ungrouped.filter(tagMatchesMenuSearch).map((tag) => {
                const isChecked =
                  !tagFilter.clearAll &&
                  !uncheckedSet.has(tag.name.toLowerCase());
                return (
                  <label key={tag.id} className="tag-filter-item">
                    <input
                      type="checkbox"
                      checked={isChecked}
                      onChange={(e) => handleToggleTag(tag.name, e.target.checked)}
                    />
                    <span className="tag-filter-badge badge badge-user">
                      {tag.name}
                    </span>
                    <span className="tag-filter-count">
                      {tagCounts[tag.name.toLowerCase()] ?? 0}
                    </span>
                  </label>
                );
              })}
            </>
          )}
        </div>
      )}
    </div>
  );
}
