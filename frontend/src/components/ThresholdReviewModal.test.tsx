import { render, screen, act, fireEvent } from "@testing-library/react";
import { ThresholdReviewModal } from "./ThresholdReviewModal";
import { _resetExportCache } from "../utils/exportData";
import { featureFlags, resetFeatureFlags } from "../utils/featureFlags";
import type { ProposedTagResponse } from "../utils/types";

// Mock the API module.
vi.mock("../utils/api", () => ({
  getAutoCodeStatus: vi.fn(),
  getAutoCodeProposals: vi.fn(),
  acceptProposal: vi.fn(),
  denyProposal: vi.fn(),
  recutProposals: vi.fn(),
  toastSaveFailed: vi.fn(),
}));

import {
  getAutoCodeStatus,
  getAutoCodeProposals,
  acceptProposal,
  denyProposal,
  recutProposals,
  toastSaveFailed,
} from "../utils/api";

const mockGetStatus = vi.mocked(getAutoCodeStatus);
const mockGetProposals = vi.mocked(getAutoCodeProposals);
const mockAcceptProposal = vi.mocked(acceptProposal);
const mockDenyProposal = vi.mocked(denyProposal);
const mockRecut = vi.mocked(recutProposals);

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
    mockGetStatus.mockReset();
    // No apply has happened in most tests — the modal falls back to its own
    // DEFAULT_LOWER / DEFAULT_UPPER.
    mockGetStatus.mockResolvedValue({
      applied_lower_threshold: null,
      applied_upper_threshold: null,
    } as never);
    mockGetProposals.mockReset();
    mockAcceptProposal.mockReset();
    mockDenyProposal.mockReset();
    mockRecut.mockReset();
    vi.mocked(toastSaveFailed).mockReset();
  });

  it("shows loading state initially", () => {
    mockGetProposals.mockReturnValue(new Promise(() => {}));
    render(
      <ThresholdReviewModal
        open={true}
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
        open={true}
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
        open={true}
        frameworkId="garrett"
        frameworkTitle="Garrett"
        onClose={vi.fn()}
        onApply={vi.fn()}
      />,
    );
    await act(async () => {});
    expect(
      screen.getByText(/Drag thresholds to control/),
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
        open={true}
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
        open={true}
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
        open={true}
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
        open={true}
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

  it("does not close on a click on the backdrop", async () => {
    // A press on a threshold handle released past the card is a click on the
    // backdrop; it used to close the review and drop the unapplied thresholds.
    mockGetProposals.mockResolvedValue({ proposals: [], total: 0 });
    const onClose = vi.fn();

    render(
      <ThresholdReviewModal
        open={true}
        frameworkId="garrett"
        frameworkTitle="Garrett"
        onClose={onClose}
        onApply={vi.fn()}
      />,
    );
    await act(async () => {});

    fireEvent.click(screen.getByTestId("bn-threshold-overlay"));
    expect(onClose).not.toHaveBeenCalled();
  });

  // D39: Apply is the re-cut, one call with both lines (it was accept-all then deny-all).
  // A run never cut has no stored lines, so its first Apply is offered at the defaults.
  it("apply button re-cuts the run at the thresholds", async () => {
    const proposals = [
      makeProposal({ id: 1, confidence: 0.8 }),
    ];
    mockGetProposals.mockResolvedValue({ proposals, total: 1 });
    mockRecut.mockResolvedValue({ accepted: 1, tentative: 0, excluded: 0 });
    const onApply = vi.fn();

    render(
      <ThresholdReviewModal
        open={true}
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
    expect(mockRecut).toHaveBeenCalledWith("garrett", 0.30, 0.70);
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
        open={true}
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

  // Owner, 7 Nov 2026: a blue timecode plays, here as everywhere; the speaker opens the
  // transcript at that moment, in a new tab or window so the review stays open.
  it("a row's timecode plays and its speaker opens the transcript over there", async () => {
    mockGetProposals.mockResolvedValue({
      proposals: [makeProposal({ id: 1, confidence: 0.5 })],
      total: 1,
    });
    render(
      <ThresholdReviewModal
        open={true}
        frameworkId="garrett"
        frameworkTitle="Garrett"
        onClose={vi.fn()}
        onApply={vi.fn()}
      />,
    );
    await act(async () => {});
    const row = screen.getByTestId("bn-proposal-row-1");
    const timecode = row.querySelector(".report-timecode a")!;
    expect(timecode.classList.contains("timecode")).toBe(true);
    expect(timecode.getAttribute("href")).toMatch(/^#t=/);
    expect(timecode.getAttribute("target")).toBeNull();
    const speaker = screen.getByTestId("bn-proposal-speaker-1");
    expect(speaker.getAttribute("href")).toMatch(/^\/report\/sessions\/.+#t-\d+$/);
    expect(speaker.getAttribute("target")).toBe("_blank");
  });

  it("per-row deny calls denyProposal API and the row moves, pinned", async () => {
    vi.useFakeTimers();
    const proposals = [
      makeProposal({ id: 1, confidence: 0.5 }),
      makeProposal({ id: 2, confidence: 0.8 }),
    ];
    mockGetProposals.mockResolvedValue({ proposals, total: 2 });
    mockDenyProposal.mockResolvedValue(undefined);

    render(
      <ThresholdReviewModal
        open={true}
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
    // A pending row: an ordinary deny, no override (D34).
    expect(mockDenyProposal).toHaveBeenCalledWith(1, undefined);

    // After the slide (200 ms) the row leaves Tentative for Excluded, pinned as the
    // researcher's decision. It used to leave the dialog: the whole run stays (D39).
    await act(async () => {
      vi.advanceTimersByTime(300);
    });
    expect(screen.getByTestId("bn-zone-tentative").querySelector('[data-testid="bn-proposal-row-1"]')).toBeNull();
    expect(screen.getByTestId("bn-zone-excluded").querySelector('[data-testid="bn-proposal-row-1"]')).not.toBeNull();
    expect(screen.getByTestId("bn-proposal-pin-1")).toBeInTheDocument();

    vi.useRealTimers();
  });

  // A per-row accept or deny that failed went to the console, and the row left
  // as if it had saved (R5). It now says so and comes back — unless the server
  // says it was already decided, which removes it either way.
  describe("a per-row review that does not save", () => {
    const renderModal = async () => {
      mockGetProposals.mockResolvedValue({
        proposals: [makeProposal({ id: 1, confidence: 0.5 })],
        total: 1,
      });
      render(
        <ThresholdReviewModal open={true} frameworkId="garrett" frameworkTitle="Garrett"
          onClose={vi.fn()} onApply={vi.fn()} />,
      );
      await act(async () => {});
    };
    const click = (action: "accept" | "deny") =>
      fireEvent.click(
        screen.getByTestId("bn-proposal-row-1").querySelector(`.threshold-action-${action}`)!,
      );
    // What the server holds for the row once it says it was decided (the dialog reads
    // it again, D44): decided on a quote card.
    const decidedOnServer = (status: "accepted" | "denied") =>
      mockGetProposals.mockResolvedValue({
        proposals: [makeProposal({ id: 1, confidence: 0.5, status, decided_by: "researcher" })],
        total: 1,
      });

    it.each([["before", 0], ["after", 300]] as const)(
      "comes back and says so when the answer lands %s the row leaves",
      async (_when, before) => {
        vi.useFakeTimers();
        try {
          let refuse: (e: unknown) => void = () => {};
          mockAcceptProposal.mockImplementation(() => new Promise((_, r) => { refuse = r; }));
          await renderModal();
          click("accept");
          await act(async () => { vi.advanceTimersByTime(before); });
          await act(async () => { refuse(new Error("offline")); });
          await act(async () => { vi.advanceTimersByTime(300); });
          expect(screen.getByTestId("bn-proposal-row-1")).toBeInTheDocument();
          expect(toastSaveFailed).toHaveBeenCalledTimes(1);
          // Nothing was accepted, so nothing is counted as accepted.
          expect(screen.getByTestId("bn-threshold-subtitle").textContent).not.toMatch(/accepted/i);
        } finally {
          vi.useRealTimers();
        }
      },
    );

    it("a review that lands is counted", async () => {
      vi.useFakeTimers();
      try {
        mockAcceptProposal.mockResolvedValue(undefined);
        await renderModal();
        click("accept");
        await act(async () => { vi.advanceTimersByTime(300); });
        expect(screen.getByTestId("bn-threshold-subtitle").textContent).toMatch(/1 accepted/i);
      } finally {
        vi.useRealTimers();
      }
    });

    // N33 (owner, 1 Nov 2026): a click the server says was decided the other way
    // elsewhere leaves, says so, and is counted where it actually landed.
    it.each([
      ["deny", "proposal_accepted", /1 accepted/i, /excluded/i],
      ["accept", "proposal_denied", /1 excluded/i, /accepted/i],
    ] as const)(
      "a %s that was decided the other way says so, and lands where it was decided",
      async (action, reason, counted, notCounted) => {
        vi.useFakeTimers();
        try {
          const refused = Object.assign(new Error("409"), { status: 409, reason });
          mockDenyProposal.mockRejectedValue(refused);
          mockAcceptProposal.mockRejectedValue(refused);
          await renderModal();
          decidedOnServer(reason === "proposal_accepted" ? "accepted" : "denied");
          click(action);
          await act(async () => { vi.advanceTimersByTime(300); });
          // It is read again (D44) and drawn where it was decided (it used to leave
          // the dialog: the whole run stays, D39).
          expect(mockGetProposals).toHaveBeenCalledTimes(2);
          const zone = reason === "proposal_accepted" ? "bn-zone-accepted" : "bn-zone-excluded";
          expect(screen.getByTestId(zone).querySelector('[data-testid="bn-proposal-row-1"]')).not.toBeNull();
          expect(toastSaveFailed).toHaveBeenCalledTimes(1);
          const subtitle = screen.getByTestId("bn-threshold-subtitle").textContent ?? "";
          expect(subtitle).toMatch(counted);
          expect(subtitle).not.toMatch(notCounted);
        } finally {
          vi.useRealTimers();
        }
      },
    );

    it("counts where it landed when the answer arrives before the row has left", async () => {
      vi.useFakeTimers();
      try {
        mockDenyProposal.mockRejectedValue(
          Object.assign(new Error("409"), { status: 409, reason: "proposal_accepted" }),
        );
        await renderModal();
        decidedOnServer("accepted");
        click("deny");
        await act(async () => {}); // the answer is in before the 200 ms slide ends
        await act(async () => { vi.advanceTimersByTime(300); });
        const subtitle = screen.getByTestId("bn-threshold-subtitle").textContent ?? "";
        expect(subtitle).toMatch(/1 accepted/i);
        expect(subtitle).not.toMatch(/excluded/i);
      } finally {
        vi.useRealTimers();
      }
    });

    it("counts where it landed when the answer arrives after the row has left", async () => {
      vi.useFakeTimers();
      try {
        let refuse: (e: unknown) => void = () => {};
        mockDenyProposal.mockImplementation(() => new Promise((_, r) => { refuse = r; }));
        await renderModal();
        decidedOnServer("accepted");
        click("deny");
        await act(async () => { vi.advanceTimersByTime(300); });
        await act(async () => {
          refuse(Object.assign(new Error("409"), { status: 409, reason: "proposal_accepted" }));
        });
        const subtitle = screen.getByTestId("bn-threshold-subtitle").textContent ?? "";
        expect(subtitle).toMatch(/1 accepted/i);
        expect(subtitle).not.toMatch(/excluded/i);
      } finally {
        vi.useRealTimers();
      }
    });

    it("a suggestion that is gone (404) leaves uncounted", async () => {
      vi.useFakeTimers();
      try {
        mockDenyProposal.mockRejectedValue(Object.assign(new Error("404"), { status: 404 }));
        await renderModal();
        click("deny");
        await act(async () => { vi.advanceTimersByTime(300); });
        expect(screen.queryByTestId("bn-proposal-row-1")).not.toBeInTheDocument();
        const subtitle = screen.getByTestId("bn-threshold-subtitle").textContent ?? "";
        expect(subtitle).not.toMatch(/excluded|accepted/i);
      } finally {
        vi.useRealTimers();
      }
    });

    it("an answer from before the modal was closed and opened again changes nothing", async () => {
      vi.useFakeTimers();
      try {
        let refuse: (e: unknown) => void = () => {};
        mockAcceptProposal.mockImplementation(() => new Promise((_, r) => { refuse = r; }));
        mockGetProposals.mockResolvedValue({
          proposals: [makeProposal({ id: 1, confidence: 0.5 })], total: 1,
        });
        const props = { frameworkId: "garrett", frameworkTitle: "Garrett",
          onClose: vi.fn(), onApply: vi.fn() };
        const { rerender } = render(<ThresholdReviewModal open={true} {...props} />);
        await act(async () => {});
        click("accept");
        await act(async () => { vi.advanceTimersByTime(300); });
        rerender(<ThresholdReviewModal open={false} {...props} />);
        rerender(<ThresholdReviewModal open={true} {...props} />);
        await act(async () => {});
        await act(async () => { refuse(new Error("offline")); });
        expect(toastSaveFailed).toHaveBeenCalledTimes(1); // it still says so
        // A review in this opening is counted from zero, not from the stale -1.
        mockAcceptProposal.mockResolvedValue(undefined);
        click("accept");
        await act(async () => { vi.advanceTimersByTime(300); });
        expect(screen.getByTestId("bn-threshold-subtitle").textContent).toMatch(/1 accepted/i);
      } finally {
        vi.useRealTimers();
      }
    });

    it("does nothing in an exported report, which has no server", async () => {
      (window as unknown as Record<string, unknown>).BRISTLENOSE_EXPORT = {
        version: 1, exported_at: "2026-10-20T00:00:00Z", health: {}, endpoints: {},
      };
      _resetExportCache();
      try {
        await renderModal();
        click("accept");
        expect(mockAcceptProposal).not.toHaveBeenCalled();
        expect(screen.getByTestId("bn-proposal-row-1")).toBeInTheDocument();
      } finally {
        delete (window as unknown as Record<string, unknown>).BRISTLENOSE_EXPORT;
        _resetExportCache();
      }
    });

    it("lands, quietly, when it was already decided the same way", async () => {
      vi.useFakeTimers();
      try {
        mockDenyProposal.mockRejectedValue(
          Object.assign(new Error("409"), { status: 409, reason: "proposal_denied" }),
        );
        await renderModal();
        decidedOnServer("denied");
        click("deny");
        await act(async () => { vi.advanceTimersByTime(300); });
        // In Excluded now, rather than out of the dialog (D39).
        expect(screen.getByTestId("bn-zone-excluded").querySelector('[data-testid="bn-proposal-row-1"]')).not.toBeNull();
        expect(toastSaveFailed).not.toHaveBeenCalled();
      } finally {
        vi.useRealTimers();
      }
    });
  });

  // Parked behind `proposalRationaleTooltip` (see utils/featureFlags.ts):
  // the first test forces the flag on, the second asserts what ships.
  it("shows the rationale tooltip on a row's tag badge (flag on)", async () => {
    featureFlags.proposalRationaleTooltip = true;
    try {
      mockGetProposals.mockResolvedValue({
        proposals: [makeProposal({ rationale: "Speaker clearly frustrated" })],
        total: 1,
      });

      render(
        <ThresholdReviewModal
          open={true}
          frameworkId="garrett"
          frameworkTitle="Garrett"
          onClose={vi.fn()}
          onApply={vi.fn()}
        />,
      );
      await act(async () => {});

      const row = screen.getByTestId("bn-proposal-row-1");
      expect(row.querySelector(".has-tooltip .tooltip")).toHaveTextContent(
        "Speaker clearly frustrated",
      );
    } finally {
      resetFeatureFlags();
    }
  });

  it("does not render the rationale tooltip when the flag is off (shipped)", async () => {
    mockGetProposals.mockResolvedValue({
      proposals: [makeProposal({ rationale: "Speaker clearly frustrated" })],
      total: 1,
    });

    render(
      <ThresholdReviewModal
        open={true}
        frameworkId="garrett"
        frameworkTitle="Garrett"
        onClose={vi.fn()}
        onApply={vi.fn()}
      />,
    );
    await act(async () => {});

    expect(screen.getByTestId("bn-proposal-row-1")).toBeInTheDocument();
    expect(screen.queryByText("Speaker clearly frustrated")).toBeNull();
    expect(document.querySelector(".has-tooltip")).toBeNull();
  });

  it("slider thumbs are present with default values", async () => {
    const proposals = [makeProposal({ id: 1, confidence: 0.5 })];
    mockGetProposals.mockResolvedValue({ proposals, total: 1 });

    render(
      <ThresholdReviewModal
        open={true}
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

  // ── Applied thresholds ───────────────────────────────────────────────────
  // `AutoCodeJob` has stored the applied cutoffs since it was written, but the
  // modal reset to its defaults on every open — so a report reopened after an
  // apply drew threshold lines where they had never been, over a histogram of
  // what had actually happened.

  it("seeds the sliders from the thresholds actually applied", async () => {
    mockGetStatus.mockResolvedValue({
      applied_lower_threshold: 0.15,
      applied_upper_threshold: 0.85,
    } as never);
    mockGetProposals.mockResolvedValue({
      proposals: [makeProposal()],
      total: 1,
    } as never);

    render(
      <ThresholdReviewModal
        open
        frameworkId="garrett"
        frameworkTitle="Garrett"
        onClose={vi.fn()}
        onApply={vi.fn()}
      />,
    );
    await act(async () => {});

    const sliders = screen.getAllByRole("slider");
    expect(sliders[0]).toHaveAttribute("aria-valuenow", "0.15");
    expect(sliders[1]).toHaveAttribute("aria-valuenow", "0.85");
  });

  it("reopens a project whose stored thresholds drifted on exact stops, and Apply sends them clean (N185)", async () => {
    // Apply now waits for a line to move (D39), so the exclude line moves one step and
    // the accept line, unmoved, still goes out clean.
    // An earlier build stored 0.30000000000000004 / 0.8500000000000001.
    mockGetStatus.mockResolvedValue({
      applied_lower_threshold: 0.30000000000000004,
      applied_upper_threshold: 0.8500000000000001,
    } as never);
    mockGetProposals.mockResolvedValue({
      proposals: [makeProposal({ id: 1, confidence: 0.3 }), makeProposal({ id: 2, confidence: 0.85 })],
      total: 2,
    } as never);
    mockRecut.mockResolvedValue({ accepted: 0, tentative: 0, excluded: 1 });

    render(
      <ThresholdReviewModal
        open
        frameworkId="garrett"
        frameworkTitle="Garrett"
        onClose={vi.fn()}
        onApply={vi.fn()}
      />,
    );
    await act(async () => {});
    fireEvent.keyDown(screen.getByTestId("bn-threshold-lower"), { key: "ArrowRight" });
    fireEvent.click(screen.getByTestId("bn-threshold-apply"));
    await act(async () => {});

    expect(mockRecut).toHaveBeenCalledWith("garrett", 0.35, 0.85);
  });

  it("falls back to the defaults when nothing has been applied yet", async () => {
    mockGetProposals.mockResolvedValue({
      proposals: [makeProposal()],
      total: 1,
    } as never);

    render(
      <ThresholdReviewModal
        open
        frameworkId="garrett"
        frameworkTitle="Garrett"
        onClose={vi.fn()}
        onApply={vi.fn()}
      />,
    );
    await act(async () => {});

    const sliders = screen.getAllByRole("slider");
    expect(sliders[0]).toHaveAttribute("aria-valuenow", "0.3");
    expect(sliders[1]).toHaveAttribute("aria-valuenow", "0.7");
  });

  // ── Phase 2: the re-cuttable review (landing plan D2, D26, D34, D37, D39) ──
  // docs/mockups/autocode-review-dialog.html is the approved design.
  describe("the whole run, re-cuttable", () => {
    // Stored lines 0.30 / 0.70. One proposal of each kind:
    //   1 pending 0.50 · 2 accepted by the lines 0.75 · 3 accepted by the researcher 0.72
    //   4 excluded by the lines 0.20 · 5 excluded by the researcher 0.90
    //   6 accepted before the record ("unknown") 0.78 · 7 pending 0.85 (above the line:
    //   its quote was hidden at the last Apply, and is back)
    const run = () => [
      makeProposal({ id: 1, confidence: 0.5 }),
      makeProposal({ id: 2, confidence: 0.75, status: "accepted", decided_by: "threshold" }),
      makeProposal({ id: 3, confidence: 0.72, status: "accepted", decided_by: "researcher" }),
      makeProposal({ id: 4, confidence: 0.2, status: "denied", decided_by: "threshold" }),
      makeProposal({ id: 5, confidence: 0.9, status: "denied", decided_by: "researcher" }),
      makeProposal({ id: 6, confidence: 0.78, status: "accepted", decided_by: "unknown" }),
      makeProposal({ id: 7, confidence: 0.85 }),
    ];
    const open = async (proposals = run(), lines: [number | null, number | null] = [0.3, 0.7]) => {
      mockGetStatus.mockResolvedValue({
        applied_lower_threshold: lines[0],
        applied_upper_threshold: lines[1],
      } as never);
      mockGetProposals.mockResolvedValue({ proposals, total: proposals.length });
      render(
        <ThresholdReviewModal open frameworkId="garrett" frameworkTitle="Garrett"
          onClose={vi.fn()} onApply={vi.fn()} />,
      );
      await act(async () => {});
    };
    const inZone = (zone: string) =>
      [...screen.getByTestId(`bn-zone-${zone}`).querySelectorAll("[data-testid^='bn-proposal-row-']")]
        .map((r) => Number(r.getAttribute("data-testid")!.replace("bn-proposal-row-", "")))
        .sort((a, b) => a - b);
    const counter = (kind: string) =>
      Number(document.querySelector(`.threshold-zone-counter--${kind} .threshold-zone-counter-count`)!.textContent);
    const raiseAcceptLine = (steps: number) => {
      for (let i = 0; i < steps; i++) {
        fireEvent.keyDown(screen.getByTestId("bn-threshold-upper"), { key: "ArrowRight" });
      }
    };

    it("loads every proposal of the run, decided ones in their zones", async () => {
      await open();
      // 7 is pending above the accept line: Apply decides it by the lines (D41).
      expect(inZone("accepted")).toEqual([2, 3, 6, 7]);
      expect(inZone("tentative")).toEqual([1]);
      expect(inZone("excluded")).toEqual([4, 5]);
      // The histogram counts the whole run, not only what is pending.
      const bars = screen.getByTestId("bn-threshold-histogram");
      expect(bars.querySelectorAll(".threshold-histogram-square").length).toBe(7);
    });

    it("pins a researcher's and an unknown decision, named \"Your decision\"", async () => {
      await open();
      for (const id of [3, 5, 6]) {
        const pin = screen.getByTestId(`bn-proposal-pin-${id}`);
        expect(pin).toHaveAttribute("title", "Your decision");
        expect(pin.querySelector("svg")).toHaveAttribute("aria-label", "Your decision");
        expect(pin.querySelector("svg")!.getAttribute("class")).toContain("bn-icon-pinned");
        // After the confidence, in its cell.
        expect(pin.closest(".threshold-confidence")).not.toBeNull();
      }
      for (const id of [1, 2, 4, 7]) expect(screen.queryByTestId(`bn-proposal-pin-${id}`)).toBeNull();
    });

    it("counts and lists Apply's outcome: only threshold and pending rows whose zone changes move", async () => {
      await open();
      // Unmoved lines: every decision stays where its status puts it (D26); the
      // pending 0.85 is decided by the lines (D41).
      expect([counter("exclude"), counter("tentative"), counter("accept")]).toEqual([2, 1, 4]);
      raiseAcceptLine(2); // 0.70 → 0.80
      // 2 (threshold, 0.75) moves to tentative; 3 (researcher, 0.72) and 6 (unknown,
      // 0.78) are pinned and stay; 7 (0.85) is still above the line.
      expect(inZone("accepted")).toEqual([3, 6, 7]);
      expect(inZone("tentative")).toEqual([1, 2]);
      expect(inZone("excluded")).toEqual([4, 5]);
      expect([counter("exclude"), counter("tentative"), counter("accept")]).toEqual([2, 2, 3]);
      // Both lines to the top (accept 1.00, exclude 0.95): everything movable is
      // excluded, the pinned accepts are not, and the researcher's exclusion stays.
      raiseAcceptLine(4);
      for (let i = 0; i < 20; i++) {
        fireEvent.keyDown(screen.getByTestId("bn-threshold-lower"), { key: "ArrowRight" });
      }
      expect(inZone("accepted")).toEqual([3, 6]);
      expect(inZone("excluded")).toEqual([1, 2, 4, 5, 7]);
    });

    it("keeps Apply off until a line moves from the stored lines, and off again when it is put back", async () => {
      await open(run().filter((p) => p.id !== 7)); // nothing pending the lines decide
      const apply = screen.getByTestId("bn-threshold-apply");
      expect(apply).toBeDisabled();
      raiseAcceptLine(1);
      expect(apply).toBeEnabled();
      fireEvent.keyDown(screen.getByTestId("bn-threshold-upper"), { key: "ArrowLeft" });
      expect(apply).toBeDisabled();
    });

    it("Apply calls the re-cut with the lines snapped to the grid", async () => {
      mockRecut.mockResolvedValue({ accepted: 0, tentative: 1, excluded: 0 });
      await open();
      raiseAcceptLine(2);
      fireEvent.click(screen.getByTestId("bn-threshold-apply"));
      await act(async () => {});
      expect(mockRecut).toHaveBeenCalledTimes(1);
      expect(mockRecut).toHaveBeenCalledWith("garrett", 0.3, 0.8);
    });

    it.each([
      ["deny", 2, "accepted", "excluded"],
      ["accept", 4, "excluded", "accepted"],
    ] as const)(
      "a %s on a decided row sends the explicit override, and the row moves, pinned",
      async (action, id, from, to) => {
        vi.useFakeTimers();
        try {
          mockDenyProposal.mockResolvedValue(undefined);
          mockAcceptProposal.mockResolvedValue(undefined);
          await open();
          expect(inZone(from)).toContain(id);
          fireEvent.click(screen.getByTestId(`bn-proposal-row-${id}`).querySelector(`.threshold-action-${action}`)!);
          const mock = action === "deny" ? mockDenyProposal : mockAcceptProposal;
          // The override names the status the row was shown in (D44).
          expect(mock).toHaveBeenCalledWith(id, from === "accepted" ? "accepted" : "denied");
          await act(async () => { vi.advanceTimersByTime(300); });
          expect(inZone(to)).toContain(id);
          expect(screen.getByTestId(`bn-proposal-pin-${id}`)).toBeInTheDocument();
          // Pinned now: a line that would move it leaves it where the researcher put it.
          raiseAcceptLine(5);
          expect(inZone(to)).toContain(id);
        } finally {
          vi.useRealTimers();
        }
      },
    );

    it("a pending row sends no override", async () => {
      mockAcceptProposal.mockResolvedValue(undefined);
      await open();
      fireEvent.click(screen.getByTestId("bn-proposal-row-1").querySelector(".threshold-action-accept")!);
      expect(mockAcceptProposal).toHaveBeenCalledWith(1, undefined);
    });

    it("a run never cut is offered a plain cut: only pending rows move, decisions stay", async () => {
      await open(run(), [null, null]);
      // At the default lines, the threshold acceptance at 0.75 and exclusion at 0.20
      // sit where their status puts them; the pending 0.85 is accepted by the cut.
      expect(inZone("accepted")).toEqual([2, 3, 6, 7]);
      expect(inZone("excluded")).toEqual([4, 5]);
      raiseAcceptLine(2); // 0.80: 2 (threshold, 0.75) still stays, decisions are not re-cut
      expect(inZone("accepted")).toEqual([2, 3, 6, 7]);
      expect(screen.getByTestId("bn-threshold-apply")).toBeEnabled();
    });

    it("offers Apply with the lines unmoved when a pending row is above the line (D41)", async () => {
      await open([makeProposal({ id: 8, confidence: 0.9 }),
        makeProposal({ id: 2, confidence: 0.75, status: "accepted", decided_by: "threshold" })]);
      expect(inZone("accepted")).toEqual([2, 8]);
      expect(screen.getByTestId("bn-threshold-apply")).toBeEnabled();
    });

    it("a row refused as decided elsewhere is read again, not assumed (D44)", async () => {
      vi.useFakeTimers();
      try {
        mockAcceptProposal.mockRejectedValue(
          Object.assign(new Error("409"), { status: 409, reason: "proposal_accepted" }),
        );
        await open();
        // Meanwhile the lines accepted proposal 1 (a threshold decision, not a person's).
        mockGetProposals.mockResolvedValue({
          proposals: run().map((p) => (p.id === 1
            ? { ...p, status: "accepted" as const, decided_by: "threshold" as const } : p)),
          total: 7,
        });
        fireEvent.click(screen.getByTestId("bn-proposal-row-1").querySelector(".threshold-action-accept")!);
        await act(async () => { vi.advanceTimersByTime(300); });
        expect(mockGetProposals).toHaveBeenCalledTimes(2);
        expect(inZone("accepted")).toContain(1);
        expect(screen.queryByTestId("bn-proposal-pin-1")).toBeNull();
      } finally {
        vi.useRealTimers();
      }
    });

    it("a stale override refused by the server draws the newer decision, quietly (D44)", async () => {
      vi.useFakeTimers();
      try {
        mockDenyProposal.mockRejectedValue(
          Object.assign(new Error("409"), { status: 409, reason: "proposal_denied" }),
        );
        await open();
        // A quote card excluded 2 after the dialog drew it accepted.
        mockGetProposals.mockResolvedValue({
          proposals: run().map((p) => (p.id === 2
            ? { ...p, status: "denied" as const, decided_by: "researcher" as const } : p)),
          total: 7,
        });
        fireEvent.click(screen.getByTestId("bn-proposal-row-2").querySelector(".threshold-action-deny")!);
        expect(mockDenyProposal).toHaveBeenCalledWith(2, "accepted");
        await act(async () => { vi.advanceTimersByTime(300); });
        expect(inZone("excluded")).toContain(2);
        expect(screen.getByTestId("bn-proposal-pin-2")).toBeInTheDocument();
        // It went the way the click asked (an override expects one decided status, so
        // a refusal is always the other one), so there is nothing to complain about.
        expect(toastSaveFailed).not.toHaveBeenCalled();
      } finally {
        vi.useRealTimers();
      }
    });

    it.each([["the Close button", "bn-threshold-close"], ["the header ×", null]] as const)(
      "%s says whether a row decision was saved, so the page can refresh its tags (D42)",
      async (_label, testId) => {
        vi.useFakeTimers();
        try {
          mockDenyProposal.mockResolvedValue(undefined);
          const onClose = vi.fn();
          mockGetStatus.mockResolvedValue({ applied_lower_threshold: 0.3, applied_upper_threshold: 0.7 } as never);
          mockGetProposals.mockResolvedValue({ proposals: run(), total: 7 });
          const props = { frameworkId: "garrett", frameworkTitle: "Garrett", onApply: vi.fn(), onClose };
          const { rerender } = render(<ThresholdReviewModal open {...props} />);
          await act(async () => {});
          const closeIt = () => fireEvent.click(testId
            ? screen.getByTestId(testId)
            : document.querySelector(".codebook-modal-close")!);
          closeIt();
          expect(onClose).toHaveBeenLastCalledWith(false);
          rerender(<ThresholdReviewModal open={false} {...props} />);
          rerender(<ThresholdReviewModal open {...props} />);
          await act(async () => {});
          fireEvent.click(screen.getByTestId("bn-proposal-row-2").querySelector(".threshold-action-deny")!);
          await act(async () => { vi.advanceTimersByTime(300); });
          closeIt();
          expect(onClose).toHaveBeenLastCalledWith(true);
        } finally {
          vi.useRealTimers();
        }
      },
    );

    it("does not draw the run when the stored lines cannot be read, and Apply stays off (D43)", async () => {
      mockGetStatus.mockRejectedValue(Object.assign(new Error("timed out"), { name: "TimeoutError" }));
      mockGetProposals.mockResolvedValue({ proposals: run(), total: 7 });
      render(
        <ThresholdReviewModal open frameworkId="garrett" frameworkTitle="Garrett"
          onClose={vi.fn()} onApply={vi.fn()} />,
      );
      await act(async () => {});
      expect(screen.getByText("Failed to load proposals")).toBeInTheDocument();
      expect(screen.queryByTestId("bn-threshold-histogram")).toBeNull();
      expect(screen.getByTestId("bn-threshold-apply")).toBeDisabled();
    });

    it("an Apply that fails or times out says so and stays open (D43)", async () => {
      mockRecut.mockRejectedValue(Object.assign(new Error("timed out"), { name: "TimeoutError" }));
      const onApply = vi.fn();
      mockGetStatus.mockResolvedValue({ applied_lower_threshold: 0.3, applied_upper_threshold: 0.7 } as never);
      mockGetProposals.mockResolvedValue({ proposals: run(), total: 7 });
      render(
        <ThresholdReviewModal open frameworkId="garrett" frameworkTitle="Garrett"
          onClose={vi.fn()} onApply={onApply} />,
      );
      await act(async () => {});
      raiseAcceptLine(1);
      fireEvent.click(screen.getByTestId("bn-threshold-apply"));
      await act(async () => {});
      expect(screen.getByText(/Apply failed/)).toBeInTheDocument();
      expect(onApply).not.toHaveBeenCalled();
      expect(screen.getByTestId("bn-threshold-apply")).toBeEnabled();
    });

    it("has no sparkle in the title (D37)", async () => {
      await open();
      const title = document.getElementById("bn-threshold-title")!;
      expect(title.querySelector("svg")).toBeNull();
      expect(title).toHaveTextContent("AutoCode Review: Garrett");
    });

    it("opens on the whole run when nothing is pending", async () => {
      const decided = run().map((p) => (p.status === "pending"
        ? { ...p, status: "accepted" as const, decided_by: "threshold" as const } : p));
      await open(decided);
      expect(screen.getByTestId("bn-threshold-histogram")).toBeInTheDocument();
      expect(inZone("accepted")).toEqual([1, 2, 3, 6, 7]);
      expect(inZone("excluded")).toEqual([4, 5]);
      // The subtitle keeps its shipped words.
      expect(screen.getByTestId("bn-threshold-subtitle")).toHaveTextContent(
        "0 of 7 proposals remaining (5 accepted, 2 excluded)",
      );
      expect(screen.getByTestId("bn-threshold-apply")).toBeDisabled();
    });
  });

  // The owner's review-pane rulings (24 Nov 2026).
  describe("the review pane's small fixes", () => {
    const show = async (proposals: ProposedTagResponse[]) => {
      mockGetProposals.mockResolvedValue({ proposals, total: proposals.length });
      render(
        <ThresholdReviewModal open frameworkId="garrett" frameworkTitle="Garrett"
          onClose={vi.fn()} onApply={vi.fn()} />,
      );
      await act(async () => {});
    };

    it("opens and closes a zone from the keyboard: its header is a button", async () => {
      await show([makeProposal({ id: 1, confidence: 0.9 })]);
      const header = screen.getByTestId("bn-zone-header-accepted");
      expect(header.tagName).toBe("BUTTON");
      expect(header).toHaveAttribute("aria-expanded", "false");
      fireEvent.click(header);
      expect(header).toHaveAttribute("aria-expanded", "true");
    });

    it("lists sessions in number order, not by their best proposal", async () => {
      await show([
        makeProposal({ id: 1, session_id: "s10", confidence: 0.6 }),
        makeProposal({ id: 2, session_id: "s3", confidence: 0.69 }),
        makeProposal({ id: 3, session_id: "s2", confidence: 0.4 }),
      ]);
      const headers = [...screen.getByTestId("bn-zone-tentative")
        .querySelectorAll(".report-session-header")].map((h) => h.textContent);
      expect(headers).toEqual(["Session 2", "Session 3", "Session 10"]);
    });

    it("draws a tentative tag with the tentative tag's dashed outline, and only there", async () => {
      await show([
        makeProposal({ id: 1, confidence: 0.5 }),
        makeProposal({ id: 2, confidence: 0.9 }),
      ]);
      fireEvent.click(screen.getByTestId("bn-zone-header-accepted"));
      const badge = (id: number) =>
        screen.getByTestId(`bn-proposal-row-${id}`).querySelector(".report-tag .badge")!;
      expect(badge(1)).toHaveClass("badge-proposed");
      expect(badge(2)).not.toHaveClass("badge-proposed");
    });

    it("keeps a row in place, dimmed and counted, until its decision lands it", async () => {
      vi.useFakeTimers();
      try {
        mockDenyProposal.mockResolvedValue(undefined);
        await show([makeProposal({ id: 1, confidence: 0.5 }), makeProposal({ id: 2, confidence: 0.4 })]);
        const count = () => screen.getByTestId("bn-zone-header-tentative").textContent;
        expect(count()).toContain("(2)");
        fireEvent.click(screen.getByTestId("bn-proposal-row-1").querySelector(".threshold-action-deny")!);
        const row = screen.getByTestId("bn-zone-tentative").querySelector('[data-testid="bn-proposal-row-1"]');
        expect(row).toHaveClass("report-row--deciding");
        expect(count()).toContain("(2)");
        await act(async () => { vi.advanceTimersByTime(300); });
        expect(screen.getByTestId("bn-zone-excluded").querySelector('[data-testid="bn-proposal-row-1"]'))
          .not.toBeNull();
        expect(count()).toContain("(1)");
      } finally {
        vi.useRealTimers();
      }
    });

    it("cuts each quote to a line until Word wrap is ticked, then draws it whole", async () => {
      await show([makeProposal({ id: 1, confidence: 0.5 })]);
      const table = () => screen.getByTestId("bn-zone-tentative").querySelector("table")!;
      const wrap = screen.getByTestId("bn-threshold-wrap");
      expect(wrap).not.toBeChecked();
      expect(screen.getByLabelText("Word wrap")).toBe(wrap);
      expect(table()).not.toHaveClass("threshold-proposal-table--wrap");
      fireEvent.click(wrap);
      expect(table()).toHaveClass("threshold-proposal-table--wrap");
    });
  });
});
