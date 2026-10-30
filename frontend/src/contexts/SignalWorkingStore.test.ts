import { afterEach, describe, expect, it, vi } from "vitest";
import {
  getSignalWorkingOpen,
  resetSignalWorkingStore,
  setSignalWorkingOpen,
  toggleSignalWorking,
} from "./SignalWorkingStore";

afterEach(() => resetSignalWorkingStore());

describe("SignalWorkingStore", () => {
  it("starts closed", () => {
    expect(getSignalWorkingOpen()).toBe(false);
  });

  it("toggles, and says so to every listener once", () => {
    toggleSignalWorking();
    expect(getSignalWorkingOpen()).toBe(true);
    toggleSignalWorking();
    expect(getSignalWorkingOpen()).toBe(false);
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
