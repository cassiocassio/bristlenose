import { describe, it, expect, beforeEach, vi } from "vitest";
import { setAnnounceElement, announce } from "./announce";

describe("announce", () => {
  let el: HTMLDivElement;

  beforeEach(() => {
    el = document.createElement("div");
    setAnnounceElement(el);
  });

  it("sets textContent after rAF", () => {
    vi.useFakeTimers();
    announce("Quote starred");
    // Before rAF, cleared to empty.
    expect(el.textContent).toBe("");
    // After rAF fires, message appears.
    vi.advanceTimersByTime(0);
    // rAF callback runs on next frame — advance timers.
    // jsdom rAF is setTimeout-based, so advance once.
    vi.advanceTimersByTime(16);
    expect(el.textContent).toBe("Quote starred");
    vi.useRealTimers();
  });

  it("clears after 5 seconds", () => {
    vi.useFakeTimers();
    announce("Tag added: usability");
    vi.advanceTimersByTime(16);
    expect(el.textContent).toBe("Tag added: usability");
    vi.advanceTimersByTime(5000);
    expect(el.textContent).toBe("");
    vi.useRealTimers();
  });

  it("does not throw when no element registered", () => {
    setAnnounceElement(null);
    expect(() => announce("no-op")).not.toThrow();
  });
});
