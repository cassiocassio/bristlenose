/**
 * ActivityChipStack — container for 0-N background job chips.
 *
 * Renders via createPortal to document.body so chips persist across tab
 * navigation. Owns polling for each job. Shows a summary chip when 2+
 * jobs are active, expandable to show individual chips.
 */

import { useState, useEffect, useRef, useCallback } from "react";
import { createPortal } from "react-dom";
import { getAutoCodeStatus } from "../utils/api";
import type { AutoCodeJobStatus } from "../utils/types";
import { ActivityChip } from "./ActivityChip";
import type { ActivityChipJob } from "./ActivityChip";

/** Normalised status shape used internally by the chip stack. */
export interface NormalisedJobStatus {
  status: "running" | "completed" | "failed" | "cancelled";
  progressLabel: string | null;
  durationLabel: string | null;
  errorMessage: string | null;
}

export interface ActivityJob {
  /** Unique key, e.g. "autocode:garrett" or "clips". */
  id: string;
  /** Human-readable label, e.g. "AutoCoding Garrett". */
  label: string;
  /** Label shown in completed state (falls back to label if not set). */
  completedLabel?: string;
  /** Framework ID for the status API. */
  frameworkId: string;
  /** Called once when job transitions to completed/failed/cancelled. */
  onComplete?: () => void;
  /** Called when user clicks the action link (e.g. "View Analysis"). */
  onAction?: () => void;
  /** Action link text. */
  actionLabel?: string;
  /** href for the action link. */
  actionHref?: string;
  /** Called when user cancels a running job. */
  onCancel?: () => void;
  /**
   * Custom poll function. If provided, called instead of getAutoCodeStatus().
   * Must return a NormalisedJobStatus (or throw to be silently ignored).
   */
  pollFn?: () => Promise<NormalisedJobStatus>;
}

interface ActivityChipStackProps {
  /** Active jobs to track. Parent adds/removes jobs; stack handles polling. */
  jobs: ActivityJob[];
  /** Called when user dismisses a completed/failed chip. */
  onDismiss: (jobId: string) => void;
}

function formatDuration(startedAt: string, completedAt: string): string {
  const start = new Date(startedAt).getTime();
  const end = new Date(completedAt).getTime();
  const secs = Math.round((end - start) / 1000);
  const min = Math.floor(secs / 60);
  const sec = secs % 60;
  return min > 0 ? `${min}:${String(sec).padStart(2, "0")}` : `${sec}s`;
}

/** Convert an AutoCode API status to the normalised shape. */
function normaliseAutoCode(status: AutoCodeJobStatus): NormalisedJobStatus {
  const s = status.status;
  const effectiveStatus: "running" | "completed" | "failed" | "cancelled" =
    s === "pending" ? "running" : (s as "running" | "completed" | "failed" | "cancelled");

  let progressLabel: string | null = null;
  if (effectiveStatus === "running") {
    progressLabel = `${status.processed_quotes}/${status.total_quotes}`;
  }

  let durationLabel: string | null = null;
  if (effectiveStatus === "completed" && status.started_at && status.completed_at) {
    durationLabel = formatDuration(status.started_at, status.completed_at);
  }

  return {
    status: effectiveStatus,
    progressLabel,
    durationLabel,
    errorMessage: status.error_message || null,
  };
}

function toChipJob(job: ActivityJob, norm: NormalisedJobStatus | null): ActivityChipJob {
  return {
    id: job.id,
    label: job.label,
    completedLabel: job.completedLabel,
    status: norm?.status ?? "running",
    progressLabel: norm?.progressLabel ?? null,
    durationLabel: norm?.durationLabel ?? null,
    errorMessage: norm?.errorMessage ?? null,
  };
}

const POLL_INTERVAL = 2000;

export function ActivityChipStack({ jobs, onDismiss }: ActivityChipStackProps) {
  const [statuses, setStatuses] = useState<Record<string, NormalisedJobStatus | null>>({});
  const [expanded, setExpanded] = useState(false);
  const completeFired = useRef<Set<string>>(new Set());
  // Ref mirror of statuses so the interval callback can read current values
  // without restarting the timer on every status change.
  const statusesRef = useRef(statuses);
  statusesRef.current = statuses;

  // Poll each job — dispatch by pollFn (custom) or getAutoCodeStatus (default).
  const pollJob = useCallback((job: ActivityJob) => {
    const promise = job.pollFn
      ? job.pollFn()
      : getAutoCodeStatus(job.frameworkId).then(normaliseAutoCode);

    promise
      .then((norm) => {
        setStatuses((prev) => ({ ...prev, [job.id]: norm }));
      })
      .catch(() => {
        // Silently ignore — endpoint may not exist yet.
      });
  }, []);

  useEffect(() => {
    if (jobs.length === 0) return;

    // Immediate poll for all jobs.
    for (const job of jobs) {
      pollJob(job);
    }

    const id = setInterval(() => {
      for (const job of jobs) {
        // Don't poll terminal jobs.
        const s = statusesRef.current[job.id]?.status;
        if (s === "completed" || s === "failed" || s === "cancelled") continue;
        pollJob(job);
      }
    }, POLL_INTERVAL);

    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobs, pollJob]);

  // Fire onComplete once per job.
  useEffect(() => {
    for (const job of jobs) {
      const s = statuses[job.id]?.status;
      if ((s === "completed" || s === "failed" || s === "cancelled") && !completeFired.current.has(job.id)) {
        completeFired.current.add(job.id);
        job.onComplete?.();
      }
    }
  }, [jobs, statuses]);

  if (jobs.length === 0) return null;

  const chipJobs = jobs.map((job) => ({
    job,
    chip: toChipJob(job, statuses[job.id] ?? null),
  }));

  const runningCount = chipJobs.filter((c) => c.chip.status === "running").length;
  const showSummary = jobs.length >= 2;

  const content = (
    <div className="activity-chip-stack" role="status" data-testid="bn-activity-chip-stack">
      {showSummary && !expanded && (
        <div
          className="activity-chip activity-chip-summary"
          data-testid="bn-activity-chip-summary"
          onClick={() => setExpanded(true)}
        >
          <div className="chip-spinner" />
          <span>
            {runningCount > 0
              ? `${runningCount} task${runningCount !== 1 ? "s" : ""} running`
              : `${jobs.length} task${jobs.length !== 1 ? "s" : ""}`}
          </span>
          <button
            className="chip-toggle"
            aria-label="Expand"
            data-testid="bn-activity-chip-expand"
          >
            &#x25BE;
          </button>
        </div>
      )}
      {(!showSummary || expanded) &&
        chipJobs.map(({ job, chip }) => (
          <ActivityChip
            key={job.id}
            job={chip}
            onAction={chip.status === "completed" && job.onAction ? () => { job.onAction!(); onDismiss(job.id); } : undefined}
            actionLabel={job.actionLabel}
            actionHref={job.actionHref}
            onDismiss={chip.status === "completed" && job.onAction ? undefined : () => onDismiss(job.id)}
            onCancel={chip.status === "running" ? job.onCancel : undefined}
          />
        ))}
      {showSummary && expanded && (
        <button
          className="activity-chip activity-chip-collapse"
          onClick={() => setExpanded(false)}
          aria-label="Collapse"
          data-testid="bn-activity-chip-collapse"
        >
          &#x25B4;
        </button>
      )}
    </div>
  );

  return createPortal(content, document.body);
}
