import { describe, it, expect } from "vitest";
import { PALETTES, isPalette, readSavedPalette, applyBootPalette } from "./bootPalette";

/** Minimal in-memory storage stub — avoids touching the shared jsdom localStorage. */
function makeStorage(value?: string): Pick<Storage, "getItem"> {
  return { getItem: (k: string) => (k === "bristlenose-palette" && value !== undefined ? value : null) };
}

describe("bootPalette", () => {
  it("PALETTES is the closed valid set", () => {
    expect([...PALETTES]).toEqual(["default", "edo"]);
  });

  describe("isPalette", () => {
    it("accepts only known palettes", () => {
      expect(isPalette("default")).toBe(true);
      expect(isPalette("edo")).toBe(true);
    });
    it("rejects unknown / malformed values", () => {
      // The exact case the boot-script regex used to accept (review Finding 2).
      expect(isPalette("edo2")).toBe(false);
      expect(isPalette("")).toBe(false);
      expect(isPalette(null)).toBe(false);
      expect(isPalette(42)).toBe(false);
    });
  });

  describe("readSavedPalette", () => {
    it("returns null when unset", () => {
      expect(readSavedPalette(makeStorage())).toBeNull();
    });
    it("parses the JSON-encoded store format", () => {
      expect(readSavedPalette(makeStorage('"edo"'))).toBe("edo");
    });
    it("accepts a bare legacy string", () => {
      expect(readSavedPalette(makeStorage("edo"))).toBe("edo");
    });
    it("returns null for an unknown stored value (no silent wrong-palette)", () => {
      expect(readSavedPalette(makeStorage('"edo2"'))).toBeNull();
      expect(readSavedPalette(makeStorage("garbage"))).toBeNull();
    });
  });

  describe("applyBootPalette", () => {
    it("sets data-color-theme for a valid saved palette", () => {
      const root = document.createElement("html");
      applyBootPalette(root, makeStorage('"edo"'));
      expect(root.getAttribute("data-color-theme")).toBe("edo");
    });
    it("leaves the server-injected attribute untouched when unset", () => {
      const root = document.createElement("html");
      root.setAttribute("data-color-theme", "edo"); // server default (desktop)
      applyBootPalette(root, makeStorage());
      expect(root.getAttribute("data-color-theme")).toBe("edo");
    });
    it("does not apply an unknown stored value", () => {
      const root = document.createElement("html");
      applyBootPalette(root, makeStorage('"edo2"'));
      expect(root.hasAttribute("data-color-theme")).toBe(false);
    });
  });
});
