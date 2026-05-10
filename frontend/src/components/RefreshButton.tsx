/**
 * RefreshButton — manual backstop for the auto-refetch poll loop.
 *
 * Disabled when no run has completed yet (`lastRun === null`). While the
 * server poll triggered by the click is in flight, shows a spinning icon
 * and no-ops further clicks. Reuses `.toolbar-btn` so it inherits the
 * toolbar control look without a new variant.
 */

import { useCallback, useState } from "react";
import { useTranslation } from "react-i18next";
import { useLastRun, triggerManualRefresh } from "../contexts/LastRunStore";

interface RefreshButtonProps {
  className?: string;
  "data-testid"?: string;
  /**
   * Icon-only mode for NavBar — no text label, uses `.bn-tab.bn-tab-icon`
   * to match Settings / Help / Export. Default false (toolbar-btn style
   * with label, for use inside a `.toolbar`).
   */
  iconOnly?: boolean;
}

function RefreshIcon({ spinning }: { spinning: boolean }) {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.4"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={spinning ? "bn-refresh-icon-spin" : undefined}
      aria-hidden="true"
    >
      <path d="M14 8a6 6 0 1 1-1.76-4.24" />
      <polyline points="14 2 14 5 11 5" />
    </svg>
  );
}

export function RefreshButton({
  className,
  "data-testid": testId,
  iconOnly = false,
}: RefreshButtonProps) {
  const { t } = useTranslation();
  const { lastRun } = useLastRun();
  const [spinning, setSpinning] = useState(false);

  const handleClick = useCallback(async () => {
    if (spinning) return;
    setSpinning(true);
    try {
      await triggerManualRefresh();
    } finally {
      setSpinning(false);
    }
  }, [spinning]);

  // Pre-pipeline / no-data: there's nothing to refresh. Render nothing
  // rather than a greyed-out button — a disabled control with no path
  // to enabled is just visual noise. The empty state copy carries the
  // page; auto-poll handles the warm-up window.
  if (lastRun === null) return null;

  const label = t("buttons.refresh");
  const baseClass = iconOnly ? "bn-tab bn-tab-icon" : "toolbar-btn";
  const classes = [baseClass, className].filter(Boolean).join(" ");

  return (
    <button
      type="button"
      className={classes}
      onClick={handleClick}
      disabled={spinning}
      title={iconOnly ? label : undefined}
      aria-label={iconOnly ? label : undefined}
      data-testid={testId ?? "bn-refresh-btn"}
    >
      {iconOnly ? (
        <RefreshIcon spinning={spinning} />
      ) : (
        <>
          <span className="toolbar-icon-svg">
            <RefreshIcon spinning={spinning} />
          </span>
          {label}
        </>
      )}
    </button>
  );
}
