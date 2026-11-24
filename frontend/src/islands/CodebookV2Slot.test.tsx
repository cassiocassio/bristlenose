import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { CodebookSlot, slotState } from "./CodebookV2Slot";

// The rule the codebook pages' slot follows (owner, 24 Nov 2026), and the two edges
// the review found: a switched-off codebook, and an exported report.

describe("slotState", () => {
  it("offers AutoCode for a codebook not installed", () => {
    expect(slotState("garrett", false, true, undefined, false)).toBe("act");
  });

  it("says Applied for sentiment whatever the server says (D20)", () => {
    expect(slotState("sentiment", true, true, undefined, false)).toBe("done");
    expect(slotState("sentiment", true, false, "unfinished", false)).toBe("done");
  });

  it("says AutoCoding while the server or this window's chip says a run goes", () => {
    expect(slotState("garrett", true, true, "running", false)).toBe("run");
    expect(slotState("garrett", true, true, "applied", true)).toBe("run");
  });

  it("says Applied once a run completed, and offers AutoCode again, to resume, after one that did not", () => {
    expect(slotState("garrett", true, true, "applied", false)).toBe("done");
    expect(slotState("garrett", true, true, "unfinished", false)).toBe("act");
    expect(slotState("garrett", true, true, undefined, false)).toBe("act");
  });

  it("offers no button on a switched-off codebook: switching it off stopped the run", () => {
    expect(slotState("garrett", true, false, "unfinished", false)).toBeNull();
    expect(slotState("garrett", true, false, undefined, false)).toBeNull();
    // Applied stays said, knocked back by the page.
    expect(slotState("garrett", true, false, "applied", false)).toBe("done");
  });
});

describe("CodebookSlot in an exported report (no action)", () => {
  it("draws no button and no words that would shimmer for ever", () => {
    const { container, rerender } = render(<CodebookSlot state="run" testId="s" />);
    expect(container).toBeEmptyDOMElement();
    rerender(<CodebookSlot state="act" testId="s" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("still says Applied", () => {
    render(<CodebookSlot state="done" testId="s" />);
    expect(screen.getByTestId("s")).toHaveTextContent("Applied");
  });
});
