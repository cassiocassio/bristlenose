/**
 * Tests for useScrollSpy — tracks active section heading during scroll.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useScrollSpy } from "./useScrollSpy";

// ── Helpers ──────────────────────────────────────────────────────────────

/** Create a mock element with a controlled getBoundingClientRect().top. */
function mockElement(top: number): HTMLElement {
  const el = document.createElement("div");
  el.getBoundingClientRect = () =>
    ({ top, bottom: top + 50, left: 0, right: 100, width: 100, height: 50, x: 0, y: top }) as DOMRect;
  return el;
}

function fireScroll() {
  window.dispatchEvent(new Event("scroll"));
}

// ── Setup ────────────────────────────────────────────────────────────────

let elementMap: Record<string, HTMLElement>;

beforeEach(() => {
  elementMap = {};
  vi.spyOn(document, "getElementById").mockImplementation(
    (id: string) => elementMap[id] ?? null,
  );
  // Mock rAF to run callbacks synchronously.
  vi.spyOn(globalThis, "requestAnimationFrame").mockImplementation((cb) => {
    cb(0);
    return 0;
  });
  vi.spyOn(globalThis, "cancelAnimationFrame").mockImplementation(() => {});
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ── Tests ────────────────────────────────────────────────────────────────

describe("useScrollSpy", () => {
  it("returns null for empty ids array", () => {
    const { result } = renderHook(() => useScrollSpy([]));
    expect(result.current).toBeNull();
  });

  it("returns null when no elements are above threshold", () => {
    elementMap["s1"] = mockElement(200);
    elementMap["s2"] = mockElement(400);
    const { result } = renderHook(() => useScrollSpy(["s1", "s2"], 100));
    // Initial run: both elements are below threshold (200, 400 > 100)
    expect(result.current).toBeNull();
  });

  it("returns last element above threshold (bottom-to-top walk)", () => {
    elementMap["s1"] = mockElement(50);
    elementMap["s2"] = mockElement(80);
    elementMap["s3"] = mockElement(200);
    const { result } = renderHook(() => useScrollSpy(["s1", "s2", "s3"], 100));
    // s1 at 50 and s2 at 80 are both <= 100. Bottom-to-top: s2 wins.
    expect(result.current).toBe("s2");
  });

  it("returns first element if only one is above threshold", () => {
    elementMap["s1"] = mockElement(30);
    elementMap["s2"] = mockElement(200);
    const { result } = renderHook(() => useScrollSpy(["s1", "s2"], 100));
    expect(result.current).toBe("s1");
  });

  it("updates on scroll event", () => {
    elementMap["s1"] = mockElement(200);
    const { result } = renderHook(() => useScrollSpy(["s1"], 100));
    expect(result.current).toBeNull();

    // Simulate scroll: move element above threshold.
    elementMap["s1"] = mockElement(50);
    act(() => fireScroll());
    expect(result.current).toBe("s1");
  });

  it("handles missing DOM elements gracefully", () => {
    // s2 does not exist in the map — getElementById returns null.
    elementMap["s1"] = mockElement(50);
    const { result } = renderHook(() => useScrollSpy(["s1", "s2"], 100));
    expect(result.current).toBe("s1");
  });

  it("cleans up scroll listener on unmount", () => {
    const removeSpy = vi.spyOn(window, "removeEventListener");
    const { unmount } = renderHook(() => useScrollSpy(["s1"], 100));
    unmount();
    expect(removeSpy).toHaveBeenCalledWith("scroll", expect.any(Function));
  });

  it("re-evaluates when ids change", () => {
    elementMap["a"] = mockElement(50);
    elementMap["b"] = mockElement(30);
    const { result, rerender } = renderHook(
      ({ ids }) => useScrollSpy(ids, 100),
      { initialProps: { ids: ["a"] } },
    );
    expect(result.current).toBe("a");

    rerender({ ids: ["b"] });
    expect(result.current).toBe("b");
  });
});
