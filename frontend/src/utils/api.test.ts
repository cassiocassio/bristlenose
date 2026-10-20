import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { patchStarred, patchTags, putFrameworkStates, sendPut } from "./api";
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

/**
 * A curation write names one gesture's change, and writes to one path go out
 * one at a time. Sent together, a star and its unstar (or an act and its ⌘Z)
 * reached the server's threadpool together and could commit the wrong way
 * round, leaving the server opposite to the screen (R4).
 */
describe("curation writes", () => {
  /** A fetch that answers only when told to. */
  function held(): Array<(r: Response) => void> {
    const answers: Array<(r: Response) => void> = [];
    fetchMock.mockImplementation(
      () => new Promise<Response>((resolve) => answers.push(resolve)),
    );
    return answers;
  }
  const settle = () => new Promise((r) => setTimeout(r, 0));

  it("sends a PATCH carrying only the change", async () => {
    fetchMock.mockResolvedValue(answer(200, { status: "ok" }));
    await patchTags({ "q-p1-10": { add: ["x"] } });
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(/\/tags$/);
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(String(init.body))).toEqual({ "q-p1-10": { add: ["x"] } });
  });

  it("holds a second write to the same path until the first has landed", async () => {
    const answers = held();
    const first = patchStarred({ "q-p1-10": true });
    const second = patchStarred({ "q-p1-10": false });
    await settle();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    answers[0](answer(200, { status: "ok" }));
    await first;
    await settle();
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(JSON.parse(String((fetchMock.mock.calls[1][1] as RequestInit).body))).toEqual({
      "q-p1-10": false,
    });
    answers[1](answer(200, { status: "ok" }));
    await second;
  });

  it("sends the next write after one that failed", async () => {
    const answers = held();
    const first = patchStarred({ "q-p1-10": true });
    const second = patchStarred({ "q-p1-26": true });
    await settle();
    answers[0](answer(500, { detail: "boom" }));
    await expect(first).rejects.toThrow();
    await settle();
    expect(fetchMock).toHaveBeenCalledTimes(2);
    answers[1](answer(200, { status: "ok" }));
    await expect(second).resolves.toBeUndefined();
  });

  it("does not hold a write to another path", async () => {
    const answers = held();
    void patchStarred({ "q-p1-10": true });
    void patchTags({ "q-p1-10": { add: ["x"] } });
    await settle();
    expect(fetchMock).toHaveBeenCalledTimes(2);
    for (const a of answers) a(answer(200, { status: "ok" }));
  });
});
