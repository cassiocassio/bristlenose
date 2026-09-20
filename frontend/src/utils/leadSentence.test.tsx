import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderLead, splitLead } from "./leadSentence";

// `splitLead` decides where the break falls and needs no DOM. `renderLead`
// decides what the two halves ARE — and that is a contract with its callers,
// not a detail: it emits paragraphs, so a caller wrapping it in a <p> produces
// invalid nesting the browser silently repairs. This file used to test the
// split alone, on the grounds that "the renderer is two lines over splitLead".
// That stopped being true on 20 Sep 2026 and CodebookV2Page broke for exactly
// the reason the comment said not to worry about.

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

describe("what renderLead emits", () => {
  it("emits the claim and the evidence as SEPARATE paragraphs", () => {
    // The prompt has told the model since v0.2.0 that `||` is "a paragraph
    // break, not a syntactic pause" and that the card renders the evidence
    // "after a blank line". The renderer emitted a single space until today.
    render(<div>{renderLead("The claim. || The evidence.")}</div>);
    const claim = document.querySelector("p.bn-lead-claim");
    const rest = document.querySelector("p.bn-lead-rest");
    expect(claim?.textContent).toBe("The claim.");
    expect(rest?.textContent).toBe("The evidence.");
    expect(claim?.tagName).toBe("P");
    expect(rest?.tagName).toBe("P");
  });

  it("keeps <strong> on the claim — the split is semantic, not only visual", () => {
    render(<div>{renderLead("The claim. || The evidence.")}</div>);
    expect(document.querySelector("p.bn-lead-claim strong")?.textContent).toBe("The claim.");
  });

  it("strips the em dash that follows `||` in almost the whole corpus", () => {
    // MEASURED 20 Sep 2026: 51 of the 54 cached elaborations carry `||`
    // FOLLOWED BY a dash — the model was told to break the paragraph and kept
    // the run-on joiner as well. Left in, 94% of cards would open their second
    // paragraph with an em dash, which says "keep going" directly underneath a
    // break that says "you may stop here".
    render(<div>{renderLead("The claim || \u2014 the evidence.")}</div>);
    expect(document.querySelector("p.bn-lead-claim")?.textContent).toBe("The claim.");
    expect(document.querySelector("p.bn-lead-rest")?.textContent).toBe("The evidence.");
  });

  it("supplies a full stop the claim was missing", () => {
    render(<div>{renderLead("The claim || the evidence.")}</div>);
    expect(document.querySelector("p.bn-lead-claim")?.textContent).toBe("The claim.");
  });

  it("emits a bare string, not a paragraph, when there is nothing to rank", () => {
    // One rank gets no markup: wrapping it would announce every word as
    // emphasised to a screen reader for no visual difference.
    render(<div data-testid="w">{renderLead("Only one sentence here.")}</div>);
    expect(screen.getByTestId("w").querySelector("p")).toBeNull();
    expect(screen.getByTestId("w").textContent).toBe("Only one sentence here.");
  });

  it("emits BLOCK elements, which is the contract its callers must respect", () => {
    // Not a detail. A <p> cannot contain a <p>, so a caller wrapping this in a
    // paragraph produces invalid nesting the browser repairs silently — no
    // error, no failing test, just a collapsed layout. CodebookV2Page did
    // exactly that and was changed to a <div> on 20 Sep 2026. Asserting the
    // emitted tag is what makes the obligation visible to the next caller.
    render(<div data-testid="host">{renderLead("The claim. || The evidence.")}</div>);
    const emitted = [...screen.getByTestId("host").children].map((n) => n.tagName);
    expect(emitted).toEqual(["P", "P"]);
  });
});
