import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  DEFAULT_PREFS,
  DISPLAY_KEYS,
  _resetDisplayPrefs,
  applySavedDisplayPrefs,
  getDisplayPrefs,
  setDisplayPref,
  subscribe,
} from "./DisplayPrefsStore";

const w = window as unknown as Record<string, unknown>;
let postMessage: ReturnType<typeof vi.fn>;

const attr = (name: string) => document.documentElement.getAttribute(name);

beforeEach(() => {
  localStorage.clear();
  postMessage = vi.fn();
  w.webkit = { messageHandlers: { navigation: { postMessage } } };
  _resetDisplayPrefs();
});

afterEach(() => {
  delete w.webkit;
});

describe("DisplayPrefsStore", () => {
  it("boots with columns, Normal density and long quotes broken (on by default)", () => {
    expect(getDisplayPrefs()).toEqual({ layout: "columns", density: 0.5, breaks: "on" });
    expect(DEFAULT_PREFS.breaks).toBe("on");
  });

  it("sets the three attributes on <html> when a pref changes", () => {
    setDisplayPref("layout", "single");
    setDisplayPref("density", 0);
    setDisplayPref("breaks", "on");
    expect(attr("data-bn-layout")).toBe("single");
    expect(attr("data-bn-density")).toBe("custom");
    expect(attr("data-bn-breaks")).toBe("on");
  });

  it("saves a choice and hands it to the Mac app", () => {
    setDisplayPref("density", 1);
    expect(localStorage.getItem(DISPLAY_KEYS.density)).toBe("1");
    expect(postMessage).toHaveBeenCalledWith({
      type: "report-pref",
      key: "bn-display-density",
      value: "1",
    });
  });

  it("puts the saved values back before first paint, and does not write them again", () => {
    localStorage.setItem(DISPLAY_KEYS.layout, "single");
    localStorage.setItem(DISPLAY_KEYS.breaks, "on");
    applySavedDisplayPrefs();
    expect(getDisplayPrefs()).toEqual({ layout: "single", density: 0.5, breaks: "on" });
    expect(attr("data-bn-layout")).toBe("single");
    expect(postMessage).not.toHaveBeenCalled();
  });

  it("ignores a stored value that is not allowed, keeping the default for that setting", () => {
    localStorage.setItem(DISPLAY_KEYS.layout, "triple");
    localStorage.setItem(DISPLAY_KEYS.density, "tiny");
    localStorage.setItem(DISPLAY_KEYS.breaks, "on");
    applySavedDisplayPrefs();
    expect(getDisplayPrefs()).toEqual({ layout: "columns", density: 0.5, breaks: "on" });
  });

  it("refuses to set a value that is not allowed", () => {
    // @ts-expect-error — the type forbids it; the store must too, for a caller that slips past
    setDisplayPref("layout", "triple");
    expect(getDisplayPrefs().layout).toBe("columns");
    expect(localStorage.getItem(DISPLAY_KEYS.layout)).toBeNull();
    expect(postMessage).not.toHaveBeenCalled();
  });

  it("re-reads storage on every applySaved, so a reopened menu shows the saved value", () => {
    setDisplayPref("layout", "single");
    localStorage.setItem(DISPLAY_KEYS.layout, "columns");
    applySavedDisplayPrefs();
    expect(getDisplayPrefs().layout).toBe("columns");
  });

  it("notifies once per real change and not for a no-op", () => {
    const listener = vi.fn();
    const off = subscribe(listener);
    setDisplayPref("density", 0.2);
    setDisplayPref("density", 0.2);
    expect(listener).toHaveBeenCalledTimes(1);
    off();
  });
});

describe("density is continuous", () => {
  const cssVar = () => document.documentElement.style.getPropertyValue("--bn-density-s");

  it("Normal, exactly, applies no density rule: attribute normal, no variable", () => {
    setDisplayPref("density", 0.5);
    expect(attr("data-bn-density")).toBe("normal");
    expect(cssVar()).toBe("");
  });

  it("any other value is custom, and the variable is how far from Normal, -1 to 1", () => {
    setDisplayPref("density", 0);
    expect(attr("data-bn-density")).toBe("custom");
    expect(Number(cssVar())).toBe(-1);
    setDisplayPref("density", 1);
    expect(Number(cssVar())).toBe(1);
    setDisplayPref("density", 0.75);
    expect(Number(cssVar())).toBeCloseTo(0.5);
    setDisplayPref("density", 0.5);
    expect(cssVar()).toBe("");
  });

  it("clamps to 0..1 and rounds to two places, so a dragged slider stores a short value", () => {
    setDisplayPref("density", 7);
    expect(getDisplayPrefs().density).toBe(1);
    setDisplayPref("density", -3);
    expect(getDisplayPrefs().density).toBe(0);
    setDisplayPref("density", 0.3333333);
    expect(getDisplayPrefs().density).toBe(0.33);
    expect(localStorage.getItem(DISPLAY_KEYS.density)).toBe("0.33");
  });

  it("refuses a value that is not a number", () => {
    setDisplayPref("density", 0.2);
    // @ts-expect-error — the type forbids it; the store must too
    setDisplayPref("density", "roomy");
    setDisplayPref("density", Number.NaN);
    expect(getDisplayPrefs().density).toBe(0.2);
  });

  it("loads the three words the first build stored, as the stops they named", () => {
    for (const [word, value] of [["compact", 0], ["normal", 0.5], ["spacious", 1]] as const) {
      localStorage.setItem(DISPLAY_KEYS.density, word);
      applySavedDisplayPrefs();
      expect(getDisplayPrefs().density).toBe(value);
    }
  });

  it("a stored word that is an object property name is just a bad value, never a crash", () => {
    for (const bad of ["constructor", "toString", "__proto__", "hasOwnProperty"]) {
      localStorage.setItem(DISPLAY_KEYS.density, bad);
      applySavedDisplayPrefs();
      expect(getDisplayPrefs().density).toBe(0.5);
    }
  });

  it("loads a saved number, and ignores a malformed one", () => {
    localStorage.setItem(DISPLAY_KEYS.density, "0.35");
    applySavedDisplayPrefs();
    expect(getDisplayPrefs().density).toBe(0.35);
    localStorage.setItem(DISPLAY_KEYS.density, "NaN");
    applySavedDisplayPrefs();
    expect(getDisplayPrefs().density).toBe(0.5);
  });
});

describe("another window changing the saved value", () => {
  it("is picked up, so a choice equal to the stale in-memory value still saves", () => {
    setDisplayPref("layout", "columns"); // no-op, memory already columns
    // Another window saves Single.
    localStorage.setItem(DISPLAY_KEYS.layout, "single");
    window.dispatchEvent(new StorageEvent("storage", { key: DISPLAY_KEYS.layout, newValue: "single" }));
    expect(getDisplayPrefs().layout).toBe("single");
    setDisplayPref("layout", "columns");
    expect(localStorage.getItem(DISPLAY_KEYS.layout)).toBe("columns");
  });
});
