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
    llm_provider: "anthropic",
    llm_model: "claude-sonnet-4-5-20250929",
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

    expect(screen.getByText(/AutoCoded 10 transcripts/)).toBeInTheDocument();
    expect(screen.getByTestId("bn-autocode-toast-report")).toBeInTheDocument();
    expect(onComplete).toHaveBeenCalledOnce();
  });

  it("shows error message on failure", async () => {
    mockGetStatus.mockResolvedValue(
      makeStatus({ status: "failed", error_message: "No API key" }),
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

    expect(screen.getByText(/AutoCode failed: No API key/)).toBeInTheDocument();
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
