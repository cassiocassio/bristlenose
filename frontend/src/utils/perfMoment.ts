/**
 * Page half of the perf moment timer (docs/design-perf-ledger.md).
 *
 * The Mac begins an interval when the thing is asked for (`ready`, or a
 * route-change to a transcript); the page ends it when the content is on screen,
 * which only the page knows. The end is two animation frames after the render
 * that put the content in the DOM: the first frame commits it, the second is
 * when it has been painted. It posts `{ type: "perf-mark", name }` on the
 * navigation handler, the channel `ready` and `route-change` use, and leaves a
 * `performance.mark("bn.<name>.end")` so a Playwright run reads the same names.
 *
 * Posts directly rather than through `shims/bridge.ts`, which this module must
 * not depend on. Outside the Mac app and in the HTML export it does nothing.
 */

import { useEffect } from "react";
import { isExportMode } from "./exportData";

export type PerfMoment = "open-transcript" | "first-card-painted";

const firedOnce = new Set<PerfMoment>();

/** Forget which once-per-page moments have fired. Tests only. */
export function resetPerfMoments(): void {
  firedOnce.clear();
}

export function markMomentEnd(name: PerfMoment): void {
  if (isExportMode()) return;
  try {
    performance.mark(`bn.${name}.end`);
  } catch {
    // No performance API: the native interval is the one that matters.
  }
  try {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (window as any).webkit?.messageHandlers?.navigation?.postMessage({ type: "perf-mark", name });
  } catch {
    // Not in WKWebView, or the handler went away during a race.
  }
}

/**
 * End `name` once the content is painted. `ready` is whether the content is in the
 * DOM; `key` restarts the wait (a different transcript); `oncePerPage` ends it only
 * the first time this page load gets there, for moments the native side begins once
 * per web view (`first-card-painted` begins at `ready`).
 */
export function useMomentOnPaint(
  name: PerfMoment,
  ready: boolean,
  key: string | null = null,
  oncePerPage = false,
): void {
  useEffect(() => {
    if (!ready) return;
    if (oncePerPage && firedOnce.has(name)) return;
    let second = 0;
    const first = requestAnimationFrame(() => {
      second = requestAnimationFrame(() => {
        if (oncePerPage) {
          if (firedOnce.has(name)) return;
          firedOnce.add(name);
        }
        markMomentEnd(name);
      });
    });
    return () => {
      cancelAnimationFrame(first);
      cancelAnimationFrame(second);
    };
  }, [name, ready, key, oncePerPage]);
}
