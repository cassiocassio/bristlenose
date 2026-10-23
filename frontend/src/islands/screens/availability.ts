/**
 * Whether the Screens lens has anything to offer: the server's answer, `available`, never derived
 * here. The rule — reading on and possible, and screens found or recordings still to read — has one
 * copy, `screens_available` in server/routes/screens.py, which the Mac's rail reads too. Not a
 * preference: a project whose recordings show no shared screen never shows the lens at all
 * (docs/design-screens.md S5). Never in an exported report — the route is server-only.
 *
 * Read from `GET …/screens/status` (server/routes/screens.py), the cheap progress read the Mac's
 * sidebar row uses: on mount, on every run's completion (`refreshKey`), and every STATUS_POLL_MS
 * while reading is in progress, for at most STATUS_POLL_LIMIT looks. A failed look is tried once
 * more and then stops, console only (owner, 23 Oct 2026: not-needy UX). The lens, when its own read
 * finds screens, says so here too (`markScreensFound`), so the nav never trails what the lens is
 * already showing.
 *
 * Small on purpose and free of the lens: the nav is on first paint and the lens is a lazy chunk.
 */

import { useEffect, useSyncExternalStore } from "react";
import { useLastRun } from "../../contexts/LastRunStore";
import { apiGet } from "../../utils/api";
import { isExportMode } from "../../utils/exportData";

/** GET …/screens/status. `has_screens` is absent from a server older than the lens's graduation. */
export interface ScreensStatus {
  enabled: boolean;
  unavailable: string | null;
  running: boolean;
  done: number;
  total: number;
  seconds_done: number;
  seconds_total: number;
  rate: number | null;
  has_screens?: boolean;
  /** Whether the lens is offered (the server's `screens_available`). Absent from an older server: no. */
  available?: boolean;
}

/** Reading is under way: recordings remain that have been neither read nor given up on. Decides
 *  whether to look again, not whether the lens shows. */
export function statusStillReading(s: ScreensStatus): boolean {
  return s.enabled && s.unavailable == null && s.total > 0 && (s.running || s.done < s.total);
}

/** Show the Screens lens iff the server says so. */
export function screensAvailable(s: ScreensStatus | null): boolean {
  return s?.available === true;
}

/** 15 s apart while reading, for an hour at most; a run's completion starts it again. */
export const STATUS_POLL_MS = 15_000;
export const STATUS_POLL_LIMIT = 240;

let available = false;
const listeners = new Set<() => void>();

function set(next: boolean): void {
  if (next === available) return;
  available = next;
  listeners.forEach((l) => l());
}

function subscribe(l: () => void): () => void {
  listeners.add(l);
  return () => listeners.delete(l);
}

/** The lens found screens on its own read: the nav shows it, whatever the last status said. */
export function markScreensFound(): void {
  if (!isExportMode()) set(true);
}

/** For tests. */
export function resetScreensAvailability(): void {
  available = false;
  listeners.forEach((l) => l());
}

/**
 * Whether to offer the Screens lens, kept current. Mount it once (the nav does): it owns the
 * status reads. Always false in an exported report, which asks the server nothing.
 */
export function useScreensAvailable(): boolean {
  const { refreshKey } = useLastRun();
  useEffect(() => {
    if (isExportMode()) return;
    let live = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    // `n` counts the looks; `failures`, the failed looks in a row.
    const look = (n: number, failures: number) => {
      apiGet<ScreensStatus>("/screens/status")
        .then((s) => {
          if (!live) return;
          set(screensAvailable(s));
          if (statusStillReading(s) && n + 1 < STATUS_POLL_LIMIT) timer = setTimeout(() => look(n + 1, 0), STATUS_POLL_MS);
        })
        .catch((e: unknown) => {
          // A 401 while the sidecar restarts, or an older server: keep what we had, look once
          // more, then stop.
          console.error("Screens: /screens/status failed", e);
          if (live && failures === 0 && n + 1 < STATUS_POLL_LIMIT) timer = setTimeout(() => look(n + 1, 1), STATUS_POLL_MS);
        });
    };
    look(0, 0);
    return () => {
      live = false;
      if (timer) clearTimeout(timer);
    };
  }, [refreshKey]);
  return useSyncExternalStore(subscribe, () => available && !isExportMode(), () => false);
}
