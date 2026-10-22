import { render, screen, act, fireEvent } from "@testing-library/react";
import { ActivityChipStack } from "./ActivityChipStack";
import type { ActivityJob, NormalisedJobStatus } from "./ActivityChipStack";
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
    // The link doubles as the dismissal, so it and the close button are exact
    // complements: whichever is absent, the other is there. Pinned for the
    // partial and zero-proposal branches below; this is the plain-completed one.
    expect(screen.queryByTestId("bn-activity-chip-close")).not.toBeInTheDocument();
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
  // an unqualified success. The correct behaviour existed in a duplicate toast
  // component that nothing rendered, and therefore reached no researcher.

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

  it("a job that tagged everything is completed, not partial", async () => {
    // The other side of the `processed < total` boundary. Without it a
    // normaliser that called *every* completed job partial would satisfy the
    // test above, and a run that went fine would reach the researcher as a
    // warning about batches that never failed.
    mockGetStatus.mockResolvedValue(
      makeStatus({
        status: "completed",
        processed_quotes: 10,
        total_quotes: 10,
        completed_at: "2026-02-20T10:01:30Z",
      }),
    );

    render(<ActivityChipStack jobs={[makeJob()]} onDismiss={vi.fn()} />);
    await act(async () => {});

    expect(screen.getByTestId("bn-activity-chip")).toHaveAttribute(
      "data-status",
      "completed",
    );
    expect(screen.queryByText(/some batches failed/)).not.toBeInTheDocument();
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

  // ── Failure messages ─────────────────────────────────────────────────────
  // `error_message` is `str(exc)` from a bare `except` — raw SDK text, usually
  // a stringified JSON body. `normaliseAutoCode` resolves `failure_kind`
  // through `autocodeFailure()` at the API/UI boundary and never touches it.
  // These three cases are the only coverage `autocodeFailure()` has anywhere;
  // they used to live in `AutoCodeToast.test.tsx`, pinning a component nothing
  // rendered, and moved here when that duplicate was deleted.

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

    render(<ActivityChipStack jobs={[makeJob()]} onDismiss={vi.fn()} />);
    await act(async () => {});

    expect(screen.getByText(/Your API key was rejected/)).toBeInTheDocument();
  });

  it("never shows the raw exception text", async () => {
    // The whole point: it used to be interpolated straight into the sentence,
    // so a rate limit reached the researcher as a stringified JSON body.
    mockGetStatus.mockResolvedValue(
      makeStatus({
        status: "failed",
        failure_kind: "rate_limited",
        error_message: "Error code: 429 - {'type': 'rate_limit_error'}",
      }),
    );

    render(<ActivityChipStack jobs={[makeJob()]} onDismiss={vi.fn()} />);
    await act(async () => {});

    expect(screen.queryByText(/rate_limit_error/)).not.toBeInTheDocument();
    expect(screen.queryByText(/429/)).not.toBeInTheDocument();
    expect(screen.getByText(/Rate limited/)).toBeInTheDocument();
  });

  it("falls back to the generic sentence when unclassified", async () => {
    // Every job that failed before `failure_kind` existed, and any the
    // classifier declined to name.
    mockGetStatus.mockResolvedValue(
      makeStatus({ status: "failed", failure_kind: "", error_message: "boom" }),
    );

    render(<ActivityChipStack jobs={[makeJob()]} onDismiss={vi.fn()} />);
    await act(async () => {});

    expect(screen.getByText(/Tagging failed/)).toBeInTheDocument();
    expect(screen.queryByText(/boom/)).not.toBeInTheDocument();
  });

  // R13: a job whose status can no longer be read (the server restarted or went away, or
  // no longer knows the job) used to spin for ever, because every failed poll was ignored.
  describe("a job whose status can no longer be read", () => {
    it("ends in the failed state, offers a dismiss, and stops polling", async () => {
      const onComplete = vi.fn();
      mockGetStatus.mockRejectedValue(new Error("Failed to fetch"));
      render(<ActivityChipStack jobs={[makeJob({ onComplete })]} onDismiss={vi.fn()} />);
      await act(async () => {});
      for (let i = 0; i < 5; i++) {
        await act(async () => {
          vi.advanceTimersByTime(2000);
        });
      }
      expect(screen.getByTestId("bn-activity-chip")).toHaveAttribute("data-status", "failed");
      expect(screen.getByTestId("bn-activity-chip-close")).toBeInTheDocument();
      expect(onComplete).toHaveBeenCalledTimes(1);
      const calls = mockGetStatus.mock.calls.length;
      await act(async () => {
        vi.advanceTimersByTime(10_000);
      });
      expect(mockGetStatus.mock.calls.length).toBe(calls);
    });

    it("ends a custom-polled job (clips, screens) the same way", async () => {
      const pollFn = vi.fn(() => Promise.reject(new Error("Failed to fetch")));
      render(<ActivityChipStack jobs={[makeJob({ id: "screens:1", pollFn })]} onDismiss={vi.fn()} />);
      await act(async () => {});
      for (let i = 0; i < 5; i++) {
        await act(async () => {
          vi.advanceTimersByTime(2000);
        });
      }
      expect(screen.getByTestId("bn-activity-chip")).toHaveAttribute("data-status", "failed");
    });

    it("never turns a job that already finished into a failure", async () => {
      // A finished chip stays up until dismissed, and every change to the job list polls each
      // job once more: with the server gone, those failures must not add up to "failed".
      mockGetStatus.mockResolvedValueOnce(
        makeStatus({ status: "completed", processed_quotes: 10, completed_at: "2026-02-20T10:01:30Z" }),
      );
      mockGetStatus.mockRejectedValue(new Error("Failed to fetch"));
      const { rerender } = render(<ActivityChipStack jobs={[makeJob()]} onDismiss={vi.fn()} />);
      await act(async () => {});
      for (let i = 0; i < 6; i++) {
        rerender(<ActivityChipStack jobs={[makeJob()]} onDismiss={vi.fn()} />);
        await act(async () => {});
      }
      expect(mockGetStatus.mock.calls.length).toBeGreaterThanOrEqual(6);
      expect(screen.getByTestId("bn-activity-chip")).toHaveAttribute("data-status", "completed");
    });

    it("keeps running through a few failed polls that are followed by an answer", async () => {
      // Four failures, an answer, four more: never five in a row.
      const fail = () => mockGetStatus.mockRejectedValueOnce(new Error("Failed to fetch"));
      for (let i = 0; i < 4; i++) fail();
      mockGetStatus.mockResolvedValueOnce(makeStatus());
      for (let i = 0; i < 4; i++) fail();
      mockGetStatus.mockResolvedValue(makeStatus());
      render(<ActivityChipStack jobs={[makeJob()]} onDismiss={vi.fn()} />);
      await act(async () => {});
      for (let i = 0; i < 9; i++) {
        await act(async () => {
          vi.advanceTimersByTime(2000);
        });
      }
      expect(mockGetStatus.mock.calls.length).toBeGreaterThanOrEqual(10);
      expect(screen.getByTestId("bn-activity-chip")).toHaveAttribute("data-status", "running");
    });
  });

  // R13 follow-ups: a later poll must not rewrite a finished job, a job that leaves and comes
  // back under the same id starts clean, and a hung read is not asked again on top of itself.
  describe("a job's life under its id", () => {
    const done = () =>
      makeStatus({ status: "completed", processed_quotes: 10, completed_at: "2026-02-20T10:01:30Z" });
    const lost = () => Promise.reject(new Error("Failed to fetch"));
    const never = () => new Promise<never>(() => {});
    const endLost = async () => {
      for (let i = 0; i < 5; i++) {
        await act(async () => {
          vi.advanceTimersByTime(2000);
        });
      }
    };

    it("asks again only once the last read has answered", async () => {
      const pollFn = vi.fn(never);
      render(<ActivityChipStack jobs={[makeJob({ pollFn })]} onDismiss={vi.fn()} />);
      await act(async () => {});
      await act(async () => {
        vi.advanceTimersByTime(10_000);
      });
      expect(pollFn).toHaveBeenCalledTimes(1);
    });

    it("keeps a finished job's outcome against a later poll's different one", async () => {
      // Every change to the job list polls each job once more; after a restart the server
      // answers "failed" for a clip export that finished.
      mockGetStatus.mockResolvedValueOnce(done());
      mockGetStatus.mockResolvedValue(makeStatus({ status: "failed" }));
      const { rerender } = render(<ActivityChipStack jobs={[makeJob()]} onDismiss={vi.fn()} />);
      await act(async () => {});
      rerender(<ActivityChipStack jobs={[makeJob()]} onDismiss={vi.fn()} />);
      await act(async () => {});
      expect(mockGetStatus).toHaveBeenCalledTimes(2);
      expect(screen.getByTestId("bn-activity-chip")).toHaveAttribute("data-status", "completed");
    });

    it("follows a new run under the same id, and says when it finishes", async () => {
      const onComplete = vi.fn();
      mockGetStatus.mockResolvedValueOnce(done());
      mockGetStatus.mockResolvedValueOnce(makeStatus());
      mockGetStatus.mockResolvedValue(done());
      const { rerender } = render(<ActivityChipStack jobs={[makeJob({ onComplete })]} onDismiss={vi.fn()} />);
      await act(async () => {});
      expect(onComplete).toHaveBeenCalledTimes(1);
      rerender(<ActivityChipStack jobs={[makeJob({ onComplete })]} onDismiss={vi.fn()} />);
      await act(async () => {});
      expect(screen.getByTestId("bn-activity-chip")).toHaveAttribute("data-status", "running");
      await act(async () => {
        vi.advanceTimersByTime(2000);
      });
      expect(onComplete).toHaveBeenCalledTimes(2);
    });

    it("starts clean when a job is dismissed and its id comes back", async () => {
      const first = vi.fn(lost);
      const { rerender } = render(<ActivityChipStack jobs={[makeJob({ pollFn: first })]} onDismiss={vi.fn()} />);
      await act(async () => {});
      await endLost();
      expect(screen.getByTestId("bn-activity-chip")).toHaveAttribute("data-status", "failed");
      rerender(<ActivityChipStack jobs={[]} onDismiss={vi.fn()} />);
      // Back under the same id, its first read failing: one failure is not five.
      const second = vi.fn(lost);
      rerender(<ActivityChipStack jobs={[makeJob({ pollFn: second })]} onDismiss={vi.fn()} />);
      await act(async () => {});
      expect(second).toHaveBeenCalledTimes(1);
      expect(screen.getByTestId("bn-activity-chip")).toHaveAttribute("data-status", "running");
    });

    it("does not count a dismissed job's late failure against the one back under its id", async () => {
      let fail!: (e: Error) => void;
      const first = vi.fn(() => new Promise<NormalisedJobStatus>((_, r) => (fail = r)));
      const { rerender } = render(<ActivityChipStack jobs={[makeJob({ pollFn: first })]} onDismiss={vi.fn()} />);
      await act(async () => {});
      rerender(<ActivityChipStack jobs={[]} onDismiss={vi.fn()} />);
      const second = vi.fn(lost);
      rerender(<ActivityChipStack jobs={[makeJob({ pollFn: second })]} onDismiss={vi.fn()} />);
      await act(async () => {});
      for (let i = 0; i < 3; i++) {
        await act(async () => {
          vi.advanceTimersByTime(2000);
        });
      }
      expect(second).toHaveBeenCalledTimes(4);
      await act(async () => {
        fail(new Error("Failed to fetch"));
      });
      expect(screen.getByTestId("bn-activity-chip")).toHaveAttribute("data-status", "running");
    });

    it("keeps the returning job to one read out when a dismissed job's read settles", async () => {
      let answer!: (s: NormalisedJobStatus) => void;
      const first = vi.fn(() => new Promise<NormalisedJobStatus>((r) => (answer = r)));
      const { rerender } = render(<ActivityChipStack jobs={[makeJob({ pollFn: first })]} onDismiss={vi.fn()} />);
      await act(async () => {});
      rerender(<ActivityChipStack jobs={[]} onDismiss={vi.fn()} />);
      const second = vi.fn(never);
      rerender(<ActivityChipStack jobs={[makeJob({ pollFn: second })]} onDismiss={vi.fn()} />);
      await act(async () => {});
      await act(async () => {
        answer({ status: "running", progressLabel: null, durationLabel: null, errorMessage: null, partialMessage: null });
      });
      await act(async () => {
        vi.advanceTimersByTime(4000);
      });
      expect(second).toHaveBeenCalledTimes(1);
    });

    it("says when a job thought lost really finishes, once", async () => {
      const onComplete = vi.fn();
      let up = false;
      const pollFn = vi.fn(() =>
        up
          ? Promise.resolve<NormalisedJobStatus>({ status: "completed", progressLabel: null, durationLabel: null, errorMessage: null, partialMessage: null })
          : Promise.reject(new Error("Failed to fetch")),
      );
      const { rerender } = render(<ActivityChipStack jobs={[makeJob({ pollFn, onComplete })]} onDismiss={vi.fn()} />);
      await act(async () => {});
      await endLost();
      expect(onComplete).toHaveBeenCalledTimes(1);
      up = true;
      rerender(<ActivityChipStack jobs={[makeJob({ pollFn, onComplete })]} onDismiss={vi.fn()} />);
      await act(async () => {});
      expect(screen.getByTestId("bn-activity-chip")).toHaveAttribute("data-status", "completed");
      expect(onComplete).toHaveBeenCalledTimes(2);
      rerender(<ActivityChipStack jobs={[makeJob({ pollFn, onComplete })]} onDismiss={vi.fn()} />);
      await act(async () => {});
      expect(onComplete).toHaveBeenCalledTimes(2);
    });

    it("counts a poll that throws rather than rejects as a failed poll", async () => {
      const pollFn = vi.fn((): Promise<NormalisedJobStatus> => {
        throw new Error("boom");
      });
      render(<ActivityChipStack jobs={[makeJob({ pollFn })]} onDismiss={vi.fn()} />);
      await act(async () => {});
      await endLost();
      expect(pollFn).toHaveBeenCalledTimes(5);
      expect(screen.getByTestId("bn-activity-chip")).toHaveAttribute("data-status", "failed");
    });

    it("drops a read that was still out when its job was dismissed", async () => {
      let answer!: (s: NormalisedJobStatus) => void;
      const first = vi.fn(() => new Promise<NormalisedJobStatus>((r) => (answer = r)));
      const { rerender } = render(<ActivityChipStack jobs={[makeJob({ pollFn: first })]} onDismiss={vi.fn()} />);
      await act(async () => {});
      rerender(<ActivityChipStack jobs={[]} onDismiss={vi.fn()} />);
      const second = vi.fn(never);
      rerender(<ActivityChipStack jobs={[makeJob({ pollFn: second })]} onDismiss={vi.fn()} />);
      await act(async () => {});
      expect(second).toHaveBeenCalledTimes(1);
      await act(async () => {
        answer({ status: "failed", progressLabel: null, durationLabel: null, errorMessage: null, partialMessage: null });
      });
      expect(screen.getByTestId("bn-activity-chip")).toHaveAttribute("data-status", "running");
    });
  });

  // RE#38: a window keeps its chips across a reload. A chip that had already finished comes back
  // carrying how it ended, and must neither ask again nor do its ending a second time (a Copy
  // Screens would copy again, an AutoCode failure would be posted to the shell again).
  describe("a chip that comes back already finished", () => {
    const finished: NormalisedJobStatus = {
      status: "completed", progressLabel: null, durationLabel: null, errorMessage: null, partialMessage: null,
    };

    it("shows how it ended, asks nothing and does not end again", async () => {
      const onComplete = vi.fn();
      const onSettled = vi.fn();
      const pollFn = vi.fn((): Promise<NormalisedJobStatus> => Promise.resolve({ ...finished, status: "running" }));
      render(
        <ActivityChipStack
          jobs={[makeJob({ id: "screens:1", pollFn, onComplete, outcome: finished })]}
          onDismiss={vi.fn()}
          onSettled={onSettled}
        />,
      );
      await act(async () => {});
      await act(async () => {
        vi.advanceTimersByTime(10_000);
      });
      expect(screen.getByTestId("bn-activity-chip")).toHaveAttribute("data-status", "completed");
      expect(pollFn).not.toHaveBeenCalled();
      expect(onComplete).not.toHaveBeenCalled();
      expect(onSettled).not.toHaveBeenCalled();
    });

    it("says how a chip ended, once, so the window can carry it", async () => {
      const onSettled = vi.fn();
      const pollFn = vi.fn(() => Promise.resolve(finished));
      render(<ActivityChipStack jobs={[makeJob({ id: "clips:1", pollFn })]} onDismiss={vi.fn()} onSettled={onSettled} />);
      await act(async () => {});
      await act(async () => {
        vi.advanceTimersByTime(4000);
      });
      expect(onSettled).toHaveBeenCalledTimes(1);
      expect(onSettled).toHaveBeenCalledWith("clips:1", finished);
    });

    it("tells the completion handler how the job ended, and records the ending after it settles", async () => {
      let finish!: () => void;
      const onComplete = vi.fn(() => new Promise<void>((r) => (finish = r)));
      const onSettled = vi.fn();
      const pollFn = vi.fn(() => Promise.resolve(finished));
      render(
        <ActivityChipStack jobs={[makeJob({ id: "screens:1", pollFn, onComplete })]} onDismiss={vi.fn()} onSettled={onSettled} />,
      );
      await act(async () => {});
      expect(onComplete).toHaveBeenCalledWith(finished);
      expect(onSettled).not.toHaveBeenCalled();
      await act(async () => finish());
      expect(onSettled).toHaveBeenCalledWith("screens:1", finished);
    });

    it("still records the ending when the completion handler throws", async () => {
      const err = vi.spyOn(console, "error").mockImplementation(() => {});
      const onSettled = vi.fn();
      const onComplete = vi.fn(() => {
        throw new Error("boom");
      });
      render(
        <ActivityChipStack
          jobs={[makeJob({ id: "clips:1", pollFn: () => Promise.resolve(finished), onComplete })]}
          onDismiss={vi.fn()}
          onSettled={onSettled}
        />,
      );
      await act(async () => {});
      expect(onSettled).toHaveBeenCalledWith("clips:1", finished);
      err.mockRestore();
    });

    it("does not carry a chip that ended only because nothing could be read", async () => {
      const onSettled = vi.fn();
      const pollFn = vi.fn(() => Promise.reject(new Error("Failed to fetch")));
      render(<ActivityChipStack jobs={[makeJob({ id: "clips:1", pollFn })]} onDismiss={vi.fn()} onSettled={onSettled} />);
      await act(async () => {});
      for (let i = 0; i < 5; i++) {
        await act(async () => {
          vi.advanceTimersByTime(2000);
        });
      }
      expect(screen.getByTestId("bn-activity-chip")).toHaveAttribute("data-status", "failed");
      expect(onSettled).not.toHaveBeenCalled();
    });
  });
});
