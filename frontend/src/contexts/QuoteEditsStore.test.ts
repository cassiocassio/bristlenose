import { describe, it, expect, beforeEach, vi } from "vitest";
import {
  CLASS_QUOTE_EDITS,
  isQuoteEdits,
  setQuoteEdits,
  subscribe,
  toggleQuoteEdits,
  _resetQuoteEdits,
} from "./QuoteEditsStore";

/**
 * The store is the single source of truth for View ▸ Show / Hide Quote Edits;
 * the Mac menu is only a mirror of it. These pin what the menu relies on: off at
 * boot, one toggle entry point, a root class, and nothing written to storage
 * (it must be off at every launch).
 */
describe("QuoteEditsStore", () => {
  beforeEach(() => {
    localStorage.clear();
    _resetQuoteEdits();
  });

  it("is off at boot", () => {
    expect(isQuoteEdits()).toBe(false);
    expect(document.documentElement.classList.contains(CLASS_QUOTE_EDITS)).toBe(false);
  });

  it("toggles on and off, and the root class follows", () => {
    toggleQuoteEdits();
    expect(isQuoteEdits()).toBe(true);
    expect(document.documentElement.classList.contains(CLASS_QUOTE_EDITS)).toBe(true);
    toggleQuoteEdits();
    expect(isQuoteEdits()).toBe(false);
    expect(document.documentElement.classList.contains(CLASS_QUOTE_EDITS)).toBe(false);
  });

  it("writes nothing to storage, so it is off at the next launch", () => {
    setQuoteEdits(true);
    expect(localStorage.length).toBe(0);
  });

  it("notifies subscribers once per real change, and not for a no-op", () => {
    const listener = vi.fn();
    const unsubscribe = subscribe(listener);
    setQuoteEdits(true);
    setQuoteEdits(true);
    expect(listener).toHaveBeenCalledTimes(1);
    setQuoteEdits(false);
    expect(listener).toHaveBeenCalledTimes(2);
    unsubscribe();
    setQuoteEdits(true);
    expect(listener).toHaveBeenCalledTimes(2);
  });
});
