/** Session tapestry scale — the parts SessionsTable needs before any slice is opened. */

export const TAPESTRY_GUTTER = 82;
export const TAPESTRY_RIGHT = 14;
/** Clips are drawn as rounded clips at or below this many seconds per pixel, as slivers above it.
 *  Here, not in SessionTapestry, so the closed strip (TapestryPreview, on first paint) can share it
 *  without importing the lazy timeline. */
export const CLIP_THRESHOLD = 2.5;

/**
 * Short sessions count for less, fading out between these two lengths (seconds). At or below the
 * start a session is treated, for the scale only, as if it were as long as the longest; at or
 * above the end it counts as itself; between the two it slides in a straight line. A taper, not a
 * threshold: a call a minute shorter or longer moves the scale a little, not by a jump. Not a
 * guarantee everywhere: step 1's quarter-of-the-median edge is still a hard step once the median is
 * over about 80 minutes (§4.6.1, known limits), and short calls are lifted to the longest session
 * even when that one is an outlier.
 *
 * Why: short calls are mostly tests, trials and quick chats, and the median counts sessions, not
 * minutes, so a dozen of them outvote the interviews and push every real one many screens wide
 * (docs/design-progressive-lenses.md §4.6.1; decided 9 Nov 2026). The end sits under the shortest
 * session a researcher calls a real interview, so a project of ordinary 25-minute-plus sessions is
 * untouched by construction.
 */
export const SHORT_BAND_START = 8 * 60;
export const SHORT_BAND_END = 20 * 60;

/** How much a duration of `d` seconds counts towards the scale: 1 at or above the band's end, 0 at
 *  or below its start. Exported for the tests. */
export function shortWeight(d: number): number {
  if (d <= SHORT_BAND_START) return 0;
  if (d >= SHORT_BAND_END) return 1;
  return (d - SHORT_BAND_START) / (SHORT_BAND_END - SHORT_BAND_START);
}

/** Each known duration lifted towards the longest by how little it counts: d' = d + (1 − w)(L − d).
 *  If every session is short they are all lifted to the longest, so the scale fits the longest
 *  whole: a project of short calls shows everything. Unknown durations (0) are left as they are. */
export function liftShort(durations: readonly number[]): number[] {
  const longest = durations.reduce((m, d) => (d > m ? d : m), 0);
  return durations.map((d) => (d > 0 ? d + (1 - shortWeight(d)) * (longest - d) : d));
}

/**
 * One shared scale for every slice, from every session's duration, so it is fixed
 * from ingest and never moves while sessions arrive (docs/design-progressive-lenses.md
 * §4.6; the reference is `fitShortest` in docs/mockups/progressive-lenses-replay.html,
 * before step 0):
 *
 * 0. Short sessions fade out of the scale (`liftShort`): under 8 minutes they do not set it,
 *    over 20 they count in full, and the weight slides in between. Run before everything else.
 * 1. Leave out outliers either way: sessions shorter than a quarter of the median or
 *    longer than four times it. A minority must not set the scale for the rest; a
 *    majority moves the median, so stays in. Left-out sessions still draw at this scale.
 * 2. Fit the shortest that remain to the usable width: no timeline opens with white
 *    space on its right.
 * 3. Cap: the longest that remain opens at no more than four widths.
 * 4. The 4 s/px ceiling wins over everything. It binds when the shortest kept session is longer
 *    than 4 × usable seconds (about an hour at a 1000 px table, 34 minutes at 600 px) or the
 *    longest kept is more than 16 × usable seconds (the cap in step 3). (This
 *    comment used to say "below a ~220 px table"; that was wrong for hour-long projects.)
 *
 * A duration of 0 (not known yet: a platform transcript before its import) is left out.
 */
export function fitScale(durations: readonly number[], width: number): number {
  const usable = Math.max(1, width - TAPESTRY_GUTTER - TAPESTRY_RIGHT);
  const sorted = liftShort(durations).filter((d) => d > 0).sort((a, b) => a - b);
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
  // A pixel in hand: the timeline rounds its width up, and duration / (duration / usable) is not
  // always usable in floating point, so a timeline fitted exactly overflowed by 1 px (a sideways
  // scroll, a scrollbar) at about 3% of widths.
  const usable = Math.max(1, width - TAPESTRY_GUTTER - TAPESTRY_RIGHT - 1);
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
