/**
 * Live landing's pacing: how many AutoCode tags land on screen now, from how many wait.
 *
 * The lab's "by queue size" mode (`experiments/autocode-landing/template.html`, preset "As
 * planned"), with its tuned values copied here (docs/design-autocode-landing-plan.md Phase 4).
 * Retune in the lab, then change both. The pace aims at "everything waiting, played over the
 * horizon", speeds up freely and slows gently, and never lands tags more often than three times a
 * second (WCAG 2.3.1). When the server has finished, or a hidden window is shown again, what waits
 * is played out over `drain` seconds in at most that many landings, several tags at once in each,
 * so a large end-of-run top-up is a few landings, never a strobe.
 *
 * Pure: the playback store (`contexts/AutoCodePlayback.ts`) owns the clock and the queue.
 *
 * @module livePacing
 */

/** The lab's "As planned" playback handles. */
export const PACING = {
  /** Starting pace, tags a second. */
  startRate: 0.6,
  /** Pace = tags waiting ÷ this many seconds. */
  horizon: 8,
  /** Speed-up limit, tags a second per second. */
  accel: 0.8,
  /** Slow-down limit, tags a second per second. */
  decel: 0.3,
  /** Flash limit, tags a second (WCAG 2.3.1: three flashes in any second). */
  maxRate: 3,
  /** Play the rest when the server is done over this many seconds. */
  drain: 1.5,
} as const;

/**
 * The shortest gap between two landings. A third of a second would let four landings fall in
 * one closed second (at 0, ⅓, ⅔ and 1 s); 350 ms keeps any second to three, which is the cap
 * whether a landing carries one tag or several (they flash together, as one flash).
 */
export const MIN_LANDING_GAP_S = 0.35;

/** Landings a drain is played in: as many as fit in `drain` seconds at the minimum gap. */
export const DRAIN_LANDINGS = Math.floor(PACING.drain / MIN_LANDING_GAP_S) + 1;

export interface PacerState {
  /** Current pace, tags a second. */
  rate: number;
  /** Tags owed by the pace and not landed yet. */
  credits: number;
  /** Seconds since the last landing. */
  sinceLanding: number;
  /** A drain under way: the landings it has left. */
  drainLeft: number | null;
}

export function newPacer(): PacerState {
  return { rate: PACING.startRate, credits: 0, sinceLanding: Infinity, drainLeft: null };
}

/**
 * Advance the pacer by `dt` seconds with `waiting` tags queued, and say how many land now.
 *
 * `"buffer"` while the server is still sending: one tag per landing at most, at the pace.
 * `"drain"` once it has finished (or to catch up after a hidden window): what waits is split
 * over the drain's landings, the last one taking whatever is left.
 */
export function stepPacer(
  p: PacerState,
  dt: number,
  waiting: number,
  mode: "buffer" | "drain",
): number {
  p.sinceLanding += dt;
  if (waiting <= 0) {
    p.drainLeft = null;
    p.credits = Math.min(p.credits, 1);
    // The pace eases off with nothing to play, as gently as it ever does.
    p.rate = Math.max(0, p.rate - PACING.decel * dt);
    return 0;
  }
  if (mode === "drain") {
    if (p.drainLeft === null) p.drainLeft = DRAIN_LANDINGS;
    if (p.sinceLanding < MIN_LANDING_GAP_S) return 0;
    const n = Math.ceil(waiting / Math.max(1, p.drainLeft));
    p.drainLeft = Math.max(1, p.drainLeft - 1);
    p.sinceLanding = 0;
    p.credits = 0;
    return n;
  }
  p.drainLeft = null;
  const target = waiting / PACING.horizon;
  const d = target - p.rate;
  p.rate += d > 0 ? Math.min(d, PACING.accel * dt) : Math.max(d, -PACING.decel * dt);
  p.rate = Math.max(0, Math.min(p.rate, PACING.maxRate));
  p.credits = Math.min(p.credits + p.rate * dt, 2);
  if (p.credits >= 1 && p.sinceLanding >= MIN_LANDING_GAP_S) {
    p.credits -= 1;
    p.sinceLanding = 0;
    return 1;
  }
  return 0;
}

// ── For the tag sidebar overview (Phase 6) and any histogram that grows live ──

/** Rounded steps a growing scale snaps to. */
const NICE = [1, 2, 2.5, 5, 10];

/** The next rounded step at or above `x` (5, 10, 20, 25, 50, 100, …). */
export function niceUp(x: number): number {
  if (x <= 5) return 5;
  const mag = 10 ** Math.floor(Math.log10(x));
  for (const n of NICE) if (n * mag >= x - 1e-9) return n * mag;
  return 10 * mag;
}

/**
 * A scale that only grows, in rounded steps, while a run lands: the tallest bar keeps its
 * height until it outgrows the scale, which then steps up with a quarter's headroom, as the lab
 * does. Pass the previous scale back in.
 */
export function growOnlyScale(previous: number, tallest: number): number {
  return tallest > previous ? niceUp(tallest * 1.25) : previous;
}

/**
 * Squares (one per proposal) or bars, chosen once at the start of a run from what is known up
 * front, the number of quotes, so a chart never switches mid-run: the lab's rule, about a fifth
 * of quotes in the tallest bin.
 */
export function chooseSquares(quoteCount: number, maxStack: number): boolean {
  return quoteCount * 0.22 <= maxStack;
}
