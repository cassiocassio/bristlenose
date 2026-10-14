import { beforeEach, describe, expect, it } from "vitest";
import {
  arrangeColumn,
  boardColumns,
  clearPlacement,
  placementFromDrop,
  placementsFor,
  putPlacement,
  setPlacements,
  ONE_COLUMN_STAGE,
  WIDE_STAGE,
  GUTTER,
  leaderPath,
  MIN_STEP,
  placeColumn,
  resetArrangementMemory,
  sideFor,
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

describe("boardColumns", () => {
  // Cards sit beside the screengrab, never over it; the screengrab shrinks, the cards do not.
  it("gives each side with cards a column, and a side without cards none", () => {
    expect(boardColumns(1600, { L: true, R: true })).toBe("lr");
    expect(boardColumns(1600, { L: false, R: true })).toBe("r");
    expect(boardColumns(1600, { L: true, R: false })).toBe("l");
    expect(boardColumns(1600, { L: false, R: false })).toBe("none");
  });
  it("stops putting cards beside the screengrab below the width that keeps it legible", () => {
    expect(boardColumns(ONE_COLUMN_STAGE, { L: false, R: true })).toBe("r");
    expect(boardColumns(ONE_COLUMN_STAGE - 1, { L: false, R: true })).toBe("none");
  });
  it("leaves the first, unmeasured layout its columns", () => {
    expect(boardColumns(0, { L: false, R: true })).toBe("r");
  });
  it("keeps a legible screengrab between two columns and their gutters", () => {
    expect(WIDE_STAGE - 2 * (270 + 32)).toBe(480);
    expect(ONE_COLUMN_STAGE - (270 + 32)).toBe(480);
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
  const edge = (side: "L" | "R", frac: number, z = 31) => ({ kind: "edge" as const, side, frac, z });

  it("keeps a researcher's placement per screengrab as intent, and survives a reload", () => {
    putPlacement("1", "s1@100", "q-p1-10", edge("L", 0.3));
    resetArrangementMemory();
    expect(placementsFor("1", "s1@100")).toEqual({ "q-p1-10": edge("L", 0.3) });
    expect(placementsFor("1", "s1@104")).toEqual({});
    expect(topZ("1")).toBe(31);
  });

  it("returns one card, or one screengrab's cards, to automatic without touching another's", () => {
    putPlacement("1", "s1@100", "a", edge("L", 0));
    putPlacement("1", "s1@100", "c", edge("R", 0.5, 33));
    putPlacement("1", "s2@50", "b", edge("R", 0, 32));
    clearPlacement("1", "s1@100", "a");
    expect(placementsFor("1", "s1@100")).toEqual({ c: edge("R", 0.5, 33) });
    setPlacements("1", "s1@100", {});
    expect(placementsFor("1", "s1@100")).toEqual({});
    expect(placementsFor("1", "s2@50")).toEqual({ b: edge("R", 0, 32) });
  });

  it("converts the first build's coordinates to intent, once", () => {
    localStorage.setItem("bristlenose-screens-arrangement-1", JSON.stringify({
      "s1@100/a": { x: -0.3, y: 0.2, z: 31 }, // left of the screengrab
      "s1@100/b": { x: 1.02, y: 0.5, z: 32 }, // past its right edge
      "s1@100/c": { x: 0.4, y: 0.4, z: 33 }, // over it
    }));
    expect(placementsFor("1", "s1@100")).toEqual({
      a: edge("L", 0.2, 31),
      b: edge("R", 0.5, 32),
      c: { kind: "over", x: 0.4, y: 0.4, z: 33 },
    });
    expect(localStorage.getItem("bristlenose-screens-arrangement-1")).toBeNull();
    resetArrangementMemory();
    expect(Object.keys(placementsFor("1", "s1@100"))).toEqual(["a", "b", "c"]);
  });

  // Keyed by the page's project id. That id is always "1" today, so in practice this separates
  // arrangements by origin only; the test pins the key's shape for when multi-project makes it real.
  it("keys the arrangement by the project id it is given", () => {
    putPlacement("1", "s1@100", "q-p1-10", edge("L", 0.3));
    resetArrangementMemory(); // what a reload, or opening the other project, starts from
    expect(placementsFor("2", "s1@100")).toEqual({});
    expect(topZ("2")).toBe(30);
    setPlacements("2", "s1@100", {});
    expect(placementsFor("1", "s1@100")).toEqual({ "q-p1-10": edge("L", 0.3) });
  });
});

describe("placementFromDrop", () => {
  const shot = { left: 300, top: 0, width: 600, height: 400 };
  it("reads a drop beside the screengrab as a side and a place down its edge", () => {
    expect(placementFromDrop({ left: 10, top: 100, width: 270 }, shot, 40)).toEqual({ kind: "edge", side: "L", frac: 0.25, z: 40 });
    expect(placementFromDrop({ left: 940, top: 200, width: 270 }, shot, 41)).toEqual({ kind: "edge", side: "R", frac: 0.5, z: 41 });
  });
  it("reads a drop with its centre over the screengrab as over it", () => {
    expect(placementFromDrop({ left: 400, top: 40, width: 270 }, shot, 42)).toEqual({ kind: "over", x: 100 / 600, y: 0.1, z: 42 });
  });
});

describe("arrangeColumn", () => {
  const card = (id: string, want: number, placed = false, height = 100, z = 0) => ({ id, want, placed, height, z });

  it("is the automatic column when nobody has placed a card", () => {
    const { tops } = arrangeColumn([card("b", 300), card("a", 0)], 800);
    expect(tops).toEqual({ a: 0, b: 300 });
  });

  // The owner: respect the cards the researcher moved, and re-organise the ones they didn't.
  it("keeps placed cards where they were put, and moves untouched ones out of their way", () => {
    // An untouched card wants 200; a placed card sits at 180. The placed card wins.
    const { tops } = arrangeColumn([card("auto", 200), card("mine", 180, true)], 800);
    expect(tops.mine).toBe(180);
    expect(tops.auto + 100 + GUTTER <= 180 || tops.auto >= 180 + 100 + GUTTER).toBe(true);
    // ...into the free slot nearest its anchor: just below the placed card (292) is 92 away, above
    // it (68) is 132 away.
    expect(tops.auto).toBe(180 + 100 + GUTTER);
  });

  it("keeps the researcher's order between placed cards, pushing a later one down rather than overlapping", () => {
    const { tops } = arrangeColumn([card("second", 50, true, 100, 32), card("first", 40, true, 100, 31)], 800);
    expect(tops.first).toBe(40);
    expect(tops.second).toBe(40 + 100 + GUTTER);
  });

  it("re-flows untouched cards in anchor order around several placed ones", () => {
    const { tops } = arrangeColumn(
      [card("p1", 100, true), card("p2", 400, true), card("u1", 120), card("u2", 300)],
      800,
    );
    expect(tops.p1).toBe(100);
    expect(tops.p2).toBe(400);
    const spans = Object.entries(tops).map(([id, t]) => [t, t + 100, id] as const).sort((a, b) => a[0] - b[0]);
    for (let i = 1; i < spans.length; i++) expect(spans[i][0]).toBeGreaterThanOrEqual(spans[i - 1][1] + GUTTER);
  });
});
