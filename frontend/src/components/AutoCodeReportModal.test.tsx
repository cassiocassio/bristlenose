import { render, screen, within, act, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AutoCodeReportModal } from "./AutoCodeReportModal";
import type { ProposedTagResponse } from "../utils/types";

// Mock the API module.
vi.mock("../utils/api", () => ({
  getAutoCodeProposals: vi.fn(),
  acceptAllProposals: vi.fn(),
  denyProposal: vi.fn(),
}));

import { getAutoCodeProposals, acceptAllProposals, denyProposal } from "../utils/api";

const mockGetProposals = vi.mocked(getAutoCodeProposals);
const mockAcceptAll = vi.mocked(acceptAllProposals);
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
    confidence: 0.85,
    rationale: "Speaker expressed difficulty with login",
    status: "pending",
    ...overrides,
  };
}

describe("AutoCodeReportModal", () => {
  beforeEach(() => {
    mockGetProposals.mockReset();
    mockAcceptAll.mockReset();
    mockDenyProposal.mockReset();
  });

  it("shows loading state initially", () => {
    mockGetProposals.mockReturnValue(new Promise(() => {})); // Never resolves
    render(
      <AutoCodeReportModal
        frameworkId="garrett"
        frameworkTitle="Garrett"
        onClose={vi.fn()}
        onAcceptAll={vi.fn()}
        onTagTentatively={vi.fn()}
      />,
    );
    expect(screen.getByText(/Loading proposals/)).toBeInTheDocument();
  });

  it("renders proposals grouped by session", async () => {
    const proposals = [
      makeProposal({ id: 1, session_id: "session-1", speaker_code: "P1" }),
      makeProposal({ id: 2, session_id: "session-1", speaker_code: "P2", tag_name: "Delight" }),
      makeProposal({ id: 3, session_id: "session-2", speaker_code: "P3", tag_name: "Trust" }),
    ];
    mockGetProposals.mockResolvedValue({ proposals, total: 3 });

    render(
      <AutoCodeReportModal
        frameworkId="garrett"
        frameworkTitle="Garrett"
        onClose={vi.fn()}
        onAcceptAll={vi.fn()}
        onTagTentatively={vi.fn()}
      />,
    );

    await act(async () => {});

    // Check subtitle shows correct counts.
    expect(screen.getByTestId("bn-report-subtitle")).toHaveTextContent("3 tags proposed across 2 sessions");

    // Check both sessions appear.
    expect(screen.getByText("session-1")).toBeInTheDocument();
    expect(screen.getByText("session-2")).toBeInTheDocument();

    // Check all rows render.
    expect(screen.getByTestId("bn-report-row-1")).toBeInTheDocument();
    expect(screen.getByTestId("bn-report-row-2")).toBeInTheDocument();
    expect(screen.getByTestId("bn-report-row-3")).toBeInTheDocument();
  });

  it("shows empty state when no pending proposals", async () => {
    mockGetProposals.mockResolvedValue({ proposals: [], total: 0 });

    render(
      <AutoCodeReportModal
        frameworkId="garrett"
        frameworkTitle="Garrett"
        onClose={vi.fn()}
        onAcceptAll={vi.fn()}
        onTagTentatively={vi.fn()}
      />,
    );

    await act(async () => {});
    expect(screen.getByText("No proposals to review.")).toBeInTheDocument();
  });

  it("renders framework title in header", async () => {
    mockGetProposals.mockResolvedValue({ proposals: [], total: 0 });

    render(
      <AutoCodeReportModal
        frameworkId="garrett"
        frameworkTitle="Jesse James Garrett"
        onClose={vi.fn()}
        onAcceptAll={vi.fn()}
        onTagTentatively={vi.fn()}
      />,
    );

    await act(async () => {});
    expect(screen.getByText(/Jesse James Garrett/)).toBeInTheDocument();
  });

  it("deny button removes row and calls API", async () => {
    vi.useFakeTimers();
    const proposals = [
      makeProposal({ id: 1 }),
      makeProposal({ id: 2, tag_name: "Delight" }),
    ];
    mockGetProposals.mockResolvedValue({ proposals, total: 2 });
    mockDenyProposal.mockResolvedValue(undefined);

    render(
      <AutoCodeReportModal
        frameworkId="garrett"
        frameworkTitle="Garrett"
        onClose={vi.fn()}
        onAcceptAll={vi.fn()}
        onTagTentatively={vi.fn()}
      />,
    );

    await act(async () => {});

    // Click deny on first row.
    fireEvent.click(screen.getByTestId("bn-report-deny-1"));

    expect(mockDenyProposal).toHaveBeenCalledWith(1);

    // Row should have removing class immediately.
    expect(screen.getByTestId("bn-report-row-1")).toHaveClass("removing");

    // After animation, row is gone.
    act(() => {
      vi.advanceTimersByTime(300);
    });

    expect(screen.queryByTestId("bn-report-row-1")).not.toBeInTheDocument();
    // Subtitle updates.
    expect(screen.getByTestId("bn-report-subtitle")).toHaveTextContent("1 tag proposed");

    vi.useRealTimers();
  });

  it("accept all button calls API and fires callback", async () => {
    mockGetProposals.mockResolvedValue({
      proposals: [makeProposal()],
      total: 1,
    });
    mockAcceptAll.mockResolvedValue({ accepted: 1 });
    const onAcceptAll = vi.fn();

    render(
      <AutoCodeReportModal
        frameworkId="garrett"
        frameworkTitle="Garrett"
        onClose={vi.fn()}
        onAcceptAll={onAcceptAll}
        onTagTentatively={vi.fn()}
      />,
    );

    await act(async () => {});

    fireEvent.click(screen.getByTestId("bn-report-accept-all"));

    await act(async () => {});
    expect(mockAcceptAll).toHaveBeenCalledWith("garrett");
    expect(onAcceptAll).toHaveBeenCalledOnce();
  });

  it("tag tentatively button fires callback without API call", async () => {
    mockGetProposals.mockResolvedValue({
      proposals: [makeProposal()],
      total: 1,
    });
    const onTagTentatively = vi.fn();

    render(
      <AutoCodeReportModal
        frameworkId="garrett"
        frameworkTitle="Garrett"
        onClose={vi.fn()}
        onAcceptAll={vi.fn()}
        onTagTentatively={onTagTentatively}
      />,
    );

    await act(async () => {});

    fireEvent.click(screen.getByTestId("bn-report-tag-tentatively"));
    expect(onTagTentatively).toHaveBeenCalledOnce();
    // No API calls for tag tentatively.
    expect(mockAcceptAll).not.toHaveBeenCalled();
  });

  it("close button fires onClose", async () => {
    mockGetProposals.mockResolvedValue({ proposals: [], total: 0 });
    const onClose = vi.fn();

    render(
      <AutoCodeReportModal
        frameworkId="garrett"
        frameworkTitle="Garrett"
        onClose={onClose}
        onAcceptAll={vi.fn()}
        onTagTentatively={vi.fn()}
      />,
    );

    await act(async () => {});

    fireEvent.click(screen.getByTestId("bn-report-close"));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("displays speaker code and tag name in rows", async () => {
    mockGetProposals.mockResolvedValue({
      proposals: [makeProposal({ speaker_code: "P1", tag_name: "Frustration" })],
      total: 1,
    });

    render(
      <AutoCodeReportModal
        frameworkId="garrett"
        frameworkTitle="Garrett"
        onClose={vi.fn()}
        onAcceptAll={vi.fn()}
        onTagTentatively={vi.fn()}
      />,
    );

    await act(async () => {});

    const row = screen.getByTestId("bn-report-row-1");
    expect(within(row).getByText("P1")).toBeInTheDocument();
    expect(within(row).getByText("Frustration")).toBeInTheDocument();
  });

  it("shows rationale tooltip on tag badge hover", async () => {
    mockGetProposals.mockResolvedValue({
      proposals: [makeProposal({ rationale: "Speaker clearly frustrated" })],
      total: 1,
    });

    render(
      <AutoCodeReportModal
        frameworkId="garrett"
        frameworkTitle="Garrett"
        onClose={vi.fn()}
        onAcceptAll={vi.fn()}
        onTagTentatively={vi.fn()}
      />,
    );

    await act(async () => {});

    expect(screen.getByText("Speaker clearly frustrated")).toBeInTheDocument();
  });

  it("formats timecodes correctly", async () => {
    mockGetProposals.mockResolvedValue({
      proposals: [makeProposal({ start_timecode: 3661 })], // 1:01:01
      total: 1,
    });

    render(
      <AutoCodeReportModal
        frameworkId="garrett"
        frameworkTitle="Garrett"
        onClose={vi.fn()}
        onAcceptAll={vi.fn()}
        onTagTentatively={vi.fn()}
      />,
    );

    await act(async () => {});
    expect(screen.getByText("1:01:01")).toBeInTheDocument();
  });

  it("filters out non-pending proposals", async () => {
    const proposals = [
      makeProposal({ id: 1, status: "pending" }),
      makeProposal({ id: 2, status: "accepted", tag_name: "Delight" }),
    ];
    mockGetProposals.mockResolvedValue({ proposals, total: 2 });

    render(
      <AutoCodeReportModal
        frameworkId="garrett"
        frameworkTitle="Garrett"
        onClose={vi.fn()}
        onAcceptAll={vi.fn()}
        onTagTentatively={vi.fn()}
      />,
    );

    await act(async () => {});

    expect(screen.getByTestId("bn-report-row-1")).toBeInTheDocument();
    expect(screen.queryByTestId("bn-report-row-2")).not.toBeInTheDocument();
    expect(screen.getByTestId("bn-report-subtitle")).toHaveTextContent("1 tag proposed");
  });
});
