/**
 * TagRow — single tag in the tag sidebar: checkbox + badge + micro-bar + count.
 *
 * The checkbox toggles tag visibility (filter). The badge assigns the tag
 * to selected quotes (when `onAssign` is provided and quotes are selected).
 *
 * Uses the MicroBar atom for the proportional bar — supports two-tone
 * (tentative + accepted) when `tentativeCount` is provided.
 *
 * @module TagRow
 */

import { useCallback } from "react";
import { MicroBar } from "./MicroBar";

interface TagRowProps {
  name: string;
  checked: boolean;
  count: number;
  /** Pending autocode proposal count for this tag. */
  tentativeCount?: number;
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
  tentativeCount = 0,
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

  const hasTentative = tentativeCount > 0;
  const acceptedFrac = maxCount > 0 ? count / maxCount : 0;
  const tentativeFrac = maxCount > 0 ? tentativeCount / maxCount : 0;

  const badgeClassName = `badge${assignActive ? " badge-assignable" : ""}${flashing ? " badge-accept-flash" : ""}`;

  return (
    <div className={`tag-row${soloFocused ? " tag-row-solo-focused" : ""}`}>
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
        {hasTentative ? (
          <MicroBar
            value={acceptedFrac}
            tentativeValue={tentativeFrac}
            colour={barColour}
            title={`${tentativeCount} tentative + ${count} accepted`}
          />
        ) : count > 0 ? (
          <MicroBar value={acceptedFrac} colour={barColour} />
        ) : null}
        <span className={`tag-count${soloFocused ? " tag-solo-focused" : ""}`}>
          {count}
        </span>
      </span>
    </div>
  );
}
