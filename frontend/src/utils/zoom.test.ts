import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { applySavedZoom, applyZoom, getZoom } from "./zoom";

beforeEach(() => {
  localStorage.clear();
  document.documentElement.style.fontSize = "";
});

afterEach(() => {
  document.documentElement.style.fontSize = "";
});

describe("zoom at boot (R89)", () => {
  it("puts a saved zoom back", () => {
    localStorage.setItem("bristlenose-zoom", "1.2");
    applySavedZoom();
    expect(document.documentElement.style.fontSize).toBe("120%");
  });

  it("clamps a saved zoom out of range", () => {
    localStorage.setItem("bristlenose-zoom", "9");
    applySavedZoom();
    expect(document.documentElement.style.fontSize).toBe("200%");
  });

  it("leaves the page alone with nothing saved, or garbage", () => {
    applySavedZoom();
    expect(document.documentElement.style.fontSize).toBe("");
    localStorage.setItem("bristlenose-zoom", "big");
    applySavedZoom();
    expect(document.documentElement.style.fontSize).toBe("");
    expect(getZoom()).toBe(1);
  });

  it("a zoom step is saved for the next boot", () => {
    applyZoom(getZoom() + 0.1);
    expect(localStorage.getItem("bristlenose-zoom")).toBe("1.1");
    document.documentElement.style.fontSize = "";
    applySavedZoom();
    expect(document.documentElement.style.fontSize).toBe("110%");
  });
});
