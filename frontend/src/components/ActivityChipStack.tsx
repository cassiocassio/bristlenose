/**
 * ActivityChipStack — container for 0-N background job chips.
 *
 * Renders via createPortal to document.body so chips persist across tab
 * navigation. Owns polling for each job. Shows a summary chip when 2+
 * jobs are active, expandable to show individual chips.
 */

import { useState, useEffect, useRef, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { createPortal } from "react-dom";
import i18n from "../i18n";
import { getAutoCodeStatus } from "../utils/api";
import type { AutoCodeJobStatus } from "../utils/types";
import { autocodeFailure } from "../utils/autocodeFailure";
import { postLLMFailure } from "../shims/bridge";
import { ActivityChip } from "./ActivityChip";
import type { ActivityChipJob } from "./ActivityChip";

/** Normalised status shape used internally by the chip stack. */
export interface NormalisedJobStatus {
  /**
   * `"partial"` is a *completed* job that did not do all of the work — the
   * engine gathers its batches with `return_exceptions=True`, logs the ones
   * that threw and carries on, so `processed < total` is a real outcome the
   * API reports as `"completed"`. It is a distinct status rather than a flag
   * on `"completed"` because a flag is what the render site forgets: this
   * shortfall was already fixed once, in `AutoCodeToast`, which is not mounted.
   */
  status: "running" | "completed" | "partial" | "failed" | "cancelled";
  progressLabel: string | null;
  durationLabel: string | null;
  errorMessage: string | null;
  /** Resolved sentence for `"partial"`; null for every other status. */
  partialMessage: string | null;
  /**
   * Whether there is anything behind the report link. A finished job can hold
   * zero proposals — every batch refused, or nothing the model returned mapped
   * to a tag — and the link then opens "0 of 0 proposals remaining. No
   * proposals to review."
   *
   * Optional, and absence means "not a proposals report, don't gate": a job
   * polled through a custom `pollFn` (clip extraction) has an action link that
   * is not a report, so only `false` suppresses one. Written that way rather
   * than defaulting to `true` so a *new* AutoCode-shaped caller that forgets
   * the field fails open (a link that works) rather than closed (a chip that
   * cannot be dismissed).
   */
  hasProposals?: boolean;
  /**
   * The raw `LLMFailureKind` and the provider that produced it, carried
   * unresolved alongside the localised `errorMessage` so the native shell can
   * be told what happened (`postLLMFailure`). A sentence is for a researcher;
   * a kind is for a state machine, and the shell has one. Absent for a job
   * that did not fail, and for custom `pollFn` jobs that are not LLM work.
   */
  failureKind?: string;
  provider?: string;
}

/** Terminal statuses — no further polling, and `onComplete` has fired. */
function isTerminal(s: NormalisedJobStatus["status"] | undefined): boolean {
  return s === "completed" || s === "partial" || s === "failed" || s === "cancelled";
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
export function normaliseAutoCode(status: AutoCodeJobStatus): NormalisedJobStatus {
  const s = status.status;
  const reported: "running" | "completed" | "failed" | "cancelled" =
    s === "pending" ? "running" : (s as "running" | "completed" | "failed" | "cancelled");

  // A job can COMPLETE having tagged a subset (see `NormalisedJobStatus`).
  // `processed_quotes` only advances on a batch that succeeded, so the
  // shortfall is exactly the work that failed.
  const short =
    reported === "completed" && status.processed_quotes < status.total_quotes;
  const effectiveStatus: NormalisedJobStatus["status"] = short ? "partial" : reported;

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
    // Resolved here, not at the render site — same boundary rule as
    // `errorMessage` below. Reuses the string the (unmounted) toast already
    // had translated into all 21 locales rather than minting a new key.
    partialMessage: short
      ? i18n.t("autocode.toast.donePartial", {
          processed: status.processed_quotes,
          total: status.total_quotes,
          defaultValue: "Tagged {{processed}} of {{total}} quotes — some batches failed.",
        })
      : null,
    // Resolve at the API/UI boundary, not at the render site: error_message is
    // str(exc) from a bare except, so interpolating it made a rate limit read as
    // "Tagging failed: Error code: 429 - {'type': 'error', ...}".
    errorMessage:
      effectiveStatus === "failed"
        ? autocodeFailure(status.failure_kind).message
        : null,
    hasProposals: status.proposed_count > 0,
    failureKind: effectiveStatus === "failed" ? status.failure_kind : undefined,
    provider: status.llm_provider || undefined,
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
    partialMessage: norm?.partialMessage ?? null,
  };
}

const POLL_INTERVAL = 2000;

export function ActivityChipStack({ jobs, onDismiss }: ActivityChipStackProps) {
  const { t } = useTranslation();
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
        if (isTerminal(statusesRef.current[job.id]?.status)) continue;
        pollJob(job);
      }
    }, POLL_INTERVAL);

    return () => clearInterval(id);
  }, [jobs, pollJob]);

  // Fire onComplete once per job.
  useEffect(() => {
    for (const job of jobs) {
      const norm = statuses[job.id];
      if (isTerminal(norm?.status) && !completeFired.current.has(job.id)) {
        completeFired.current.add(job.id);
        // Tell the shell before the callback, and inside the same
        // fired-once guard: polling is every 2s and a terminal job stays
        // terminal, so anywhere else would repost the same verdict forever.
        if (norm?.failureKind && norm.provider) {
          postLLMFailure(norm.failureKind, norm.provider);
        }
        job.onComplete?.();
      }
    }
  }, [jobs, statuses]);

  if (jobs.length === 0) return null;

  const chipJobs = jobs.map((job) => ({
    job,
    norm: statuses[job.id] ?? null,
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
          role="button"
          tabIndex={0}
          onClick={() => setExpanded(true)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              setExpanded(true);
            }
          }}
        >
          <span className="chip-label bn-thinking-shimmer">
            {runningCount > 0
              ? `${runningCount} task${runningCount !== 1 ? "s" : ""} running`
              : `${jobs.length} task${jobs.length !== 1 ? "s" : ""}`}
          </span>
          <button
            className="chip-toggle"
            aria-label={t("activity.expand")}
            data-testid="bn-activity-chip-expand"
          >
            &#x25BE;
          </button>
        </div>
      )}
      {(!showSummary || expanded) &&
        chipJobs.map(({ job, norm, chip }) => {
          // A partial run has proposals behind the door exactly as a whole one
          // does — fewer of them. It keeps the report link (which doubles as
          // the dismissal, hence no close button when it is present).
          //
          // …unless there are none. `hasProposals` is the second half of that
          // sentence, and it was missing: a job that finished having tagged
          // nothing offered View Report into an empty modal, and — because the
          // link doubles as the dismissal — no way to dismiss the chip either.
          // A status with no `norm` yet is not yet reportable.
          const reportable =
            (chip.status === "completed" || chip.status === "partial") &&
            norm?.hasProposals !== false &&
            job.onAction;
          return (
          <ActivityChip
            key={job.id}
            job={chip}
            onAction={reportable ? () => { job.onAction!(); onDismiss(job.id); } : undefined}
            actionLabel={job.actionLabel}
            actionHref={job.actionHref}
            onDismiss={reportable ? undefined : () => onDismiss(job.id)}
            onCancel={chip.status === "running" ? job.onCancel : undefined}
          />
          );
        })}
      {showSummary && expanded && (
        <button
          className="activity-chip activity-chip-collapse"
          onClick={() => setExpanded(false)}
          aria-label={t("activity.collapse")}
          data-testid="bn-activity-chip-collapse"
        >
          &#x25B4;
        </button>
      )}
    </div>
  );

  return createPortal(content, document.body);
}
