import { afterEach, describe, expect, it, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";
import {
  getSignalWorkingOpen,
  resetSignalWorkingStore,
  setSignalWorkingOpen,
  toggleSignalWorking,
  useSignalWorkingOpen,
} from "./SignalWorkingStore";

afterEach(() => resetSignalWorkingStore());

describe("SignalWorkingStore", () => {
  it("starts closed", () => {
    expect(getSignalWorkingOpen()).toBe(false);
  });

  it("toggles, and tells every subscribed reader once per change", () => {
    let renders = 0;
    const a = renderHook(() => { renders += 1; return useSignalWorkingOpen(); });
    const b = renderHook(() => useSignalWorkingOpen());
    const before = renders;
    act(() => toggleSignalWorking());
    expect(getSignalWorkingOpen()).toBe(true);
    // Both readers see it, and the first re-rendered once for the one change.
    expect(a.result.current).toBe(true);
    expect(b.result.current).toBe(true);
    expect(renders - before).toBe(1);
    act(() => toggleSignalWorking());
    expect(a.result.current).toBe(false);
    expect(b.result.current).toBe(false);
  });

  it("does nothing when asked for the state it is already in", () => {
    const spy = vi.spyOn(Storage.prototype, "setItem");
    setSignalWorkingOpen(false);
    expect(spy).not.toHaveBeenCalled();
    spy.mockRestore();
  });

  it("remembers the choice in localStorage as a convenience", () => {
    setSignalWorkingOpen(true);
    expect(localStorage.getItem("bn-signal-working-open")).toBe("1");
  });

  it("still carries the state when storage throws", () => {
    const spy = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("denied");
    });
    setSignalWorkingOpen(true);
    expect(getSignalWorkingOpen()).toBe(true);
    spy.mockRestore();
  });
});
