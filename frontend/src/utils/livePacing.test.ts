import { describe, expect, it } from "vitest";
import {
  DRAIN_LANDINGS,
  MIN_LANDING_GAP_S,
  PACING,
  chooseSquares,
  growOnlyScale,
  newPacer,
  niceUp,
  stepPacer,
} from "./livePacing";

const DT = 0.05;

/** Run the pacer for `seconds` with a queue fed by `arrivals` (time → count), recording each
 *  landing's time and size. */
function simulate(
  seconds: number,
  arrivals: Record<number, number>,
  mode: (t: number) => "buffer" | "drain" = () => "buffer",
): { landings: { t: number; n: number }[]; rates: number[]; left: number } {
  const p = newPacer();
  let waiting = 0;
  const landings: { t: number; n: number }[] = [];
  const rates: number[] = [];
  const due = Object.entries(arrivals).map(([t, n]) => ({ t: Number(t), n }));
  for (let i = 0, t = 0; t < seconds; i++, t = i * DT) {
    for (const a of due) if (Math.abs(a.t - t) < DT / 2) waiting += a.n;
    const n = Math.min(waiting, stepPacer(p, DT, waiting, mode(t)));
    if (n > 0) landings.push({ t, n });
    waiting -= n;
    rates.push(p.rate);
  }
  return { landings, rates, left: waiting };
}

/** The most landings in any closed one-second window. */
function maxPerSecond(times: number[]): number {
  let max = 0;
  for (let i = 0; i < times.length; i++) {
    let n = 0;
    for (let j = i; j < times.length && times[j] <= times[i] + 1 + 1e-9; j++) n++;
    max = Math.max(max, n);
  }
  return max;
}

describe("livePacing", () => {
  it("copies the lab's As planned handles", () => {
    expect(PACING).toEqual({ startRate: 0.6, horizon: 8, accel: 0.8, decel: 0.3, maxRate: 3, drain: 1.5 });
  });

  it("never lands more than three times in any second, however long the queue", () => {
    const { landings } = simulate(30, { 0: 500 });
    expect(landings.length).toBeGreaterThan(40);
    expect(maxPerSecond(landings.map((l) => l.t))).toBeLessThanOrEqual(3);
    // One tag per landing while the server is still sending.
    expect(landings.every((l) => l.n === 1)).toBe(true);
  });

  it("starts below the cap, speeds up freely and slows gently", () => {
    const { rates } = simulate(40, { 0: 60 });
    expect(rates[0]).toBeLessThanOrEqual(PACING.startRate + PACING.accel * DT + 1e-9);
    for (let i = 1; i < rates.length; i++) {
      const d = rates[i] - rates[i - 1];
      expect(d).toBeLessThanOrEqual(PACING.accel * DT + 1e-9);
      expect(d).toBeGreaterThanOrEqual(-PACING.decel * DT - 1e-9);
    }
    expect(Math.max(...rates)).toBeLessThanOrEqual(PACING.maxRate);
  });

  it("drains what is left over about a second and a half, a few landings of several tags", () => {
    const { landings, left } = simulate(3, { 0: 40 }, () => "drain");
    expect(left).toBe(0);
    expect(landings.length).toBe(DRAIN_LANDINGS);
    expect(landings.reduce((s, l) => s + l.n, 0)).toBe(40);
    const last = landings[landings.length - 1].t;
    expect(last).toBeLessThanOrEqual(PACING.drain + 1e-9);
    expect(maxPerSecond(landings.map((l) => l.t))).toBeLessThanOrEqual(3);
    for (let i = 1; i < landings.length; i++) {
      expect(landings[i].t - landings[i - 1].t).toBeGreaterThanOrEqual(MIN_LANDING_GAP_S - 1e-9);
    }
  });

  it("drains a short queue one tag a landing", () => {
    const { landings } = simulate(3, { 0: 3 }, () => "drain");
    expect(landings.map((l) => l.n)).toEqual([1, 1, 1]);
  });

  it("lands nothing with nothing waiting", () => {
    const p = newPacer();
    expect(stepPacer(p, 1, 0, "buffer")).toBe(0);
    expect(stepPacer(p, 1, 0, "drain")).toBe(0);
  });
});

describe("grow-only scales (for the tag sidebar overview)", () => {
  it("only grows, in rounded steps", () => {
    expect(niceUp(3)).toBe(5);
    expect(niceUp(6)).toBe(10);
    expect(niceUp(11)).toBe(20);
    expect(niceUp(21)).toBe(25);
    expect(niceUp(26)).toBe(50);
    let scale = 5;
    const seen: number[] = [];
    for (const tallest of [1, 4, 6, 3, 9, 13, 2, 30]) {
      scale = growOnlyScale(scale, tallest);
      seen.push(scale);
    }
    for (let i = 1; i < seen.length; i++) expect(seen[i]).toBeGreaterThanOrEqual(seen[i - 1]);
    expect(seen).toEqual([5, 5, 10, 10, 10, 20, 20, 50]);
  });

  it("chooses squares or bars once, from the quote count", () => {
    expect(chooseSquares(40, 18)).toBe(true);
    expect(chooseSquares(200, 18)).toBe(false);
  });
});
