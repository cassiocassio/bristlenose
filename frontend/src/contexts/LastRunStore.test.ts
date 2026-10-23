/**
 * LastRunStore tests — polling lifecycle, visibility pause, in-flight skip,
 * mount baseline, run_id-keyed comparison.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import {
  useLastRun,
  resetLastRunStore,
  startLastRunPolling,
  stopLastRunPolling,
  triggerManualRefresh,
} from "./LastRunStore";

// authHeaders is read inside fetch — mock to a no-op map.
vi.mock("../utils/api", () => ({
  authHeaders: () => ({}),
}));

// announce → no-op (jsdom has no aria-live region).
const announceMock = vi.fn();
vi.mock("../utils/announce", () => ({
  announce: (msg: string) => announceMock(msg),
}));

// i18n.t passthrough — return the key for assertion clarity.
vi.mock("../i18n", () => ({
  default: { t: (k: string) => k },
}));

type FetchResponse = {
  status: number;
  ok: boolean;
  json: () => Promise<unknown>;
};

function makeResponse(body: unknown, status = 200): FetchResponse {
  return {
    status,
    ok: status >= 200 && status < 300,
    json: async () => body,
  };
}

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  resetLastRunStore();
  announceMock.mockClear();
  fetchMock = vi.fn();
  globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;
  // Default visibility: visible.
  Object.defineProperty(document, "visibilityState", {
    configurable: true,
    get: () => "visible",
  });
});

afterEach(() => {
  stopLastRunPolling();
  vi.useRealTimers();
});

describe("LastRunStore — initial state", () => {
  it("starts with null lastRun and refreshKey 0", () => {
    const { result } = renderHook(() => useLastRun());
    expect(result.current.lastRun).toBeNull();
    expect(result.current.refreshKey).toBe(0);
  });
});

describe("LastRunStore — first poll baseline", () => {
  it("records the first poll's run without bumping: the lenses have just read it", async () => {
    fetchMock.mockResolvedValueOnce(
      makeResponse({
        run_id: "01J123",
        outcome: "completed",
        completed_at: "2026-05-09T12:00:00Z",
      }),
    );
    const { result } = renderHook(() => useLastRun());

    await act(async () => {
      startLastRunPolling("1");
      // Allow the first poll's microtask + state set.
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/projects/1/last-run",
      expect.any(Object),
    );
    expect(result.current.lastRun?.run_id).toBe("01J123");
    expect(result.current.refreshKey).toBe(0);
  });

  it("leaves state untouched when first poll returns null", async () => {
    fetchMock.mockResolvedValueOnce(makeResponse(null));
    const { result } = renderHook(() => useLastRun());

    await act(async () => {
      startLastRunPolling("1");
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(result.current.lastRun).toBeNull();
    expect(result.current.refreshKey).toBe(0);
  });

  const run = { run_id: "01J123", outcome: "completed", completed_at: "2026-05-09T12:00:00Z" };

  it("bumps for a run that completes after a first poll that found none", async () => {
    fetchMock.mockResolvedValueOnce(makeResponse(null)).mockResolvedValueOnce(makeResponse(run));
    const { result } = renderHook(() => useLastRun());
    vi.useFakeTimers();
    await act(async () => {
      startLastRunPolling("1");
      await Promise.resolve();
      await Promise.resolve();
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3001);
    });
    expect(result.current.lastRun?.run_id).toBe("01J123");
    expect(result.current.refreshKey).toBe(1);
  });

  // Hidden at open is the one exception (owner's ruling, 23 Oct 2026): the run may have finished
  // while hidden, after the lenses read, so the first answer once shown bumps.
  it("bumps when the first answer comes later because the page was hidden at open", async () => {
    let hidden = true;
    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      get: () => (hidden ? "hidden" : "visible"),
    });
    fetchMock.mockResolvedValue(makeResponse(run));
    const { result } = renderHook(() => useLastRun());
    await act(async () => {
      startLastRunPolling("1");
      await Promise.resolve();
    });
    expect(fetchMock).not.toHaveBeenCalled();
    hidden = false;
    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(result.current.lastRun?.run_id).toBe("01J123");
    expect(result.current.refreshKey).toBe(1);
  });

  it("leaves the baseline to the next answer when the open-time poll fails", async () => {
    fetchMock.mockRejectedValueOnce(new Error("network down")).mockResolvedValueOnce(makeResponse(run));
    const { result } = renderHook(() => useLastRun());
    vi.useFakeTimers();
    await act(async () => {
      startLastRunPolling("1");
      await Promise.resolve();
      await Promise.resolve();
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3001);
    });
    expect(result.current.lastRun?.run_id).toBe("01J123");
    expect(result.current.refreshKey).toBe(0);
  });

  // The baseline is state, not a property of the open-time call: a switch that lands while the old
  // project's poll is in flight skips that call, and must still not bump for the new project.
  it("keeps the new project's baseline when the switch lands during the old project's poll", async () => {
    let answerOld!: (r: FetchResponse) => void;
    fetchMock
      .mockReturnValueOnce(new Promise<FetchResponse>((r) => (answerOld = r)))
      .mockResolvedValueOnce(makeResponse({ ...run, run_id: "01J900" }));
    const { result } = renderHook(() => useLastRun());
    vi.useFakeTimers();
    await act(async () => {
      startLastRunPolling("1");
      await Promise.resolve();
    });
    await act(async () => {
      startLastRunPolling("2"); // project 1's poll is still in flight: this one is skipped
      answerOld(makeResponse(run)); // and project 1's answer is discarded
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3001);
    });
    expect(fetchMock).toHaveBeenLastCalledWith("/api/projects/2/last-run", expect.any(Object));
    expect(result.current.lastRun?.run_id).toBe("01J900");
    expect(result.current.refreshKey).toBe(0);
  });
});

describe("LastRunStore — run_id is the comparison key", () => {
  it("does not bump refreshKey when run_id is unchanged", async () => {
    const sameRun = {
      run_id: "01J123",
      outcome: "completed",
      completed_at: "2026-05-09T12:00:00Z",
    };
    // First poll returns the run; second poll returns same run with a
    // different completed_at (server clock skew, replayed event, etc.).
    fetchMock
      .mockResolvedValueOnce(makeResponse(sameRun))
      .mockResolvedValueOnce(
        makeResponse({ ...sameRun, completed_at: "2026-05-09T12:01:00Z" }),
      );

    const { result } = renderHook(() => useLastRun());
    vi.useFakeTimers();

    await act(async () => {
      startLastRunPolling("1");
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(result.current.refreshKey).toBe(0);

    // Advance to next poll tick.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3001);
      await Promise.resolve();
    });

    expect(result.current.refreshKey).toBe(0);
    expect(result.current.lastRun?.run_id).toBe("01J123");
  });

  it("bumps refreshKey when run_id changes", async () => {
    fetchMock
      .mockResolvedValueOnce(
        makeResponse({
          run_id: "01J100",
          outcome: "completed",
          completed_at: "2026-05-09T12:00:00Z",
        }),
      )
      .mockResolvedValueOnce(
        makeResponse({
          run_id: "01J200",
          outcome: "completed",
          completed_at: "2026-05-09T12:05:00Z",
        }),
      );

    const { result } = renderHook(() => useLastRun());
    vi.useFakeTimers();

    await act(async () => {
      startLastRunPolling("1");
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(result.current.refreshKey).toBe(0);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3001);
      await Promise.resolve();
    });
    expect(result.current.refreshKey).toBe(1);
    expect(result.current.lastRun?.run_id).toBe("01J200");
  });
});

describe("LastRunStore — announce on completion", () => {
  it("does NOT announce on the first poll (could be startup seed)", async () => {
    fetchMock.mockResolvedValueOnce(
      makeResponse({
        run_id: "01J100",
        outcome: "completed",
        completed_at: "2026-05-09T12:00:00Z",
      }),
    );
    renderHook(() => useLastRun());
    await act(async () => {
      startLastRunPolling("1");
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(announceMock).not.toHaveBeenCalled();
  });

  it("announces on transitions from one run_id to another", async () => {
    fetchMock
      .mockResolvedValueOnce(
        makeResponse({
          run_id: "01J100",
          outcome: "completed",
          completed_at: "2026-05-09T12:00:00Z",
        }),
      )
      .mockResolvedValueOnce(
        makeResponse({
          run_id: "01J200",
          outcome: "completed",
          completed_at: "2026-05-09T12:05:00Z",
        }),
      );
    renderHook(() => useLastRun());
    vi.useFakeTimers();

    await act(async () => {
      startLastRunPolling("1");
      await Promise.resolve();
      await Promise.resolve();
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3001);
      await Promise.resolve();
    });

    expect(announceMock).toHaveBeenCalledTimes(1);
    expect(announceMock).toHaveBeenCalledWith("announce.pipelineCompleted");
  });
});

describe("LastRunStore — error handling", () => {
  it("treats 401 as silent back-off (no state change)", async () => {
    fetchMock.mockResolvedValueOnce(makeResponse(null, 401));
    const { result } = renderHook(() => useLastRun());

    await act(async () => {
      startLastRunPolling("1");
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(result.current.lastRun).toBeNull();
    expect(result.current.refreshKey).toBe(0);
  });

  it("swallows network errors silently", async () => {
    fetchMock.mockRejectedValueOnce(new Error("network down"));
    const { result } = renderHook(() => useLastRun());

    await act(async () => {
      startLastRunPolling("1");
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(result.current.lastRun).toBeNull();
  });
});

describe("LastRunStore — visibility pause", () => {
  it("does not poll when document is hidden", async () => {
    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      get: () => "hidden",
    });

    const { result } = renderHook(() => useLastRun());
    await act(async () => {
      startLastRunPolling("1");
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(fetchMock).not.toHaveBeenCalled();
    expect(result.current.refreshKey).toBe(0);
  });
});

describe("LastRunStore — triggerManualRefresh", () => {
  it("is a no-op when no project is active", async () => {
    const { result } = renderHook(() => useLastRun());
    await act(async () => {
      await triggerManualRefresh();
    });
    expect(result.current.refreshKey).toBe(0);
    expect(fetchMock).not.toHaveBeenCalled();
    expect(announceMock).not.toHaveBeenCalled();
  });

  it("bumps refreshKey synchronously and announces after poll", async () => {
    fetchMock.mockResolvedValue(
      makeResponse({
        run_id: "01J100",
        outcome: "completed",
        completed_at: "2026-05-09T12:00:00Z",
      }),
    );
    const { result } = renderHook(() => useLastRun());

    // Seed via initial poll.
    await act(async () => {
      startLastRunPolling("1");
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(result.current.refreshKey).toBe(0);
    announceMock.mockClear();

    await act(async () => {
      await triggerManualRefresh();
    });

    // Bump even though server returned same run_id.
    expect(result.current.refreshKey).toBe(1);
    expect(announceMock).toHaveBeenCalledWith("announce.pipelineCompleted");
  });

  it("does NOT double-announce when pollOnce catches a new run mid-click", async () => {
    fetchMock
      .mockResolvedValueOnce(
        makeResponse({
          run_id: "01J100",
          outcome: "completed",
          completed_at: "2026-05-09T12:00:00Z",
        }),
      )
      .mockResolvedValueOnce(
        makeResponse({
          run_id: "01J200",
          outcome: "completed",
          completed_at: "2026-05-09T12:05:00Z",
        }),
      );

    renderHook(() => useLastRun());
    await act(async () => {
      startLastRunPolling("1");
      await Promise.resolve();
      await Promise.resolve();
    });
    announceMock.mockClear();

    await act(async () => {
      await triggerManualRefresh();
    });

    // pollOnce already announced the transition; manual must not duplicate it.
    expect(announceMock).toHaveBeenCalledTimes(1);
  });
});

describe("LastRunStore — project switching", () => {
  it("resets state when activeProjectId changes", async () => {
    fetchMock.mockResolvedValueOnce(
      makeResponse({
        run_id: "01J100",
        outcome: "completed",
        completed_at: "2026-05-09T12:00:00Z",
      }),
    );
    fetchMock.mockResolvedValueOnce(makeResponse(null));

    const { result } = renderHook(() => useLastRun());

    await act(async () => {
      startLastRunPolling("1");
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(result.current.lastRun?.run_id).toBe("01J100");

    await act(async () => {
      startLastRunPolling("2");
      await Promise.resolve();
      await Promise.resolve();
    });

    // State reset on project switch (lastRun cleared); refreshKey
    // preserved since it's a monotonic bump counter.
    expect(result.current.lastRun).toBeNull();
  });
});
