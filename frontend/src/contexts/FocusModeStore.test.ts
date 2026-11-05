import { describe, it, expect, beforeEach, vi } from "vitest";
import {
  FOCUS_MODE_KEY,
  applySavedFocusMode,
  isFocusMode,
  setFocusMode,
  toggleFocusMode,
  subscribe,
  _resetFocusMode,
} from "./FocusModeStore";

/**
 * The store's job is to be the single source of truth for a state driven from
 * three places (toolbar button, `z` key, native menu) and read by two (the DOM
 * class, the native checkmark). These tests pin the contract that makes that
 * safe; the CSS behaviour itself is pinned in tests/test_focus_mode_css.py.
 */
describe("FocusModeStore", () => {
  beforeEach(() => {
    localStorage.clear();
    _resetFocusMode();
  });

  it("is off when nothing has been saved", () => {
    expect(isFocusMode()).toBe(false);
    expect(document.documentElement.classList.contains("bn-focus-mode")).toBe(false);
  });

  it("saves each change, so it is still on at the next launch (owner, 4 Nov 2026)", () => {
    setFocusMode(true);
    expect(localStorage.getItem(FOCUS_MODE_KEY)).toBe("on");
    setFocusMode(false);
    expect(localStorage.getItem(FOCUS_MODE_KEY)).toBe("off");
  });

  it("puts a saved 'on' back at boot, with the class set and nothing written", () => {
    localStorage.setItem(FOCUS_MODE_KEY, "on");
    const before = localStorage.getItem(FOCUS_MODE_KEY);
    applySavedFocusMode();
    expect(isFocusMode()).toBe(true);
    expect(document.documentElement.classList.contains("bn-focus-mode")).toBe(true);
    expect(localStorage.getItem(FOCUS_MODE_KEY)).toBe(before);
  });

  it("boots off for a saved 'off' or any other stored value, and never rewrites it", () => {
    for (const v of ["off", "yes", "true", ""]) {
      localStorage.setItem(FOCUS_MODE_KEY, v);
      applySavedFocusMode();
      expect(isFocusMode()).toBe(false);
      expect(localStorage.getItem(FOCUS_MODE_KEY)).toBe(v);
    }
  });

  it("hands the choice to the Mac app", () => {
    const post = vi.fn();
    (window as unknown as Record<string, unknown>).webkit = { messageHandlers: { navigation: { postMessage: post } } };
    setFocusMode(true);
    expect(post).toHaveBeenCalledWith({ type: "report-pref", key: "bn-focus-mode", value: "on" });
    delete (window as unknown as Record<string, unknown>).webkit;
  });

  it("toggles state and the DOM class together", () => {
    toggleFocusMode();
    expect(isFocusMode()).toBe(true);
    expect(document.documentElement.classList.contains("bn-focus-mode")).toBe(true);

    toggleFocusMode();
    expect(isFocusMode()).toBe(false);
    expect(document.documentElement.classList.contains("bn-focus-mode")).toBe(false);
  });

  it("adds the transition hook and never removes it", () => {
    // `bn-focus-ready` carries the transitions. If it came and went with the
    // state, the fade would play going in and snap coming out.
    setFocusMode(true);
    expect(document.documentElement.classList.contains("bn-focus-ready")).toBe(true);
    setFocusMode(false);
    expect(document.documentElement.classList.contains("bn-focus-ready")).toBe(true);
  });

  it("notifies subscribers once per real change, not per call", () => {
    let calls = 0;
    // The same path useSyncExternalStore uses — no test-only seam.
    const unsub = subscribe(() => {
      calls += 1;
    });

    setFocusMode(true);
    setFocusMode(true); // no-op — already on
    expect(calls).toBe(1);

    setFocusMode(false);
    expect(calls).toBe(2);

    unsub();
    setFocusMode(true);
    expect(calls).toBe(2);
  });
});
