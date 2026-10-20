/**
 * ActivityStore — module-level store for background job tracking.
 *
 * Owns the list of active jobs (e.g. AutoCode runs). Lives at the module
 * level so it survives React Router navigation — components subscribe via
 * `useActivityJobs()` which uses `useSyncExternalStore`.
 *
 * Same pattern as QuotesContext.tsx and SidebarStore.ts.
 */

import { useSyncExternalStore } from "react";
import { getClipExtractionStatus, getScreensExportStatus, listAutoCodeJobs } from "../utils/api";
import { isExportMode } from "../utils/exportData";

export interface ActivityJobEntry {
  /** "catchup" = the on-enable delta re-apply (numberless chip; §4a). */
  type: "autocode" | "clips" | "catchup" | "screens";
  frameworkId: string;
  frameworkTitle: string;
  /** Which codebook lens started this job — the route its "View Report" action
   *  should return to.
   *
   *  Two lenses run side by side (D29), and the chip used to send every
   *  reader to `/report/codebook` regardless. A researcher who installed a
   *  codebook from v2 and clicked View Report landed in v1 — a different lens
   *  than the one they were working in, with no indication anything had moved.
   *  Absent means the shipped lens, which is the pre-v2 behaviour. */
  originRoute?: string;
  /** Total items (clips count) — used by clips jobs. */
  total?: number;
  /** A screens export that ends by putting its files on the clipboard (the Mac app's Copy
   *  Screens). */
  copyWhenDone?: boolean;
}

// ── Module-level state ───────────────────────────────────────────────────

let jobs = new Map<string, ActivityJobEntry>();
let snapshot = new Map<string, ActivityJobEntry>();
const listeners = new Set<() => void>();

function notify(): void {
  for (const l of listeners) l();
}

// ── Mutations ────────────────────────────────────────────────────────────

export function addJob(id: string, entry: ActivityJobEntry): void {
  jobs = new Map(jobs);
  jobs.set(id, entry);
  snapshot = jobs;
  notify();
}

export function removeJob(id: string): void {
  if (!jobs.has(id)) return;
  jobs = new Map(jobs);
  jobs.delete(id);
  snapshot = jobs;
  notify();
}

// ── Subscription ─────────────────────────────────────────────────────────

export function getJobs(): Map<string, ActivityJobEntry> {
  return snapshot;
}

function subscribe(cb: () => void): () => void {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

export function useActivityJobs(): Map<string, ActivityJobEntry> {
  return useSyncExternalStore(subscribe, getJobs, getJobs);
}

// ── Rehydration ──────────────────────────────────────────────────────────

let rehydratedProjectId: string | null = null;
let retried = false;

/** A read that failed on load is tried once more after this long; the page loads once. */
const REHYDRATE_RETRY_MS = 5_000;

function hasJob(test: (job: ActivityJobEntry) => boolean): boolean {
  for (const job of jobs.values()) if (test(job)) return true;
  return false;
}

/**
 * Put back the chips of the jobs the server is still running (R14). The list above lives only in
 * the page, so a reload during an AutoCode run or an export dropped its chip, and the job's end,
 * with its Reveal or View Report, was never shown. Once per project, when the report loads.
 *
 * Running jobs only: a finished one's chip, once dismissed, would come back on every reload, since
 * nothing records a dismissal. A job a producer has added meanwhile is kept, not doubled (the
 * server holds one export of each kind per project, and one AutoCode run per codebook), and the
 * producers remove a restored chip by type, as they do their own, when they start the next run.
 * A restored Copy Screens is a plain export: the server does not record that it was a copy.
 * Never rejects. A failed read adds nothing and all three are read once more a little later, since
 * the report loads once; what was restored by then is kept, not doubled.
 */
export function rehydrateActivityJobs(projectId: string): Promise<void> {
  if (isExportMode() || rehydratedProjectId === projectId) return Promise.resolve();
  rehydratedProjectId = projectId;
  // Started inside a promise, so a helper that throws rather than rejects is a failed read too.
  const read = <T>(fn: () => Promise<T>) => Promise.resolve().then(fn);
  return Promise.allSettled([
    read(() => getClipExtractionStatus()),
    read(() => getScreensExportStatus()),
    read(() => listAutoCodeJobs()),
  ]).then(([clips, screens, autocode]) => {
    if (rehydratedProjectId !== projectId) return;
    let failed = false;
    for (const [kind, r] of [["clips", clips], ["screens", screens], ["autocode", autocode]] as const) {
      if (r.status === "rejected") {
        failed = true;
        console.warn(`Activity: the ${kind} status read failed on load`, r.reason);
      }
    }
    if (failed && !retried) {
      retried = true;
      setTimeout(() => {
        if (rehydratedProjectId !== projectId) return;
        rehydratedProjectId = null;
        void rehydrateActivityJobs(projectId);
      }, REHYDRATE_RETRY_MS);
    }
    if (clips.status === "fulfilled" && clips.value?.status === "running" && !hasJob((j) => j.type === "clips")) {
      addJob("clips:restored", { type: "clips", frameworkId: "", frameworkTitle: "", total: clips.value.total });
    }
    if (screens.status === "fulfilled" && screens.value?.status === "running" && !hasJob((j) => j.type === "screens")) {
      addJob("screens:restored", {
        type: "screens", frameworkId: "", frameworkTitle: "", total: screens.value.total, copyWhenDone: false,
      });
    }
    const runs = autocode.status === "fulfilled" ? autocode.value?.jobs : undefined;
    if (!Array.isArray(runs)) return;
    for (const run of runs) {
      if (typeof run?.framework_id !== "string") continue;
      // A catch-up (a finished run re-coding new sessions) has no chip of its own today.
      if (run.completed_at) continue;
      if (hasJob((j) => j.type === "autocode" && j.frameworkId === run.framework_id)) continue;
      addJob(`autocode:${run.framework_id}:restored`, {
        type: "autocode",
        frameworkId: run.framework_id,
        frameworkTitle: run.title,
        originRoute: "/report/codebook/",
      });
    }
  }).catch((err: unknown) => console.warn("Activity: restoring the chips on load failed", err));
}

/** Reset for tests. */
export function resetActivityStore(): void {
  jobs = new Map();
  snapshot = jobs;
  rehydratedProjectId = null;
  retried = false;
  notify();
}
