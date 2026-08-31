import { describe, expect, it } from "vitest";
import { splitLead } from "./leadSentence";

// The renderer is two lines over `splitLead`; the rule worth pinning is where
// the break falls, which is testable without a DOM.

describe("the author's marker wins", () => {
  it("splits on `||` and trims the seam", () => {
    expect(splitLead("The claim. || The evidence.")).toEqual({
      lead: "The claim.",
      rest: "The evidence.",
    });
  });

  it("beats the first-sentence heuristic even when autoSplit is on", () => {
    // A human decided where the claim ends. No heuristic gets to overrule it —
    // including one that would have found an earlier, plausible boundary.
    expect(splitLead("One. Two. || Three.", { autoSplit: true }).lead).toBe("One. Two.");
  });
});

describe("autoSplit is opt-in", () => {
  const text = "The claim. The evidence.";

  it("does nothing without the flag", () => {
    // The signal cards depend on this: an elaboration the model left unmarked
    // must stay one rank rather than acquiring a break nobody authored.
    expect(splitLead(text)).toEqual({ lead: text, rest: "" });
  });

  it("finds the first sentence with it", () => {
    expect(splitLead(text, { autoSplit: true })).toEqual({
      lead: "The claim.",
      rest: "The evidence.",
    });
  });
});

describe("a split in the wrong place is worse than no split", () => {
  // Each of these reads as a bug rather than as design if it splits, because it
  // would rank half a clause. Conservative beats clever.
  const s = (t: string) => splitLead(t, { autoSplit: true });

  it("does not break on an abbreviation", () => {
    expect(s("Used by Dr. Norman in 1988. Then revised.").lead).toBe(
      "Used by Dr. Norman in 1988.",
    );
    expect(s("Slips, e.g. Typing errors. And mistakes.").lead).toBe(
      "Slips, e.g. Typing errors.",
    );
  });

  it("does not break on a decimal", () => {
    expect(s("Scores above 4.5 are strong. Below that, weak.").lead).toBe(
      "Scores above 4.5 are strong.",
    );
  });

  it("does not break on an ellipsis", () => {
    expect(s("It trails off... Then resumes properly. And ends.").lead).toBe(
      "It trails off... Then resumes properly.",
    );
  });

  it("does not break mid-sentence on a stop that is not one", () => {
    // A stop followed by lowercase is not a boundary.
    expect(s("The www.example.com site works. Fine.").rest).toBe("Fine.");
  });

  it("leaves a single sentence whole", () => {
    expect(s("Seven principles of interaction design.")).toEqual({
      lead: "Seven principles of interaction design.",
      rest: "",
    });
  });

  it("leaves text with no terminator whole", () => {
    expect(s("no punctuation here at all")).toEqual({
      lead: "no punctuation here at all",
      rest: "",
    });
  });
});
