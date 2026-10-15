import { describe, expect, it } from "vitest";
import { dotWindow, Lru, makeSwipe, MAX_DOTS, slideWindow, SWIPE_IDLE_MS } from "./carousel";

describe("dotWindow", () => {
  it("shows every dot up to MAX_DOTS, and a window around the current one past it", () => {
    expect(dotWindow(3, 1)).toEqual([0, 3]);
    expect(dotWindow(MAX_DOTS, 9)).toEqual([0, MAX_DOTS]);
    expect(dotWindow(30, 0)).toEqual([0, 10]);
    expect(dotWindow(30, 15)).toEqual([10, 20]);
    expect(dotWindow(30, 29)).toEqual([20, 30]);
    for (let cur = 0; cur < 30; cur++) {
      const [a, b] = dotWindow(30, cur);
      expect(b - a).toBe(MAX_DOTS);
      expect(cur >= a && cur < b).toBe(true);
    }
  });
});

describe("makeSwipe", () => {
  it("steps once per horizontal swipe, momentum included, and again after the wheel has rested", () => {
    let t = 0;
    const steps: number[] = [];
    const swipe = makeSwipe((d) => steps.push(d), () => t);
    // A trackpad swipe left-to-right reads as positive deltaX: dozens of events, then momentum.
    for (let i = 0; i < 30; i++) {
      expect(swipe(40 - i, 2)).toBe(true);
      t += 16;
    }
    expect(steps).toEqual([1]);
    t += SWIPE_IDLE_MS + 1;
    swipe(-30, 0);
    expect(steps).toEqual([1, -1]);
  });
  it("leaves a vertical scroll alone, and a tremor neither steps nor locks", () => {
    let t = 0;
    const steps: number[] = [];
    const swipe = makeSwipe((d) => steps.push(d), () => t);
    expect(swipe(3, 40)).toBe(false);
    expect(swipe(4, 1)).toBe(true);
    expect(steps).toEqual([]);
    t += 16;
    swipe(30, 0);
    expect(steps).toEqual([1]);
  });
});

describe("slideWindow", () => {
  it("is the showing slide and its neighbours, wrapping, once each", () => {
    expect(slideWindow(5, 0)).toEqual([4, 0, 1]);
    expect(slideWindow(5, 4)).toEqual([3, 4, 0]);
    expect(slideWindow(2, 0)).toEqual([1, 0]);
    expect(slideWindow(1, 0)).toEqual([0]);
  });
});

describe("Lru", () => {
  it("drops the least recently used past its cap, and a get refreshes", () => {
    const c = new Lru<number>(2);
    c.set("a", 1);
    c.set("b", 2);
    expect(c.get("a")).toBe(1); // a is now the most recent
    c.set("c", 3);
    expect(c.has("b")).toBe(false);
    expect(c.has("a")).toBe(true);
    expect(c.size).toBe(2);
  });
});
