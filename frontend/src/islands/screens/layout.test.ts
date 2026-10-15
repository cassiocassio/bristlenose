import { beforeEach, describe, expect, it } from "vitest";
import {
  arrangeColumn,
  boardColumns,
  CARD_W,
  cardEdge,
  clearPlacement,
  COLUMN_GUTTER,
  composeBoard,
  edgeFor,
  HYSTERESIS,
  placementFromDrop,
  placementsFor,
  placeRow,
  putPlacement,
  setPlacements,
  stageMode,
  ONE_COLUMN_STAGE,
  WIDE_STAGE,
  GUTTER,
  leaderPath,
  MIN_STEP,
  placeColumn,
  resetArrangementMemory,
  topZ,
  type BoardCard,
  type Composition,
  type Mode,
  type Rect,
} from "./layout";

describe("edgeFor", () => {
  // Boundary labelling: a card goes to the band nearest its line.
  it("sends a line to the side of the page it is in, both sides only when there are two columns", () => {
    const left = { x: 0.05, y: 0.4, w: 0.1, h: 0.05 };
    const right = { x: 0.7, y: 0.4, w: 0.2, h: 0.05 };
    expect(edgeFor(left, "lr")).toBe("L");
    expect(edgeFor(right, "lr")).toBe("R");
    expect(edgeFor(left, "r")).toBe("R");
  });
  it("sends a header or footer line in the middle of the page to the band above or below", () => {
    const search = { x: 0.35, y: 0.03, w: 0.3, h: 0.04 };
    const footer = { x: 0.4, y: 0.92, w: 0.2, h: 0.03 };
    expect(edgeFor(search, "lr")).toBe("T");
    expect(edgeFor(footer, "r")).toBe("B");
  });
  it("keeps the bands to clear cases: a top line at the side edge, or a line just below the top, goes to a side", () => {
    expect(edgeFor({ x: 0.0, y: 0.03, w: 0.1, h: 0.04 }, "lr")).toBe("L"); // a logo in the corner
    expect(edgeFor({ x: 0.3, y: 0.2, w: 0.1, h: 0.04 }, "lr")).toBe("L"); // below the top 15%
  });
  it("turns the sides into rows above and below when there is no room for a column", () => {
    expect(edgeFor({ x: 0.05, y: 0.3, w: 0.1, h: 0.05 }, "rows")).toBe("T");
    expect(edgeFor({ x: 0.8, y: 0.7, w: 0.1, h: 0.05 }, "rows")).toBe("B");
  });
});

