/**
 * ActivityChip — pure display component for a single background job.
 *
 * Shows running/completed/failed/cancelled state. No close button while
 * running — background processes can't be accidentally dismissed.
 * A "Cancel" text button is shown while running if onCancel is provided.
 */

export interface ActivityChipJob {
  id: string;
  label: string;
  status: "running" | "completed" | "failed" | "cancelled";
  progressLabel: string | null;
  durationLabel: string | null;
  errorMessage: string | null;
}

interface ActivityChipProps {
  job: ActivityChipJob;
  /** Called when user clicks the action link (e.g. "Report"). Only shown when completed. */
  onAction?: () => void;
  /** Action link text. */
  actionLabel?: string;
  /** Called when user clicks dismiss. Only rendered when done (completed/failed/cancelled). */
  onDismiss?: () => void;
  /** Called when user clicks cancel. Only rendered while running. */
  onCancel?: () => void;
}

export function ActivityChip({ job, onAction, actionLabel, onDismiss, onCancel }: ActivityChipProps) {
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
              aria-label="Cancel"
              data-testid="bn-activity-chip-cancel"
            >
              Cancel
            </button>
          )}
        </>
      )}
      {isCompleted && (
        <>
          <span className="chip-check">&#x2713;</span>
          <span>
            {job.label}
            {job.durationLabel ? ` in ${job.durationLabel}` : ""}
            .
          </span>
          {onAction && actionLabel && (
            // eslint-disable-next-line jsx-a11y/anchor-is-valid
            <a
              className="chip-link"
              onClick={onAction}
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
            {job.label} failed{job.errorMessage ? `: ${job.errorMessage}` : ""}.
          </span>
        </>
      )}
      {isCancelled && (
        <>
          <span className="chip-error">&#x2717;</span>
          <span>{job.label} cancelled.</span>
        </>
      )}
      {isDone && onDismiss && (
        <button
          className="chip-close"
          onClick={onDismiss}
          aria-label="Dismiss"
          data-testid="bn-activity-chip-close"
        >
          &times;
        </button>
      )}
    </div>
  );
}
