import { render, screen } from "@testing-library/react";
import { Suspense } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// React holds a revealed lazy component back until 300 ms after its fallback was committed
// (FALLBACK_THROTTLE_MS), so a lens whose chunk arrives in 10 ms still took 280 ms on the first
// visit (measured 4 Nov 2026). The fix is to render the loaded component itself, which cannot
// suspend. (Choosing the component once per mount with useState is not pinned by a test: React
// reconciles a resolved lazy component in place, so re-choosing on every render left every test
// green. It is right by construction, not by proof.) These tests use a FRESH module each time, because a lazy that has already been
// rendered once is resolved and says nothing.

vi.mock("../hooks/useProjectId", () => ({ useProjectId: () => 1 }));
vi.mock("../contexts/LastRunStore", () => ({
  startLastRunPolling: () => {},
  useLastRun: () => ({ refreshKey: 0 }),
}));

function stubTable() {
  vi.doMock("../islands/SessionsTable", () => ({
    SessionsTable: () => <div data-testid="grid" />,
  }));
}

beforeEach(() => {
  vi.resetModules();
  stubTable();
});
afterEach(() => vi.doUnmock("../islands/SessionsTable"));

describe("SessionsTab first visit", () => {
  it("without the preload, a fresh lazy suspends: the fallback commits first", async () => {
    const { SessionsTab } = await import("./SessionsTab");
    render(
      <Suspense fallback={<i data-testid="fallback" />}>
        <SessionsTab />
      </Suspense>,
    );
    expect(screen.queryByTestId("fallback")).not.toBeNull(); // this is the 300 ms trap
    expect(await screen.findByTestId("grid")).toBeTruthy();
  });

  it("after the preload, the grid renders at once and no fallback is ever committed", async () => {
    const mod = await import("./SessionsTab");
    await mod.preloadSessionsTable();
    render(
      <Suspense fallback={<i data-testid="fallback" />}>
        <mod.SessionsTab />
      </Suspense>,
    );
    expect(screen.queryByTestId("fallback")).toBeNull();
    expect(screen.getByTestId("grid")).toBeTruthy();
  });

  it("a failed preload is harmless and leaves the lazy path working", async () => {
    vi.doMock("../islands/SessionsTable", () => {
      throw new Error("chunk failed to load");
    });
    const mod = await import("./SessionsTab");
    await expect(mod.preloadSessionsTable()).resolves.toBeUndefined();
    stubTable();
  });
});
