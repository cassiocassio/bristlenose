import { describe, it, expect, vi, afterEach } from "vitest";
import { redirectHashToPathname } from "./hashRedirect";

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("redirectHashToPathname", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    // Reset URL
    window.history.replaceState(null, "", "/report/");
  });

  it("redirects #quotes to /report/quotes/", () => {
    window.history.replaceState(null, "", "/report/#quotes");
    const spy = vi.spyOn(window.history, "replaceState");
    redirectHashToPathname();
    expect(spy).toHaveBeenCalledWith(null, "", "/report/quotes/");
  });

  it("redirects #sessions to /report/sessions/", () => {
    window.history.replaceState(null, "", "/report/#sessions");
    const spy = vi.spyOn(window.history, "replaceState");
    redirectHashToPathname();
    expect(spy).toHaveBeenCalledWith(null, "", "/report/sessions/");
  });

  it("redirects #project to /report/", () => {
    window.history.replaceState(null, "", "/report/#project");
    const spy = vi.spyOn(window.history, "replaceState");
    redirectHashToPathname();
    expect(spy).toHaveBeenCalledWith(null, "", "/report/");
  });

  it("redirects #settings to /report/settings/", () => {
    window.history.replaceState(null, "", "/report/#settings");
    const spy = vi.spyOn(window.history, "replaceState");
    redirectHashToPathname();
    expect(spy).toHaveBeenCalledWith(null, "", "/report/settings/");
  });

  it("leaves non-tab hashes alone", () => {
    window.history.replaceState(null, "", "/report/#t-123");
    const spy = vi.spyOn(window.history, "replaceState");
    redirectHashToPathname();
    expect(spy).not.toHaveBeenCalled();
  });

  it("does nothing when no hash", () => {
    window.history.replaceState(null, "", "/report/");
    const spy = vi.spyOn(window.history, "replaceState");
    redirectHashToPathname();
    expect(spy).not.toHaveBeenCalled();
  });

  it("leaves anchor-like hashes alone", () => {
    window.history.replaceState(null, "", "/report/#sections");
    const spy = vi.spyOn(window.history, "replaceState");
    redirectHashToPathname();
    expect(spy).not.toHaveBeenCalled();
  });
});
