/**
 * TagRow — single tag in the tag sidebar: checkbox + badge + micro-bar + count.
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
}

export function TagRow({
  name,
  checked,
  count,
  maxCount,
  badgeBg,
  barColour,
  onToggle,
}: TagRowProps) {
  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      onToggle(name, e.target.checked);
    },
    [name, onToggle],
  );

  // Micro-bar width: proportional to max count in the group, min 2px
  const barWidth = maxCount > 0 ? Math.max(2, (count / maxCount) * 100) : 0;

  return (
    <label className="tag-row">
      <span className="tag-name-area">
        <input
          type="checkbox"
          className="bn-checkbox"
          checked={checked}
          onChange={handleChange}
        />
        <span className="badge" style={{ backgroundColor: badgeBg }}>
          {name}
        </span>
      </span>
      <span className="tag-bar-area">
        {count > 0 && (
          <span
            className="tag-micro-bar"
            style={{
              width: `${barWidth}%`,
              backgroundColor: barColour,
            }}
          />
        )}
        <span className="tag-count">{count}</span>
      </span>
    </label>
  );
}
