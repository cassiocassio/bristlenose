import { buildTagVocabulary } from "./tagVocabulary";
import type { CodebookGroupResponse } from "./types";

const group = (
  id: number,
  name: string,
  framework_id: string | null,
  tags: [number, string][],
): CodebookGroupResponse => ({
  id, name, subtitle: "", colour_set: "ux", order: id, total_quotes: 0, is_default: false,
  framework_id,
  tags: tags.map(([tid, tname], i) => ({ id: tid, name: tname, count: 0, colour_index: i })),
});

describe("buildTagVocabulary", () => {
  it("lists the researcher's own groups first, the codebook's order kept within each kind", () => {
    const built = buildTagVocabulary([
      group(1, "UXR", "uxr", [[1, "trust"]]),
      group(2, "Sentiment", "sentiment", [[2, "delight"]]),
      group(3, "Mine", null, [[3, "trust"]]),
      group(4, "Uncategorised", null, [[4, "moan"]]),
    ]);
    expect(built.map((g) => g.groupName)).toEqual(["Mine", "Uncategorised", "UXR", "Sentiment"]);
  });

  it("carries each tag's row and each group's codebook", () => {
    const [g] = buildTagVocabulary([group(1, "UXR", "uxr", [[11, "trust"]])]);
    expect(g.frameworkId).toBe("uxr");
    expect(g.tags).toEqual([{ name: "trust", colourIndex: 0, id: 11 }]);
  });
});
