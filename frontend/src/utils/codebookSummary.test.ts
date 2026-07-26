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
