/**
 * AutoCodeToast — floating progress chip for AutoCode jobs.
 *
 * Polls the status endpoint every 2 seconds, shows running/complete/failed
 * state, and persists across tab navigation via createPortal to document.body.
 */

import { useState, useEffect, useRef, useCallback } from "react";
import { createPortal } from "react-dom";
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

export function AutoCodeToast({
  frameworkId,
  onComplete,
  onOpenReport,
  onDismiss,
}: AutoCodeToastProps) {
  const [job, setJob] = useState<AutoCodeJobStatus | null>(null);
  const completeFired = useRef(false);
  const dismissTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

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

  // Fire onComplete once when the job finishes.
  useEffect(() => {
    if (!job) return;
    if ((job.status === "completed" || job.status === "failed") && !completeFired.current) {
      completeFired.current = true;
      onComplete();
    }
  }, [job, onComplete]);

  // Auto-dismiss 30s after completion.
  useEffect(() => {
    if (job?.status === "completed" || job?.status === "failed") {
      dismissTimer.current = setTimeout(onDismiss, 30_000);
      return () => {
        if (dismissTimer.current) clearTimeout(dismissTimer.current);
      };
    }
  }, [job?.status, onDismiss]);

  const toast = (
    <div className="autocode-toast" data-testid="bn-autocode-toast">
      {(!job || job.status === "pending" || job.status === "running") && (
        <>
          <div className="toast-spinner" />
          <span>
            &#x2726; AutoCoding{" "}
            {job ? `${job.processed_quotes}/${job.total_quotes}` : "…"}{" "}
            transcripts…
          </span>
        </>
      )}
      {job?.status === "completed" && (
        <>
          <span className="toast-check">&#x2713;</span>
          <span>
            &#x2726; AutoCoded {job.total_quotes} transcripts
            {job.completed_at && job.started_at
              ? ` in ${formatDuration(job.started_at, job.completed_at)}`
              : ""}
            .
          </span>
          {/* eslint-disable-next-line jsx-a11y/anchor-is-valid */}
          <a
            className="toast-link"
            onClick={onOpenReport}
            data-testid="bn-autocode-toast-report"
          >
            Report
          </a>
        </>
      )}
      {job?.status === "failed" && (
        <>
          <span className="toast-error">&#x2717;</span>
          <span>&#x2726; AutoCode failed{job.error_message ? `: ${job.error_message}` : ""}.</span>
        </>
      )}
      <button
        className="toast-close"
        onClick={onDismiss}
        aria-label="Dismiss"
        data-testid="bn-autocode-toast-close"
      >
        &times;
      </button>
    </div>
  );

  return createPortal(toast, document.body);
}
