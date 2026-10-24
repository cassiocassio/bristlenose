import { afterEach, describe, expect, it, vi } from "vitest";
import {
  REPORT_RETRY_KEY,
  clearReportRetry,
  markReportRetry,
  reportWasRetried,
  retryReport,
} from "./reportRetry";

describe("the report's retry mark", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    sessionStorage.clear();
  });

  it("marks, reads and clears one flag that carries nothing else", () => {
    expect(reportWasRetried()).toBe(false);
    markReportRetry();
    expect(reportWasRetried()).toBe(true);
    expect(sessionStorage.getItem(REPORT_RETRY_KEY)).toBe("1");
    expect(sessionStorage.length).toBe(1);
    clearReportRetry();
    expect(reportWasRetried()).toBe(false);
  });

  it("Retry marks before it reloads", () => {
    const reload = vi.fn(() => expect(reportWasRetried()).toBe(true));
    const original = window.location;
    Object.defineProperty(window, "location", {
      configurable: true,
      value: { ...original, reload },
    });
    try {
      retryReport();
      expect(reload).toHaveBeenCalledOnce();
    } finally {
      Object.defineProperty(window, "location", { configurable: true, value: original });
    }
  });

  it("storage that throws reads as not retried, and marking or clearing never throws", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("denied");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("denied");
    });
    vi.spyOn(Storage.prototype, "removeItem").mockImplementation(() => {
      throw new Error("denied");
    });
    expect(() => markReportRetry()).not.toThrow();
    expect(() => clearReportRetry()).not.toThrow();
    expect(reportWasRetried()).toBe(false);
  });
});
