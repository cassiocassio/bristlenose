import { describe, it, expect, beforeEach } from "vitest";
import {
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
    _resetFocusMode();
  });

  it("boots off — Focus is a lean-in action, not a default state", () => {
    expect(isFocusMode()).toBe(false);
    expect(document.documentElement.classList.contains("bn-focus-mode")).toBe(false);
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
