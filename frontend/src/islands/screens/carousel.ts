/**
 * The Screens lens's backdrop carousel: one participant's version of a screen at a time, the
 * versions as slides (docs/design-screens.md S5). The web form of the house carousel — the session
 * tapestry's `.bn-tp-nav` disks, under the Welcome window's SlotRotator rules
 * (docs/design-welcome-screen.md §3a): edge chevrons revealed on hover only, never latched on by
 * focus; the disk is the whole hit area; page dots windowed past MAX_DOTS; one slide per horizontal
 * swipe, with a lock; a frame that cross-fades, holding only the showing slide and its
 * neighbours (slideWindow).
 */

/** More slides than this and the dots show a window of them around the current one. */
export const MAX_DOTS = 10;

/** The dots to draw, [start, end), for `n` slides with `cur` showing. */
export function dotWindow(n: number, cur: number, max = MAX_DOTS): [number, number] {
  if (n <= max) return [0, n];
  const start = Math.min(Math.max(0, cur - Math.floor(max / 2)), n - max);
  return [start, start + max];
}

/** A horizontal wheel movement smaller than this is a tremor, not a swipe (px). */
export const SWIPE_MIN = 12;
/** A swipe has ended once the wheel has been still this long (ms); macOS momentum keeps it alive. */
export const SWIPE_IDLE_MS = 280;

/**
 * One step per horizontal swipe. A trackpad swipe arrives as dozens of wheel events, momentum
 * included: the first that is clearly horizontal steps, and the rest are swallowed until the wheel
 * has been still for SWIPE_IDLE_MS. Returns whether the event was ours (horizontal), so the caller
 * can stop the page scrolling or going Back with it.
 */
export function makeSwipe(step: (dir: 1 | -1) => void, now: () => number = () => Date.now()) {
  let lockedUntil = -Infinity;
  return (dx: number, dy: number): boolean => {
    if (Math.abs(dx) <= Math.abs(dy)) return false;
    const t = now();
    const locked = t < lockedUntil;
    lockedUntil = t + SWIPE_IDLE_MS;
    if (!locked && Math.abs(dx) >= SWIPE_MIN) step(dx > 0 ? 1 : -1);
    else if (!locked) lockedUntil = -Infinity; // a tremor neither steps nor locks
    return true;
  };
}

/** The slides fetched and mounted: the showing one and its neighbours either side (wrapping, since
 *  the carousel wraps). Every version at full width for a screen of a dozen participants was a
 *  dozen 1600px stills held at once; a turn needs only the next one ready. */
export function slideWindow(total: number, cur: number, reach = 1): number[] {
  const out: number[] = [];
  for (let d = -reach; d <= reach; d++) {
    const j = (((cur + d) % total) + total) % total;
    if (total > 0 && !out.includes(j)) out.push(j);
  }
  return out;
}

/** A small least-recently-used cache: a get refreshes an entry, a set past `cap` drops the oldest.
 *  Holds the lens's stills (data URIs), which would otherwise accumulate for the page's life. */
export class Lru<V> {
  private map = new Map<string, V>();
  constructor(readonly cap: number) {}
  get(k: string): V | undefined {
    const v = this.map.get(k);
    if (v !== undefined) {
      this.map.delete(k);
      this.map.set(k, v);
    }
    return v;
  }
  has(k: string): boolean {
    return this.map.has(k);
  }
  set(k: string, v: V): void {
    this.map.delete(k);
    this.map.set(k, v);
    while (this.map.size > this.cap) this.map.delete(this.map.keys().next().value as string);
  }
  get size(): number {
    return this.map.size;
  }
}
