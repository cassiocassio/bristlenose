import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { scrollToLand } from "./scrollToLand";

/** A target whose measured top follows `tops`, one value per settle. */
function target(tops: number[]) {
  const el = document.createElement("h2");
  document.body.appendChild(el);
  const scroll = vi.fn();
  el.scrollIntoView = scroll;
  let i = 0;
  el.getBoundingClientRect = () => ({ top: tops[Math.min(i++, tops.length - 1)] }) as DOMRect;
  return { el, scroll };
}

describe("scrollToLand", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
    document.body.innerHTML = "";
  });

  it("scrolls again when the first scroll stops short of the heading", () => {
    // Cards laid out on the way past moved the heading: 420px off after the
    // first scroll, on target after the second, confirmed by the third.
    const { el, scroll } = target([420, 0, 0]);
    scrollToLand(el);
    vi.advanceTimersByTime(1000);
    expect(scroll).toHaveBeenCalledTimes(3);
    expect(scroll).toHaveBeenLastCalledWith({ behavior: "smooth", block: "start" });
  });

  it("stops after one confirming pass when the first scroll landed", () => {
    const { el, scroll } = target([0, 0]);
    scrollToLand(el);
    vi.advanceTimersByTime(1000);
    expect(scroll).toHaveBeenCalledTimes(2);
  });

  it("waits for the page to stop scrolling before measuring", () => {
    const { el, scroll } = target([420, 0, 0]);
    scrollToLand(el);
    for (let t = 0; t < 10; t++) {
      vi.advanceTimersByTime(100);
      window.dispatchEvent(new Event("scroll"));
    }
    expect(scroll).toHaveBeenCalledTimes(1);
    vi.advanceTimersByTime(1000);
    expect(scroll).toHaveBeenCalledTimes(3);
  });

  it("gives up after three passes", () => {
    const { el, scroll } = target([400, 300, 200, 100, 0]);
    scrollToLand(el);
    vi.advanceTimersByTime(5000);
    expect(scroll).toHaveBeenCalledTimes(3);
  });

  it("leaves the scroll alone once the researcher takes it over", () => {
    const { el, scroll } = target([420, 0, 0]);
    scrollToLand(el);
    window.dispatchEvent(new Event("wheel"));
    vi.advanceTimersByTime(1000);
    expect(scroll).toHaveBeenCalledTimes(1);
  });

  it("a second jump replaces the first one's correction", () => {
    const first = target([420, 0, 0]);
    const second = target([0, 0]);
    scrollToLand(first.el);
    scrollToLand(second.el);
    vi.advanceTimersByTime(1000);
    expect(first.scroll).toHaveBeenCalledTimes(1);
    expect(second.scroll).toHaveBeenCalledTimes(2);
  });
});
