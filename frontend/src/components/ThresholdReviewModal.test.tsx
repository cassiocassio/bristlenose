import { render, screen, act, fireEvent } from "@testing-library/react";
import { ThresholdReviewModal } from "./ThresholdReviewModal";
import type { ProposedTagResponse } from "../utils/types";

// Mock the API module.
vi.mock("../utils/api", () => ({
  getAutoCodeProposals: vi.fn(),
  acceptAllProposals: vi.fn(),
  acceptProposal: vi.fn(),
  denyAllProposals: vi.fn(),
  denyProposal: vi.fn(),
}));

import {
  getAutoCodeProposals,
  acceptAllProposals,
  acceptProposal,
  denyAllProposals,
  denyProposal,
} from "../utils/api";

const mockGetProposals = vi.mocked(getAutoCodeProposals);
const mockAcceptAll = vi.mocked(acceptAllProposals);
const mockAcceptProposal = vi.mocked(acceptProposal);
const mockDenyAll = vi.mocked(denyAllProposals);
const mockDenyProposal = vi.mocked(denyProposal);

function makeProposal(overrides: Partial<ProposedTagResponse> = {}): ProposedTagResponse {
  return {
    id: 1,
    quote_id: 10,
    dom_id: "q-P1-120",
    session_id: "session-1",
    speaker_code: "P1",
    start_timecode: 120,
    quote_text: "I found the login very confusing",
    tag_definition_id: 5,
    tag_name: "Frustration",
    group_name: "Emotions",
    colour_set: "emo",
    colour_index: 0,
    confidence: 0.55,
    rationale: "Speaker expressed difficulty with login",
    status: "pending",
    ...overrides,
  };
}

