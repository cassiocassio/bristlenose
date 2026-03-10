import { describe, expect, it } from "vitest";
import { COLOUR_SETS, getTagBg, getGroupBg, getBarColour } from "./colours";

describe("COLOUR_SETS", () => {
  it("includes sentiment colour set", () => {
    expect(COLOUR_SETS.sentiment).toBeDefined();
    expect(COLOUR_SETS.sentiment.slots).toBe(7);
  });
});

describe("getTagBg — sentiment", () => {
  it("returns sentiment-1-bg for index 0", () => {
    expect(getTagBg("sentiment", 0)).toBe("var(--bn-sentiment-1-bg)");
  });

  it("returns sentiment-7-bg for index 6", () => {
    expect(getTagBg("sentiment", 6)).toBe("var(--bn-sentiment-7-bg)");
  });

  it("wraps around for index >= 7", () => {
    expect(getTagBg("sentiment", 7)).toBe("var(--bn-sentiment-1-bg)");
  });
});

describe("getGroupBg — sentiment", () => {
  it("returns sentiment group background", () => {
    expect(getGroupBg("sentiment")).toBe("var(--bn-group-sentiment)");
  });
});

describe("getBarColour — sentiment", () => {
  it("returns sentiment bar colour", () => {
    expect(getBarColour("sentiment")).toBe("var(--bn-bar-sentiment)");
  });
});
