/** Session tapestry scale — the parts SessionsTable needs before any slice is opened. */

export const TAPESTRY_GUTTER = 82;
export const TAPESTRY_RIGHT = 14;

/**
 * One shared scale for every slice: fit the longest session, clamped to 1–4 s/px.
 * Upper clamp: a short project is never blown up. Lower clamp: below 4 s/px a
 * 60-minute session still fits a laptop's grid; longer ones scroll.
 * Measured basis: experiments/session-tapestry/README.md.
 */
export function fitScale(longestSeconds: number, width: number): number {
  const usable = Math.max(1, width - TAPESTRY_GUTTER - TAPESTRY_RIGHT);
  return Math.min(4, Math.max(1, longestSeconds / usable));
}

/** Zoom slider 0–100 → seconds per pixel, log-spaced from fit down to 0.25 s/px. */
export function zoomScale(fit: number, value: number): number {
  return Math.exp(Math.log(fit) + (Math.log(0.25) - Math.log(fit)) * (value / 100));
}

// ── What the researcher left open ─────────────────────────────────────────
// Which timelines are open, the zoom and the sideways scroll, per project, so going to a
// transcript and back shows the same page. Module state covers in-app navigation;
// sessionStorage covers a reload. A per-viewer convenience: every storage access is guarded.

export interface TapestryView {
  open: string[];
  zoom: number;
  scrollLeft: number;
}

const views = new Map<string, TapestryView>();
const storageKey = (projectId: string) => `bn-tapestry-view:${projectId}`;

export function loadTapestryView(projectId: string): TapestryView {
  const held = views.get(projectId);
  if (held) return held;
  try {
    const raw = sessionStorage.getItem(storageKey(projectId));
    if (raw) {
      const v = JSON.parse(raw) as Partial<TapestryView>;
      const view = {
        open: Array.isArray(v.open) ? v.open.filter((x): x is string => typeof x === "string") : [],
        zoom: typeof v.zoom === "number" ? Math.max(0, Math.min(100, v.zoom)) : 0,
        scrollLeft: typeof v.scrollLeft === "number" ? Math.max(0, v.scrollLeft) : 0,
      };
      views.set(projectId, view);
      return view;
    }
  } catch {
    // Storage unavailable or unreadable: start closed.
  }
  return { open: [], zoom: 0, scrollLeft: 0 };
}

export function saveTapestryView(projectId: string, patch: Partial<TapestryView>): void {
  const next = { ...loadTapestryView(projectId), ...patch };
  views.set(projectId, next);
  try {
    sessionStorage.setItem(storageKey(projectId), JSON.stringify(next));
  } catch {
    // Storage unavailable: module state still carries it within this page.
  }
}

/** Tests only. */
export function resetTapestryViews(): void {
  views.clear();
  try {
    for (let i = sessionStorage.length - 1; i >= 0; i--) {
      const k = sessionStorage.key(i);
      if (k?.startsWith("bn-tapestry-view:")) sessionStorage.removeItem(k);
    }
  } catch {
    // nothing to clear
  }
}
