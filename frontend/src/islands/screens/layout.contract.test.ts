/**
 * The lens's placement rules against tests/fixtures/screens-layout-contract.json — the same file
 * tests/test_screens_board.py holds bristlenose/screens_board.py to. The Miro board places quotes
 * with a Python copy of these rules; this keeps the two from drifting.
 */
import { describe, expect, it } from "vitest";
import contract from "../../../../tests/fixtures/screens-layout-contract.json";
import { CARD_W, edgeFor, placeColumn, placeRow, rectFromIntent, type Intent, type Mode } from "./layout";

describe("screens layout contract", () => {
  it("is written for the lens's card width", () => {
    for (const c of contract.rectFromIntent) expect(c.cardW).toBe(CARD_W);
  });

  it.each(contract.edgeFor)("edgeFor %j", (c) => {
    const [x, y, w, h] = c.box;
    expect(edgeFor({ x, y, w, h }, c.mode as Mode)).toBe(c.edge);
  });

  it.each(contract.placeColumn)("placeColumn %j", (c) => {
    const out = placeColumn(c.cards.map(([want, height]) => ({ want, height })), c.limit);
    expect(out.placed.map((p) => p.top)).toEqual(c.tops.map((t) => expect.closeTo(t, 6)));
    expect(out.stacked).toBe(c.stacked);
  });

  it.each(contract.placeRow)("placeRow %j", (c) => {
    const out = placeRow(c.cards.map(([want, width, height]) => ({ want, width, height })), c.limit);
    expect(out.lefts).toEqual(c.lefts);
    expect(out.tops).toEqual(c.tops);
    expect(out.height).toBe(c.height);
  });

  it.each(contract.rectFromIntent)("rectFromIntent %j", (c) => {
    const [left, top, width, height] = c.shot;
    const r = rectFromIntent(c.intent as Intent, { left, top, width, height }, c.height);
    expect(r.left).toBeCloseTo(c.left, 6);
    expect(r.top).toBeCloseTo(c.top, 6);
  });
});
