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

export interface ActivityJobEntry {
  /** "catchup" = the on-enable delta re-apply (numberless chip; §4a). */
  type: "autocode" | "clips" | "catchup";
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

/** Reset for tests. */
export function resetActivityStore(): void {
  jobs = new Map();
  snapshot = jobs;
  notify();
}
