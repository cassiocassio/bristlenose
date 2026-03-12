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

/** Install rAF/cAF mocks that run synchronously. Must be called AFTER
 *  vi.useFakeTimers() if fake timers are in use, since fake timers
 *  replace globalThis.requestAnimationFrame. */
function installRafMock() {
  const raf = ((cb: FrameRequestCallback) => { cb(0); return 0; }) as typeof globalThis.requestAnimationFrame;
  const caf = (() => {}) as typeof globalThis.cancelAnimationFrame;
  // Set on both globalThis and window to cover all resolution paths.
  globalThis.requestAnimationFrame = raf;
  globalThis.cancelAnimationFrame = caf;
  window.requestAnimationFrame = raf;
  window.cancelAnimationFrame = caf;
}

beforeEach(() => {
  elementMap = {};
  vi.spyOn(document, "getElementById").mockImplementation(
    (id: string) => elementMap[id] ?? null,
  );
  // Install rAF mock (non-fake-timer tests).
  installRafMock();
  // Mock window.innerHeight for viewport visibility checks.
  Object.defineProperty(window, "innerHeight", { value: 800, writable: true });
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});

// ── Tests ────────────────────────────────────────────────────────────────

describe("useScrollSpy", () => {
  it("returns null for empty ids array", () => {
    const { result } = renderHook(() => useScrollSpy([]));
    expect(result.current).toBeNull();
  });

  it("defaults to first id when all elements are below threshold (page at top)", () => {
    elementMap["s1"] = mockElement(200);
    elementMap["s2"] = mockElement(400);
    const { result } = renderHook(() => useScrollSpy(["s1", "s2"], 100));
    // Initial run: both elements are below threshold (200, 400 > 100).
    // Fallback: first section is active since the page is at the top.
    expect(result.current).toBe("s1");
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
    elementMap["s2"] = mockElement(400);
    const { result } = renderHook(() => useScrollSpy(["s1", "s2"], 100));
    // At top of page: fallback to first id.
    expect(result.current).toBe("s1");

    // Simulate scroll: s2 moves above threshold — becomes active (deeper).
    elementMap["s2"] = mockElement(50);
    act(() => fireScroll());
    expect(result.current).toBe("s2");
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

// ── Click intent override ────────────────────────────────────────────────

describe("click intent override", () => {
  it("honours click during immune phase (smooth scroll animation)", () => {
    vi.useFakeTimers();
    installRafMock();
    vi.setSystemTime(1000);

    // s1 is above threshold (normal winner), s3 is the clicked item.
    elementMap["s1"] = mockElement(50);
    elementMap["s2"] = mockElement(200);
    elementMap["s3"] = mockElement(400);

    const clickedRef = { current: "s3" };
    const { result } = renderHook(() =>
      useScrollSpy(["s1", "s2", "s3"], 100, clickedRef),
    );
    // During immune phase (<600ms from click detection): s3 wins regardless.
    expect(result.current).toBe("s3");
  });

  it("stays sticky when nearby heading is the normal winner (post-settle)", () => {
    vi.useFakeTimers();
    installRafMock();
    vi.setSystemTime(1000);

    // s3 at threshold, s4 is the clicked last item (adjacent, index diff = 1).
    elementMap["s1"] = mockElement(-200);
    elementMap["s2"] = mockElement(-50);
    elementMap["s3"] = mockElement(60);   // above threshold — normal winner
    elementMap["s4"] = mockElement(500);  // clicked, adjacent to s3

    const clickedRef = { current: "s4" };
    const { result } = renderHook(() =>
      useScrollSpy(["s1", "s2", "s3", "s4"], 100, clickedRef),
    );
    // Immune phase: s4 wins.
    expect(result.current).toBe("s4");

    // Advance past the settle period.
    vi.setSystemTime(1000 + 700);
    act(() => fireScroll());

    // Sticky phase: s3 is the normal winner at index 2, s4 is clicked at index 3.
    // |2 - 3| = 1 ≤ 1 → override stays.
    expect(result.current).toBe("s4");
  });

  it("clears override when user scrolls far away (post-settle)", () => {
    vi.useFakeTimers();
    installRafMock();
    vi.setSystemTime(1000);

    elementMap["s1"] = mockElement(50);  // above threshold — normal winner
    elementMap["s2"] = mockElement(200);
    elementMap["s3"] = mockElement(400);
    elementMap["s4"] = mockElement(600); // clicked (last)

    const clickedRef = { current: "s4" };
    const { result } = renderHook(() =>
      useScrollSpy(["s1", "s2", "s3", "s4"], 100, clickedRef),
    );
    expect(result.current).toBe("s4"); // immune phase

    // Advance past settle + scroll so s1 is the normal winner.
    vi.setSystemTime(1000 + 700);
    act(() => fireScroll());

    // s1 at index 0 vs s4 at index 3: |0 - 3| = 3 > 1 → override clears.
    expect(result.current).toBe("s1");
    expect(clickedRef.current).toBeNull();
  });

  it("ignores clicked ID that is not in the ids list", () => {
    elementMap["s1"] = mockElement(50);
    elementMap["s2"] = mockElement(200);
    elementMap["unknown"] = mockElement(400);

    const clickedRef = { current: "unknown" };
    const { result } = renderHook(() =>
      useScrollSpy(["s1", "s2"], 100, clickedRef),
    );
    // "unknown" not in ids list → override skipped, normal spy runs.
    expect(result.current).toBe("s1");
  });

  it("works without clickedIdRef (backward compat)", () => {
    elementMap["s1"] = mockElement(50);
    elementMap["s2"] = mockElement(80);
    // No clickedIdRef passed — behaves exactly as before.
    const { result } = renderHook(() => useScrollSpy(["s1", "s2"], 100));
    expect(result.current).toBe("s2");
  });

  it("overrides for the last heading even with glitched getBoundingClientRect", () => {
    vi.useFakeTimers();
    installRafMock();
    vi.setSystemTime(1000);

    // Simulate the Safari bug: element returns impossible rect during smooth scroll.
    elementMap["s1"] = mockElement(-200);
    elementMap["s2"] = mockElement(60);  // above threshold — normal winner
    elementMap["s3"] = mockElement(500); // clicked, but Safari returns garbage rect

    // Override the s3 mock to return impossible values (bottom < top).
    elementMap["s3"].getBoundingClientRect = () =>
      ({ top: -849, bottom: -877, left: 0, right: 100, width: 100, height: -28, x: 0, y: -849 }) as DOMRect;

    const clickedRef = { current: "s3" };
    const { result } = renderHook(() =>
      useScrollSpy(["s1", "s2", "s3"], 100, clickedRef),
    );
    // Immune phase doesn't check getBoundingClientRect — s3 still wins.
    expect(result.current).toBe("s3");
  });

  it("updates override when user clicks a different heading", () => {
    vi.useFakeTimers();
    installRafMock();
    vi.setSystemTime(1000);

    elementMap["s1"] = mockElement(50);
    elementMap["s2"] = mockElement(300);
    elementMap["s3"] = mockElement(500);

    const clickedRef = { current: "s2" };
    const { result } = renderHook(() =>
      useScrollSpy(["s1", "s2", "s3"], 100, clickedRef),
    );
    expect(result.current).toBe("s2");

    // User clicks a different heading — new immune phase starts.
    vi.setSystemTime(2000);
    clickedRef.current = "s3";
    act(() => fireScroll());
    expect(result.current).toBe("s3");
  });

  it("adjacent heading keeps override sticky (last-two-headings case)", () => {
    vi.useFakeTimers();
    installRafMock();
    vi.setSystemTime(1000);

    // The exact user scenario: 4 headings, user clicks the very last one.
    // Page can't scroll far enough — second-to-last is at threshold.
    elementMap["s1"] = mockElement(-500);
    elementMap["s2"] = mockElement(-200);
    elementMap["s3"] = mockElement(80);   // above threshold — normal winner (index 2)
    elementMap["s4"] = mockElement(350);  // clicked (index 3)

    const clickedRef = { current: "s4" };
    const { result } = renderHook(() =>
      useScrollSpy(["s1", "s2", "s3", "s4"], 100, clickedRef),
    );
    expect(result.current).toBe("s4"); // immune

    // Settle: s3 at index 2, s4 at index 3 → |2-3| = 1 → sticky holds.
    vi.setSystemTime(1000 + 700);
    act(() => fireScroll());
    expect(result.current).toBe("s4");

    // Even after many scrolls, as long as s3 is the normal winner, s4 holds.
    vi.setSystemTime(1000 + 5000);
    act(() => fireScroll());
    expect(result.current).toBe("s4");
    expect(clickedRef.current).toBe("s4"); // NOT cleared
  });
});
