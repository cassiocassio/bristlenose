import { describe, it, expect, afterEach } from "vitest";
import { nextSpatial, entryPoint, readCardRects, type CardRect } from "./spatialNav";

/**
 * A three-lane masonry grid, deliberately ragged — lanes hold different
 * numbers of cards at unaligned heights, which is the shape a rectangular-grid
 * mental model gets wrong. Lane centres are 100 / 300 / 500.
 *
 *   L0        L1        L2
 *   a  (50)   b  (60)   c  (55)
 *   d (200)   e (260)   f (180)
 *   g (400)             h (330)
 */
const GRID: CardRect[] = [
  { id: "a", cx: 100, cy: 50 },
  { id: "b", cx: 300, cy: 60 },
  { id: "c", cx: 500, cy: 55 },
  { id: "d", cx: 100, cy: 200 },
  { id: "e", cx: 300, cy: 260 },
  { id: "f", cx: 500, cy: 180 },
  { id: "g", cx: 100, cy: 400 },
  { id: "h", cx: 500, cy: 330 },
];

describe("nextSpatial", () => {
  it("moves right into the neighbouring lane", () => {
    expect(nextSpatial(GRID, "a", "right")).toBe("b");
    expect(nextSpatial(GRID, "b", "right")).toBe("c");
  });

  it("moves left into the neighbouring lane", () => {
    expect(nextSpatial(GRID, "c", "left")).toBe("b");
    expect(nextSpatial(GRID, "b", "left")).toBe("a");
  });

  it("moves down within the lane rather than to the next DOM card", () => {
    // The bug this whole module exists for: `b` is the next card in DOM order,
    // but it renders to the *right* of `a`. Down means down.
    expect(nextSpatial(GRID, "a", "down")).toBe("d");
    expect(nextSpatial(GRID, "d", "down")).toBe("g");
  });

  it("moves up within the lane", () => {
    expect(nextSpatial(GRID, "g", "up")).toBe("d");
    expect(nextSpatial(GRID, "d", "up")).toBe("a");
  });

  it("returns null at the edges of the grid", () => {
    expect(nextSpatial(GRID, "a", "left")).toBeNull();
    expect(nextSpatial(GRID, "a", "up")).toBeNull();
    expect(nextSpatial(GRID, "c", "right")).toBeNull();
    expect(nextSpatial(GRID, "g", "down")).toBeNull();
  });

  it("excludes same-lane cards from a horizontal move", () => {
    // `d` sits directly below `a` in the same lane. A naive nearest-neighbour
    // without the lane tolerance would return it for `right`.
    const result = nextSpatial(GRID, "a", "right");
    expect(result).not.toBe("d");
  });

  it("crosses a ragged lane end rather than stopping", () => {
    // L1 has no third card, so `down` from `e` has to leave the lane.
    // Asserts the *property* (something strictly below, not a dead end)
    // rather than which card wins: the scoring rule is a documented,
    // swappable choice (docs/mockups/quotes-spatial-arrow-nav.html keeps two
    // alternatives), and pinning the identity here would make changing it
    // cost a test failure for no user-visible change.
    const from = GRID.find((r) => r.id === "e")!;
    const target = nextSpatial(GRID, "e", "down");
    expect(target).not.toBeNull();
    expect(GRID.find((r) => r.id === target)!.cy).toBeGreaterThan(from.cy);
  });

  it("answers a vertical press with a card below, not a taller neighbour beside it", () => {
    // The regression that shipped in the first cut. `.quote-group` is
    // `align-items: start`, so same-row cards have different centres once
    // their heights differ — and plain nearest-centre then scored a tall
    // neighbour one lane over as closer than the card genuinely below.
    // Real measurements at the 388px lane pitch: 412 (sideways) vs 435
    // (below), so `↓` moved LEFT. Not masonry-specific — the rectangular
    // grid Chromium and Firefox render has the same shape.
    const staggered: CardRect[] = [
      { id: "tall-left", cx: 194, cy: 200 }, // 400px card, lane 0
      { id: "short-right", cx: 582, cy: 60 }, // 120px card, lane 1, same row
      { id: "below-right", cx: 582, cy: 495 }, // lane 1, genuinely below
    ];
    expect(nextSpatial(staggered, "short-right", "down")).toBe("below-right");
  });

  it("returns null when the current id is not among the measured cards", () => {
    // Happens when the focused quote has been filtered or hidden out of the
    // DOM; the caller falls back to an entry point.
    expect(nextSpatial(GRID, "does-not-exist", "down")).toBeNull();
  });

  it("returns null for an empty grid", () => {
    expect(nextSpatial([], "a", "down")).toBeNull();
  });

  it("resolves a tie in DOM order", () => {
    const tied: CardRect[] = [
      { id: "from", cx: 100, cy: 100 },
      { id: "first", cx: 300, cy: 100 },
      { id: "second", cx: 300, cy: 100 },
    ];
    expect(nextSpatial(tied, "from", "right")).toBe("first");
  });
});

describe("entryPoint", () => {
  it("enters at the top of reading order for forward keys", () => {
    expect(entryPoint(["a", "b", "c"], "down")).toBe("a");
    expect(entryPoint(["a", "b", "c"], "right")).toBe("a");
  });

  it("enters at the end of reading order for backward keys", () => {
    expect(entryPoint(["a", "b", "c"], "up")).toBe("c");
    expect(entryPoint(["a", "b", "c"], "left")).toBe("c");
  });

  it("returns null with no quotes", () => {
    expect(entryPoint([], "down")).toBeNull();
  });
});

describe("readCardRects", () => {
  /** Give an id a real box; jsdom reports zero for everything by default. */
  function place(id: string, box: Partial<DOMRect>) {
    const el = document.createElement("div");
    el.id = id;
    el.getBoundingClientRect = () =>
      ({ left: 0, top: 0, width: 0, height: 0, ...box, toJSON: () => ({}) }) as DOMRect;
    document.body.appendChild(el);
  }

  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("measures laid-out cards to their centres", () => {
    // The positive case. Without it, a regression that made the function
    // return [] unconditionally would still pass every other test here —
    // and an empty measurement is exactly what makes the arrows silently
    // inert, so it has to be pinned directly.
    place("a", { left: 10, top: 20, width: 200, height: 100 });
    expect(readCardRects(["a"])).toEqual([{ id: "a", cx: 110, cy: 70 }]);
  });

  it("skips ids with no element", () => {
    place("present", { left: 0, top: 0, width: 200, height: 100 });
    expect(readCardRects(["present", "absent"]).map((r) => r.id)).toEqual(["present"]);
  });

  it("skips cards with no box", () => {
    // A `display: none` quote reports a zero rect. Keeping it would put a
    // card at the origin, where it wins every distance comparison from
    // anywhere on the page.
    place("hidden", { left: 0, top: 0, width: 0, height: 0 });
    expect(readCardRects(["hidden"])).toEqual([]);
  });

  it("skips physically impossible boxes", () => {
    // WebKit reports negative heights mid-smooth-scroll (frontend/CLAUDE.md).
    // The zero-size check doesn't catch it — width stays plausible, so `cx`
    // survives while `cy` is garbage and focus jumps somewhere believable.
    place("glitched", { left: 0, top: 400, width: 200, height: -150 });
    expect(readCardRects(["glitched"])).toEqual([]);
  });
});
