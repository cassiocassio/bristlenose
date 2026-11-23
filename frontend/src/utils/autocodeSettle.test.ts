import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./api", () => ({ getAutoCodeStatus: vi.fn() }));

import { getAutoCodeStatus } from "./api";
import { waitForStoppedRunToSettle } from "./autocodeSettle";

const status = vi.mocked(getAutoCodeStatus);

function answer(ending: boolean | undefined) {
  return { status: "cancelled", ending } as unknown as Awaited<ReturnType<typeof getAutoCodeStatus>>;
}

describe("waitForStoppedRunToSettle", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("waits while the stopped run is still ending, and resolves once it has ended", async () => {
    status
      .mockResolvedValueOnce(answer(true))
      .mockResolvedValueOnce(answer(true))
      .mockResolvedValueOnce(answer(false));
    let done = false;
    const wait = waitForStoppedRunToSettle("garrett", { pollMs: 100, limitMs: 10_000 }).then(() => {
      done = true;
    });
    await vi.advanceTimersByTimeAsync(0);
    expect(done).toBe(false);
    await vi.advanceTimersByTimeAsync(100);
    expect(done).toBe(false);
    await vi.advanceTimersByTimeAsync(100);
    await wait;
    expect(done).toBe(true);
    expect(status).toHaveBeenCalledTimes(3);
    expect(status).toHaveBeenCalledWith("garrett");
  });

  it("does not wait for a run that has already ended, or a server that does not say", async () => {
    status.mockResolvedValueOnce(answer(undefined));
    await waitForStoppedRunToSettle("garrett");
    expect(status).toHaveBeenCalledTimes(1);
  });

  it("gives up at its limit, and when the status cannot be read", async () => {
    status.mockResolvedValue(answer(true));
    const wait = waitForStoppedRunToSettle("garrett", { pollMs: 100, limitMs: 250 });
    await vi.advanceTimersByTimeAsync(1000);
    await wait;
    expect(status.mock.calls.length).toBeLessThanOrEqual(4);

    status.mockReset();
    status.mockRejectedValueOnce(new Error("offline"));
    await waitForStoppedRunToSettle("garrett");
    expect(status).toHaveBeenCalledTimes(1);
  });
});
