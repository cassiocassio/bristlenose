/**
 * ActivityChip — pure display component for a single background job.
 *
 * Shows running/completed/failed/cancelled state. No close button while
 * running — background processes can't be accidentally dismissed.
 * A "Cancel" text button is shown while running if onCancel is provided.
 */

import { useTranslation } from "react-i18next";

export interface ActivityChipJob {
  id: string;
  label: string;
  /** Label shown in completed state (falls back to label if not set). */
  completedLabel?: string;
  status: "running" | "completed" | "failed" | "cancelled";
  progressLabel: string | null;
  durationLabel: string | null;
  errorMessage: string | null;
}

interface ActivityChipProps {
  job: ActivityChipJob;
  /** Called when user clicks the action link (e.g. "View Analysis"). Only shown when completed. */
  onAction?: () => void;
  /** Action link text. */
  actionLabel?: string;
  /** href for the action link (enables Cmd+click to open in new tab). */
  actionHref?: string;
  /** Called when user clicks dismiss. Only rendered when done (completed/failed/cancelled). */
  onDismiss?: () => void;
  /** Called when user clicks cancel. Only rendered while running. */
  onCancel?: () => void;
}

export function ActivityChip({ job, onAction, actionLabel, actionHref, onDismiss, onCancel }: ActivityChipProps) {
  const { t } = useTranslation();
  const isRunning = job.status === "running";
  const isCompleted = job.status === "completed";
  const isFailed = job.status === "failed";
  const isCancelled = job.status === "cancelled";
  const isDone = isCompleted || isFailed || isCancelled;

  return (
    <div className="activity-chip" data-testid="bn-activity-chip" data-status={job.status}>
      {isRunning && (
        <>
          <div className="chip-spinner" />
          <span>
            {job.label}
            {job.progressLabel ? ` ${job.progressLabel}` : ""}
            &hellip;
          </span>
          {onCancel && (
            <button
              className="chip-cancel"
              onClick={onCancel}
              aria-label={t("activity.cancelAriaLabel")}
              data-testid="bn-activity-chip-cancel"
            >
              {t("activity.cancel")}
            </button>
          )}
        </>
      )}
      {isCompleted && (
        <>
          <span className="chip-check">&#x2713;</span>
          <span>
            {job.completedLabel ?? job.label}
            {job.durationLabel ? ` ${t("activity.durationIn", { duration: job.durationLabel })}` : ""}
            .
          </span>
          {onAction && actionLabel && (
            <a
              className="chip-link"
              href={actionHref ?? "#"}
              onClick={(e) => {
                if (e.metaKey || e.ctrlKey || e.shiftKey) return;
                e.preventDefault();
                onAction();
              }}
              data-testid="bn-activity-chip-action"
            >
              {actionLabel}
            </a>
          )}
        </>
      )}
      {isFailed && (
        <>
          <span className="chip-error">&#x2717;</span>
          <span>
            {job.errorMessage
              ? t("activity.failed", { label: job.label, error: job.errorMessage })
              : t("activity.failedNoError", { label: job.label })}
          </span>
        </>
      )}
      {isCancelled && (
        <>
          <span className="chip-error">&#x2717;</span>
          <span>{t("activity.cancelled", { label: job.label })}</span>
        </>
      )}
      {isDone && onDismiss && (
        <button
          className="chip-close"
          onClick={onDismiss}
          aria-label={t("activity.dismiss")}
          data-testid="bn-activity-chip-close"
        >
          &times;
        </button>
      )}
    </div>
  );
}
