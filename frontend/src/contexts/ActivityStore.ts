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
  frameworkId: string;
  frameworkTitle: string;
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
