import { describe, expect, it } from "vitest";
import { reachPhrase, vocabularyPhrase } from "./codebookReach";

describe("vocabularyPhrase — a property of the codebook", () => {
  it("names the size of the vocabulary", () => {
    expect(vocabularyPhrase(23)).toBe("23 tags");
    expect(vocabularyPhrase(1)).toBe("1 tag");
  });
});

describe("reachPhrase — two facts, not a ratio", () => {
  it("separates vocabulary from reach and names the scope", () => {
    // "28 tags on 2 quotes" welded a codebook-wide fact to a project-wide one,
    // reading as "these 28 were applied, landing on 2". The interpunct splits
    // them; the project name marks where the scope changes.
    expect(reachPhrase(28, 2, "Ikea")).toBe("28 tags · applied to 2 quotes in Ikea");
  });

  it("uses an interpunct, not a hyphen or a bullet", () => {
    expect(reachPhrase(28, 2, "Ikea")).toContain(" · ");
  });

  it("singularises the reach", () => {
    expect(reachPhrase(28, 1, "Ikea")).toBe("28 tags · applied to 1 quote in Ikea");
  });

  it("names the zero rather than going quiet", () => {
    // Reversed 3 Sep 2026. Dropping the clause was right to refuse "applied to
    // 0 quotes" — which asserts an application that never happened — and wrong
    // about the alternative: a bare "31 tags" is what a NOT-INSTALLED card says
    // minus three words, and what a failed run says, and what a run that never
    // happened says. Four states, one rendering. "none applied" denies the
    // application instead of asserting it at zero, and separates the legitimate
    // outcome (it ran, nothing matched) from the rest.
    expect(reachPhrase(31, 0, "Ikea")).toBe("31 tags · none applied to Ikea");
  });

  it("drops the reach clause when there is no project to name", () => {
    // The clause exists to say *where* the count applies. With no name it
    // renders "…in " with nothing after it — worse than the sentence it
    // replaced. Was an unscoped variant before the CLDR conversion; a second
    // plural key across 21 locales is not worth a branch the lens never
    // reaches (the name arrives from `/info` on mount).
    expect(reachPhrase(28, 2, "")).toBe("28 tags");
    expect(reachPhrase(28, 2, "   ")).toBe("28 tags");
  });
});
