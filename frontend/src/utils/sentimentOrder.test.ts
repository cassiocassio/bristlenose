import { describe, expect, it } from "vitest";
import { inSentimentOrder } from "./sentimentOrder";

const named = (...names: string[]) => names.map((name) => ({ name }));
const names = (tags: readonly { name: string }[]) => tags.map((t) => t.name);

describe("inSentimentOrder", () => {
  it("puts a name it does not list after the listed ones, in the order they came", () => {
    const tags = named("zeal", "delight", "awe", "Frustration");
    expect(names(inSentimentOrder("sentiment", tags))).toEqual(["Frustration", "delight", "zeal", "awe"]);
  });

  it("hands any other group back as it came, the same array", () => {
    const tags = named("delight", "frustration");
    expect(inSentimentOrder("ux", tags)).toBe(tags);
  });
});
