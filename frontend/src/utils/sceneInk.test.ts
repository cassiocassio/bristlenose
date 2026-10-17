import { describe, expect, it } from "vitest";
import { screenInk } from "./sceneInk";

describe("screenInk", () => {
  it("picks the ink most colours prefer", () => {
    expect(screenInk(["#e8e0d0", "#d8d0c0", "#4a3a30"])).toBe("#1a1a1a");
    expect(screenInk(["#2a2a40", "#303048", "#e8e0d0"])).toBe("#fff");
  });

  it("is dark on a tie and with no colours", () => {
    expect(screenInk(["#e8e0d0", "#2a2a40"])).toBe("#1a1a1a");
    expect(screenInk([])).toBe("#1a1a1a");
  });
});
