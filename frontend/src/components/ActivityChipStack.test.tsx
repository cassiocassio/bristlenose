import { render, screen, act, fireEvent } from "@testing-library/react";
import { ActivityChipStack } from "./ActivityChipStack";
import type { ActivityJob } from "./ActivityChipStack";
import type { AutoCodeJobStatus } from "../utils/types";

// Mock the API module.
vi.mock("../utils/api", () => ({
  getAutoCodeStatus: vi.fn(),
}));

vi.mock("../shims/bridge", () => ({
  postLLMFailure: vi.fn(),
}));

import { getAutoCodeStatus } from "../utils/api";
import { postLLMFailure } from "../shims/bridge";

const mockGetStatus = vi.mocked(getAutoCodeStatus);
const mockPostLLMFailure = vi.mocked(postLLMFailure);

function makeStatus(overrides: Partial<AutoCodeJobStatus> = {}): AutoCodeJobStatus {
  return {
    id: 1,
    framework_id: "garrett",
    status: "running",
    total_quotes: 10,
    processed_quotes: 3,
    proposed_count: 0,
    error_message: "",
    failure_kind: "",
    llm_provider: "anthropic",
    llm_model: "claude-sonnet-4-5-20250929",
    applied_lower_threshold: null,
    applied_upper_threshold: null,
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
    mockPostLLMFailure.mockClear();
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
      makeStatus({
        status: "completed",
        processed_quotes: 10,
        completed_at: "2026-02-20T10:01:30Z",
      }),
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
      makeStatus({
        status: "completed",
        processed_quotes: 10,
        completed_at: "2026-02-20T10:01:30Z",
      }),
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
      makeStatus({
        status: "completed",
        processed_quotes: 10,
        completed_at: "2026-02-20T10:01:30Z",
      }),
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
      makeStatus({
        status: "completed",
        processed_quotes: 10,
        proposed_count: 14,
        completed_at: "2026-02-20T10:01:30Z",
      }),
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

  it("stops polling cancelled jobs", async () => {
    mockGetStatus.mockResolvedValue(
      makeStatus({ status: "cancelled" }),
    );

    render(
      <ActivityChipStack
        jobs={[makeJob()]}
        onDismiss={vi.fn()}
      />,
    );

    await act(async () => {});
    expect(mockGetStatus).toHaveBeenCalledTimes(1);

    // Should not poll again — job is cancelled.
    await act(async () => {
      vi.advanceTimersByTime(2000);
    });
    expect(mockGetStatus).toHaveBeenCalledTimes(1);
  });

  it("fires onComplete for cancelled jobs", async () => {
    const onComplete = vi.fn();
    mockGetStatus.mockResolvedValue(
      makeStatus({ status: "cancelled" }),
    );

    render(
      <ActivityChipStack
        jobs={[makeJob({ onComplete })]}
        onDismiss={vi.fn()}
      />,
    );

    await act(async () => {});
    expect(onComplete).toHaveBeenCalledTimes(1);
  });

  it("shows close button on cancelled chip", async () => {
    mockGetStatus.mockResolvedValue(
      makeStatus({ status: "cancelled" }),
    );

    render(
      <ActivityChipStack
        jobs={[makeJob()]}
        onDismiss={vi.fn()}
      />,
    );

    await act(async () => {});
    expect(screen.getByTestId("bn-activity-chip-close")).toBeInTheDocument();
  });

  // ── Partial completion ───────────────────────────────────────────────────
  // The engine gathers batches with `return_exceptions=True` and carries on, so
  // a job can report "completed" having tagged a subset. That shortfall used to
  // be dropped: `progressLabel` is only set while running, so the chip claimed
  // an unqualified success. The correct behaviour existed in `AutoCodeToast` —
  // which is not mounted — and therefore reached no researcher.

  it("warns instead of claiming success when a job tagged only a subset", async () => {
    mockGetStatus.mockResolvedValue(
      makeStatus({
        status: "completed",
        processed_quotes: 7,
        total_quotes: 10,
        completed_at: "2026-02-20T10:01:30Z",
      }),
    );

    render(<ActivityChipStack jobs={[makeJob()]} onDismiss={vi.fn()} />);
    await act(async () => {});

    expect(screen.getByTestId("bn-activity-chip")).toHaveAttribute("data-status", "partial");
    expect(screen.getByText(/Tagged 7 of 10 quotes/)).toBeInTheDocument();
  });

  it("keeps the action link on a partial chip — the proposals still need review", async () => {
    mockGetStatus.mockResolvedValue(
      makeStatus({
        status: "completed",
        processed_quotes: 7,
        total_quotes: 10,
        proposed_count: 9,
        completed_at: "2026-02-20T10:01:30Z",
      }),
    );

    render(
      <ActivityChipStack
        jobs={[makeJob({ onAction: vi.fn(), actionLabel: "Report" })]}
        onDismiss={vi.fn()}
      />,
    );
    await act(async () => {});

    expect(screen.getByTestId("bn-activity-chip-action")).toBeInTheDocument();
    // No close button when the report link is present — the link dismisses.
    expect(screen.queryByTestId("bn-activity-chip-close")).not.toBeInTheDocument();
  });

  it("drops the action link when a finished job produced no proposals", async () => {
    // This is the chip from the 3 Sep report: "Tagged 0 of 33 quotes — some
    // batches failed. View Report", where the report was empty. The engine now
    // calls an all-batches-failed job `failed`, but a genuine partial can also
    // land zero proposals, so the gate is on the count and not on the status.
    mockGetStatus.mockResolvedValue(
      makeStatus({
        status: "completed",
        processed_quotes: 7,
        total_quotes: 10,
        proposed_count: 0,
        completed_at: "2026-02-20T10:01:30Z",
      }),
    );

    render(
      <ActivityChipStack
        jobs={[makeJob({ onAction: vi.fn(), actionLabel: "Report" })]}
        onDismiss={vi.fn()}
      />,
    );
    await act(async () => {});

    expect(screen.queryByTestId("bn-activity-chip-action")).not.toBeInTheDocument();
    // …and the close button returns, so the chip can still be got rid of.
    expect(screen.getByTestId("bn-activity-chip-close")).toBeInTheDocument();
  });

  it("tells the native shell when a job dies of an exhausted account", async () => {
    // The Mac app has a global out-of-credit pill fed only by the pipeline
    // runner, so a sidecar AutoCode job that emptied the account lit nothing.
    mockGetStatus.mockResolvedValue(
      makeStatus({
        status: "failed",
        failure_kind: "out_of_credit",
        llm_provider: "anthropic",
      }),
    );

    render(<ActivityChipStack jobs={[makeJob()]} onDismiss={vi.fn()} />);
    await act(async () => {});

    expect(mockPostLLMFailure).toHaveBeenCalledWith("out_of_credit", "anthropic");
  });

  it("posts the verdict once, not on every 2s poll", async () => {
    mockGetStatus.mockResolvedValue(
      makeStatus({
        status: "failed",
        failure_kind: "out_of_credit",
        llm_provider: "anthropic",
      }),
    );

    render(<ActivityChipStack jobs={[makeJob()]} onDismiss={vi.fn()} />);
    await act(async () => {});
    // A terminal job stays terminal. Reposting would hand the shell the same
    // verdict for as long as the chip is on screen.
    await act(async () => {});

    expect(mockPostLLMFailure).toHaveBeenCalledOnce();
  });

  it("says nothing to the shell about a job that succeeded", async () => {
    mockGetStatus.mockResolvedValue(
      makeStatus({
        status: "completed",
        processed_quotes: 10,
        proposed_count: 14,
        completed_at: "2026-02-20T10:01:30Z",
      }),
    );

    render(<ActivityChipStack jobs={[makeJob()]} onDismiss={vi.fn()} />);
    await act(async () => {});

    expect(mockPostLLMFailure).not.toHaveBeenCalled();
  });

  it("stops polling partial jobs", async () => {
    mockGetStatus.mockResolvedValue(
      makeStatus({
        status: "completed",
        processed_quotes: 7,
        total_quotes: 10,
        completed_at: "2026-02-20T10:01:30Z",
      }),
    );

    render(<ActivityChipStack jobs={[makeJob()]} onDismiss={vi.fn()} />);
    await act(async () => {});
    expect(mockGetStatus).toHaveBeenCalledTimes(1);

    await act(async () => {
      vi.advanceTimersByTime(2000);
    });
    expect(mockGetStatus).toHaveBeenCalledTimes(1);
  });

  it("fires onComplete for partial jobs", async () => {
    const onComplete = vi.fn();
    mockGetStatus.mockResolvedValue(
      makeStatus({
        status: "completed",
        processed_quotes: 7,
        total_quotes: 10,
        completed_at: "2026-02-20T10:01:30Z",
      }),
    );

    render(
      <ActivityChipStack jobs={[makeJob({ onComplete })]} onDismiss={vi.fn()} />,
    );
    await act(async () => {});

    expect(onComplete).toHaveBeenCalledTimes(1);
  });
});
