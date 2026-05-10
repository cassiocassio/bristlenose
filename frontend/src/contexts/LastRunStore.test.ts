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
  it("bumps refreshKey when first poll returns any terminus", async () => {
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
    expect(result.current.refreshKey).toBe(1);
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
    expect(result.current.refreshKey).toBe(1);

    // Advance to next poll tick.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3001);
      await Promise.resolve();
    });

    expect(result.current.refreshKey).toBe(1);
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
    expect(result.current.refreshKey).toBe(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3001);
      await Promise.resolve();
    });
    expect(result.current.refreshKey).toBe(2);
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
