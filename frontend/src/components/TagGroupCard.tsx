/**
 * TagGroupCard — tinted group card with eye toggle, tag rows, and group total.
 *
 * Eye toggle state is read from SidebarStore (persisted to SQLite).
 * Checkbox changes go through to QuotesStore.tagFilter.
 *
 * @module TagGroupCard
 */

import { useCallback, useMemo } from "react";
import type { CodebookTagResponse } from "../utils/types";
import { getTagBg, getBarColour } from "../utils/colours";
import { useSidebarStore } from "../contexts/SidebarStore";
import { EyeToggle } from "./EyeToggle";
import { TagRow } from "./TagRow";

interface TagGroupCardProps {
  name: string;
  subtitle: string;
  colourSet: string;
  tags: CodebookTagResponse[];
  groupBg: string;
  /** Tag counts keyed by lowercase tag name (from QuotesStore). */
  tagCounts: Record<string, number>;
  /** Set of unchecked lowercase tag names. */
  uncheckedSet: Set<string>;
  clearAll: boolean;
  onToggleTag: (tagName: string, checked: boolean) => void;
  /** Called when this group's eye toggle is clicked. */
  onToggleEye?: () => void;
  /** When true, skip the group header row (name, subtitle, group eye).
   *  Used for single-group frameworks where the framework disclosure
   *  already provides collapse + eye toggle, making the group header redundant. */
  hideGroupHeader?: boolean;
}

export function TagGroupCard({
  name,
  subtitle,
  colourSet,
  tags,
  groupBg,
  tagCounts,
  uncheckedSet,
  clearAll,
  onToggleTag,
  onToggleEye,
  hideGroupHeader,
}: TagGroupCardProps) {
  const { hiddenTagGroups } = useSidebarStore();
  const isHidden = hiddenTagGroups.has(name);

  const handleEyeClick = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    onToggleEye?.();
  }, [onToggleEye]);

  // Max count across tags in this group (for micro-bar scaling)
  const maxCount = useMemo(
    () => Math.max(0, ...tags.map((t) => tagCounts[t.name.toLowerCase()] ?? 0)),
    [tags, tagCounts],
  );

  // Group total (sum of visible tag counts)
  const groupTotal = useMemo(
    () => tags.reduce((sum, t) => sum + (tagCounts[t.name.toLowerCase()] ?? 0), 0),
    [tags, tagCounts],
  );

  const barColour = getBarColour(colourSet);

  return (
    <div
      className={`tag-filter-group${isHidden ? " eye-hidden" : ""}`}
      style={{ background: groupBg }}
    >
      {!hideGroupHeader && (
        <div className="tag-filter-group-header-row">
          <div className="tag-filter-group-info">
            <div className="tag-filter-group-name">{name}</div>
            {subtitle && !isHidden && (
              <div className="tag-filter-group-subtitle">{subtitle}</div>
            )}
          </div>
          <EyeToggle
            open={!isHidden}
            onClick={handleEyeClick}
            className="group-eye"
            aria-label={isHidden ? `Show ${name}` : `Hide ${name}`}
          />
        </div>
      )}
      {!isHidden && (
        <>
          <div className="tag-filter-group-tags">
            {tags.map((tag) => {
              const isChecked = !clearAll && !uncheckedSet.has(tag.name.toLowerCase());
              return (
                <TagRow
                  key={tag.id}
                  name={tag.name}
                  checked={isChecked}
                  count={tagCounts[tag.name.toLowerCase()] ?? 0}
                  maxCount={maxCount}
                  badgeBg={getTagBg(colourSet, tag.colour_index)}
                  barColour={barColour}
                  onToggle={onToggleTag}
                />
              );
            })}
          </div>
          {tags.length > 1 && (
            <div className="group-total-row">
              <span className="group-total-label">Total</span>
              <span className="group-total-count">{groupTotal}</span>
            </div>
          )}
        </>
      )}
    </div>
  );
}
