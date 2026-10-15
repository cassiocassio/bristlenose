import { describe, expect, it } from "vitest";
import { readingOrder } from "./narrative";

describe("readingOrder", () => {
  it("reads the margins top to bottom then left to right, then the list in its own order", () => {
    const margins = [
      { id: "right-high", top: 100, left: 900 },
      { id: "left-low", top: 400, left: 0 },
      { id: "band-above", top: 0, left: 500 },
      { id: "left-high", top: 100, left: 0 },
    ];
    expect(readingOrder(margins, ["l1", "l2"])).toEqual(["band-above", "left-high", "right-high", "left-low", "l1", "l2"]);
  });
  it("keeps the given order (time) where two cards sit at one spot", () => {
    expect(readingOrder([{ id: "b", top: 5, left: 5 }, { id: "a", top: 5, left: 5 }], [])).toEqual(["b", "a"]);
  });
});
