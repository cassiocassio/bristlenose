import { render, screen, act, fireEvent } from "@testing-library/react";
import { AutoCodeToast } from "./AutoCodeToast";
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

describe("AutoCodeToast", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mockGetStatus.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders spinner and progress while running", async () => {
    mockGetStatus.mockResolvedValue(makeStatus({ processed_quotes: 3, total_quotes: 10 }));

    render(
      <AutoCodeToast
        frameworkId="garrett"
        onComplete={vi.fn()}
        onOpenReport={vi.fn()}
        onDismiss={vi.fn()}
      />,
    );

    // Flush initial poll.
    await act(async () => {});

    expect(screen.getByTestId("bn-autocode-toast")).toBeInTheDocument();
    expect(screen.getByText(/3\/10/)).toBeInTheDocument();
  });

  it("shows completion message and report link when completed", async () => {
    const onComplete = vi.fn();
    mockGetStatus.mockResolvedValue(
      makeStatus({
        status: "completed",
        total_quotes: 10,
        processed_quotes: 10,
        proposed_count: 14,
        completed_at: "2026-02-20T10:01:30Z",
      }),
    );

    render(
      <AutoCodeToast
        frameworkId="garrett"
        onComplete={onComplete}
        onOpenReport={vi.fn()}
        onDismiss={vi.fn()}
      />,
    );

    await act(async () => {});

    expect(screen.getByText(/AutoCoded 10 quotes/)).toBeInTheDocument();
    expect(screen.getByTestId("bn-autocode-toast-report")).toBeInTheDocument();
    expect(onComplete).toHaveBeenCalledOnce();
  });

  it("a completed job that tagged a subset says so", async () => {
    // autocode.py gathers batches with return_exceptions=True and carries on
    // past a failure, so a job can COMPLETE having tagged fewer quotes than it
    // set out to. processed_quotes only increments after a batch succeeds.
    mockGetStatus.mockResolvedValue(
      makeStatus({
        status: "completed",
        total_quotes: 72,
        processed_quotes: 58,
        proposed_count: 61,
      }),
    );

    render(
      <AutoCodeToast
        frameworkId="garrett"
        onComplete={vi.fn()}
        onOpenReport={vi.fn()}
        onDismiss={vi.fn()}
      />,
    );

    await act(async () => {});

    expect(screen.getByText(/58 of 72/)).toBeInTheDocument();
  });

  it("a fully-processed job does not claim a partial", async () => {
    mockGetStatus.mockResolvedValue(
      makeStatus({
        status: "completed",
        total_quotes: 72,
        processed_quotes: 72,
        proposed_count: 90,
      }),
    );

    render(
      <AutoCodeToast
        frameworkId="garrett"
        onComplete={vi.fn()}
        onOpenReport={vi.fn()}
        onDismiss={vi.fn()}
      />,
    );

    await act(async () => {});

    expect(screen.queryByText(/of 72 quotes —/)).not.toBeInTheDocument();
  });

  it("says why the job failed, from failure_kind", async () => {
    mockGetStatus.mockResolvedValue(
      makeStatus({
        status: "failed",
        failure_kind: "invalid_key",
        // Raw SDK text, as `str(exc)` from a bare `except` actually produces.
        error_message:
          "Error code: 401 - {'type': 'error', 'error': {'type': " +
          "'authentication_error', 'message': 'invalid x-api-key'}}",
      }),
    );

    render(
      <AutoCodeToast
        frameworkId="garrett"
        onComplete={vi.fn()}
        onOpenReport={vi.fn()}
        onDismiss={vi.fn()}
      />,
    );

    await act(async () => {});

    expect(
      screen.getByText(/Your API key was rejected/),
    ).toBeInTheDocument();
  });

  it("never shows the raw exception text", async () => {
    // The whole point: `error_message` is written for a log. It used to be
    // interpolated straight into the sentence, so a 401 reached the researcher
    // as a stringified JSON body.
    mockGetStatus.mockResolvedValue(
      makeStatus({
        status: "failed",
        failure_kind: "rate_limited",
        error_message: "Error code: 429 - {'type': 'rate_limit_error'}",
      }),
    );

    render(
      <AutoCodeToast
        frameworkId="garrett"
        onComplete={vi.fn()}
        onOpenReport={vi.fn()}
        onDismiss={vi.fn()}
      />,
    );

    await act(async () => {});

    expect(screen.queryByText(/rate_limit_error/)).not.toBeInTheDocument();
    expect(screen.queryByText(/429/)).not.toBeInTheDocument();
    expect(screen.getByText(/Rate limited/)).toBeInTheDocument();
  });

  it("falls back to the generic sentence when unclassified", async () => {
    // Every job that failed before `failure_kind` existed.
    mockGetStatus.mockResolvedValue(
      makeStatus({ status: "failed", failure_kind: "", error_message: "boom" }),
    );

    render(
      <AutoCodeToast
        frameworkId="garrett"
        onComplete={vi.fn()}
        onOpenReport={vi.fn()}
        onDismiss={vi.fn()}
      />,
    );

    await act(async () => {});

    expect(screen.getByText(/Tagging failed/)).toBeInTheDocument();
    expect(screen.queryByText(/boom/)).not.toBeInTheDocument();
  });

  it("dismiss button fires onDismiss", async () => {
    const onDismiss = vi.fn();
    mockGetStatus.mockResolvedValue(makeStatus());

    render(
      <AutoCodeToast
        frameworkId="garrett"
        onComplete={vi.fn()}
        onOpenReport={vi.fn()}
        onDismiss={onDismiss}
      />,
    );

    await act(async () => {});

    fireEvent.click(screen.getByTestId("bn-autocode-toast-close"));
    expect(onDismiss).toHaveBeenCalledOnce();
  });

  it("report link fires onOpenReport", async () => {
    const onOpenReport = vi.fn();
    mockGetStatus.mockResolvedValue(
      makeStatus({
        status: "completed",
        proposed_count: 14,
        completed_at: "2026-02-20T10:01:30Z",
      }),
    );

    render(
      <AutoCodeToast
        frameworkId="garrett"
        onComplete={vi.fn()}
        onOpenReport={onOpenReport}
        onDismiss={vi.fn()}
      />,
    );

    await act(async () => {});

    fireEvent.click(screen.getByTestId("bn-autocode-toast-report"));
    expect(onOpenReport).toHaveBeenCalledOnce();
  });

  it("polls every 2 seconds", async () => {
    mockGetStatus.mockResolvedValue(makeStatus());

    render(
      <AutoCodeToast
        frameworkId="garrett"
        onComplete={vi.fn()}
        onOpenReport={vi.fn()}
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

  it("renders progress bar with correct width when running", async () => {
    mockGetStatus.mockResolvedValue(
      makeStatus({ processed_quotes: 5, total_quotes: 10 }),
    );

    render(
      <AutoCodeToast
        frameworkId="garrett"
        onComplete={vi.fn()}
        onOpenReport={vi.fn()}
        onDismiss={vi.fn()}
      />,
    );

    await act(async () => {});

    const progress = screen.getByTestId("bn-autocode-progress");
    expect(progress).toBeInTheDocument();
    const fill = progress.querySelector(".toast-progress-fill") as HTMLElement;
    expect(fill).toBeTruthy();
    expect(fill.style.width).toBe("50%");
  });

  it("shows elapsed time while running", async () => {
    const now = Date.now();
    vi.setSystemTime(now);
    mockGetStatus.mockResolvedValue(
      makeStatus({
        status: "running",
        started_at: new Date(now - 15_000).toISOString(),
      }),
    );

    render(
      <AutoCodeToast
        frameworkId="garrett"
        onComplete={vi.fn()}
        onOpenReport={vi.fn()}
        onDismiss={vi.fn()}
      />,
    );

    await act(async () => {});

    expect(screen.getByText(/15s/)).toBeInTheDocument();
  });

  it("hides dismiss button when completed (user must click Report)", async () => {
    mockGetStatus.mockResolvedValue(
      makeStatus({
        status: "completed",
        proposed_count: 14,
        completed_at: "2026-02-20T10:01:30Z",
      }),
    );

    render(
      <AutoCodeToast
        frameworkId="garrett"
        onComplete={vi.fn()}
        onOpenReport={vi.fn()}
        onDismiss={vi.fn()}
      />,
    );

    await act(async () => {});

    expect(screen.queryByTestId("bn-autocode-toast-close")).not.toBeInTheDocument();
    expect(screen.getByTestId("bn-autocode-toast-report")).toBeInTheDocument();
  });

  it("offers no report when a completed job produced no proposals", async () => {
    // The report modal reads "0 of 0 proposals remaining. No proposals to
    // review." — so the link led somewhere empty, and because the link doubles
    // as the dismissal there was then no way to close the toast either.
    mockGetStatus.mockResolvedValue(
      makeStatus({
        status: "completed",
        total_quotes: 33,
        processed_quotes: 33,
        proposed_count: 0,
        completed_at: "2026-02-20T10:01:30Z",
      }),
    );

    render(
      <AutoCodeToast
        frameworkId="garrett"
        onComplete={vi.fn()}
        onOpenReport={vi.fn()}
        onDismiss={vi.fn()}
      />,
    );

    await act(async () => {});

    expect(screen.queryByTestId("bn-autocode-toast-report")).not.toBeInTheDocument();
    // The complement: no link means the close button has to be there.
    expect(screen.getByTestId("bn-autocode-toast-close")).toBeInTheDocument();
  });

  it("does not auto-dismiss after completion", async () => {
    const onDismiss = vi.fn();
    mockGetStatus.mockResolvedValue(
      makeStatus({
        status: "completed",
        completed_at: "2026-02-20T10:01:30Z",
      }),
    );

    render(
      <AutoCodeToast
        frameworkId="garrett"
        onComplete={vi.fn()}
        onOpenReport={vi.fn()}
        onDismiss={onDismiss}
      />,
    );

    await act(async () => {});
    await act(async () => {
      vi.advanceTimersByTime(60_000);
    });

    expect(onDismiss).not.toHaveBeenCalled();
  });

  it("fires onComplete only once", async () => {
    const onComplete = vi.fn();
    mockGetStatus.mockResolvedValue(
      makeStatus({ status: "completed", completed_at: "2026-02-20T10:01:30Z" }),
    );

    render(
      <AutoCodeToast
        frameworkId="garrett"
        onComplete={onComplete}
        onOpenReport={vi.fn()}
        onDismiss={vi.fn()}
      />,
    );

    await act(async () => {});
    await act(async () => {
      vi.advanceTimersByTime(2000);
    });
    await act(async () => {
      vi.advanceTimersByTime(2000);
    });

    expect(onComplete).toHaveBeenCalledTimes(1);
  });
});
