/**
 * Tests for useAnchorReporter — reports the reader's position to the shell.
 *
 * What is worth pinning is the behaviour a reader would notice: reopening a
 * project lands where they were, a lens that keeps no position lands at the
 * top, and the shell isn't written to disk more often than the position
 * actually changes.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";

import { useAnchorReporter } from "./useAnchorReporter";
import { postAnchorChange } from "../shims/bridge";

vi.mock("../shims/bridge", () => ({
  postAnchorChange: vi.fn(),
}));

const posted = vi.mocked(postAnchorChange);

/** Put headings in the document at controlled scroll positions. */
function renderHeadings(entries: Array<{ id: string; top: number }>) {
  document.body.innerHTML = "";
  for (const { id, top } of entries) {
    const el = document.createElement("h3");
    el.id = id;
    el.getBoundingClientRect = () =>
      ({ top, bottom: top + 40, left: 0, right: 100,
         width: 100, height: 40, x: 0, y: top }) as DOMRect;
    document.body.appendChild(el);
  }
}

function installRafMock() {
  const raf = ((cb: FrameRequestCallback) => { cb(0); return 0; }) as typeof globalThis.requestAnimationFrame;
  const caf = (() => {}) as typeof globalThis.cancelAnimationFrame;
  globalThis.requestAnimationFrame = raf;
  globalThis.cancelAnimationFrame = caf;
  window.requestAnimationFrame = raf;
  window.cancelAnimationFrame = caf;
}

/** Scroll, then let the settle timer fire. */
function scrollAndSettle() {
  act(() => {
    window.dispatchEvent(new Event("scroll"));
    vi.advanceTimersByTime(500);
  });
}

beforeEach(() => {
  posted.mockClear();
  vi.useFakeTimers();
  installRafMock();
});

afterEach(() => {
  vi.useRealTimers();
  document.body.innerHTML = "";
});

describe("useAnchorReporter", () => {
  it("reports the heading the reader is under", () => {
    // Two themes scrolled past the top, one still below: the reader is under
    // the second.
    renderHeadings([
      { id: "theme-onboarding", top: -400 },
      { id: "theme-billing", top: -50 },
      { id: "theme-support", top: 600 },
    ]);
    renderHook(() => useAnchorReporter("/report/quotes/", true));

    scrollAndSettle();

    expect(posted).toHaveBeenLastCalledWith("quotes", "theme-billing");
  });

  it("reports the top of the page as null", () => {
    // Nothing has scrolled past the threshold yet.
    renderHeadings([
      { id: "theme-onboarding", top: 300 },
      { id: "theme-billing", top: 900 },
    ]);
    renderHook(() => useAnchorReporter("/report/quotes/", true));

    scrollAndSettle();

    expect(posted).toHaveBeenLastCalledWith("quotes", null);
  });

  it("counts section headings as well as themes", () => {
    // Sections and themes are the same UI object on this lens — both are
    // QuoteGroup headings — so watching only themes would make the Sections
    // half of the page always restore to the top.
    renderHeadings([{ id: "section-what-they-tried", top: -20 }]);
    renderHook(() => useAnchorReporter("/report/quotes/", true));

    scrollAndSettle();

    expect(posted).toHaveBeenLastCalledWith("quotes", "section-what-they-tried");
  });

  it("reads codebook framework headers", () => {
    renderHeadings([{ id: "codebook-fw-nielsen", top: -10 }]);
    renderHook(() => useAnchorReporter("/report/codebook/", true));

    scrollAndSettle();

    expect(posted).toHaveBeenLastCalledWith("codebook", "codebook-fw-nielsen");
  });

  it("clears the position on a lens that keeps none", () => {
    // Analysis restores to the top (decided 16 Aug 2026). It must say so
    // rather than stay quiet — otherwise the Quotes anchor the reader left
    // behind would still be on disk, and would be restored against Analysis.
    renderHeadings([{ id: "theme-billing", top: -50 }]);
    renderHook(() => useAnchorReporter("/report/analysis/", true));

    expect(posted).toHaveBeenCalledWith("analysis", null);
  });

  it("doesn't repeat a position that hasn't changed", () => {
    // The shell persists this to projects.json. Scrolling within one theme
    // fires many scroll events and must not cause many writes.
    renderHeadings([{ id: "theme-billing", top: -50 }]);
    renderHook(() => useAnchorReporter("/report/quotes/", true));

    scrollAndSettle();
    scrollAndSettle();
    scrollAndSettle();

    expect(posted).toHaveBeenCalledTimes(1);
  });

  it("does nothing outside the native shell", () => {
    // In a browser there is no shell to tell, and no reason to hold a scroll
    // listener on the page.
    renderHeadings([{ id: "theme-billing", top: -50 }]);
    renderHook(() => useAnchorReporter("/report/quotes/", false));

    scrollAndSettle();

    expect(posted).not.toHaveBeenCalled();
  });
  it("names the lens it is reporting for", () => {
    // route-change and anchor-change are independent messages, so a bare null
    // can't distinguish "back at the top of Quotes" from "left Quotes". Without
    // the lens, a switch away would clear a perfectly good remembered position.
    renderHeadings([{ id: "theme-billing", top: -50 }]);
    const { rerender } = renderHook(
      ({ path }) => useAnchorReporter(path, true),
      { initialProps: { path: "/report/quotes/" } },
    );
    scrollAndSettle();
    expect(posted).toHaveBeenLastCalledWith("quotes", "theme-billing");

    rerender({ path: "/report/analysis/" });
    expect(posted).toHaveBeenLastCalledWith("analysis", null);
  });
});
