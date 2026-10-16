import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { scrollToLand } from "./scrollToLand";

/** A heading whose measured top follows `tops`, one value per settle. */
function target(tops: number[], parent: HTMLElement = document.body) {
  const el = document.createElement("h2");
  parent.appendChild(el);
  const scroll = vi.fn();
  el.scrollIntoView = scroll;
  let i = 0;
  el.getBoundingClientRect = () => ({ top: tops[Math.min(i++, tops.length - 1)] }) as DOMRect;
  return { el, scroll };
}

/** A panel that scrolls on its own, so the page is not the scroller. */
function panel() {
  const p = document.createElement("div");
  p.style.overflowY = "auto";
  Object.defineProperty(p, "scrollHeight", { value: 2000 });
  Object.defineProperty(p, "clientHeight", { value: 500 });
  document.body.appendChild(p);
  return p;
}

describe("scrollToLand", () => {
  let scrollBy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.useFakeTimers();
    scrollBy = vi.fn();
    window.scrollBy = scrollBy as unknown as typeof window.scrollBy;
    // A long page scrolled part way, with room to move both ways.
    Object.defineProperty(document.documentElement, "scrollHeight", { value: 10000, configurable: true });
    Object.defineProperty(window, "scrollY", { value: 3000, configurable: true });
    const style = document.createElement("style");
    style.textContent = "h2 { scroll-margin-top: 48px }"; // the sticky toolbar's offset
    document.head.appendChild(style);
  });
  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
    document.body.innerHTML = "";
    document.head.innerHTML = "";
  });

  describe("on the page", () => {
    it("scrolls the rest of the way when the first scroll stops short", () => {
      // Cards laid out on the way past moved the heading 420px down the window.
      const { el, scroll } = target([420, 48]);
      scrollToLand(el);
      vi.advanceTimersByTime(1000);
      expect(scroll).toHaveBeenCalledTimes(1);
      expect(scrollBy).toHaveBeenCalledTimes(1);
      expect(scrollBy).toHaveBeenCalledWith({ top: 372, behavior: "smooth" });
    });

    it("keeps the heading below the toolbar when the engine ignores its scroll margin", () => {
      const { el } = target([0, 48]);
      scrollToLand(el);
      vi.advanceTimersByTime(1000);
      expect(scrollBy).toHaveBeenCalledWith({ top: -48, behavior: "smooth" });
    });

    it("leaves a heading that landed alone", () => {
      const { el, scroll } = target([48]);
      scrollToLand(el);
      vi.advanceTimersByTime(1000);
      expect(scroll).toHaveBeenCalledTimes(1);
      expect(scrollBy).not.toHaveBeenCalled();
    });

    it("stops at the end of the page, where a heading near the bottom cannot reach the top", () => {
      Object.defineProperty(window, "scrollY", { value: 10000 - window.innerHeight, configurable: true });
      const { el } = target([300]);
      scrollToLand(el);
      vi.advanceTimersByTime(1000);
      expect(scrollBy).not.toHaveBeenCalled();
    });

    it("waits for the page to stop scrolling before measuring", () => {
      const { el } = target([420, 48]);
      scrollToLand(el);
      for (let t = 0; t < 10; t++) {
        vi.advanceTimersByTime(100);
        document.dispatchEvent(new Event("scroll"));
      }
      expect(scrollBy).not.toHaveBeenCalled();
      vi.advanceTimersByTime(1000);
      expect(scrollBy).toHaveBeenCalledTimes(1);
    });

    it("gives up after three passes", () => {
      const { el } = target([400, 300, 200, 100, 0]);
      scrollToLand(el);
      vi.advanceTimersByTime(5000);
      expect(scrollBy).toHaveBeenCalledTimes(2); // the first pass was scrollIntoView
    });

    it("leaves the scroll alone once the researcher takes it over", () => {
      const { el } = target([420, 48]);
      scrollToLand(el);
      window.dispatchEvent(new Event("wheel"));
      vi.advanceTimersByTime(1000);
      expect(scrollBy).not.toHaveBeenCalled();
    });

    it("a second jump replaces the first one's correction", () => {
      const first = target([420, 48]);
      const second = target([48]);
      scrollToLand(first.el);
      scrollToLand(second.el);
      vi.advanceTimersByTime(1000);
      expect(first.scroll).toHaveBeenCalledTimes(1);
      expect(scrollBy).not.toHaveBeenCalled();
    });
  });

  describe("in a scrolling panel", () => {
    it("scrolls again until two stops agree", () => {
      const { el, scroll } = target([420, 0, 0], panel());
      scrollToLand(el);
      vi.advanceTimersByTime(1000);
      expect(scroll).toHaveBeenCalledTimes(3);
      expect(scroll).toHaveBeenLastCalledWith({ behavior: "smooth", block: "start" });
      expect(scrollBy).not.toHaveBeenCalled();
    });

    it("stops after one confirming pass when the first scroll landed", () => {
      const { el, scroll } = target([0, 0], panel());
      scrollToLand(el);
      vi.advanceTimersByTime(1000);
      expect(scroll).toHaveBeenCalledTimes(2);
    });

    it("waits for the panel to stop, not only the page", () => {
      const p = panel();
      const { el, scroll } = target([420, 0, 0], p);
      scrollToLand(el);
      for (let t = 0; t < 10; t++) {
        vi.advanceTimersByTime(100);
        p.dispatchEvent(new Event("scroll")); // does not bubble
      }
      expect(scroll).toHaveBeenCalledTimes(1);
      vi.advanceTimersByTime(1000);
      expect(scroll).toHaveBeenCalledTimes(3);
    });
  });
});
