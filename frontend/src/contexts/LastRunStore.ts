/**
 * LastRunStore — module-level store for pipeline-run readiness.
 *
 * Polls `GET /api/projects/{id}/last-run` at a steady cadence. When the
 * server's `run_id` changes, the store emits a new `refreshKey` so page
 * wrappers can re-fetch their islands' data.
 *
 * Design constraints (from the v3 handoff):
 *   - One timer per project (not per island). N islands × N intervals
 *     would hammer the endpoint and waste battery.
 *   - Pause polling when the document is hidden (visibilitychange).
 *   - Skip the next poll if a fetch from the previous tick is still
 *     in-flight (single boolean — not a debounce window).
 *   - 401 → silent back-off; the sidecar may be restarting. Don't toast.
 *   - Mount baseline is `lastSeenRunId = null`. The first poll that
 *     returns *any* terminus refetches unconditionally — closes the
 *     hole where the pipeline completed before the SPA opened the
 *     project.
 *   - `run_id` is a ULID (monotonic), used as the comparison key.
 *     `completed_at` is for display.
 *
 * Endpoint contract (server-side, pinned):
 *   { run_id: string, outcome: string, completed_at: string } | null
 *
 * @module LastRunStore
 */

import { useSyncExternalStore } from "react";
import { authHeaders } from "../utils/api";
import { announce } from "../utils/announce";
import i18n from "../i18n";

// ── Types ────────────────────────────────────────────────────────────────

export interface LastRunInfo {
  run_id: string;
  outcome: string;
  completed_at: string;
}

export interface LastRunState {
  /** Latest server-reported run, or null if no run has completed yet. */
  lastRun: LastRunInfo | null;
  /**
   * Bumped each time `lastRun.run_id` changes. Page wrappers feed this
   * into island `useEffect` deps so islands refetch on completion
   * without losing local UI state (open accordions, scroll position).
   */
  refreshKey: number;
}

// ── Constants ────────────────────────────────────────────────────────────

const POLL_INTERVAL_MS = 3000;

// ── Module-level state ──────────────────────────────────────────────────

let state: LastRunState = { lastRun: null, refreshKey: 0 };
const listeners = new Set<() => void>();

let pollTimer: ReturnType<typeof setTimeout> | null = null;
let inFlight = false;
let activeProjectId: string | null = null;
let visibilityListenerInstalled = false;

// ── Internal helpers ────────────────────────────────────────────────────

function getSnapshot(): LastRunState {
  return state;
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function setState(next: LastRunState): void {
  state = next;
  listeners.forEach((l) => l());
}

function isHidden(): boolean {
  return typeof document !== "undefined" && document.visibilityState === "hidden";
}

async function pollOnce(): Promise<void> {
  if (inFlight) return; // previous tick still resolving
  if (activeProjectId === null) return;
  if (isHidden()) return;

  const projectId = activeProjectId;
  inFlight = true;
  try {
    const resp = await fetch(`/api/projects/${projectId}/last-run`, {
      headers: authHeaders(),
    });
    if (resp.status === 401) {
      // Silent back-off — sidecar may be restarting.
      return;
    }
    if (!resp.ok) return;
    const body = (await resp.json()) as LastRunInfo | null;

    // Project switched mid-flight — discard.
    if (activeProjectId !== projectId) return;

    if (body === null) {
      // No run yet. Keep state as-is (mount baseline).
      return;
    }

    const prev = state.lastRun;
    if (prev?.run_id === body.run_id) {
      // Same run — keep refreshKey stable.
      return;
    }
    setState({
      lastRun: body,
      refreshKey: state.refreshKey + 1,
    });
    // Screen-reader announcement on terminus transitions only — not on
    // first poll when prev was null and the body is just a startup seed
    // (the user didn't trigger anything from this session). Once we
    // have prev → new, that's a completion the user just witnessed.
    if (prev !== null) {
      announce(i18n.t("announce.pipelineCompleted"));
    }
  } catch {
    // Network blip. Don't surface; next tick will retry.
  } finally {
    inFlight = false;
  }
}

function scheduleNextTick(): void {
  if (pollTimer !== null) return;
  pollTimer = setTimeout(async () => {
    pollTimer = null;
    await pollOnce();
    if (activeProjectId !== null) scheduleNextTick();
  }, POLL_INTERVAL_MS);
}

function handleVisibilityChange(): void {
  if (isHidden()) {
    if (pollTimer !== null) {
      clearTimeout(pollTimer);
      pollTimer = null;
    }
  } else {
    // Resumed — poll immediately, then resume cadence.
    pollOnce().then(() => {
      if (activeProjectId !== null) scheduleNextTick();
    });
  }
}

function installVisibilityListener(): void {
  if (visibilityListenerInstalled) return;
  if (typeof document === "undefined") return;
  document.addEventListener("visibilitychange", handleVisibilityChange);
  visibilityListenerInstalled = true;
}

// ── Public API ──────────────────────────────────────────────────────────

/**
 * Start polling for `projectId`. Idempotent — calling again with the
 * same id is a no-op. Calling with a different id resets state and
 * restarts polling.
 */
export function startLastRunPolling(projectId: string): void {
  if (activeProjectId === projectId) return;

  activeProjectId = projectId;
  // Reset state when switching projects so the new project's first
  // returning terminus is treated as "new" by consumers.
  state = { lastRun: null, refreshKey: state.refreshKey };
  listeners.forEach((l) => l());

  installVisibilityListener();
  // First poll immediately so the SPA reconciles against any run that
  // completed before the project was opened.
  pollOnce().then(() => {
    if (activeProjectId !== null) scheduleNextTick();
  });
}

/**
 * Stop polling and clear active project. Listeners stay subscribed so a
 * later `startLastRunPolling()` re-uses them. Test isolation only —
 * production use is `start` once per project mount.
 */
export function stopLastRunPolling(): void {
  activeProjectId = null;
  if (pollTimer !== null) {
    clearTimeout(pollTimer);
    pollTimer = null;
  }
}

/**
 * Manual refresh — bumps `refreshKey` synchronously so islands refetch
 * immediately, then polls the server for fresh `lastRun` state. Fires an
 * announce() unconditionally so AT users get confirmation that the click
 * took effect even when the server has nothing new to report.
 *
 * No-op if no project is active. Safe to call repeatedly; the in-flight
 * guard inside `pollOnce()` skips the second poll when one is already
 * resolving (the synchronous `refreshKey` bump still happens).
 */
export async function triggerManualRefresh(): Promise<void> {
  if (activeProjectId === null) return;
  setState({ ...state, refreshKey: state.refreshKey + 1 });
  // Snapshot the run_id so we can tell whether pollOnce() already fired
  // its own transition-announce. We only announce ourselves when it
  // didn't — otherwise AT users hear "Pipeline completed" twice.
  const prevRunId = state.lastRun?.run_id;
  await pollOnce();
  if (state.lastRun?.run_id === prevRunId) {
    announce(i18n.t("announce.pipelineCompleted"));
  }
}

/** Reset for tests. */
export function resetLastRunStore(): void {
  stopLastRunPolling();
  inFlight = false;
  state = { lastRun: null, refreshKey: 0 };
  listeners.forEach((l) => l());
}

// ── React hook ──────────────────────────────────────────────────────────

/** Subscribe to the last-run store. Re-renders when `refreshKey` changes. */
export function useLastRun(): LastRunState {
  return useSyncExternalStore(subscribe, getSnapshot);
}
