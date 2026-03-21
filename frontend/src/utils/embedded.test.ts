import { describe, it, expect, afterEach } from "vitest";
import { isEmbedded, _resetEmbeddedCache } from "./embedded";

function setEmbedded(value: unknown): void {
  (window as unknown as Record<string, unknown>).__BRISTLENOSE_EMBEDDED__ = value;
}

function clearEmbedded(): void {
  delete (window as unknown as Record<string, unknown>).__BRISTLENOSE_EMBEDDED__;
}

afterEach(() => {
  clearEmbedded();
  _resetEmbeddedCache();
});

describe("isEmbedded", () => {
  it("returns false when flag is not set", () => {
    expect(isEmbedded()).toBe(false);
  });

  it("returns true when flag is true", () => {
    setEmbedded(true);
    expect(isEmbedded()).toBe(true);
  });

  it("returns false when flag is truthy but not boolean true", () => {
    setEmbedded(1);
    expect(isEmbedded()).toBe(false);
    _resetEmbeddedCache();
    setEmbedded("true");
    expect(isEmbedded()).toBe(false);
  });

  it("caches the result", () => {
    setEmbedded(true);
    expect(isEmbedded()).toBe(true);
    clearEmbedded();
    expect(isEmbedded()).toBe(true); // still cached
  });

  it("_resetEmbeddedCache allows re-detection", () => {
    expect(isEmbedded()).toBe(false);
    setEmbedded(true);
    _resetEmbeddedCache();
    expect(isEmbedded()).toBe(true);
  });
});
