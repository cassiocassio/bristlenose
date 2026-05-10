/**
 * RefreshButton — disabled state, spin during click, calls
 * triggerManualRefresh.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { RefreshButton } from "./RefreshButton";
import {
  resetLastRunStore,
  startLastRunPolling,
  stopLastRunPolling,
} from "../contexts/LastRunStore";

vi.mock("../utils/api", () => ({
  authHeaders: () => ({}),
}));

vi.mock("../utils/announce", () => ({
  announce: vi.fn(),
}));

vi.mock("../i18n", () => ({
  default: { t: (k: string) => k },
}));

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (k: string) => k }),
}));

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  resetLastRunStore();
  fetchMock = vi.fn();
  globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;
  Object.defineProperty(document, "visibilityState", {
    configurable: true,
    get: () => "visible",
  });
});

afterEach(() => {
  stopLastRunPolling();
});

describe("RefreshButton", () => {
  it("renders nothing when lastRun is null (no run yet)", () => {
    const { container } = render(<RefreshButton />);
    expect(screen.queryByTestId("bn-refresh-btn")).toBeNull();
    expect(container.firstChild).toBeNull();
  });

  it("enables once lastRun is populated, then triggers a refetch on click", async () => {
    fetchMock.mockResolvedValue({
      status: 200,
      ok: true,
      json: async () => ({
        run_id: "01J100",
        outcome: "completed",
        completed_at: "2026-05-09T12:00:00Z",
      }),
    });

    render(<RefreshButton />);

    await act(async () => {
      startLastRunPolling("1");
      await Promise.resolve();
      await Promise.resolve();
    });

    const btn = screen.getByTestId("bn-refresh-btn");
    await waitFor(() => expect(btn).not.toBeDisabled());

    fetchMock.mockClear();
    await act(async () => {
      fireEvent.click(btn);
    });

    // Manual refresh polls the endpoint again.
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/projects/1/last-run",
      expect.any(Object),
    );
  });

  it("ignores repeat clicks while a refresh is in flight", async () => {
    // Seed: resolved poll so lastRun !== null.
    fetchMock.mockResolvedValueOnce({
      status: 200,
      ok: true,
      json: async () => ({
        run_id: "01J100",
        outcome: "completed",
        completed_at: "2026-05-09T12:00:00Z",
      }),
    });

    render(<RefreshButton />);

    await act(async () => {
      startLastRunPolling("1");
      await Promise.resolve();
      await Promise.resolve();
    });

    const btn = screen.getByTestId("bn-refresh-btn");
    await waitFor(() => expect(btn).not.toBeDisabled());

    fetchMock.mockClear();

    // Click triggers a fetch we hold pending.
    let resolveFetch: ((v: unknown) => void) | undefined;
    fetchMock.mockImplementationOnce(
      () =>
        new Promise((res) => {
          resolveFetch = res;
        }),
    );
    fireEvent.click(btn);
    await waitFor(() => expect(btn).toBeDisabled());

    // Repeat clicks while spinning are no-ops.
    fireEvent.click(btn);
    fireEvent.click(btn);
    expect(fetchMock).toHaveBeenCalledTimes(1);

    await act(async () => {
      resolveFetch?.({
        status: 200,
        ok: true,
        json: async () => ({
          run_id: "01J100",
          outcome: "completed",
          completed_at: "2026-05-09T12:00:00Z",
        }),
      });
      await Promise.resolve();
    });

    await waitFor(() => expect(btn).not.toBeDisabled());
  });
});
