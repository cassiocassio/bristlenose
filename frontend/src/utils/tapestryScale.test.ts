import { describe, expect, it } from "vitest";
import { fitScale, liftShort, shortWeight } from "./tapestryScale";

// A 1280 px window: 906 px usable.
const W = 906 + 82 + 14;
const m = (...mins: number[]) => mins.map((x) => x * 60);
const rep = (n: number, x: number) => Array.from({ length: n }, () => x);

describe("short sessions fade out of the scale (design-progressive-lenses §4.6.1)", () => {
  it("weights 0 at or under 8 minutes, 1 at or over 20, a straight line between", () => {
    expect(shortWeight(0)).toBe(0);
    expect(shortWeight(8 * 60)).toBe(0);
    expect(shortWeight(14 * 60)).toBeCloseTo(0.5, 10);
    expect(shortWeight(20 * 60)).toBe(1);
    expect(shortWeight(3 * 3600)).toBe(1);
  });
  it("lifts a short call to the longest, and leaves unknown durations alone", () => {
    expect(liftShort([300, 3600, 0])).toEqual([3600, 3600, 0]);
  });
  it("lifts each duration to somewhere between itself and the longest", () => {
    const d = m(2, 9, 14, 19, 25, 60);
    const lifted = liftShort(d);
    lifted.forEach((v, i) => {
      expect(v).toBeGreaterThanOrEqual(d[i]);
      expect(v).toBeLessThanOrEqual(60 * 60);
    });
  });
  it("lifts nothing when every session is at or over the band's end", () => {
    const d = m(20, 25, 38, 45, 60);
    expect(liftShort(d)).toEqual(d);
  });
  it("fits the long interviews when short calls are the more numerous", () => {
    for (const d of [[...rep(5, 5), ...rep(4, 30)], [...rep(18, 5), 30, 33]]) {
      const fit = fitScale(m(...d), W);
      expect(Math.max(...m(...d)) / fit / 906).toBeLessThan(1.11);
      expect(fit).toBeGreaterThan(1.9);
    }
  });
  it("fits the longest of a handful of test calls (1, 2, 3, 14 minutes)", () => {
    const fit = fitScale(m(1, 2, 3, 14), W);
    expect(fit).toBeCloseTo(0.927, 2);
    expect(14 * 60 / fit / 906).toBeCloseTo(1, 5);
  });
  it("leaves a project of micro-interviews as it was", () => {
    expect(fitScale(m(...rep(20, 5)), W)).toBeCloseTo(0.331, 3);
  });
  it("leaves ordinary projects exactly as they were (every session at or over the band's end)", () => {
    expect(fitScale(m(25, 30, 38, 45, 52, 60), W)).toBeCloseTo(1.6556, 3);
    expect(fitScale(m(43, 48, 52, 55, 60, 70), W)).toBeCloseTo(2.8477, 3);
    expect(fitScale(m(24, 26, 28, 30, 32, 35), W)).toBeCloseTo(1.5894, 3);
  });
  it("still leaves out a session under a quarter of the median when it is over the band", () => {
    // 20 minutes beside an 85-minute median: left out by the old rule, so it does not set the scale.
    expect(fitScale(m(20, 80, 85, 90), W)).toBeCloseTo(fitScale(m(80, 85, 90), W), 10);
  });
  it("keeps a workshop that is an outlier an outlier", () => {
    const fit = fitScale(m(30, 30, 30, 180), W);
    expect(fit).toBeCloseTo(1.9868, 3);
    expect(180 * 60 / fit / 906).toBeCloseTo(6, 3);
  });
  it("lets the 4 s/px ceiling bound check-ins beside a workshop", () => {
    const fit = fitScale(m(...rep(8, 10), 180), W);
    expect(fit).toBe(4);
  });
  it("moves continuously: one session swept across the band never makes the scale jump", () => {
    // The rule this exists for. The step between neighbouring lengths stays small, including
    // across both edges of the band and the old "shorter than a quarter of the median" edge.
    const rest = m(58, 60, 61, 62);
    let prev = fitScale([...rest, 60], W);
    for (let sec = 60; sec <= 40 * 60; sec += 15) {
      const cur = fitScale([...rest, sec], W);
      expect(Math.abs(Math.log(cur / prev))).toBeLessThan(0.05);
      prev = cur;
    }
  });
});
