import { describe, it, expect, vi, afterEach } from "vitest";
import { installNavigationShims } from "./navigation";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

afterEach(() => {
  vi.restoreAllMocks();
  delete (window as unknown as Record<string, unknown>).switchToTab;
  delete (window as unknown as Record<string, unknown>).scrollToAnchor;
  delete (window as unknown as Record<string, unknown>).navigateToSession;
});

function setupShims() {
  const navigateSpy = vi.fn();
  const scrollSpy = vi.fn();

  installNavigationShims(navigateSpy, scrollSpy);

  return { navigateSpy, scrollSpy };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("installNavigationShims", () => {
  it("installs switchToTab on window", () => {
    setupShims();
    expect(typeof window.switchToTab).toBe("function");
  });

  it("installs scrollToAnchor on window", () => {
    setupShims();
    expect(typeof window.scrollToAnchor).toBe("function");
  });

  it("installs navigateToSession on window", () => {
    setupShims();
    expect(typeof window.navigateToSession).toBe("function");
  });

  it("switchToTab('quotes') calls navigate('/report/quotes/')", () => {
    const { navigateSpy } = setupShims();
    window.switchToTab!("quotes");
    expect(navigateSpy).toHaveBeenCalledWith("/report/quotes/");
  });

  it("switchToTab('project') calls navigate('/report/')", () => {
    const { navigateSpy } = setupShims();
    window.switchToTab!("project");
    expect(navigateSpy).toHaveBeenCalledWith("/report/");
  });

  it("switchToTab with unknown tab defaults to /report/", () => {
    const { navigateSpy } = setupShims();
    window.switchToTab!("nonexistent");
    expect(navigateSpy).toHaveBeenCalledWith("/report/");
  });

  it("scrollToAnchor delegates to the provided callback", () => {
    const { scrollSpy } = setupShims();
    window.scrollToAnchor!("my-anchor", { block: "center" });
    expect(scrollSpy).toHaveBeenCalledWith("my-anchor", { block: "center" });
  });

  it("navigateToSession calls navigate with session path", () => {
    const { navigateSpy } = setupShims();
    window.navigateToSession!("s1");
    expect(navigateSpy).toHaveBeenCalledWith("/report/sessions/s1");
  });

  it("navigateToSession with anchor calls scroll", () => {
    const { navigateSpy, scrollSpy } = setupShims();
    window.navigateToSession!("s1", "t-123");
    expect(navigateSpy).toHaveBeenCalledWith("/report/sessions/s1");
    expect(scrollSpy).toHaveBeenCalledWith("t-123", {
      block: "center",
      highlight: true,
    });
  });
});
