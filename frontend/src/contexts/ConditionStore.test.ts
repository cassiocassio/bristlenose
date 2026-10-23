/**
 * ConditionStore — the refresh key and lens readiness during a run
 * (docs/design-progressive-lenses.md §3.2, Phase 0 steps 2–3).
 */

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";
import {
  ALL_LENSES,
  resetConditionStore,
  startConditionPolling,
  useLenses,
} from "./ConditionStore";
import { resetLastRunStore, useLastRun } from "./LastRunStore";
import { toast } from "../utils/toast";

vi.mock("../utils/api", () => ({ authHeaders: () => ({}) }));
vi.mock("../utils/announce", () => ({ announce: vi.fn() }));
vi.mock("../utils/toast", () => ({ toast: vi.fn() }));
vi.mock("../i18n", () => ({ default: { t: (k: string) => k } }));

const posted: unknown[] = [];
vi.mock("../shims/bridge", () => ({
  postLensAvailability: (lenses: unknown) => posted.push(lenses),
}));

function respond(body: unknown, status = 200) {
  return { status, ok: status >= 200 && status < 300, json: async () => body };
}

let fetchMock: ReturnType<typeof vi.fn>;

async function tick(ms = 3000) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

beforeEach(() => {
  vi.useFakeTimers();
  resetConditionStore();
  resetLastRunStore();
  posted.length = 0;
  fetchMock = vi.fn();
  globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;
});

afterEach(() => {
  resetConditionStore();
  vi.useRealTimers();
});

describe("ConditionStore — refresh key", () => {
  it("records the first version without refetching", async () => {
    fetchMock.mockResolvedValue(respond({ data_version: 4, lenses: ALL_LENSES }));
    const { result } = renderHook(() => useLastRun());
    startConditionPolling("1");
    await tick(0);
    expect(result.current.refreshKey).toBe(0);
  });

  it("bumps the refresh key when the version moves, once per move", async () => {
    fetchMock
      .mockResolvedValueOnce(respond({ data_version: 1, lenses: ALL_LENSES }))
      .mockResolvedValueOnce(respond({ data_version: 2, lenses: ALL_LENSES }))
      .mockResolvedValueOnce(respond({ data_version: 2, lenses: ALL_LENSES }));
    const { result } = renderHook(() => useLastRun());
    startConditionPolling("1");
    await tick(0);
    await tick();
    expect(result.current.refreshKey).toBe(1);
    await tick();
    expect(result.current.refreshKey).toBe(1);
  });

  it("is silent on 401 and keeps its state", async () => {
    fetchMock.mockResolvedValue(respond(null, 401));
    const { result } = renderHook(() => useLenses());
    startConditionPolling("1");
    await tick(0);
    expect(result.current).toEqual(ALL_LENSES);
    expect(posted).toEqual([]);
    // A page left open across a serve restart: its next write says to reload, the poll says nothing (R87).
    expect(vi.mocked(toast)).not.toHaveBeenCalled();
  });
});

describe("ConditionStore — lens readiness", () => {
  it("posts the lenses to the host on the first poll and on each change only", async () => {
    const sessionsOnly = { ...ALL_LENSES, project: false, quotes: false, codebook: false, signals: false, discussion: false };
    const withQuotes = { ...sessionsOnly, quotes: true };
    fetchMock
      .mockResolvedValueOnce(respond({ data_version: 0, lenses: sessionsOnly }))
      .mockResolvedValueOnce(respond({ data_version: 0, lenses: sessionsOnly }))
      .mockResolvedValueOnce(respond({ data_version: 1, lenses: withQuotes }));
    const { result } = renderHook(() => useLenses());
    startConditionPolling("1");
    await tick(0);
    expect(result.current.quotes).toBe(false);
    await tick();
    expect(posted).toHaveLength(1);
    await tick();
    expect(result.current.quotes).toBe(true);
    expect(posted).toEqual([sessionsOnly, withQuotes]);
  });

  it("treats a lens the server does not name as available", async () => {
    fetchMock.mockResolvedValue(respond({ data_version: 0, lenses: { quotes: false } }));
    const { result } = renderHook(() => useLenses());
    startConditionPolling("1");
    await tick(0);
    expect(result.current).toEqual({ ...ALL_LENSES, quotes: false });
  });
});
