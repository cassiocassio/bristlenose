import { render, screen, act, fireEvent } from "@testing-library/react";
import { ActivityChipStack } from "./ActivityChipStack";
import type { ActivityJob } from "./ActivityChipStack";
import type { AutoCodeJobStatus } from "../utils/types";

// Mock the API module.
vi.mock("../utils/api", () => ({
  getAutoCodeStatus: vi.fn(),
}));

import { getAutoCodeStatus } from "../utils/api";

const mockGetStatus = vi.mocked(getAutoCodeStatus);

function makeStatus(overrides: Partial<AutoCodeJobStatus> = {}): AutoCodeJobStatus {
  return {
    id: 1,
    framework_id: "garrett",
    status: "running",
    total_quotes: 10,
    processed_quotes: 3,
    proposed_count: 0,
    error_message: "",
    llm_provider: "anthropic",
    llm_model: "claude-sonnet-4-5-20250929",
    input_tokens: 0,
    output_tokens: 0,
    started_at: "2026-02-20T10:00:00Z",
    completed_at: null,
    ...overrides,
  };
}

function makeJob(overrides: Partial<ActivityJob> = {}): ActivityJob {
  return {
    id: "autocode:garrett",
    label: "\u2726 AutoCoding Garrett",
    frameworkId: "garrett",
    actionLabel: "Report",
    ...overrides,
  };
}

describe("ActivityChipStack", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mockGetStatus.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders nothing when jobs array is empty", () => {
    render(<ActivityChipStack jobs={[]} onDismiss={vi.fn()} />);

    expect(screen.queryByTestId("bn-activity-chip-stack")).not.toBeInTheDocument();
  });

  it("renders a single chip for one job", async () => {
    mockGetStatus.mockResolvedValue(makeStatus());

    render(
      <ActivityChipStack
        jobs={[makeJob()]}
        onDismiss={vi.fn()}
      />,
    );

    await act(async () => {});

    expect(screen.getByTestId("bn-activity-chip-stack")).toBeInTheDocument();
    expect(screen.getByTestId("bn-activity-chip")).toBeInTheDocument();
    expect(screen.queryByTestId("bn-activity-chip-summary")).not.toBeInTheDocument();
  });

  it("renders summary chip for 2+ jobs", async () => {
    mockGetStatus.mockResolvedValue(makeStatus());

    render(
      <ActivityChipStack
        jobs={[
          makeJob({ id: "autocode:garrett", frameworkId: "garrett" }),
          makeJob({ id: "autocode:norman", frameworkId: "norman", label: "\u2726 AutoCoding Norman" }),
        ]}
        onDismiss={vi.fn()}
      />,
    );

    await act(async () => {});

    expect(screen.getByTestId("bn-activity-chip-summary")).toBeInTheDocument();
    expect(screen.getByText(/2 tasks running/)).toBeInTheDocument();
    // Individual chips should NOT be visible while collapsed.
    expect(screen.queryAllByTestId("bn-activity-chip")).toHaveLength(0);
  });

  it("expand/collapse toggle works", async () => {
    mockGetStatus.mockResolvedValue(makeStatus());

    render(
      <ActivityChipStack
        jobs={[
          makeJob({ id: "autocode:garrett", frameworkId: "garrett" }),
          makeJob({ id: "autocode:norman", frameworkId: "norman", label: "\u2726 AutoCoding Norman" }),
        ]}
        onDismiss={vi.fn()}
      />,
    );

    await act(async () => {});

    // Collapsed — summary visible.
    expect(screen.getByTestId("bn-activity-chip-summary")).toBeInTheDocument();

    // Expand.
    fireEvent.click(screen.getByTestId("bn-activity-chip-expand"));
    expect(screen.queryByTestId("bn-activity-chip-summary")).not.toBeInTheDocument();
    expect(screen.getAllByTestId("bn-activity-chip")).toHaveLength(2);

    // Collapse.
    fireEvent.click(screen.getByTestId("bn-activity-chip-collapse"));
    expect(screen.getByTestId("bn-activity-chip-summary")).toBeInTheDocument();
  });

  it("polls each job every 2 seconds", async () => {
    mockGetStatus.mockResolvedValue(makeStatus());

    render(
      <ActivityChipStack
        jobs={[makeJob()]}
        onDismiss={vi.fn()}
      />,
    );

    await act(async () => {});
    expect(mockGetStatus).toHaveBeenCalledTimes(1);

    await act(async () => {
      vi.advanceTimersByTime(2000);
    });
    expect(mockGetStatus).toHaveBeenCalledTimes(2);

    await act(async () => {
      vi.advanceTimersByTime(2000);
    });
    expect(mockGetStatus).toHaveBeenCalledTimes(3);
  });

  it("stops polling completed jobs", async () => {
    mockGetStatus.mockResolvedValue(
      makeStatus({ status: "completed", completed_at: "2026-02-20T10:01:30Z" }),
    );

    render(
      <ActivityChipStack
        jobs={[makeJob()]}
        onDismiss={vi.fn()}
      />,
    );

    // Initial poll.
    await act(async () => {});
    expect(mockGetStatus).toHaveBeenCalledTimes(1);

    // Should not poll again — job is completed.
    await act(async () => {
      vi.advanceTimersByTime(2000);
    });
    expect(mockGetStatus).toHaveBeenCalledTimes(1);
  });

  it("fires onComplete once per job", async () => {
    const onComplete = vi.fn();
    mockGetStatus.mockResolvedValue(
      makeStatus({ status: "completed", completed_at: "2026-02-20T10:01:30Z" }),
    );

    render(
      <ActivityChipStack
        jobs={[makeJob({ onComplete })]}
        onDismiss={vi.fn()}
      />,
    );

    await act(async () => {});
    expect(onComplete).toHaveBeenCalledTimes(1);

    // Re-render shouldn't fire again.
    await act(async () => {
      vi.advanceTimersByTime(2000);
    });
    expect(onComplete).toHaveBeenCalledTimes(1);
  });

  it("fires onDismiss when close button clicked on completed chip", async () => {
    const onDismiss = vi.fn();
    mockGetStatus.mockResolvedValue(
      makeStatus({ status: "completed", completed_at: "2026-02-20T10:01:30Z" }),
    );

    render(
      <ActivityChipStack
        jobs={[makeJob()]}
        onDismiss={onDismiss}
      />,
    );

    await act(async () => {});

    fireEvent.click(screen.getByTestId("bn-activity-chip-close"));
    expect(onDismiss).toHaveBeenCalledWith("autocode:garrett");
  });

  it("does not show close button on running chip", async () => {
    mockGetStatus.mockResolvedValue(makeStatus());

    render(
      <ActivityChipStack
        jobs={[makeJob()]}
        onDismiss={vi.fn()}
      />,
    );

    await act(async () => {});

    expect(screen.queryByTestId("bn-activity-chip-close")).not.toBeInTheDocument();
  });

  it("shows action link on completed chip", async () => {
    const onAction = vi.fn();
    mockGetStatus.mockResolvedValue(
      makeStatus({ status: "completed", completed_at: "2026-02-20T10:01:30Z" }),
    );

    render(
      <ActivityChipStack
        jobs={[makeJob({ onAction, actionLabel: "Report" })]}
        onDismiss={vi.fn()}
      />,
    );

    await act(async () => {});

    const link = screen.getByTestId("bn-activity-chip-action");
    expect(link).toHaveTextContent("Report");
    fireEvent.click(link);
    expect(onAction).toHaveBeenCalledOnce();
  });
});
