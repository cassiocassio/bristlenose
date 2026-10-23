import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import contractJson from "../../../tests/fixtures/report-prefs-contract.json";
import { MIRRORED_PREF_KEYS, MIRRORED_PREF_PREFIXES, storePref } from "./nativePrefs";

const w = window as unknown as Record<string, unknown>;
let postMessage: ReturnType<typeof vi.fn>;

beforeEach(() => {
  localStorage.clear();
  postMessage = vi.fn();
  w.webkit = { messageHandlers: { navigation: { postMessage } } };
});

afterEach(() => {
  delete w.webkit;
});

describe("storePref (R89)", () => {
  it("lists exactly the contract's keys, which BridgeHandler.reportPrefKeys also asserts", () => {
    expect([...MIRRORED_PREF_KEYS].sort()).toEqual([...contractJson.keys].sort());
    expect([...MIRRORED_PREF_PREFIXES].sort()).toEqual([...contractJson.key_prefixes].sort());
  });

  it("writes a listed key and hands it to the Mac app", () => {
    storePref("bn-toc-width", "300");
    expect(localStorage.getItem("bn-toc-width")).toBe("300");
    expect(postMessage).toHaveBeenCalledWith({ type: contractJson.message_type, key: "bn-toc-width", value: "300" });
  });

  it("keeps an unlisted key to this page", () => {
    storePref("bn-inspector-source", "cb-1");
    expect(localStorage.getItem("bn-inspector-source")).toBe("cb-1");
    expect(postMessage).not.toHaveBeenCalled();
  });

  it("hands over a key that matches a listed prefix (the quote grouping)", () => {
    storePref("bristlenose-quote-grouping-1", "session");
    expect(postMessage).toHaveBeenCalledWith({ type: "report-pref", key: "bristlenose-quote-grouping-1", value: "session" });
  });

  it("keeps a value the viewer never chose to this page", () => {
    storePref("bn-inspector-height", "352", false);
    expect(localStorage.getItem("bn-inspector-height")).toBe("352");
    expect(postMessage).not.toHaveBeenCalled();
  });

  it("removes with null, and tells the app so", () => {
    localStorage.setItem("bristlenose-zoom", "1.2");
    storePref("bristlenose-zoom", null);
    expect(localStorage.getItem("bristlenose-zoom")).toBeNull();
    expect(postMessage).toHaveBeenCalledWith({ type: "report-pref", key: "bristlenose-zoom", value: null });
  });

  it("posts a rewrite of the same value once", () => {
    storePref("bn-tags-width", "300");
    storePref("bn-tags-width", "300");
    storePref("bn-tags-width", "310");
    expect(postMessage).toHaveBeenCalledTimes(2);
  });

  it("judges a change against the storage every window on the project shares", () => {
    // Window A posts 300; window B, same partition, posts 400; A goes back to 300.
    storePref("bn-toc-width", "300");
    localStorage.setItem("bn-toc-width", "400");
    storePref("bn-toc-width", "300");
    expect(postMessage).toHaveBeenCalledTimes(2);
    expect(postMessage).toHaveBeenLastCalledWith({ type: "report-pref", key: "bn-toc-width", value: "300" });
  });

  it("outside the app writes storage and posts nothing, without throwing", () => {
    delete w.webkit;
    expect(() => storePref("bn-toc-open", "true")).not.toThrow();
    expect(localStorage.getItem("bn-toc-open")).toBe("true");
  });

  it("still posts when storage refuses the write", () => {
    const spy = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    try {
      storePref("bn-toc-open", "true");
    } finally {
      spy.mockRestore();
    }
    expect(postMessage).toHaveBeenCalledWith({ type: "report-pref", key: "bn-toc-open", value: "true" });
  });
});
