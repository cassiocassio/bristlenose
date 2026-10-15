import { describe, expect, it } from "vitest";
import { peopleOf, sequenceByPerson, stepFrom } from "./narrative";

describe("sequenceByPerson", () => {
  // Per person, in time order: p1 ①②③, p2 ①②. No global sequence.
  it("numbers each person's quotes among their own, by time", () => {
    const seq = sequenceByPerson([
      { id: "a", person: "p1", t: 30 },
      { id: "b", person: "p2", t: 10 },
      { id: "c", person: "p1", t: 5 },
      { id: "d", person: "p2", t: 40 },
      { id: "e", person: "p1", t: 50 },
    ]);
    expect(seq.c).toEqual({ person: "p1", n: 1, total: 3 });
    expect(seq.a).toEqual({ person: "p1", n: 2, total: 3 });
    expect(seq.e).toEqual({ person: "p1", n: 3, total: 3 });
    expect(seq.b).toEqual({ person: "p2", n: 1, total: 2 });
    expect(seq.d).toEqual({ person: "p2", n: 2, total: 2 });
  });
});

describe("peopleOf", () => {
  it("lists the people in the report's order", () => {
    expect(peopleOf([{ id: "a", person: "p10", t: 0 }, { id: "b", person: "p2", t: 0 }, { id: "c", person: "p2", t: 1 }]))
      .toEqual(["p2", "p10"]);
  });
});

describe("stepFrom", () => {
  // Moves as FocusContext's moveFocus does: from nothing to an end, one at a time, clamped.
  it("starts at an end, moves one, and clamps", () => {
    const order = ["a", "b", "c"];
    expect(stepFrom(order, null, 1)).toBe("a");
    expect(stepFrom(order, null, -1)).toBe("c");
    expect(stepFrom(order, "a", 1)).toBe("b");
    expect(stepFrom(order, "c", 1)).toBe("c");
    expect(stepFrom(order, "a", -1)).toBe("a");
    expect(stepFrom(order, "elsewhere", 1)).toBe("a");
    expect(stepFrom([], "a", 1)).toBeNull();
  });
});
