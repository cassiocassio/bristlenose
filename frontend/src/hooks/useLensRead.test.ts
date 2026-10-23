import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { HANDOVER_MS, RETRY_PAUSE_MS, handoverClass, useLensRead, type LensReadKind } from "./useLensRead";

// A read the test answers by hand, in any order.
function reads() {
  const pending: { resolve: (v: string) => void; reject: (e: unknown) => void }[] = [];
  const read = vi.fn(
    () => new Promise<string>((resolve, reject) => pending.push({ resolve, reject })),
  );
  return { read, pending };
}

const flush = () => act(async () => { await vi.advanceTimersByTimeAsync(0); });

function mount(read: () => Promise<string>, refreshKey = 0, key = "p1") {
  const apply = vi.fn<(v: string, kind: LensReadKind) => void>();
  const onError = vi.fn();
  const view = renderHook(
    ({ refreshKey, key }) => useLensRead({ read, apply, onError, refreshKey, key, label: "test read failed:" }),
    { initialProps: { refreshKey, key } },
  );
  return { apply, onError, view };
}

describe("useLensRead", () => {
  let logged: ReturnType<typeof vi.spyOn>;
  beforeEach(() => {
    vi.useFakeTimers();
    logged = vi.spyOn(console, "error").mockImplementation(() => {});
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  async function drawn(refreshKey = 0) {
    const r = reads();
    const m = mount(r.read, refreshKey);
    r.pending[0].resolve("old");
    await flush();
    expect(m.apply).toHaveBeenLastCalledWith("old", "first");
    return { ...r, ...m };
  }

  it("reads once on open, even when a run has already moved the key", async () => {
    const { read } = await drawn(3);
    expect(read).toHaveBeenCalledTimes(1);
  });

  it("a failed first read is the lens's to say", async () => {
    const r = reads();
    const m = mount(r.read);
    r.pending[0].reject(new Error("500"));
    await flush();
    expect(m.onError).toHaveBeenCalledWith(expect.any(Error), "first");
    expect(logged).toHaveBeenCalledWith("test read failed:", expect.any(Error));
  });

  it("nothing shows while a refresh is in flight, and a failed one changes nothing", async () => {
    const { pending, apply, onError, view } = await drawn();
    view.rerender({ refreshKey: 1, key: "p1" });
    await flush();
    expect(view.result.current.handingOver).toBe(false);
    pending[1].reject(new Error("busy"));
    await flush();
    expect(apply).toHaveBeenCalledTimes(1);
    expect(onError).not.toHaveBeenCalled();
    expect(view.result.current.handingOver).toBe(false);
    expect(logged).toHaveBeenCalledWith("test read failed:", expect.any(Error));
  });

  it("tries a failed refresh exactly once more, after the pause", async () => {
    const { read, pending, view } = await drawn();
    view.rerender({ refreshKey: 1, key: "p1" });
    pending[1].reject(new Error("busy"));
    await flush();
    await act(async () => { await vi.advanceTimersByTimeAsync(RETRY_PAUSE_MS - 1); });
    expect(read).toHaveBeenCalledTimes(2);
    await act(async () => { await vi.advanceTimersByTimeAsync(1); });
    expect(read).toHaveBeenCalledTimes(3);
  });

  it("swaps with the hand-over when the retry answers", async () => {
    const { pending, apply, view } = await drawn();
    view.rerender({ refreshKey: 1, key: "p1" });
    pending[1].reject(new Error("busy"));
    await flush();
    await act(async () => { await vi.advanceTimersByTimeAsync(RETRY_PAUSE_MS); });
    pending[2].resolve("new");
    await flush();
    expect(apply).toHaveBeenLastCalledWith("new", "refresh");
    expect(view.result.current.handingOver).toBe(true);
    await act(async () => { await vi.advanceTimersByTimeAsync(HANDOVER_MS); });
    expect(view.result.current.handingOver).toBe(false);
  });

  it("stops after the second failure: no third read", async () => {
    const { read, pending, apply, onError, view } = await drawn();
    view.rerender({ refreshKey: 1, key: "p1" });
    pending[1].reject(new Error("busy"));
    await flush();
    await act(async () => { await vi.advanceTimersByTimeAsync(RETRY_PAUSE_MS); });
    pending[2].reject(new Error("busy"));
    await act(async () => { await vi.advanceTimersByTimeAsync(RETRY_PAUSE_MS * 20); });
    expect(read).toHaveBeenCalledTimes(3);
    expect(apply).toHaveBeenCalledTimes(1);
    expect(onError).not.toHaveBeenCalled();
    expect(view.result.current.handingOver).toBe(false);
  });

  it("skips the retry when a newer run's read has started", async () => {
    const { read, pending, apply, view } = await drawn();
    view.rerender({ refreshKey: 1, key: "p1" });
    pending[1].reject(new Error("busy"));
    await flush();
    view.rerender({ refreshKey: 2, key: "p1" });
    await act(async () => { await vi.advanceTimersByTimeAsync(RETRY_PAUSE_MS * 2); });
    expect(read).toHaveBeenCalledTimes(3); // first, refresh 1, refresh 2: no retry of 1
    pending[2].resolve("newer");
    await flush();
    expect(apply).toHaveBeenLastCalledWith("newer", "refresh");
  });

  it("an older answer never overwrites a newer one", async () => {
    const { pending, apply, view } = await drawn();
    view.rerender({ refreshKey: 1, key: "p1" });
    view.rerender({ refreshKey: 2, key: "p1" });
    pending[2].resolve("newer");
    await flush();
    pending[1].resolve("older");
    await flush();
    expect(apply).toHaveBeenLastCalledWith("newer", "refresh");
    expect(apply).toHaveBeenCalledTimes(2);
  });

  it("a first read still pending is not dropped because a refresh started and failed", async () => {
    const r = reads();
    const m = mount(r.read);
    m.view.rerender({ refreshKey: 1, key: "p1" });
    r.pending[1].reject(new Error("busy"));
    await flush();
    r.pending[0].resolve("first");
    await flush();
    expect(m.apply).toHaveBeenCalledWith("first", "first");
  });

  it("sets aside every answer from before the key changed", async () => {
    const { pending, apply, view } = await drawn();
    view.rerender({ refreshKey: 1, key: "p1" });
    view.rerender({ refreshKey: 1, key: "p2" });
    pending[1].resolve("from p1");
    await flush();
    expect(apply).not.toHaveBeenCalledWith("from p1", expect.anything());
    pending[2].resolve("p2");
    await flush();
    expect(apply).toHaveBeenLastCalledWith("p2", "first");
  });

  it("no hand-over when nothing was drawn before", async () => {
    const r = reads();
    const m = mount(r.read);
    r.pending[0].reject(new Error("500"));
    await flush();
    m.view.rerender({ refreshKey: 1, key: "p1" });
    r.pending[1].resolve("now");
    await flush();
    expect(m.apply).toHaveBeenCalledWith("now", "refresh");
    expect(m.view.result.current.handingOver).toBe(false);
  });

  it("a reload is not retried and is the lens's to hear", async () => {
    const { read, pending, onError, view } = await drawn();
    act(() => view.result.current.reload());
    pending[1].reject(new Error("busy"));
    await act(async () => { await vi.advanceTimersByTimeAsync(RETRY_PAUSE_MS * 2); });
    expect(read).toHaveBeenCalledTimes(2);
    expect(onError).toHaveBeenCalledWith(expect.any(Error), "reload");
  });

  it("a read that throws before its promise fails like a rejected one", async () => {
    const m = mount(() => { throw new Error("no fetch"); });
    await flush();
    expect(m.onError).toHaveBeenCalledWith(expect.any(Error), "first");
  });

  it("a first answer the lens cannot take is a failed read, not a lens left loading", async () => {
    const r = reads();
    const m = mount(r.read);
    m.apply.mockImplementationOnce(() => { throw new TypeError("no sections"); });
    r.pending[0].resolve("odd body");
    await flush();
    expect(m.onError).toHaveBeenCalledWith(expect.any(TypeError), "first");
    // Nothing was drawn, so the next good answer is not a hand-over.
    m.view.rerender({ refreshKey: 1, key: "p1" });
    r.pending[1].resolve("good");
    await flush();
    expect(m.apply).toHaveBeenLastCalledWith("good", "refresh");
    expect(m.view.result.current.handingOver).toBe(false);
  });

  it("unmounting cancels a pending retry", async () => {
    const { read, pending, view } = await drawn();
    view.rerender({ refreshKey: 1, key: "p1" });
    pending[1].reject(new Error("busy"));
    await flush();
    view.unmount();
    await act(async () => { await vi.advanceTimersByTimeAsync(RETRY_PAUSE_MS * 2); });
    expect(read).toHaveBeenCalledTimes(2);
  });
});

describe("handoverClass", () => {
  it("adds the class only while handing over", () => {
    expect(handoverClass(false, "bn-dashboard")).toBe("bn-dashboard");
    expect(handoverClass(true, "bn-dashboard")).toBe("bn-dashboard bn-handover");
    expect(handoverClass(true)).toBe("bn-handover");
  });
});
