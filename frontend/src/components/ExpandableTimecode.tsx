/**
 * ExpandableTimecode — wraps a timecode element (TimecodeLink or
 * plain <span>) with chevron arrows above/below for context expansion.
 *
 * Arrows appear on hover. Clicks call the expand callbacks with
 * stopPropagation to avoid triggering the parent's video seek.
 */

import type { ReactNode, MouseEvent } from "react";

interface ExpandableTimecodeProps {
  children: ReactNode;
  canExpandAbove: boolean;
  canExpandBelow: boolean;
  onExpandAbove: () => void;
  onExpandBelow: () => void;
  exhaustedAbove?: boolean;
  exhaustedBelow?: boolean;
  "data-testid"?: string;
}

export function ExpandableTimecode({
  children,
  canExpandAbove,
  canExpandBelow,
  onExpandAbove,
  onExpandBelow,
  exhaustedAbove = false,
  exhaustedBelow = false,
  "data-testid": testId,
}: ExpandableTimecodeProps) {
  const handleClickAbove = (e: MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    onExpandAbove();
  };

  const handleClickBelow = (e: MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    onExpandBelow();
  };

  return (
    <span className="timecode-expandable" data-testid={testId}>
      {canExpandAbove && (
        <button
          className="expand-arrow"
          data-dir="up"
          onClick={handleClickAbove}
          disabled={exhaustedAbove}
          aria-label="Show previous transcript segment"
          data-testid={testId ? `${testId}-arrow-up` : undefined}
        >
          &#x2303;
        </button>
      )}
      {children}
      {canExpandBelow && (
        <button
          className="expand-arrow"
          data-dir="down"
          onClick={handleClickBelow}
          disabled={exhaustedBelow}
          aria-label="Show next transcript segment"
          data-testid={testId ? `${testId}-arrow-down` : undefined}
        >
          &#x2304;
        </button>
      )}
    </span>
  );
}
