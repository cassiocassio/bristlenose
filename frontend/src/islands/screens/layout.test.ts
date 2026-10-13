import { beforeEach, describe, expect, it } from "vitest";
import {
  clearSpots,
  GUTTER,
  leaderPath,
  MIN_STEP,
  placeColumn,
  putSpot,
  resetArrangementMemory,
  sideFor,
  spotsFor,
  topZ,
} from "./layout";

describe("sideFor", () => {
  it("puts a card on the side of the page its element is in, only when the stage is wide", () => {
    const left = { x: 0.1, y: 0.2, w: 0.2, h: 0.05 };
    const right = { x: 0.6, y: 0.2, w: 0.2, h: 0.05 };
    expect(sideFor(left, true)).toBe("L");
    expect(sideFor(right, true)).toBe("R");
    expect(sideFor(left, false)).toBe("R");
  });
});

describe("placeColumn", () => {
  it("sits each card level with its element when there is room", () => {
    const { placed, stacked } = placeColumn(
      [{ want: 10, height: 50 }, { want: 200, height: 50 }],
      600,
    );
    expect(stacked).toBe(false);
    expect(placed.map((p) => p.top)).toEqual([10, 200]);
  });

  it("pushes a card down by a gutter rather than overlapping the one above", () => {
    const { placed } = placeColumn([{ want: 10, height: 80 }, { want: 20, height: 50 }], 600);
    expect(placed[1].top).toBe(10 + 80 + GUTTER);
  });

  it("stacks a column that would run past the screengrab, keeping every card on it", () => {
    const cards = Array.from({ length: 6 }, (_, i) => ({ want: i * 10, height: 150 }));
    const { placed, stacked, bottom } = placeColumn(cards, 400);
    expect(stacked).toBe(true);
    expect(bottom).toBeLessThanOrEqual(400 + 1e-9);
    const steps = placed.slice(1).map((p, i) => p.top - placed[i].top);
    for (const s of steps) expect(s).toBeGreaterThanOrEqual(MIN_STEP - 1e-9);
    expect(new Set(steps.map((s) => s.toFixed(3))).size).toBe(1); // evenly stepped
  });

  it("slides a diagonal stack right a few pixels per card, and a straight one not at all", () => {
    const cards = Array.from({ length: 4 }, () => ({ want: 0, height: 200 }));
    expect(placeColumn(cards, 300, true).placed.map((p) => p.slide)).toEqual([0, 8, 16, 24]);
    expect(placeColumn(cards, 300, false).placed.every((p) => p.slide === 0)).toBe(true);
  });
});

describe("leaderPath", () => {
  it("leaves the card by the edge facing its element and ends on the element's near edge", () => {
    const card = { left: 0, top: 100, width: 200, height: 80 };
    const el = { left: 400, top: 50, width: 100, height: 20 };
    const { d, end } = leaderPath(card, el);
    expect(d.startsWith("M200,116")).toBe(true);
    expect(end).toEqual([397, 60]);
    const right = leaderPath({ left: 600, top: 0, width: 200, height: 80 }, el);
    expect(right.end).toEqual([503, 60]);
  });
});

describe("arrangement", () => {
  beforeEach(() => {
    localStorage.clear();
    resetArrangementMemory();
  });

  it("keeps a researcher's placement per screengrab, and survives a reload", () => {
    putSpot("s1@100", "q-p1-10", { x: 0.2, y: 0.3, z: 31 });
    resetArrangementMemory();
    expect(spotsFor("s1@100")).toEqual({ "q-p1-10": { x: 0.2, y: 0.3, z: 31 } });
    expect(spotsFor("s1@104")).toEqual({});
    expect(topZ()).toBe(31);
  });

  it("puts one screengrab's quotes back without touching another's", () => {
    putSpot("s1@100", "a", { x: 0, y: 0, z: 31 });
    putSpot("s2@50", "b", { x: 0, y: 0, z: 32 });
    clearSpots("s1@100");
    expect(spotsFor("s1@100")).toEqual({});
    expect(spotsFor("s2@50")).toEqual({ b: { x: 0, y: 0, z: 32 } });
  });
});
