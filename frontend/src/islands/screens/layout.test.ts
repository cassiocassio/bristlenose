import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../utils/api", () => ({ apiGet: vi.fn(), sendPut: vi.fn(() => Promise.resolve()) }));

import { apiGet, sendPut } from "../../utils/api";
import {
  arrangementFor,
  arrangementsLoaded,
  autoIntent,
  boardColumns,
  CARD_W,
  COLUMN_GUTTER,
  COLUMN_W,
  composeBoard,
  customFrame,
  edgeFor,
  HYSTERESIS,
  intentFromRect,
  MAX_STAGGER,
  loadArrangements,
  migrateArrangement,
  reloadArrangements,
  MIN_SHOT_W,
  placeRow,
  rectFromIntent,
  setArrangement,
  STAGGER_STEP,
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
  type Intent,
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
    // A column is one card at CARD_W plus its widest stagger.
    expect(COLUMN_W).toBe(CARD_W + MAX_STAGGER);
    expect(WIDE_STAGE - 2 * (COLUMN_W + COLUMN_GUTTER)).toBe(MIN_SHOT_W);
    expect(ONE_COLUMN_STAGE - (COLUMN_W + COLUMN_GUTTER)).toBe(MIN_SHOT_W);
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

/** A model of the board's grid (screens.css): a column of COLUMN_W either side, bands above and
 *  below, each a gutter from the screengrab. Where every automatic card lands, in board space. */
function boardRects(comp: Composition, cards: BoardCard[], mode: Mode, shot: { W: number; H: number }) {
  const sides = { L: false, R: false };
  for (const c of cards) {
    const e = edgeFor(c.anchor, mode);
    if (e === "L" || e === "R") sides[e] = true;
  }
  const cols = boardColumns(mode, sides);
  const shotX = cols === "l" || cols === "lr" ? COLUMN_W + COLUMN_GUTTER : 0;
  const shotY = comp.band.T ? comp.band.T + COLUMN_GUTTER : 0;
  // The band below starts under the taller of the screengrab and its side columns (the grid's row).
  const rowH = Math.max(shot.H, comp.colBottom);
  const out: Record<string, Rect> = {};
  for (const c of cards) {
    const s = comp.at[c.id];
    const r = { width: CARD_W, height: c.height };
    if (s.edge === "L") out[c.id] = { ...r, left: s.left, top: shotY + s.top };
    else if (s.edge === "R") out[c.id] = { ...r, left: shotX + shot.W + COLUMN_GUTTER + s.left, top: shotY + s.top };
    else if (s.edge === "T") out[c.id] = { ...r, left: shotX + s.left, top: s.top };
    else out[c.id] = { ...r, left: shotX + s.left, top: shotY + rowH + COLUMN_GUTTER + s.top };
  }
  return { shot: { left: shotX, top: shotY, width: shot.W, height: shot.H }, cards: out };
}

const overlaps = (a: Rect, b: Rect) =>
  a.left < b.left + b.width && b.left < a.left + a.width && a.top < b.top + b.height && b.top < a.top + a.height;

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
const SIZES: Record<Mode, { W: number; H: number }> = {
  lr: { W: 700, H: 500 }, r: { W: 500, H: 400 }, rows: { W: 560, H: 380 },
};

describe("composeBoard", () => {
  it("never puts an automatic card over the screengrab, on any edge, in any mode", () => {
    for (const mode of ["lr", "r", "rows"] as Mode[]) {
      for (let seed = 1; seed <= 25; seed++) {
        const cards = lines(1 + (seed % 9), seed);
        const comp = composeBoard(cards, mode, SIZES[mode]);
        const { shot, cards: rects } = boardRects(comp, cards, mode, SIZES[mode]);
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

  it("keeps the lines' order along a band, so the leaders do not cross; time breaks a tie", () => {
    const cards: BoardCard[] = [0.8, 0.1, 0.45, 0.1].map((x, i) => ({ id: `c${i}`, height: 60, anchor: { x, y: 0.3, w: 0.05, h: 0.02 } }));
    const { at } = composeBoard(cards, "rows", { W: 2000, H: 400 });
    const byLeft = [...cards].sort((a, b) => at[a.id].left - at[b.id].left).map((c) => c.id);
    expect(byLeft).toEqual(["c1", "c3", "c2", "c0"]);
  });

  // The owner, 15 Oct 2026: as the 1984 Mac cascaded its windows — you can count them, they read as
  // separate cards, and each one's left-edge grip shows.
  it("steps each later card of a stack diagonally away from the screengrab, within its column", () => {
    const tall = (side: number) => Array.from({ length: 6 }, (_, i) => ({
      id: `s${i}`, height: 150, anchor: { x: side, y: 0.1 + i * 0.02, w: 0.05, h: 0.02 },
    }));
    const right = composeBoard(tall(0.8), "lr", { W: 700, H: 400 });
    expect(right.stacked.R).toBe(true);
    const r = [0, 1, 2, 3, 4].map((i) => right.at[`s${i}`]);
    expect(r.map((s) => s.left)).toEqual([0, STAGGER_STEP, 2 * STAGGER_STEP, 3 * STAGGER_STEP, 0]); // away = right; the cascade restarts
    for (let i = 1; i < 4; i++) expect(r[i].top).toBeGreaterThan(r[i - 1].top); // and down
    const left = composeBoard(tall(0.05), "lr", { W: 700, H: 400 });
    const l = [0, 1, 2].map((i) => left.at[`s${i}`].left);
    expect(l).toEqual([MAX_STAGGER, MAX_STAGGER - STAGGER_STEP, MAX_STAGGER - 2 * STAGGER_STEP]); // away = left
    for (const s of Object.values(left.at)) expect(s.left + CARD_W).toBeLessThanOrEqual(COLUMN_W); // never into the gutter
    // And in board space: every staggered card stays outside the screengrab and its gutter.
    for (const [comp, side] of [[left, 0.05], [right, 0.8]] as const) {
      const cards = tall(side);
      const { shot, cards: rects } = boardRects(comp, cards, "lr", { W: 700, H: 400 });
      const guarded = { left: shot.left - COLUMN_GUTTER, top: shot.top, width: shot.width + 2 * COLUMN_GUTTER, height: shot.height };
      for (const c of cards) expect(overlaps(rects[c.id], guarded), `${side} ${c.id}`).toBe(false);
    }
    // A column with room does not stagger: every card flush to the gutter.
    const calm = composeBoard([tall(0.05)[0]], "lr", { W: 700, H: 400 });
    expect(calm.at.s0.left).toBe(MAX_STAGGER);
  });
});

describe("intent", () => {
  const shot: Rect = { left: 400, top: 100, width: 600, height: 400 };
  it("reads a card beside, above, below or over the screengrab, and puts it back where it was", () => {
    const cases: [Rect, Intent["kind"], string?][] = [
      [{ left: 30, top: 150, width: CARD_W, height: 90 }, "edge", "L"],
      [{ left: 1040, top: 300, width: CARD_W, height: 90 }, "edge", "R"],
      [{ left: 500, top: 0, width: CARD_W, height: 60 }, "edge", "T"],
      [{ left: 0, top: 560, width: CARD_W, height: 120 }, "edge", "B"], // the list, starting left of it
      [{ left: 500, top: 200, width: CARD_W, height: 90 }, "over"],
    ];
    for (const [r, kind, edge] of cases) {
      const p = intentFromRect(r, shot, 40);
      expect(p.kind).toBe(kind);
      if (edge && p.kind === "edge") expect(p.edge).toBe(edge);
      expect(rectFromIntent(p, shot, r.height)).toEqual({ left: r.left, top: r.top });
    }
  });

  // A resize in custom scales the arrangement with the screengrab: along each edge in proportion,
  // out from it by the same gutter, so a card frozen beside it never slides onto it.
  it("scales with the screengrab, and an edge card never comes over it", () => {
    const p = intentFromRect({ left: 30, top: 300, width: CARD_W, height: 90 }, shot, 40);
    const smaller: Rect = { left: 400, top: 100, width: 300, height: 200 };
    const r = rectFromIntent(p, smaller, 90);
    expect(r.top).toBe(100 + 0.5 * 200);
    expect(r.left + CARD_W).toBeLessThanOrEqual(smaller.left);
    for (const edge of ["L", "R", "T", "B"] as const) {
      const at = rectFromIntent({ kind: "edge", edge, along: 0.3, out: -50, z: 1 }, smaller, 90);
      expect(overlaps({ ...at, width: CARD_W, height: 90 }, smaller), edge).toBe(false);
    }
  });

  it("puts a card back where Tidy would: its automatic spot, as intent", () => {
    const cards = lines(5, 7);
    const s = { W: 700, H: 500 };
    const comp = composeBoard(cards, "lr", s);
    const { shot: sr, cards: rects } = boardRects(comp, cards, "lr", s);
    for (const c of cards) {
      const p = autoIntent(comp.at[c.id], c.height, s, comp.band.T, 31, Math.max(0, comp.colBottom - s.H));
      const at = rectFromIntent(p, sr, c.height);
      expect(at.left).toBeCloseTo(rects[c.id].left, 6);
      expect(at.top).toBeCloseTo(rects[c.id].top, 6);
    }
  });

  // A side column can run past the screengrab's foot (a short screengrab, tall cards): the band
  // below then starts under the column, and so must a footer card put back by Return to automatic.
  it("puts a bottom-edge card under a side column that runs past the screengrab, as the grid does", () => {
    const s = { W: 700, H: 200 };
    const cards: BoardCard[] = [
      { id: "tall", height: 400, anchor: { x: 0.8, y: 0.5, w: 0.1, h: 0.02 } },
      { id: "footer", height: 80, anchor: { x: 0.45, y: 0.95, w: 0.1, h: 0.02 } },
    ];
    const comp = composeBoard(cards, "r", s);
    expect(comp.colBottom).toBeGreaterThan(s.H);
    const { shot: sr, cards: rects } = boardRects(comp, cards, "r", s);
    const p = autoIntent(comp.at.footer, 80, s, comp.band.T, 31, Math.max(0, comp.colBottom - s.H));
    expect(rectFromIntent(p, sr, 80).top).toBeCloseTo(rects.footer.top, 6);
    expect(rects.footer.top).toBeGreaterThanOrEqual(rects.tall.top + 400); // not on the column's cards
  });

  it("holds open a column for each side with a card, and each band tall enough for its cards", () => {
    const f = customFrame([
      { intent: { kind: "edge", edge: "L", along: 0.2, out: 32, z: 1 }, height: 90 },
      { intent: { kind: "edge", edge: "B", along: 0, out: 200, z: 1 }, height: 100 },
      { intent: { kind: "over", x: 0.2, y: 0.2, z: 1 }, height: 100 },
    ]);
    expect(f).toEqual({ L: true, R: false, T: 0, B: 200 + 100 - COLUMN_GUTTER });
  });
});

describe("arrangement storage", () => {
  beforeEach(() => {
    localStorage.clear();
    resetArrangementMemory();
    vi.mocked(apiGet).mockReset();
    vi.mocked(sendPut).mockReset().mockResolvedValue(undefined);
  });
  const edge = (e: "L" | "R" | "T" | "B", along: number, z = 31): Intent => ({ kind: "edge", edge: e, along, out: COLUMN_GUTTER, z });
  const server = (versions: { screen_key: string; session_id: string; cards: unknown }[]) =>
    vi.mocked(apiGet).mockResolvedValue({ versions });
  const sent = () => vi.mocked(sendPut).mock.calls.map(([path, body]) => ({ path, body }));
  const flush = async () => {
    for (let i = 0; i < 5; i++) await new Promise((r) => setTimeout(r, 0));
  };

  it("reads every version from the project's database, once per project", async () => {
    server([
      { screen_key: "url:/x", session_id: "s1", cards: { a: edge("L", 0.3) } },
      { screen_key: "url:/x", session_id: "s2", cards: { b: edge("R", 0.6, 34) } },
    ]);
    expect(arrangementsLoaded("1")).toBe(false);
    await Promise.all([loadArrangements("1"), loadArrangements("1")]);
    expect(apiGet).toHaveBeenCalledTimes(1);
    expect(apiGet).toHaveBeenCalledWith("/screens/arrangements");
    expect(arrangementsLoaded("1")).toBe(true);
    expect(arrangementFor("1", "url:/x", "s1")).toEqual({ a: edge("L", 0.3) });
    expect(arrangementFor("1", "url:/x", "s2")).toEqual({ b: edge("R", 0.6, 34) });
    expect(topZ("1")).toBe(34);
  });

  it("sends each change for its own version alone, and Tidy as null", async () => {
    server([{ screen_key: "url:/x", session_id: "s2", cards: { b: edge("R", 0.6) } }]);
    await loadArrangements("1");
    setArrangement("1", "url:/x", "s1", { a: edge("L", 0.3) });
    setArrangement("1", "url:/x", "s1", null);
    await flush();
    expect(sent()).toEqual([
      { path: "/screens/arrangement", body: { screen_key: "url:/x", session_id: "s1", cards: { a: edge("L", 0.3) } } },
      { path: "/screens/arrangement", body: { screen_key: "url:/x", session_id: "s1", cards: null } },
    ]);
    expect(arrangementFor("1", "url:/x", "s1")).toBeNull();
    expect(arrangementFor("1", "url:/x", "s2")).toEqual({ b: edge("R", 0.6) });
  });

  it("sends writes in the order they were made, so an undo lands after its act", async () => {
    server([]);
    await loadArrangements("1");
    let release!: () => void;
    vi.mocked(sendPut).mockImplementationOnce(() => new Promise<void>((r) => (release = r)));
    setArrangement("1", "url:/x", "s1", { a: edge("L", 0.3) });
    setArrangement("1", "url:/x", "s1", null);
    await flush();
    expect(sendPut).toHaveBeenCalledTimes(1);
    release();
    await flush();
    expect(sent().map((c) => (c.body as { cards: unknown }).cards)).toEqual([{ a: edge("L", 0.3) }, null]);
  });

  it("drops a card that does not read as a placement", async () => {
    server([{ screen_key: "url:/x", session_id: "s1", cards: { a: edge("L", 0.3), b: { kind: "edge", edge: "Q" } } }]);
    await loadArrangements("1");
    expect(arrangementFor("1", "url:/x", "s1")).toEqual({ a: edge("L", 0.3) });
  });

  // A board drawn automatic over an arrangement the server still holds would be overwritten by its
  // first drag (review, 15 Oct 2026): a failed read loads nothing, and says so.
  it("loads nothing when the read fails, and reads again when asked", async () => {
    vi.mocked(apiGet).mockRejectedValueOnce(new Error("401"));
    expect(await loadArrangements("1")).toBe(false);
    expect(arrangementsLoaded("1")).toBe(false);
    server([{ screen_key: "url:/x", session_id: "s1", cards: { a: edge("L", 0.3) } }]);
    expect(await loadArrangements("1")).toBe(true);
    expect(apiGet).toHaveBeenCalledTimes(2);
    expect(arrangementFor("1", "url:/x", "s1")).toEqual({ a: edge("L", 0.3) });
  });

  it("reads again to show another window's change", async () => {
    server([{ screen_key: "url:/x", session_id: "s1", cards: { a: edge("L", 0.3) } }]);
    await loadArrangements("1");
    server([{ screen_key: "url:/x", session_id: "s1", cards: { a: edge("R", 0.8) } }]);
    expect(await reloadArrangements("1")).toBe(true);
    expect(arrangementFor("1", "url:/x", "s1")).toEqual({ a: edge("R", 0.8) });
  });

  it("waits for this page's writes before reading again, and a write made meanwhile wins", async () => {
    server([]);
    await loadArrangements("1");
    let release!: () => void;
    vi.mocked(sendPut).mockImplementationOnce(() => new Promise<void>((r) => (release = r)));
    setArrangement("1", "url:/x", "s1", { a: edge("L", 0.3) });
    const reading = reloadArrangements("1");
    await flush();
    expect(apiGet).toHaveBeenCalledTimes(1); // not yet: the write is still in flight
    // The server answers with an older state, and another drag lands while it is on its way.
    let answer!: (v: unknown) => void;
    vi.mocked(apiGet).mockImplementationOnce(() => new Promise((r) => (answer = r)) as never);
    release();
    await flush();
    expect(apiGet).toHaveBeenCalledTimes(2);
    setArrangement("1", "url:/x", "s1", { a: edge("L", 0.5) });
    answer({ versions: [] });
    await reading;
    expect(arrangementFor("1", "url:/x", "s1")).toEqual({ a: edge("L", 0.5) });
  });

  it("splits a version key at its last bar, so a screen key may hold one", async () => {
    localStorage.setItem("bristlenose-screens-arrangements-1", JSON.stringify({ "title:A | B|s3": { a: edge("L", 0.3) } }));
    server([]);
    await loadArrangements("1");
    await flush();
    expect(sent().map((c) => c.body)).toEqual([{ screen_key: "title:A | B", session_id: "s3", cards: { a: edge("L", 0.3) } }]);
  });

  it("moves this browser's arrangements to the server once; the server's copy wins", async () => {
    localStorage.setItem("bristlenose-screens-arrangements-1", JSON.stringify({
      "url:/x|s1": { a: edge("L", 0.3) },
      "url:/y|s2": { b: edge("R", 0.1) },
    }));
    server([{ screen_key: "url:/y", session_id: "s2", cards: { c: edge("T", 0.5) } }]);
    await loadArrangements("1");
    await flush();
    expect(arrangementFor("1", "url:/x", "s1")).toEqual({ a: edge("L", 0.3) });
    expect(arrangementFor("1", "url:/y", "s2")).toEqual({ c: edge("T", 0.5) });
    expect(sent()).toEqual([
      { path: "/screens/arrangement", body: { screen_key: "url:/x", session_id: "s1", cards: { a: edge("L", 0.3) } } },
    ]);
    expect(localStorage.getItem("bristlenose-screens-arrangements-1")).toBeNull();
  });

  it("keeps this browser's copy while the server will not take it", async () => {
    localStorage.setItem("bristlenose-screens-arrangements-1", JSON.stringify({ "url:/x|s1": { a: edge("L", 0.3) } }));
    vi.mocked(sendPut).mockRejectedValue(new Error("500"));
    server([]);
    await loadArrangements("1");
    await flush();
    expect(localStorage.getItem("bristlenose-screens-arrangements-1")).not.toBeNull();
  });

  // A re-read can pick a different still moment for a session: the arrangement must not care.
  it("is keyed by the screen and the session, not by the still's moment", () => {
    setArrangement("1", "url:/x", "s1", { a: edge("L", 0.3) });
    expect(arrangementFor("1", "url:/x", "s1")).toEqual({ a: edge("L", 0.3) });
    expect(migrateArrangement("1", "url:/x", "s1", 99)).toBe(false); // nothing to migrate, nothing lost
    expect(arrangementFor("1", "url:/x", "s1")).toEqual({ a: edge("L", 0.3) });
  });

  it("migrates a version's 14 Oct placements once, and the first build's coordinates with them", async () => {
    localStorage.setItem("bristlenose-screens-placements-1", JSON.stringify({
      "s1@100/a": { kind: "edge", side: "R", frac: 0.4, z: 32 },
      "s2@50/b": { kind: "edge", side: "L", frac: 0.1, z: 33 },
    }));
    localStorage.setItem("bristlenose-screens-arrangement-1", JSON.stringify({ "s1@100/c": { x: 0.4, y: 0.4, z: 34 } }));
    expect(migrateArrangement("1", "url:/x", "s1", 100)).toBe(true);
    const migrated = {
      a: { kind: "edge", edge: "R", along: 0.4, out: COLUMN_GUTTER, z: 32 },
      c: { kind: "over", x: 0.4, y: 0.4, z: 34 },
    };
    expect(arrangementFor("1", "url:/x", "s1")).toEqual(migrated);
    await flush();
    expect(sent()).toEqual([{ path: "/screens/arrangement", body: { screen_key: "url:/x", session_id: "s1", cards: migrated } }]);
    expect(localStorage.getItem("bristlenose-screens-arrangement-1")).toBeNull();
    // The other version's entry waits for its own board.
    expect(JSON.parse(localStorage.getItem("bristlenose-screens-placements-1")!)).toEqual({
      "s2@50/b": { kind: "edge", side: "L", frac: 0.1, z: 33 },
    });
    expect(migrateArrangement("1", "url:/x", "s1", 100)).toBe(false);
  });

  it("keys arrangements by the project id it is given", () => {
    setArrangement("1", "url:/x", "s1", { a: edge("L", 0.3) });
    expect(arrangementFor("2", "url:/x", "s1")).toBeNull();
    expect(topZ("2")).toBe(30);
  });
});
