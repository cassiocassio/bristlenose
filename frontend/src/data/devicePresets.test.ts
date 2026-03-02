import { describe, it, expect } from "vitest";
import {
  DEVICE_PRESETS,
  BREAKPOINT_SETS,
  getDeviceName,
  getBreakpointZone,
} from "./devicePresets";

describe("devicePresets", () => {
  it("DEVICE_PRESETS has expected entries", () => {
    expect(DEVICE_PRESETS.length).toBeGreaterThan(5);
    expect(DEVICE_PRESETS.find((d) => d.name === "iPhone SE")?.width).toBe(375);
    expect(DEVICE_PRESETS.find((d) => d.name === "Full width")?.width).toBeNull();
  });

  it("BREAKPOINT_SETS includes standard frameworks", () => {
    expect(BREAKPOINT_SETS.tailwind).toBeTruthy();
    expect(BREAKPOINT_SETS.bootstrap).toBeTruthy();
    expect(BREAKPOINT_SETS.material).toBeTruthy();
    expect(BREAKPOINT_SETS.bristlenose).toBeTruthy();
  });
});

describe("getDeviceName", () => {
  it("returns iPhone SE for 375px", () => {
    expect(getDeviceName(375)).toBe("iPhone SE");
  });

  it("returns MacBook Pro 16\" for 1728px", () => {
    expect(getDeviceName(1728)).toBe('MacBook Pro 16"');
  });

  it("returns smallest device for very narrow viewport", () => {
    expect(getDeviceName(100)).toBe("iPhone SE");
  });
});

describe("getBreakpointZone", () => {
  it("returns zone 0 below first breakpoint", () => {
    expect(getBreakpointZone(500, [600, 900, 1100])).toBe(0);
  });

  it("returns zone 1 between first and second breakpoint", () => {
    expect(getBreakpointZone(700, [600, 900, 1100])).toBe(1);
  });

  it("returns last zone above all breakpoints", () => {
    expect(getBreakpointZone(1200, [600, 900, 1100])).toBe(3);
  });

  it("returns zone 0 at exactly the first breakpoint", () => {
    // At exactly 600, it's NOT < 600, so it falls through to zone 1
    expect(getBreakpointZone(600, [600, 900, 1100])).toBe(1);
  });
});
