import { lazy, Suspense, useEffect, useState } from "react";

let pending: Promise<{ default: typeof import("./SessionsSidebar").SessionsSidebar }> | undefined;

function loadSidebar() {
  // Share the preload with an early click. A rejected preload must not poison
  // the panel's next attempt (including the existing sidebar Retry button).
  return pending ??= import("./SessionsSidebar")
    .then((m) => ({ default: m.SessionsSidebar }))
    .catch((error: unknown) => {
      pending = undefined;
      throw error;
    });
}

/** Mounted by the grid/transcript only once its main data is drawn. */
export function PreloadSessionsSidebar() {
  useEffect(() => {
    let idle: number | undefined;
    let timer: ReturnType<typeof setTimeout> | undefined;
    // Give the lens its paint, then use idle time. The timer is a fallback for
    // browsers without requestIdleCallback, not a delay imposed on an open panel.
    const frame = requestAnimationFrame(() => {
      const preload = () => { void loadSidebar().catch(() => {}); };
      if (typeof window.requestIdleCallback === "function") {
        idle = window.requestIdleCallback(preload, { timeout: 2000 });
      } else {
        timer = setTimeout(preload, 1500);
      }
    });
    return () => {
      cancelAnimationFrame(frame);
      if (idle !== undefined) window.cancelIdleCallback(idle);
      if (timer !== undefined) clearTimeout(timer);
    };
  }, []);
  return null;
}

/** The surrounding PanelErrorBoundary remounts this on Retry. */
export function DeferredSessionsSidebar({ visible }: { visible: boolean }) {
  // React.lazy caches rejected imports. A fresh instance on a boundary remount
  // lets Retry try again, while the module promise shares successful loads.
  const [Panel] = useState(() => lazy(loadSidebar));
  return visible ? <Suspense fallback={null}><Panel /></Suspense> : null;
}
