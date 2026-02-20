import { render, screen } from "@testing-library/react";
import { ConfidenceHistogram } from "./ConfidenceHistogram";
import type { ProposedTagResponse } from "../utils/types";

function makeProposal(overrides: Partial<ProposedTagResponse> = {}): ProposedTagResponse {
  return {
    id: 1,
    quote_id: 10,
    dom_id: "q-P1-120",
    session_id: "session-1",
    speaker_code: "P1",
    start_timecode: 120,
    quote_text: "Test quote",
    tag_definition_id: 5,
    tag_name: "Frustration",
    group_name: "Emotions",
    colour_set: "emo",
    colour_index: 0,
    confidence: 0.55,
    rationale: "Test rationale",
    status: "pending",
    ...overrides,
  };
}

describe("ConfidenceHistogram", () => {
  it("renders 20 bins", () => {
    const proposals = [
      makeProposal({ id: 1, confidence: 0.5 }),
    ];
    render(
      <ConfidenceHistogram proposals={proposals} lower={0.3} upper={0.7} />,
    );
    const histogram = screen.getByTestId("bn-threshold-histogram");
    const bins = histogram.querySelectorAll(".threshold-histogram-bin");
    expect(bins).toHaveLength(20);
  });

  it("renders x-axis labels", () => {
    render(
      <ConfidenceHistogram proposals={[]} lower={0.3} upper={0.7} />,
    );
    expect(screen.getByText("0.0")).toBeInTheDocument();
    expect(screen.getByText("0.4")).toBeInTheDocument();
    expect(screen.getByText("1.0")).toBeInTheDocument();
  });

  it("assigns proposals to correct bins", () => {
    const proposals = [
      makeProposal({ id: 1, confidence: 0.0 }),   // bin 0
      makeProposal({ id: 2, confidence: 0.05 }),  // bin 1
      makeProposal({ id: 3, confidence: 0.99 }),  // bin 19
    ];
    render(
      <ConfidenceHistogram proposals={proposals} lower={0.3} upper={0.7} />,
    );
    const histogram = screen.getByTestId("bn-threshold-histogram");
    const bins = histogram.querySelectorAll(".threshold-histogram-bin");

    // Bin 0 should have content (a square or bar)
    expect(bins[0].children.length).toBeGreaterThan(0);
    // Bin 1 should have content
    expect(bins[1].children.length).toBeGreaterThan(0);
    // Bin 19 should have content
    expect(bins[19].children.length).toBeGreaterThan(0);
    // Bin 10 (mid-range, no proposals) should be empty
    expect(bins[10].children.length).toBe(0);
  });

  it("renders empty bins for no proposals", () => {
    render(
      <ConfidenceHistogram proposals={[]} lower={0.3} upper={0.7} />,
    );
    const histogram = screen.getByTestId("bn-threshold-histogram");
    const bins = histogram.querySelectorAll(".threshold-histogram-bin");
    expect(bins).toHaveLength(20);
    // All bins should be empty
    for (const bin of bins) {
      expect(bin.children.length).toBe(0);
    }
  });

  it("uses unit-square mode for few proposals", () => {
    // With just 2 proposals, maxCount=1, which fits in unit squares
    const proposals = [
      makeProposal({ id: 1, confidence: 0.3 }),
      makeProposal({ id: 2, confidence: 0.8 }),
    ];
    render(
      <ConfidenceHistogram proposals={proposals} lower={0.3} upper={0.7} />,
    );
    const histogram = screen.getByTestId("bn-threshold-histogram");
    // Should have squares, not bars
    const squares = histogram.querySelectorAll(".threshold-histogram-square");
    expect(squares.length).toBeGreaterThan(0);
  });
});