describe("stageMode and boardColumns", () => {
  // Cards sit around the screengrab, never over it; the screengrab shrinks, the cards do not.
  it("gives each side with cards a column, and a side without cards none", () => {
    expect(boardColumns("lr", { L: true, R: true })).toBe("lr");
    expect(boardColumns("lr", { L: false, R: true })).toBe("r");
    expect(boardColumns("lr", { L: true, R: false })).toBe("l");
    expect(boardColumns("lr", { L: false, R: false })).toBe("none");
    expect(boardColumns("rows", { L: true, R: true })).toBe("none");
  });
  it("stops putting cards beside the screengrab below the width that keeps it legible", () => {
    expect(stageMode(WIDE_STAGE)).toBe("lr");
    expect(stageMode(WIDE_STAGE - 1)).toBe("r");
    expect(stageMode(ONE_COLUMN_STAGE)).toBe("r");
    expect(stageMode(ONE_COLUMN_STAGE - 1)).toBe("rows");
  });
  it("leaves the first, unmeasured layout one column", () => {
    expect(stageMode(0)).toBe("r");
    expect(stageMode(0, "rows")).toBe("rows");
  });
  it("keeps a legible screengrab between two columns and their gutters", () => {
    expect(WIDE_STAGE - 2 * (270 + 32)).toBe(480);
    expect(ONE_COLUMN_STAGE - (270 + 32)).toBe(480);
  });
  // A stage resting on a threshold must not flip back and forth: the layout's own height change
  // brings the page's scrollbar in or out, which moves the stage across the line again.
  it("switches down at a threshold and back up only once the stage is well past it (hysteresis)", () => {
    let mode: Mode = stageMode(ONE_COLUMN_STAGE + 5);
    expect(mode).toBe("r");
    mode = stageMode(ONE_COLUMN_STAGE - 5, mode); // a scrollbar appears: narrower, rows
    expect(mode).toBe("rows");
    mode = stageMode(ONE_COLUMN_STAGE + 5, mode); // ...and goes: back across the line, still rows
    expect(mode).toBe("rows");
    mode = stageMode(ONE_COLUMN_STAGE + HYSTERESIS - 1, mode);
    expect(mode).toBe("rows");
    mode = stageMode(ONE_COLUMN_STAGE + HYSTERESIS, mode);
    expect(mode).toBe("r");
    // The same at the two-column line, and narrowing is never held back (the screengrab's floor).
    mode = stageMode(WIDE_STAGE, mode);
    expect(mode).toBe("r");
    mode = stageMode(WIDE_STAGE + HYSTERESIS, mode);
    expect(mode).toBe("lr");
    expect(stageMode(WIDE_STAGE - 1, mode)).toBe("r");
    // A jump wider than both thresholds goes straight to two columns.
    expect(stageMode(2000, "rows")).toBe("lr");
  });
  it("never flips more than once while the stage wobbles across a threshold by a scrollbar's width", () => {
    let mode: Mode = "r";
    const seen: Mode[] = [];
    for (let i = 0; i < 20; i++) {
      mode = stageMode(ONE_COLUMN_STAGE + (i % 2 === 0 ? -8 : 7), mode);
      seen.push(mode);
    }
    const flips = seen.filter((m, i) => i > 0 && m !== seen[i - 1]).length;
    expect(flips).toBe(0);
    expect(mode).toBe("rows");
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
  const el = { left: 400, top: 50, width: 100, height: 20 };
  const turns = (d: string) => (d.match(/L/g) ?? []).length;
  it("leaves the card by the edge facing its line and ends on the line's near edge", () => {
    const card = { left: 0, top: 100, width: 200, height: 80 };
    const { d, end } = leaderPath(card, el, "L");
    expect(d.startsWith("M200,116")).toBe(true);
    expect(end).toEqual([397, 60]);
    const right = leaderPath({ left: 600, top: 0, width: 200, height: 80 }, el, "R");
    expect(right.end).toEqual([503, 60]);
  });
  it("is straight where the line is level with the card, and has a single elbow otherwise", () => {
    const level = leaderPath({ left: 0, top: 20, width: 200, height: 80 }, el, "L");
    expect(level.d).toBe("M200,60 L397,60");
    expect(turns(level.d)).toBe(1);
    const below = leaderPath({ left: 0, top: 300, width: 200, height: 80 }, el, "L");
    expect(turns(below.d)).toBe(2); // a shoulder, then one run
  });
  it("runs vertically from a band above or below", () => {
    const above = leaderPath({ left: 350, top: 0, width: 200, height: 40 }, el, "T");
    expect(above.d).toBe("M450,40 L450,47");
    const below = leaderPath({ left: 350, top: 200, width: 200, height: 40 }, el, "B");
    expect(below.end).toEqual([450, 73]);
  });
  it("fans the leaders of several cards about one line into one point", () => {
    const ends = [0, 120, 240].map((top) => leaderPath({ left: 0, top, width: 200, height: 100 }, el, "L").end);
    expect(new Set(ends.map((e) => e.join(","))).size).toBe(1);
  });
});

describe("placeRow", () => {
  it("sets each card under its line, in order, a gutter apart, and inside the band", () => {
    const { lefts, tops, height } = placeRow(
      [{ want: 100, width: 270, height: 80 }, { want: 120, width: 270, height: 60 }],
      1000,
    );
    expect(lefts).toEqual([100, 100 + 270 + GUTTER]);
    expect(tops).toEqual([0, 0]);
    expect(height).toBe(80);
  });
  it("carries on on a further line when the band runs out of width, and reserves its whole height", () => {
    const { lefts, tops, height } = placeRow(
      [{ want: 0, width: 270, height: 80 }, { want: 300, width: 270, height: 50 }],
      400,
    );
    expect(tops).toEqual([0, 80 + GUTTER]);
    for (const l of lefts) expect(l + 270).toBeLessThanOrEqual(400);
    expect(height).toBe(80 + GUTTER + 50);
  });
});

/** A model of the board's grid (screens.css): columns either side, bands above and below, each a
 *  gutter from the screengrab. Where every card of a composition lands, in board space. */
function boardRects(comp: Composition, cards: BoardCard[], mode: Mode, shot: { W: number; H: number }) {
  const sides = { L: false, R: false };
  for (const c of cards) {
    const e = cardEdge(c, mode);
    if (e === "L" || e === "R") sides[e] = true;
  }
  const cols = boardColumns(mode, sides);
  const shotX = cols === "l" || cols === "lr" ? CARD_W + COLUMN_GUTTER : 0;
  const shotY = comp.band.T ? comp.band.T + COLUMN_GUTTER : 0;
  const out: Record<string, Rect> = {};
  for (const c of cards) {
    const s = comp.at[c.id];
    const r = { width: CARD_W, height: c.height };
    if (s.edge === "L") out[c.id] = { ...r, left: 0, top: shotY + s.top };
    else if (s.edge === "R") out[c.id] = { ...r, left: shotX + shot.W + COLUMN_GUTTER, top: shotY + s.top };
    else if (s.edge === "T") out[c.id] = { ...r, left: shotX + s.left, top: s.top };
    else out[c.id] = { ...r, left: shotX + s.left, top: shotY + shot.H + COLUMN_GUTTER + s.top };
  }
  return { shot: { left: shotX, top: shotY, width: shot.W, height: shot.H }, cards: out };
}

const overlaps = (a: Rect, b: Rect) =>
  a.left < b.left + b.width && b.left < a.left + a.width && a.top < b.top + b.height && b.top < a.top + a.height;

describe("composeBoard", () => {
  // A small deterministic generator: lines all over the page, of every kind of height.
  function lines(n: number, seed: number): BoardCard[] {
    let x = seed;
    const rnd = () => ((x = (x * 1103515245 + 12345) % 2147483648) / 2147483648);
    return Array.from({ length: n }, (_, i) => ({
      id: `q${i}`,
      height: 60 + Math.floor(rnd() * 160),
      anchor: { x: rnd() * 0.9, y: rnd() * 0.97, w: 0.05 + rnd() * 0.05, h: 0.02 },
    }));
  }

  it("never puts an automatic card over the screengrab, on any edge, in any mode", () => {
    const sizes: Record<Mode, { W: number; H: number }> = {
      lr: { W: 700, H: 500 }, r: { W: 500, H: 400 }, rows: { W: 560, H: 380 },
    };
    for (const mode of ["lr", "r", "rows"] as Mode[]) {
      for (let seed = 1; seed <= 25; seed++) {
        const cards = lines(1 + (seed % 9), seed);
        const comp = composeBoard(cards, mode, sizes[mode]);
        const { shot, cards: rects } = boardRects(comp, cards, mode, sizes[mode]);
        for (const c of cards) expect(overlaps(rects[c.id], shot), `${mode} seed ${seed} ${c.id}`).toBe(false);
      }
    }
  });

  it("uses all four edges in two-column mode, and only rows when narrow", () => {
    const cards: BoardCard[] = [
      { id: "nav", height: 80, anchor: { x: 0.02, y: 0.4, w: 0.1, h: 0.03 } },
      { id: "cta", height: 80, anchor: { x: 0.8, y: 0.5, w: 0.1, h: 0.03 } },
      { id: "search", height: 80, anchor: { x: 0.4, y: 0.04, w: 0.2, h: 0.03 } },
      { id: "footer", height: 80, anchor: { x: 0.45, y: 0.95, w: 0.1, h: 0.02 } },
    ];
    const wide = composeBoard(cards, "lr", { W: 700, H: 500 });
    expect(Object.fromEntries(cards.map((c) => [c.id, wide.at[c.id].edge]))).toEqual({ nav: "L", cta: "R", search: "T", footer: "B" });
    const narrow = composeBoard(cards, "rows", { W: 560, H: 380 });
    expect(new Set(cards.map((c) => narrow.at[c.id].edge))).toEqual(new Set(["T", "B"]));
    expect(narrow.band.T).toBeGreaterThan(0);
    expect(narrow.band.B).toBeGreaterThan(0);
  });

  it("keeps the lines' order along a band, so the leaders do not cross", () => {
    const cards: BoardCard[] = [0.8, 0.1, 0.45].map((x, i) => ({ id: `c${i}`, height: 60, anchor: { x, y: 0.3, w: 0.05, h: 0.02 } }));
    const { at } = composeBoard(cards, "rows", { W: 2000, H: 400 });
    const byLeft = [...cards].sort((a, b) => at[a.id].left - at[b.id].left).map((c) => c.id);
    expect(byLeft).toEqual(["c1", "c2", "c0"]);
  });

  // The owner: respect the cards the researcher moved, and re-organise the ones they didn't.
  it("lets placed cards win: their spot in a column, and the head of the row when the columns become rows", () => {
    // The untouched card's line wants it at 170, where automatic placement would put it first and
    // push the placed card down to 282. Placed wins: the researcher's card keeps 190, and the
    // untouched one takes the free slot nearest its line (78 above, not 302 below).
    const cards: BoardCard[] = [
      { id: "auto", height: 100, anchor: { x: 0.8, y: 0.37, w: 0.1, h: 0.02 } },
      { id: "mine", height: 100, placed: { side: "R", frac: 0.38, z: 31 } },
    ];
    const col = composeBoard(cards, "r", { W: 500, H: 500 });
    expect(col.at.mine.top).toBe(190);
    expect(col.at.auto.top).toBe(190 - 100 - GUTTER);
    const rows = composeBoard(cards, "rows", { W: 560, H: 500 });
    expect(rows.at.mine).toMatchObject({ edge: "T", left: 0 });
    expect(rows.at.auto.edge).toBe("T");
    expect(rows.at.auto.left).toBeGreaterThan(0);
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
