import { describe, expect, it } from "vitest";
import { summariseFramework } from "./codebookSummary";
import type { CodebookGroupResponse } from "./types";

function group(tags: number, total: number): CodebookGroupResponse {
  return {
    id: 1,
    name: "G",
    subtitle: "",
    colour_set: "ux",
    order: 0,
    tags: Array.from({ length: tags }, (_, i) => ({
      id: i,
      name: `t${i}`,
      count: 0,
      colour_set: "ux",
      colour_index: 0,
    })) as CodebookGroupResponse["tags"],
    total_quotes: total,
    is_default: false,
    framework_id: "garrett",
  };
}

describe("summariseFramework", () => {
  it("sums tags and coded quotes across groups", () => {
    const s = summariseFramework([group(3, 10), group(5, 22)]);
    expect(s).toEqual({ tagCount: 8, codedQuotes: 32 });
  });

  it("is zero across the board for an empty framework", () => {
    expect(summariseFramework([])).toEqual({
      tagCount: 0,
      codedQuotes: 0,
    });
  });

  it("counts a single-group framework with no coded quotes", () => {
    expect(summariseFramework([group(4, 0)])).toEqual({
      tagCount: 4,
      codedQuotes: 0,
    });
  });
});

describe("B6 — a quote in two groups counts once", () => {
  it("prefers the server's distinct total over the sum", () => {
    // Two groups, 3 quotes each, but the SAME 3 quotes: 3, not 6.
    const groups = [group(2, 3), group(2, 3)];
    expect(summariseFramework(groups, 3).codedQuotes).toBe(3);
  });

  it("falls back to the sum when the server did not send one", () => {
    // A response predating framework_quote_totals. Wrong, but it is the old
    // behaviour rather than a crash or a zero.
    const groups = [group(2, 3), group(2, 3)];
    expect(summariseFramework(groups).codedQuotes).toBe(6);
  });

  it("counts tags by summing, which was never the bug", () => {
    const groups = [group(2, 3), group(4, 3)];
    expect(summariseFramework(groups, 3).tagCount).toBe(6);
  });
});
