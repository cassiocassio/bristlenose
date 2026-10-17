/** Session tapestry scale — the parts SessionsTable needs before any slice is opened. */

export const TAPESTRY_GUTTER = 82;
export const TAPESTRY_RIGHT = 14;
/** Clips are drawn as rounded clips at or below this many seconds per pixel, as slivers above it.
 *  Here, not in SessionTapestry, so the closed strip (TapestryPreview, on first paint) can share it
 *  without importing the lazy timeline. */
export const CLIP_THRESHOLD = 2.5;

/**
 * One shared scale for every slice, from every session's duration, so it is fixed
 * from ingest and never moves while sessions arrive (docs/design-progressive-lenses.md
 * §4.6; the reference is `fitShortest` in docs/mockups/progressive-lenses-replay.html):
 *
 * 1. Leave out outliers either way: sessions shorter than a quarter of the median or
 *    longer than four times it. A minority must not set the scale for the rest; a
 *    majority moves the median, so stays in. Left-out sessions still draw at this scale.
 * 2. Fit the shortest that remain to the usable width: no timeline opens with white
 *    space on its right.
 * 3. Cap: the longest that remain opens at no more than four widths.
 * 4. The 4 s/px ceiling wins over everything (it bites only below a ~220 px table).
 *
 * A duration of 0 (not known yet: a platform transcript before its import) is left out.
 */
export function fitScale(durations: readonly number[], width: number): number {
  const usable = Math.max(1, width - TAPESTRY_GUTTER - TAPESTRY_RIGHT);
  const sorted = durations.filter((d) => d > 0).sort((a, b) => a - b);
  if (sorted.length === 0) return 1;
  const mid = sorted.length / 2;
  const median = sorted.length % 2
    ? sorted[Math.floor(mid)]
    : (sorted[mid - 1] + sorted[mid]) / 2;
  const kept = sorted.filter((d) => d >= median / 4 && d <= median * 4);
  const shortest = kept[0];
  const longest = kept[kept.length - 1];
  return Math.min(4, Math.max(shortest / usable, longest / (4 * usable)));
}

/**
 * One session fitted to the width: the transcript's timeline, which has no other session to share
 * a scale with. The same 4 s/px ceiling as `fitScale`, so a very long session at a narrow window
 * scrolls sideways rather than drawing finer than the grid ever does.
 */
export function fitSession(duration: number, width: number): number {
  const usable = Math.max(1, width - TAPESTRY_GUTTER - TAPESTRY_RIGHT);
  return duration > 0 ? Math.min(4, duration / usable) : 1;
}

/** Zoom slider 0–100 → seconds per pixel, log-spaced from fit down to min(0.25, fit / 4),
 *  so a short project fitted below 0.25 s/px still has room to zoom in. */
export function zoomScale(fit: number, value: number): number {
  const far = Math.min(0.25, fit / 4);
  return Math.exp(Math.log(fit) + (Math.log(far) - Math.log(fit)) * (value / 100));
}

// ── What the researcher left open ─────────────────────────────────────────
// Which timelines are open, the zoom and each timeline's sideways scroll, per project, so going to a
// transcript and back shows the same page. Module state covers in-app navigation;
// sessionStorage covers a reload. A per-viewer convenience: every storage access is guarded.

export interface TapestryView {
  open: string[];
  zoom: number;
  /** Each session's own sideways scroll: the timelines scroll independently. */
  scroll: Record<string, number>;
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
        scroll: v.scroll && typeof v.scroll === "object"
          ? Object.fromEntries(Object.entries(v.scroll).filter(([, n]) => typeof n === "number" && n >= 0))
          : {},
      };
      views.set(projectId, view);
      return view;
    }
  } catch {
    // Storage unavailable or unreadable: start closed.
  }
  return { open: [], zoom: 0, scroll: {} };
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
