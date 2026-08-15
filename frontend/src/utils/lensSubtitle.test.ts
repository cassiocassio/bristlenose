import { describe, expect, it } from "vitest";

import {
  codebookCounts,
  codebookSubtitle,
  quotesSubtitle,
  signalsSubtitle,
} from "./lensSubtitle";
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

/**
 * The outcome under test is what the window says, not which branch ran: at zero
 * the titlebar and the Window menu entry must carry no count at all. Assertions
 * on the non-zero side check only that *something* is produced, so they don't
 * pin translated copy that the locale files own.
 */
describe("zero counts produce no subtitle", () => {
  it("quotes: empty at zero, present above it", () => {
    expect(quotesSubtitle(0)).toBe("");
    expect(quotesSubtitle(1)).not.toBe("");
  });

  it("quotes: empty at zero under the starred filter too", () => {
    // The starred branch builds its string differently ("Starred quotes · 12"),
    // so it needs its own guard — an empty starred view is the commonest way to
    // hit zero.
    expect(quotesSubtitle(0, true)).toBe("");
    expect(quotesSubtitle(3, true)).not.toBe("");
  });

  it("signals: empty at zero, present above it", () => {
    expect(signalsSubtitle(0)).toBe("");
    expect(signalsSubtitle(1)).not.toBe("");
  });

  it("codebook: empty only when there is nothing at all", () => {
    expect(codebookSubtitle(0, 0)).toBe("");
    // A codebook with no tags yet is still something to name — a fresh project
    // reads "1 Codebook · 0 Tags" rather than falling silent.
    expect(codebookSubtitle(1, 0)).not.toBe("");
    expect(codebookSubtitle(1, 4)).not.toBe("");
  });
});
