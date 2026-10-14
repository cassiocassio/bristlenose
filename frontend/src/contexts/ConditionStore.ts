/**
 * ConditionStore — what the SPA needs from the project's condition while a run
 * is in progress: the data version, and which lenses can be selected.
 *
 * Polls `GET /api/projects/{id}/condition` (docs/design-progressive-lenses.md
 * §3.2). Two jobs:
 *
 *   - **Refresh key.** When `data_version` moves, the database holds new data,
 *     so it bumps LastRunStore's `refreshKey` and every lens refetches.
 *     `/last-run` stays the run-completion signal (and its announcement); it is
 *     pinned and moves only when a run completes, so it cannot carry the
 *     per-session imports a progressive run adds.
 *   - **Lens readiness.** `lenses` is the server's one derivation
 *     (`server/lens_readiness.py`). The web nav reads it through `useLenses`,
 *     and it is posted to the Mac host, whose lens rail cannot see inside the
 *     web view.
 *
 * Same discipline as LastRunStore: one timer per project, paused while the
 * document is hidden, an in-flight guard, silent on 401, a no-op in an exported
 * report. The first poll records the version without bumping: the lenses have
 * just loaded their data.
 *
 * @module ConditionStore
 */

import { useSyncExternalStore } from "react";
import { authHeaders } from "../utils/api";
import { isExportMode } from "../utils/exportData";
import { postLensAvailability } from "../shims/bridge";
import { bumpRefreshKey } from "./LastRunStore";

// `screens` is the Screens lens. The server's readiness derivation does not name it, so it is
// always selectable here (absence is never a refusal; whether it is OFFERED is
// islands/screens/availability.ts); it is listed so the nav, the
// Mac's lens rail and the route helpers count it as a lens like the others.
export const LENS_IDS = ["project", "sessions", "quotes", "codebook", "signals", "discussion", "screens"] as const;
export type LensId = (typeof LENS_IDS)[number];
export type Lenses = Record<LensId, boolean>;

/** Every lens available — what the SPA assumes until the server says otherwise. */
export const ALL_LENSES: Lenses = Object.fromEntries(LENS_IDS.map((id) => [id, true])) as Lenses;

interface ConditionState {
  dataVersion: number | null;
  lenses: Lenses;
}

const POLL_INTERVAL_MS = 3000;

let state: ConditionState = { dataVersion: null, lenses: ALL_LENSES };
const listeners = new Set<() => void>();
let pollTimer: ReturnType<typeof setTimeout> | null = null;
let inFlight = false;
let activeProjectId: string | null = null;
let postedOnce = false;
let visibilityListenerInstalled = false;

function setState(next: ConditionState): void {
  state = next;
  listeners.forEach((l) => l());
}

function isHidden(): boolean {
  return typeof document !== "undefined" && document.visibilityState === "hidden";
}

/** A lens the server does not name stays available: absence is never a refusal. */
function readLenses(raw: unknown): Lenses {
  const src = raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {};
  return Object.fromEntries(
    LENS_IDS.map((id) => [id, typeof src[id] === "boolean" ? (src[id] as boolean) : true]),
  ) as Lenses;
}

const sameLenses = (a: Lenses, b: Lenses) => LENS_IDS.every((id) => a[id] === b[id]);

async function pollOnce(): Promise<void> {
  if (inFlight || activeProjectId === null || isHidden()) return;
  const projectId = activeProjectId;
  inFlight = true;
  try {
    const resp = await fetch(`/api/projects/${projectId}/condition`, { headers: authHeaders() });
    if (!resp.ok) return; // 401 while the sidecar restarts, 404 with no project: silent
    const body = (await resp.json()) as { data_version?: unknown; lenses?: unknown };
    if (activeProjectId !== projectId) return; // switched mid-flight

    const version = typeof body.data_version === "number" ? body.data_version : null;
    const lenses = readLenses(body.lenses);
    const prev = state;
    const versionMoved = prev.dataVersion !== null && version !== null && version !== prev.dataVersion;
    const lensesChanged = !sameLenses(prev.lenses, lenses);

    if (version !== prev.dataVersion || lensesChanged) {
      // Keep the lenses object when it is unchanged, so a version-only move
      // does not re-render everything that reads useLenses.
      setState({ dataVersion: version, lenses: lensesChanged ? lenses : prev.lenses });
    }
    if (versionMoved) bumpRefreshKey();
    if (lensesChanged || !postedOnce) {
      postedOnce = true;
      postLensAvailability(lenses);
    }
  } catch {
    // Network blip; the next tick retries.
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
    pollOnce().then(() => {
      if (activeProjectId !== null) scheduleNextTick();
    });
  }
}

/** Start polling for `projectId`. Idempotent per project; a new project resets. */
export function startConditionPolling(projectId: string): void {
  if (isExportMode()) return;
  if (activeProjectId === projectId) return;
  activeProjectId = projectId;
  postedOnce = false;
  setState({ dataVersion: null, lenses: ALL_LENSES });
  if (!visibilityListenerInstalled && typeof document !== "undefined") {
    document.addEventListener("visibilitychange", handleVisibilityChange);
    visibilityListenerInstalled = true;
  }
  pollOnce().then(() => {
    if (activeProjectId !== null) scheduleNextTick();
  });
}

export function stopConditionPolling(): void {
  activeProjectId = null;
  if (pollTimer !== null) {
    clearTimeout(pollTimer);
    pollTimer = null;
  }
}

/** Reset for tests. */
export function resetConditionStore(): void {
  stopConditionPolling();
  inFlight = false;
  postedOnce = false;
  setState({ dataVersion: null, lenses: ALL_LENSES });
}

const subscribe = (l: () => void) => {
  listeners.add(l);
  return () => {
    listeners.delete(l);
  };
};

/** Which lenses can be selected now. Every lens until the server says otherwise. */
export function useLenses(): Lenses {
  return useSyncExternalStore(subscribe, () => state.lenses);
}

/** True while a first analysis is still delivering: some lens is withheld.
 *  Export waits for the whole report (docs/design-progressive-lenses.md §5.6). */
export function isReportPartial(lenses: Lenses = state.lenses): boolean {
  return !LENS_IDS.every((id) => lenses[id]);
}
