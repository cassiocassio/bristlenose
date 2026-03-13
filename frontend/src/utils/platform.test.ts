/**
 * Tests for platform detection utility.
 */

import { isMac, _resetPlatformCache } from "./platform";

beforeEach(() => {
  _resetPlatformCache();
  // Clear userAgentData between tests
  delete (navigator as any).userAgentData;
});

describe("isMac", () => {
  it("detects Mac via userAgentData.platform", () => {
    (navigator as any).userAgentData = { platform: "macOS" };
    expect(isMac()).toBe(true);
  });

  it("detects Mac via navigator.platform (MacIntel)", () => {
    Object.defineProperty(navigator, "platform", {
      value: "MacIntel",
      configurable: true,
    });
    expect(isMac()).toBe(true);
  });

  it("detects Windows via userAgentData.platform", () => {
    (navigator as any).userAgentData = { platform: "Windows" };
    expect(isMac()).toBe(false);
  });

  it("detects Windows via navigator.platform", () => {
    Object.defineProperty(navigator, "platform", {
      value: "Win32",
      configurable: true,
    });
    expect(isMac()).toBe(false);
  });

  it("detects Linux via navigator.platform", () => {
    Object.defineProperty(navigator, "platform", {
      value: "Linux x86_64",
      configurable: true,
    });
    expect(isMac()).toBe(false);
  });

  it("prefers userAgentData over navigator.platform", () => {
    (navigator as any).userAgentData = { platform: "macOS" };
    Object.defineProperty(navigator, "platform", {
      value: "Win32",
      configurable: true,
    });
    expect(isMac()).toBe(true);
  });

  it("memoises the result", () => {
    (navigator as any).userAgentData = { platform: "macOS" };
    expect(isMac()).toBe(true);

    // Change platform — should still return cached result
    (navigator as any).userAgentData = { platform: "Windows" };
    expect(isMac()).toBe(true);
  });

  it("re-evaluates after _resetPlatformCache()", () => {
    (navigator as any).userAgentData = { platform: "macOS" };
    expect(isMac()).toBe(true);

    _resetPlatformCache();
    (navigator as any).userAgentData = { platform: "Windows" };
    expect(isMac()).toBe(false);
  });
});
