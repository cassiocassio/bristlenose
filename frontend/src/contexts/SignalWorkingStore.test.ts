import { afterEach, describe, expect, it, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";
import {
  getSignalWorkingOpen,
  resetSignalWorkingStore,
  setSignalWorkingOpen,
  toggleSignalWorking,
  useSignalWorkingOpen,
} from "./SignalWorkingStore";
import contractJson from "../../../tests/fixtures/report-prefs-contract.json";

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

  it("hands a change to the Mac app as a report preference", () => {
    // R89 extension, decision #182 (9 Nov 2026): one answer for every card, a reading mode, so the
    // Mac app keeps it past a relaunch. A bare localStorage write would be forgotten on quit.
    const w = window as unknown as Record<string, unknown>;
    const postMessage = vi.fn();
    w.webkit = { messageHandlers: { navigation: { postMessage } } };
    try {
      setSignalWorkingOpen(true);
      expect(postMessage).toHaveBeenCalledWith({ type: "report-pref", key: "bn-signal-working-open", value: "1" });
      setSignalWorkingOpen(false);
      expect(postMessage).toHaveBeenLastCalledWith({ type: "report-pref", key: "bn-signal-working-open", value: "0" });
      for (const [msg] of postMessage.mock.calls) {
        expect((msg.value as string).length).toBeLessThanOrEqual(contractJson.max_value_length);
      }
    } finally {
      delete w.webkit;
    }
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
