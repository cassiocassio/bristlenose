import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { useIsDarkAppearance } from "./useIsDarkAppearance";

// jsdom ships no `matchMedia` at all (see frontend/src/test-setup.ts for the
// same story with Web Storage), so every test that wants the media-query path
// installs one. `setOsDark` then models a live OS appearance switch: it moves
// the value the query reports AND fires the change listeners, the way a real
// MediaQueryList does.
let listeners: Array<() => void> = [];
let osDark = false;

function installMatchMedia(matches: boolean) {
  listeners = [];
  osDark = matches;
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    writable: true,
    value: vi.fn((query: string) => ({
      get matches() {
        return osDark;
      },
      media: query,
      addEventListener: (_: string, fn: () => void) => listeners.push(fn),
      removeEventListener: (_: string, fn: () => void) => {
        listeners = listeners.filter((l) => l !== fn);
      },
      dispatchEvent: vi.fn(),
    })),
  });
}

function setOsDark(v: boolean) {
  osDark = v;
  for (const fire of [...listeners]) fire();
}

function removeMatchMedia() {
  delete (window as unknown as Record<string, unknown>).matchMedia;
}

beforeEach(() => {
  document.documentElement.removeAttribute("data-theme");
  removeMatchMedia();
});

afterEach(() => {
  document.documentElement.removeAttribute("data-theme");
  removeMatchMedia();
});

describe("useIsDarkAppearance", () => {
  // ── Browser serve mode: the picker forces a choice via data-theme ────────

  it("honours a forced data-theme=dark over a light OS", () => {
    installMatchMedia(false);
    document.documentElement.setAttribute("data-theme", "dark");
    const { result } = renderHook(() => useIsDarkAppearance());
    expect(result.current).toBe(true);
  });

  it("honours a forced data-theme=light over a dark OS", () => {
    installMatchMedia(true);
    document.documentElement.setAttribute("data-theme", "light");
    const { result } = renderHook(() => useIsDarkAppearance());
    expect(result.current).toBe(false);
  });

  it("repaints when the picker writes data-theme on a live page", async () => {
    installMatchMedia(false);
    const { result } = renderHook(() => useIsDarkAppearance());
    expect(result.current).toBe(false);

    act(() => {
      document.documentElement.setAttribute("data-theme", "dark");
    });

    // MutationObserver callbacks are delivered as a microtask.
    await waitFor(() => expect(result.current).toBe(true));
  });

  // ── Desktop embedded mode: no data-theme, ever ───────────────────────────

  it("falls back to prefers-color-scheme when no data-theme is set", () => {
    // The desktop app owns appearance natively (NSApp.appearance) and writes
    // no attribute — reading the attribute alone pinned this to light.
    installMatchMedia(true);
    const { result } = renderHook(() => useIsDarkAppearance());
    expect(result.current).toBe(true);
  });

  it("follows a live OS appearance switch with no data-theme present", async () => {
    installMatchMedia(false);
    const { result } = renderHook(() => useIsDarkAppearance());
    expect(result.current).toBe(false);

    // The native side no longer remounts the webview on an appearance change,
    // so the media-query listener is the only thing that repaints us.
    act(() => setOsDark(true));
    await waitFor(() => expect(result.current).toBe(true));
  });

  it("returns to the OS preference when the picker goes back to auto", async () => {
    installMatchMedia(true);
    document.documentElement.setAttribute("data-theme", "light");
    const { result } = renderHook(() => useIsDarkAppearance());
    expect(result.current).toBe(false);

    // "Auto" removes the attribute rather than setting a value.
    act(() => {
      document.documentElement.removeAttribute("data-theme");
    });
    await waitFor(() => expect(result.current).toBe(true));
  });

  // ── Environment robustness ───────────────────────────────────────────────

  it("does not throw where matchMedia is absent", () => {
    // jsdom, and any non-browser host. Absent reads as light.
    const { result } = renderHook(() => useIsDarkAppearance());
    expect(result.current).toBe(false);
  });

  it("unsubscribes from both signals on unmount", async () => {
    installMatchMedia(false);
    const { result, unmount } = renderHook(() => useIsDarkAppearance());
    expect(listeners.length).toBe(1);

    unmount();
    expect(listeners.length).toBe(0);

    // The MutationObserver is disconnected too — no post-unmount state update.
    document.documentElement.setAttribute("data-theme", "dark");
    await new Promise((r) => setTimeout(r, 0));
    expect(result.current).toBe(false);
  });
});
