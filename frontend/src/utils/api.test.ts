import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { putFrameworkStates, sendPut } from "./api";
import { toast } from "./toast";

vi.mock("./toast", () => ({ toast: vi.fn() }));

const toastMock = vi.mocked(toast);
const fetchMock = vi.fn();

function answer(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status, headers: { "Content-Type": "application/json" },
  });
}

/** The one toast a failed write raised. */
function said(): string {
  expect(toastMock).toHaveBeenCalledTimes(1);
  return String(toastMock.mock.calls[0][0]);
}

beforeEach(() => {
  toastMock.mockReset();
  fetchMock.mockReset();
  globalThis.fetch = fetchMock as unknown as typeof fetch;
  vi.spyOn(console, "error").mockImplementation(() => undefined);
});

afterEach(() => {
  vi.restoreAllMocks();
});

/**
 * A failed write says why it failed. Every failure used to say "check your
 * connection", including the server refusing a write while an analysis runs —
 * which sent a researcher naming themselves mid-run off to check their Wi-Fi
 * (14 Oct 2026).
 */
describe("sendPut — what a failed write says", () => {
  it("blames the connection only when the request never reached the server", async () => {
    fetchMock.mockRejectedValue(new TypeError("Load failed"));
    await expect(sendPut("/x", {})).rejects.toThrow();
    expect(said()).toMatch(/connection/i);
  });

  it("names a running analysis when the server says so", async () => {
    fetchMock.mockResolvedValue(
      answer(409, { detail: "An analysis is running", reason: "run_in_progress" }),
    );
    await expect(sendPut("/x", {})).rejects.toThrow();
    const message = said();
    expect(message).toMatch(/analysis/i);
    expect(message).not.toMatch(/connection/i);
  });

  it("does not blame the connection for any other refusal", async () => {
    fetchMock.mockResolvedValue(answer(500, { detail: "boom" }));
    await expect(sendPut("/x", {})).rejects.toThrow();
    const message = said();
    expect(message).not.toMatch(/connection/i);
    expect(message).not.toMatch(/analysis/i);
  });

  it("keeps the server's reason on the error it rejects with", async () => {
    fetchMock.mockResolvedValue(answer(409, { detail: "x", reason: "run_in_progress" }));
    await expect(sendPut("/x", {})).rejects.toMatchObject({ status: 409, reason: "run_in_progress" });
  });
});

describe("putFrameworkStates — the same rule", () => {
  it("does not blame the connection for a server refusal", async () => {
    fetchMock.mockResolvedValue(answer(500, { detail: "boom" }));
    await expect(putFrameworkStates({})).resolves.toEqual({ status: "error", catchUp: [] });
    expect(said()).not.toMatch(/connection/i);
  });
});
