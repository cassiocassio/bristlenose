import { describe, expect, it } from "vitest";
import { choosePaper, contrast, parseRgb, type Rgb } from "./paper";

const hex = (s: string): Rgb => [1, 3, 5].map((i) => parseInt(s.slice(i, i + 2), 16)) as Rgb;
const DEFAULT = { light: hex("#007aff"), dark: hex("#0a84ff") };
const EDO = { light: hex("#0f5c9e"), dark: hex("#4d9fe0") };

describe("choosePaper: the accent half and the halo for a screengrab's paper", () => {
  it("a white page takes the light accent and a halo in its own white", () => {
    expect(choosePaper(hex("#ffffff"), DEFAULT)).toEqual({ casing: "rgb(255, 255, 255)", scheme: "light", midtone: false });
    expect(choosePaper(hex("#ffffff"), EDO)).toEqual({ casing: "rgb(255, 255, 255)", scheme: "light", midtone: false });
  });

  it("a dark-mode site takes the dark accent, whatever the board's theme", () => {
    expect(choosePaper(hex("#121212"), DEFAULT)).toEqual({ casing: "rgb(18, 18, 18)", scheme: "dark", midtone: false });
    expect(choosePaper(hex("#121212"), EDO)).toEqual({ casing: "rgb(18, 18, 18)", scheme: "dark", midtone: false });
  });

  it("#e0e0e0 passes a naive 3:1 but not under the blur, so it is a midtone when blurred", () => {
    expect(contrast(DEFAULT.light, hex("#e0e0e0"))).toBeGreaterThan(3);
    const blurred = choosePaper(hex("#e0e0e0"), DEFAULT);
    expect(blurred.midtone).toBe(true);
    // Hard-cased (a 1x screen), 3:1 is the bar and the paper itself will do.
    expect(choosePaper(hex("#e0e0e0"), DEFAULT, false)).toEqual({ casing: "rgb(224, 224, 224)", scheme: "light", midtone: false });
  });

  it("a mid-grey photo is a midtone: the best of white or near-black, its scheme from the accent chosen", () => {
    for (const accents of [DEFAULT, EDO]) {
      const c = choosePaper(hex("#808080"), accents);
      expect(c.midtone).toBe(true);
      expect(["rgb(255, 255, 255)", "rgb(17, 17, 17)"]).toContain(c.casing);
      const casing = parseRgb(c.casing)!;
      expect(contrast(accents[c.scheme], casing)).toBeGreaterThanOrEqual(3);
    }
  });

  it("returns the halo as a literal colour, never a token that would resolve in the forced scheme", () => {
    for (const p of ["#ffffff", "#121212", "#808080"]) expect(choosePaper(hex(p), DEFAULT).casing).toMatch(/^rgb\(\d+, \d+, \d+\)$/);
  });
});

describe("parseRgb", () => {
  it("reads rgb() and rgba()", () => {
    expect(parseRgb("rgb(10, 132, 255)")).toEqual([10, 132, 255]);
    expect(parseRgb("rgba(10, 132, 255, 0.5)")).toEqual([10, 132, 255]);
    expect(parseRgb("transparent")).toBeNull();
  });
});
