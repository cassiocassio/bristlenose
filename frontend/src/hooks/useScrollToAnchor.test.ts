import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook } from "@testing-library/react";
import { useScrollToAnchor } from "./useScrollToAnchor";

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.useFakeTimers();
  // Mock requestAnimationFrame to call the callback synchronously,
  // since jsdom's implementation isn't tied to Vitest's fake timers.
  vi.spyOn(window, "requestAnimationFrame").mockImplementation((cb) => {
    cb(0);
    return 0;
  });
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  document.getElementById("test-anchor")?.remove();
  document.getElementById("missing-anchor")?.remove();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useScrollToAnchor", () => {
  it("scrolls to element when found immediately", () => {
    const el = document.createElement("div");
    el.id = "test-anchor";
    el.scrollIntoView = vi.fn();
    document.body.appendChild(el);

    const { result } = renderHook(() => useScrollToAnchor());
    result.current("test-anchor");

    expect(el.scrollIntoView).toHaveBeenCalledWith({
      behavior: "smooth",
      block: "start",
    });
  });

  it("uses custom block option", () => {
    const el = document.createElement("div");
    el.id = "test-anchor";
    el.scrollIntoView = vi.fn();
    document.body.appendChild(el);

    const { result } = renderHook(() => useScrollToAnchor());
    result.current("test-anchor", { block: "center" });

    expect(el.scrollIntoView).toHaveBeenCalledWith({
      behavior: "smooth",
      block: "center",
    });
  });

  it("applies highlight class when requested", () => {
    const el = document.createElement("div");
    el.id = "test-anchor";
    el.scrollIntoView = vi.fn();
    document.body.appendChild(el);

    const { result } = renderHook(() => useScrollToAnchor());
    result.current("test-anchor", { highlight: true });

    expect(el.classList.contains("anchor-highlight")).toBe(true);
  });

  it("does not apply highlight by default", () => {
    const el = document.createElement("div");
    el.id = "test-anchor";
    el.scrollIntoView = vi.fn();
    document.body.appendChild(el);

    const { result } = renderHook(() => useScrollToAnchor());
    result.current("test-anchor");

    expect(el.classList.contains("anchor-highlight")).toBe(false);
  });

  it("retries when element is not found", () => {
    const { result } = renderHook(() => useScrollToAnchor());
    result.current("missing-anchor");

    // After a few retries, add the element
    const el = document.createElement("div");
    el.id = "missing-anchor";
    el.scrollIntoView = vi.fn();
    document.body.appendChild(el);

    // Advance past a few retry intervals (300ms = 3 retries)
    vi.advanceTimersByTime(300);

    expect(el.scrollIntoView).toHaveBeenCalled();
  });

  it("stops retrying after max attempts", () => {
    const { result } = renderHook(() => useScrollToAnchor());
    result.current("never-exists");

    // Advance past all 50 retries (50 × 100ms = 5000ms)
    vi.advanceTimersByTime(5100);

    // Should not throw — just silently stops
  });

  it("returns a stable callback", () => {
    const { result, rerender } = renderHook(() => useScrollToAnchor());
    const first = result.current;
    rerender();
    expect(result.current).toBe(first);
  });
});
