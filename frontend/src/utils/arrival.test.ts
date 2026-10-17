import { describe, expect, it } from "vitest";
import { markArrived } from "./arrival";

function animationEnd(target: Element, animationName: string, type = "animationend"): void {
  const e = new Event(type, { bubbles: true });
  Object.defineProperty(e, "animationName", { value: animationName });
  target.dispatchEvent(e);
}

describe("markArrived", () => {
  it("marks the element", () => {
    const el = document.createElement("div");
    markArrived(el);
    expect(el.hasAttribute("data-arrived")).toBe(true);
  });

  it("restarts a flash already running", () => {
    const el = document.createElement("div");
    markArrived(el);
    const seen: (string | null)[] = [];
    new MutationObserver((records) => {
      for (const r of records) seen.push(r.oldValue);
    }).observe(el, { attributes: true, attributeOldValue: true });
    markArrived(el);
    return Promise.resolve().then(() => {
      // Removed, then set again: the animation starts over.
      expect(seen).toEqual(["", null]);
      expect(el.hasAttribute("data-arrived")).toBe(true);
    });
  });

  it("clears the mark when its own flash ends", () => {
    const el = document.createElement("div");
    markArrived(el);
    animationEnd(el, "bn-arrival");
    expect(el.hasAttribute("data-arrived")).toBe(false);
  });

  it("clears the mark when its flash is cut short", () => {
    const el = document.createElement("div");
    markArrived(el);
    animationEnd(el, "bn-arrival", "animationcancel");
    expect(el.hasAttribute("data-arrived")).toBe(false);
  });

  it("keeps the mark when a child's animation ends", () => {
    const el = document.createElement("div");
    const badge = document.createElement("span");
    el.appendChild(badge);
    markArrived(el);
    animationEnd(badge, "bn-arrival");
    expect(el.hasAttribute("data-arrived")).toBe(true);
  });

  it("keeps the mark when another animation on it ends", () => {
    const el = document.createElement("div");
    markArrived(el);
    animationEnd(el, "badge-fade-in");
    expect(el.hasAttribute("data-arrived")).toBe(true);
  });
});
