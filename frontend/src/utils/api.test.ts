import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  deleteCodebookTag,
  patchStarred,
  patchTags,
  putFrameworkStates,
  sendPut,
  toastSaveFailed,
  updateCodebookTag,
} from "./api";
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

  it("a failed write says so once", async () => {
    fetchMock.mockResolvedValue(answer(500, { detail: "boom" }));
    await expect(patchStarred({ "q-p1-10": true })).rejects.toThrow();
    await settle();
    expect(said()).not.toMatch(/connection/i);
  });

  it("a write that never answers fails, so the next one is sent", async () => {
    vi.useFakeTimers();
    try {
      fetchMock.mockImplementation((_url: string, init: RequestInit) => new Promise((_, reject) => {
        init.signal?.addEventListener("abort", () => reject(new DOMException("timed out", "TimeoutError")));
      }));
      const first = patchStarred({ "q-p1-10": true });
      const second = patchStarred({ "q-p1-26": true });
      const firstFailed = expect(first).rejects.toThrow();
      await vi.advanceTimersByTimeAsync(30_000);
      await firstFailed;
      expect(fetchMock).toHaveBeenCalledTimes(2);
      const secondFailed = expect(second).rejects.toThrow();
      await vi.advanceTimersByTimeAsync(30_000);
      await secondFailed; // and leaves the queue free for the next test
    } finally {
      vi.useRealTimers();
    }
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

/**
 * A codebook edit refused by the server says it was refused, not that the
 * connection failed: the error carries the server's status, which is what
 * `toastSaveFailed` reads (R6). PATCH and DELETE threw a bare Error.
 */
describe("a codebook write's error carries the server's answer", () => {
  it("a refused rename", async () => {
    fetchMock.mockResolvedValue(answer(409, { detail: "Tag name already exists" }));
    const err = await updateCodebookTag(1, { name: "Taken" }).catch((e: unknown) => e);
    expect((err as { status?: number }).status).toBe(409);
    toastSaveFailed(err);
    expect(said()).not.toMatch(/connection/i);
  });

  it("a refused delete", async () => {
    fetchMock.mockResolvedValue(answer(500, { detail: "boom" }));
    const err = await deleteCodebookTag(1).catch((e: unknown) => e);
    expect((err as { status?: number }).status).toBe(500);
  });
});

/**
 * A curation write naming a quote the server no longer has (a re-run removed
 * it) wrote nothing for it. The server names it back, and the write is refused
 * for that quote, so the store can take the change back instead of drawing it.
 */
describe("a curation write that the server could not place", () => {
  it("is refused, names the quotes, and says so once", async () => {
    fetchMock.mockResolvedValue(answer(200, { status: "ok", unresolved: ["q-p9-1"] }));
    const err = await patchStarred({ "q-p9-1": true, "q-p1-10": true }).catch((e: unknown) => e);
    expect((err as { unresolved?: string[] }).unresolved).toEqual(["q-p9-1"]);
    expect(said()).not.toMatch(/connection/i);
  });

  it("resolves when the server placed everything", async () => {
    fetchMock.mockResolvedValue(answer(200, { status: "ok", unresolved: [] }));
    await expect(patchStarred({ "q-p1-10": true })).resolves.toBeUndefined();
    expect(toastMock).not.toHaveBeenCalled();
  });
});