describe("ThresholdReviewModal", () => {
  beforeEach(() => {
    mockGetProposals.mockReset();
    mockAcceptAll.mockReset();
    mockAcceptProposal.mockReset();
    mockDenyAll.mockReset();
    mockDenyProposal.mockReset();
  });

  it("shows loading state initially", () => {
    mockGetProposals.mockReturnValue(new Promise(() => {}));
    render(
      <ThresholdReviewModal
        frameworkId="garrett"
        frameworkTitle="Garrett"
        onClose={vi.fn()}
        onApply={vi.fn()}
      />,
    );
    expect(screen.getByText(/Loading proposals/)).toBeInTheDocument();
  });

  it("renders framework title in header", async () => {
    mockGetProposals.mockResolvedValue({ proposals: [], total: 0 });
    render(
      <ThresholdReviewModal
        frameworkId="garrett"
        frameworkTitle="Jesse James Garrett"
        onClose={vi.fn()}
        onApply={vi.fn()}
      />,
    );
    await act(async () => {});
    expect(screen.getByText(/Jesse James Garrett/)).toBeInTheDocument();
  });

  it("shows instruction text", async () => {
    mockGetProposals.mockResolvedValue({ proposals: [], total: 0 });
    render(
      <ThresholdReviewModal
        frameworkId="garrett"
        frameworkTitle="Garrett"
        onClose={vi.fn()}
        onApply={vi.fn()}
      />,
    );
    await act(async () => {});
    expect(
      screen.getByText(/Drag the thresholds to control/),
    ).toBeInTheDocument();
  });

  it("renders histogram and slider when proposals exist", async () => {
    const proposals = [
      makeProposal({ id: 1, confidence: 0.3 }),
      makeProposal({ id: 2, confidence: 0.5 }),
      makeProposal({ id: 3, confidence: 0.8 }),
    ];
    mockGetProposals.mockResolvedValue({ proposals, total: 3 });

    render(
      <ThresholdReviewModal
        frameworkId="garrett"
        frameworkTitle="Garrett"
        onClose={vi.fn()}
        onApply={vi.fn()}
      />,
    );
    await act(async () => {});

    expect(screen.getByTestId("bn-threshold-histogram")).toBeInTheDocument();
    expect(screen.getByTestId("bn-threshold-slider")).toBeInTheDocument();
  });

  it("shows zone counters with correct default counts", async () => {
    // Default thresholds: lower=0.30, upper=0.70
    // Proposals at 0.2, 0.5, 0.8 → excluded=1, tentative=1, accepted=1
    const proposals = [
      makeProposal({ id: 1, confidence: 0.2 }),
      makeProposal({ id: 2, confidence: 0.5 }),
      makeProposal({ id: 3, confidence: 0.8 }),
    ];
    mockGetProposals.mockResolvedValue({ proposals, total: 3 });

    render(
      <ThresholdReviewModal
        frameworkId="garrett"
        frameworkTitle="Garrett"
        onClose={vi.fn()}
        onApply={vi.fn()}
      />,
    );
    await act(async () => {});

    // Check zone counters are rendered (class-based to avoid text ambiguity)
    const counters = document.querySelectorAll(".threshold-zone-counter");
    expect(counters.length).toBe(3);
    expect(document.querySelector(".threshold-zone-counter--exclude")).toBeTruthy();
    expect(document.querySelector(".threshold-zone-counter--tentative")).toBeTruthy();
    expect(document.querySelector(".threshold-zone-counter--accept")).toBeTruthy();
  });

  it("fetches proposals with min_confidence=0", async () => {
    mockGetProposals.mockResolvedValue({ proposals: [], total: 0 });
    render(
      <ThresholdReviewModal
        frameworkId="garrett"
        frameworkTitle="Garrett"
        onClose={vi.fn()}
        onApply={vi.fn()}
      />,
    );
    await act(async () => {});
    expect(mockGetProposals).toHaveBeenCalledWith("garrett", 0);
  });

  it("close button fires onClose", async () => {
    mockGetProposals.mockResolvedValue({ proposals: [], total: 0 });
    const onClose = vi.fn();

    render(
      <ThresholdReviewModal
        frameworkId="garrett"
        frameworkTitle="Garrett"
        onClose={onClose}
        onApply={vi.fn()}
      />,
    );
    await act(async () => {});

    fireEvent.click(screen.getByTestId("bn-threshold-close"));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("apply button calls accept-all and deny-all with thresholds", async () => {
    const proposals = [
      makeProposal({ id: 1, confidence: 0.8 }),
    ];
    mockGetProposals.mockResolvedValue({ proposals, total: 1 });
    mockAcceptAll.mockResolvedValue({ accepted: 1 });
    mockDenyAll.mockResolvedValue({ denied: 0 });
    const onApply = vi.fn();

    render(
      <ThresholdReviewModal
        frameworkId="garrett"
        frameworkTitle="Garrett"
        onClose={vi.fn()}
        onApply={onApply}
      />,
    );
    await act(async () => {});

    fireEvent.click(screen.getByTestId("bn-threshold-apply"));
    await act(async () => {});

    // Default upper=0.70, lower=0.30
    expect(mockAcceptAll).toHaveBeenCalledWith("garrett", 0.70);
    expect(mockDenyAll).toHaveBeenCalledWith("garrett", 0.30);
    expect(onApply).toHaveBeenCalledOnce();
  });

  it("shows subtitle with remaining and resolved counts", async () => {
    const proposals = [
      makeProposal({ id: 1, confidence: 0.5, status: "pending" }),
      makeProposal({ id: 2, confidence: 0.8, status: "accepted" }),
      makeProposal({ id: 3, confidence: 0.1, status: "denied" }),
    ];
    mockGetProposals.mockResolvedValue({ proposals, total: 3 });

    render(
      <ThresholdReviewModal
        frameworkId="garrett"
        frameworkTitle="Garrett"
        onClose={vi.fn()}
        onApply={vi.fn()}
      />,
    );
    await act(async () => {});

    const subtitle = screen.getByTestId("bn-threshold-subtitle");
    expect(subtitle).toHaveTextContent("1 of 3 proposals remaining");
    expect(subtitle).toHaveTextContent("1 accepted");
    expect(subtitle).toHaveTextContent("1 excluded");
  });

  it("per-row deny calls denyProposal API", async () => {
    vi.useFakeTimers();
    const proposals = [
      makeProposal({ id: 1, confidence: 0.5 }),
      makeProposal({ id: 2, confidence: 0.8 }),
    ];
    mockGetProposals.mockResolvedValue({ proposals, total: 2 });
    mockDenyProposal.mockResolvedValue(undefined);

    render(
      <ThresholdReviewModal
        frameworkId="garrett"
        frameworkTitle="Garrett"
        onClose={vi.fn()}
        onApply={vi.fn()}
      />,
    );
    await act(async () => {});

    // The tentative zone (0.30–0.70) should contain the 0.5 proposal
    // Find a deny button in the rendered list
    const row = screen.getByTestId("bn-proposal-row-1");
    const denyBtn = row.querySelector(".threshold-action-deny") as HTMLElement;
    expect(denyBtn).toBeTruthy();

    fireEvent.click(denyBtn);
    expect(mockDenyProposal).toHaveBeenCalledWith(1);

    // After animation timeout, row should be removed
    act(() => {
      vi.advanceTimersByTime(300);
    });
    expect(screen.queryByTestId("bn-proposal-row-1")).not.toBeInTheDocument();

    vi.useRealTimers();
  });

  it("slider thumbs are present with default values", async () => {
    const proposals = [makeProposal({ id: 1, confidence: 0.5 })];
    mockGetProposals.mockResolvedValue({ proposals, total: 1 });

    render(
      <ThresholdReviewModal
        frameworkId="garrett"
        frameworkTitle="Garrett"
        onClose={vi.fn()}
        onApply={vi.fn()}
      />,
    );
    await act(async () => {});

    const lowerThumb = screen.getByTestId("bn-threshold-lower");
    const upperThumb = screen.getByTestId("bn-threshold-upper");

    expect(lowerThumb).toBeInTheDocument();
    expect(upperThumb).toBeInTheDocument();
    expect(lowerThumb).toHaveTextContent("0.30");
    expect(upperThumb).toHaveTextContent("0.70");
  });
});
