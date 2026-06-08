/**
 * ExpandableTimecode — wraps a timecode element (TimecodeLink or
 * plain <span>) with chevron arrows above/below for context expansion.
 *
 * Arrows appear on hover. Clicks call the expand callbacks with
 * stopPropagation to avoid triggering the parent's video seek.
 */

import type { ReactNode, MouseEvent } from "react";
import { useTranslation } from "react-i18next";

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
  const { t } = useTranslation();
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
          aria-label={t("transcript.showPrevSegment")}
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
          aria-label={t("transcript.showNextSegment")}
          data-testid={testId ? `${testId}-arrow-down` : undefined}
        >
          &#x2303;
        </button>
      )}
    </span>
  );
}
