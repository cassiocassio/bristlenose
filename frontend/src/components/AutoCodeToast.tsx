/**
 * AutoCodeToast — floating progress chip for AutoCode jobs.
 *
 * Polls the status endpoint every 2 seconds, shows running/complete/failed
 * state, and persists across tab navigation via createPortal to document.body.
 */

import { useState, useEffect, useRef, useCallback } from "react";
import { autocodeFailure } from "../utils/autocodeFailure";
import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";
import { getAutoCodeStatus } from "../utils/api";
import type { AutoCodeJobStatus } from "../utils/types";

interface AutoCodeToastProps {
  frameworkId: string;
  onComplete: () => void;
  onOpenReport: () => void;
  onDismiss: () => void;
}

function formatDuration(startedAt: string, completedAt: string): string {
  const start = new Date(startedAt).getTime();
  const end = new Date(completedAt).getTime();
  const secs = Math.round((end - start) / 1000);
  const min = Math.floor(secs / 60);
  const sec = secs % 60;
  return min > 0 ? `${min}:${String(sec).padStart(2, "0")}` : `${sec}s`;
}

function formatElapsed(secs: number): string {
  const min = Math.floor(secs / 60);
  const sec = secs % 60;
  return min > 0 ? `${min}:${String(sec).padStart(2, "0")}` : `${sec}s`;
}

export function AutoCodeToast({
  frameworkId,
  onComplete,
  onOpenReport,
  onDismiss,
}: AutoCodeToastProps) {
  const { t } = useTranslation();
  const [job, setJob] = useState<AutoCodeJobStatus | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const completeFired = useRef(false);
  const dismissTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const elapsedTimer = useRef<ReturnType<typeof setInterval> | null>(null);

  const poll = useCallback(() => {
    getAutoCodeStatus(frameworkId)
      .then(setJob)
      .catch(() => {
        // Silently ignore polling errors — endpoint may not exist yet.
      });
  }, [frameworkId]);

  // Poll every 2 seconds.
  useEffect(() => {
    poll();
    const id = setInterval(poll, 2000);
    return () => clearInterval(id);
  }, [poll]);

  // Elapsed timer — ticks every second while running.
  useEffect(() => {
    if (job?.status === "running" && job.started_at) {
      const start = new Date(job.started_at).getTime();
      const tick = () => setElapsed(Math.round((Date.now() - start) / 1000));
      tick();
      elapsedTimer.current = setInterval(tick, 1000);
      return () => {
        if (elapsedTimer.current) clearInterval(elapsedTimer.current);
      };
    }
  }, [job?.status, job?.started_at]);

  // Fire onComplete once when the job finishes.
  useEffect(() => {
    if (!job) return;
    if ((job.status === "completed" || job.status === "failed") && !completeFired.current) {
      completeFired.current = true;
      onComplete();
    }
  }, [job, onComplete]);

  // Auto-dismiss 30s after failure (not completion — user must click Report).
  useEffect(() => {
    if (job?.status === "failed") {
      dismissTimer.current = setTimeout(onDismiss, 30_000);
      return () => {
        if (dismissTimer.current) clearTimeout(dismissTimer.current);
      };
    }
  }, [job?.status, onDismiss]);

  const pct =
    job && job.total_quotes > 0
      ? Math.round((job.processed_quotes / job.total_quotes) * 100)
      : 0;

  // The toast keeps itself open only while it holds an action the researcher
  // has to take. That used to be "completed", on the assumption every
  // completed job has a report — false for a job whose batches all refused,
  // which would leave a toast with no link and no close button on screen
  // until reload. The report link and the close button are now exact
  // complements: whichever is absent, the other is there.
  const hasReport = job?.status === "completed" && job.proposed_count > 0;

  const toast = (
    <div className="autocode-toast" data-testid="bn-autocode-toast">
      {(!job || job.status === "pending" || job.status === "running") && (
        <>
          <div className="toast-spinner" />
          <div className="toast-content">
            <span>
              {job
                ? t("autocode.toast.progress", { processed: job.processed_quotes, total: job.total_quotes })
                : t("autocode.toast.progress", { processed: "…", total: "…" })}
              {job?.status === "running" && (
                <span className="toast-elapsed">{formatElapsed(elapsed)}</span>
              )}
            </span>
            {job && job.total_quotes > 0 && (
              <div className="toast-progress-track" data-testid="bn-autocode-progress">
                <div
                  className="toast-progress-fill"
                  style={{ width: `${pct}%` }}
                />
              </div>
            )}
          </div>
        </>
      )}
      {job?.status === "completed" && (
        <>
          {/* A job can COMPLETE having tagged a subset: autocode.py gathers its
              batches with return_exceptions=True, logs "Batch failed" and
              carries on. processed_quotes only increments after a batch
              succeeds, so processed < total is exactly that partial — and it
              used to report as an unqualified success with a number that was
              quietly short. WARNING: complete, usable, not what was asked. */}
          <span
            className={
              job.processed_quotes < job.total_quotes
                ? "toast-warning"
                : "toast-check"
            }
          >
            {job.processed_quotes < job.total_quotes ? "\u26A0" : "\u2713"}
          </span>
          <span>
            {job.processed_quotes < job.total_quotes
              ? t("autocode.toast.donePartial", {
                  processed: job.processed_quotes,
                  total: job.total_quotes,
                })
              : t("autocode.toast.done", {
                  total: job.total_quotes,
                  duration:
                    job.completed_at && job.started_at
                      ? formatDuration(job.started_at, job.completed_at)
                      : "",
                })}
          </span>
          {/* Gated on proposals, NOT on status. A completed job can carry zero
              proposals — every batch refused, or the model returned nothing
              mappable — and the link then opened a modal reading "0 of 0
              proposals remaining. No proposals to review." Offering a report
              that does not exist is worse than offering nothing. */}
          {hasReport && (
            /* Link-styled action; keyboard-accessible via role/tabIndex/onKeyDown. */
            /* eslint-disable-next-line jsx-a11y/anchor-is-valid */
            <a
              className="toast-link"
              role="button"
              tabIndex={0}
              onClick={onOpenReport}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onOpenReport();
                }
              }}
              data-testid="bn-autocode-toast-report"
            >
              {t("autocode.toast.report")}
            </a>
          )}
        </>
      )}
      {job?.status === "failed" && (
        <>
          <span className="toast-error">&#x2717;</span>
          <span>
            {job.status === "failed"
              ? t("autocode.toast.failedWithError", {
                  error: autocodeFailure(job.failure_kind).message,
                })
              : t("autocode.toast.failed")}
          </span>
        </>
      )}
      {!hasReport && (
        <button
          className="toast-close"
          onClick={onDismiss}
          aria-label={t("autocode.toast.dismiss")}
          data-testid="bn-autocode-toast-close"
        >
          &times;
        </button>
      )}
    </div>
  );

  return createPortal(toast, document.body);
}
