/**
 * TagRow — single tag in the tag sidebar: checkbox + badge + micro-bar + count.
 *
 * The checkbox toggles tag visibility (filter). The badge assigns the tag
 * to selected quotes (when `onAssign` is provided and quotes are selected).
 *
 * Uses sidebar-tags.css classes (.tag-row, .tag-name-area, .badge,
 * .tag-bar-area, .tag-micro-bar, .tag-count).
 *
 * @module TagRow
 */

import { useCallback } from "react";

interface TagRowProps {
  name: string;
  checked: boolean;
  count: number;
  maxCount: number;
  badgeBg: string;
  barColour: string;
  onToggle: (tagName: string, checked: boolean) => void;
  /** Called when the badge is clicked to assign the tag to selected quotes. */
  onAssign?: (tagName: string) => void;
  /** Whether quotes are selected (controls cursor + tabIndex on badge). */
  assignActive?: boolean;
  /** Whether the sidebar badge should flash (accept animation). */
  flashing?: boolean;
  /** Called when the bar area (micro-bar + count) is clicked to solo this tag. */
  onSoloClick?: (tagName: string) => void;
  /** Whether this tag is the active solo target (blue highlight on count). */
  soloFocused?: boolean;
}

export function TagRow({
  name,
  checked,
  count,
  maxCount,
  badgeBg,
  barColour,
  onToggle,
  onAssign,
  assignActive,
  flashing,
  onSoloClick,
  soloFocused,
}: TagRowProps) {
  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      onToggle(name, e.target.checked);
    },
    [name, onToggle],
  );

  const handleBadgeClick = useCallback(
    (e: React.MouseEvent) => {
      if (onAssign && assignActive) {
        e.preventDefault();
        e.stopPropagation();
        onAssign(name);
      }
    },
    [name, onAssign, assignActive],
  );

  const handleBadgeKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (onAssign && assignActive && (e.key === "Enter" || e.key === " ")) {
        e.preventDefault();
        onAssign(name);
      }
    },
    [name, onAssign, assignActive],
  );

  const handleBarClick = useCallback(() => {
    onSoloClick?.(name);
  }, [name, onSoloClick]);

  const handleBarKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (onSoloClick && (e.key === "Enter" || e.key === " ")) {
        e.preventDefault();
        onSoloClick(name);
      }
    },
    [name, onSoloClick],
  );

  // Micro-bar width: proportional to max count in the group, min 2px
  const barWidth = maxCount > 0 ? Math.max(2, (count / maxCount) * 100) : 0;

  const badgeClassName = `badge${assignActive ? " badge-assignable" : ""}${flashing ? " badge-accept-flash" : ""}`;

  return (
    <div className="tag-row">
      <span className="tag-name-area">
        <label className="tag-checkbox-label">
          <input
            type="checkbox"
            className="bn-checkbox"
            checked={checked}
            onChange={handleChange}
          />
        </label>
        <span
          className={badgeClassName}
          style={{ backgroundColor: badgeBg }}
          role={onAssign ? "button" : undefined}
          tabIndex={onAssign && assignActive ? 0 : -1}
          onClick={handleBadgeClick}
          onKeyDown={handleBadgeKeyDown}
          aria-label={assignActive ? `Assign ${name} to selected quotes` : undefined}
        >
          {name}
        </span>
      </span>
      <span
        className="tag-bar-area"
        onClick={onSoloClick ? handleBarClick : undefined}
        onKeyDown={onSoloClick ? handleBarKeyDown : undefined}
        role={onSoloClick ? "button" : undefined}
        tabIndex={onSoloClick ? 0 : undefined}
        aria-label={onSoloClick ? `Focus on ${name} quotes` : undefined}
      >
        {count > 0 && (
          <span
            className="tag-micro-bar"
            style={{
              width: `${barWidth}%`,
              backgroundColor: barColour,
            }}
          />
        )}
        <span className={`tag-count${soloFocused ? " tag-solo-focused" : ""}`}>
          {count}
        </span>
      </span>
    </div>
  );
}
