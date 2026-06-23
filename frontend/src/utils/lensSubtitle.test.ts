import { describe, expect, it } from "vitest";

import { codebookCounts } from "./lensSubtitle";
import type { CodebookResponse } from "./types";

/** Minimal codebook carrying only the fields `codebookCounts` reads. */
function makeCodebook(
  groups: Array<{ framework_id: string | null; tagCount: number }>,
  ungroupedCount = 0,
): CodebookResponse {
  return {
    groups: groups.map((g, i) => ({
      id: i,
      name: `g${i}`,
      subtitle: "",
      colour_set: "set1",
      order: i,
      tags: Array.from({ length: g.tagCount }, () => ({})),
      total_quotes: 0,
      is_default: g.framework_id === null,
      framework_id: g.framework_id,
    })),
    ungrouped: Array.from({ length: ungroupedCount }, () => ({})),
    all_tag_names: [],
  } as unknown as CodebookResponse;
}

describe("codebookCounts", () => {
  it("counts distinct frameworks and sums their tags", () => {
    expect(
      codebookCounts(
        makeCodebook([
          { framework_id: "garrett", tagCount: 5 },
          { framework_id: "garrett", tagCount: 3 }, // same framework, one codebook
          { framework_id: "norman", tagCount: 4 },
        ]),
      ),
    ).toEqual({ codebooks: 2, tags: 12 });
  });

  it("adds the user codebook when a custom group carries tags", () => {
    expect(
      codebookCounts(
        makeCodebook([
          { framework_id: "garrett", tagCount: 5 },
          { framework_id: null, tagCount: 7 }, // custom -> user per-project codebook
        ]),
      ),
    ).toEqual({ codebooks: 2, tags: 12 });
  });

  it("counts ungrouped tags toward the user codebook", () => {
    expect(
      codebookCounts(makeCodebook([{ framework_id: "garrett", tagCount: 5 }], 3)),
    ).toEqual({ codebooks: 2, tags: 8 });
  });

  it("ignores an empty user codebook", () => {
    expect(
      codebookCounts(
        makeCodebook([
          { framework_id: "garrett", tagCount: 5 },
          { framework_id: null, tagCount: 0 },
        ]),
      ),
    ).toEqual({ codebooks: 1, tags: 5 });
  });

  it("handles a user-codebook-only project", () => {
    expect(
      codebookCounts(makeCodebook([{ framework_id: null, tagCount: 4 }])),
    ).toEqual({ codebooks: 1, tags: 4 });
  });

  it("is zero for an empty codebook", () => {
    expect(codebookCounts(makeCodebook([]))).toEqual({ codebooks: 0, tags: 0 });
  });
});
