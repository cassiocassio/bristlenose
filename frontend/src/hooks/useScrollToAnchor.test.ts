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

    expect(el.hasAttribute("data-arrived")).toBe(true);
  });

  it("does not apply highlight by default", () => {
    const el = document.createElement("div");
    el.id = "test-anchor";
    el.scrollIntoView = vi.fn();
    document.body.appendChild(el);

    const { result } = renderHook(() => useScrollToAnchor());
    result.current("test-anchor");

    expect(el.hasAttribute("data-arrived")).toBe(false);
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

  it("asks the page to show a target in a hidden place, and scrolls once it is shown", () => {
    // Decision #182: a Signals card on a place the page is not showing exists, but cannot be
    // scrolled to. Scrolling at the first find would land nowhere.
    const place = document.createElement("section");
    place.id = "hidden-place";
    place.hidden = true;
    const el = document.createElement("div");
    el.id = "test-anchor";
    el.scrollIntoView = vi.fn();
    place.appendChild(el);
    document.body.appendChild(place);
    const asked: string[] = [];
    const onReveal = (e: Event) => asked.push((e as CustomEvent<{ id: string }>).detail.id);
    window.addEventListener("bn:reveal-anchor", onReveal);
    try {
      const { result } = renderHook(() => useScrollToAnchor());
      result.current("test-anchor");

      expect(asked).toEqual(["test-anchor"]);
      expect(el.scrollIntoView).not.toHaveBeenCalled();

      // Nobody claimed it, so the hook keeps trying; once shown, it lands.
      vi.advanceTimersByTime(100);
      expect(asked.length).toBe(2);
      place.hidden = false;
      vi.advanceTimersByTime(100);
      expect(el.scrollIntoView).toHaveBeenCalled();
    } finally {
      window.removeEventListener("bn:reveal-anchor", onReveal);
      place.remove();
    }
  });

  it("leaves the landing to a page that claims the reveal", () => {
    const place = document.createElement("section");
    place.id = "hidden-place";
    place.hidden = true;
    const el = document.createElement("div");
    el.id = "test-anchor";
    el.scrollIntoView = vi.fn();
    place.appendChild(el);
    document.body.appendChild(place);
    let asked = 0;
    const onReveal = (e: Event) => {
      asked += 1;
      e.preventDefault();
      place.hidden = false;
    };
    window.addEventListener("bn:reveal-anchor", onReveal);
    try {
      const { result } = renderHook(() => useScrollToAnchor());
      result.current("test-anchor");
      vi.advanceTimersByTime(1000);
      // Asked once, and no second scroll on top of the page's own.
      expect(asked).toBe(1);
      expect(el.scrollIntoView).not.toHaveBeenCalled();
    } finally {
      window.removeEventListener("bn:reveal-anchor", onReveal);
      place.remove();
    }
  });

  it("offers a visible target to the page, and lets a page that claims it land it", () => {
    // The Signals page lands its first card with the place title (`scrollToCard`); a second
    // scroll here would put the card at the top instead.
    const el = document.createElement("div");
    el.id = "test-anchor";
    el.scrollIntoView = vi.fn();
    document.body.appendChild(el);
    const claim = (e: Event) => e.preventDefault();
    window.addEventListener("bn:reveal-anchor", claim);
    try {
      const { result } = renderHook(() => useScrollToAnchor());
      result.current("test-anchor", { highlight: true });
      vi.advanceTimersByTime(500);
      expect(el.scrollIntoView).not.toHaveBeenCalled();
      expect(el.hasAttribute("data-arrived")).toBe(true);
    } finally {
      window.removeEventListener("bn:reveal-anchor", claim);
    }
  });

  it("lands an unclaimed visible target itself, once", () => {
    const el = document.createElement("div");
    el.id = "test-anchor";
    el.scrollIntoView = vi.fn();
    document.body.appendChild(el);
    let asked = 0;
    const listen = () => { asked += 1; };
    window.addEventListener("bn:reveal-anchor", listen);
    try {
      const { result } = renderHook(() => useScrollToAnchor());
      result.current("test-anchor");
      vi.advanceTimersByTime(500);
      expect(asked).toBe(1);
      expect(el.scrollIntoView).toHaveBeenCalledTimes(1);
    } finally {
      window.removeEventListener("bn:reveal-anchor", listen);
    }
  });

  it("returns a stable callback", () => {
    const { result, rerender } = renderHook(() => useScrollToAnchor());
    const first = result.current;
    rerender();
    expect(result.current).toBe(first);
  });
});
