import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../utils/api", () => ({ apiGet: vi.fn() }));

import { apiGet } from "../../utils/api";
import { _resetExportCache } from "../../utils/exportData";
import { bumpRefreshKey } from "../../contexts/LastRunStore";
import {
  markScreensFound,
  resetScreensAvailability,
  screensAvailable,
  STATUS_POLL_LIMIT,
  STATUS_POLL_MS,
  useScreensAvailable,
  type ScreensStatus,
} from "./availability";

const base: ScreensStatus = {
  enabled: true, unavailable: null, running: false, done: 3, total: 3,
  seconds_done: 0, seconds_total: 0, rate: null, has_screens: false,
};

const statusCalls = () => vi.mocked(apiGet).mock.calls.filter(([p]) => p === "/screens/status").length;

beforeEach(() => {
  vi.clearAllMocks();
  resetScreensAvailability();
});

afterEach(() => {
  vi.useRealTimers();
  delete (window as unknown as Record<string, unknown>).BRISTLENOSE_EXPORT;
  _resetExportCache();
});

describe("the rule is the server's", () => {
  it("offers the lens when the server says available, and only then", () => {
    expect(screensAvailable({ ...base, available: true })).toBe(true);
    expect(screensAvailable({ ...base, available: false })).toBe(false);
    expect(screensAvailable(null)).toBe(false);
  });

  it("never re-derives it from the parts", () => {
    // Screens found, or still reading, but the server said no: no lens (screens.py decides).
    expect(screensAvailable({ ...base, has_screens: true, available: false })).toBe(false);
    expect(screensAvailable({ ...base, running: true, done: 0, available: false })).toBe(false);
    // An older server says nothing: absent is not a yes.
    expect(screensAvailable({ ...base, has_screens: true })).toBe(false);
  });
});

describe("useScreensAvailable", () => {
  it("reads the status on mount", async () => {
    vi.mocked(apiGet).mockResolvedValue({ ...base, has_screens: true, available: true });
    const { result } = renderHook(() => useScreensAvailable());
    expect(result.current).toBe(false);
    await act(async () => {});
    expect(result.current).toBe(true);
    expect(statusCalls()).toBe(1);
  });

  it("looks again on a gentle interval while reading, and stops once reading is done", async () => {
    vi.useFakeTimers();
    let n = 0;
    vi.mocked(apiGet).mockImplementation((() => {
      n += 1;
      // Reading for two looks, then done with screens found.
      return Promise.resolve(n < 3 ? { ...base, running: true, done: n - 1, available: true } : { ...base, has_screens: true, available: true });
    }) as typeof apiGet);
    const { result } = renderHook(() => useScreensAvailable());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(statusCalls()).toBe(1);
    expect(result.current).toBe(true); // reading: offered already
    await act(async () => {
      await vi.advanceTimersByTimeAsync(STATUS_POLL_MS * 10);
    });
    expect(statusCalls()).toBe(3);
    expect(result.current).toBe(true);
  });

  it("does not poll when nothing is being read", async () => {
    vi.useFakeTimers();
    vi.mocked(apiGet).mockResolvedValue(base);
    const { result } = renderHook(() => useScreensAvailable());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(STATUS_POLL_MS * 20);
    });
    expect(statusCalls()).toBe(1);
    expect(result.current).toBe(false);
  });

  it("gives up after a bounded number of looks", async () => {
    vi.useFakeTimers();
    vi.mocked(apiGet).mockResolvedValue({ ...base, running: true });
    renderHook(() => useScreensAvailable());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(STATUS_POLL_MS * (STATUS_POLL_LIMIT + 50));
    });
    expect(statusCalls()).toBe(STATUS_POLL_LIMIT);
  });

  it("looks again when a run finishes", async () => {
    vi.mocked(apiGet).mockResolvedValue(base);
    const { result } = renderHook(() => useScreensAvailable());
    await act(async () => {});
    expect(result.current).toBe(false);
    vi.mocked(apiGet).mockResolvedValue({ ...base, has_screens: true, available: true });
    await act(async () => {
      bumpRefreshKey();
    });
    expect(statusCalls()).toBe(2);
    expect(result.current).toBe(true);
  });

  it("follows the lens when it finds screens on its own read", async () => {
    vi.mocked(apiGet).mockResolvedValue(base);
    const { result } = renderHook(() => useScreensAvailable());
    await act(async () => {});
    expect(result.current).toBe(false);
    act(() => markScreensFound());
    expect(result.current).toBe(true);
  });

  it("asks nothing and offers nothing in an exported report", async () => {
    (window as unknown as Record<string, unknown>).BRISTLENOSE_EXPORT = {
      version: 1, exported_at: "2026-10-14T00:00:00Z", health: {}, endpoints: {},
    };
    _resetExportCache();
    vi.mocked(apiGet).mockResolvedValue({ ...base, has_screens: true, available: true });
    const { result } = renderHook(() => useScreensAvailable());
    await act(async () => {});
    act(() => markScreensFound());
    expect(statusCalls()).toBe(0);
    expect(result.current).toBe(false);
  });
});
