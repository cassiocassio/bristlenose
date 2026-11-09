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

import { ANCHOR_SELECTORS, useAnchorReporter } from "./useAnchorReporter";
import { postAnchorChange } from "../shims/bridge";

vi.mock("../shims/bridge", () => ({
  postAnchorChange: vi.fn(),
}));

const posted = vi.mocked(postAnchorChange);

interface Entry {
  id: string;
  top: number;
  /** The element's rendered height; jsdom measures every rect as all-zero, so it is always stubbed. */
  height?: number;
  /** `tag.class`, default an `<h3>`. */
  as?: string;
  /** Put it inside a `<section hidden>`. */
  hidden?: boolean;
}

/** Put elements in the document at controlled scroll positions. */
function renderHeadings(entries: Entry[]) {
  document.body.innerHTML = "";
  for (const { id, top, height = 40, as = "h3", hidden = false } of entries) {
    const [tag, ...classes] = as.split(".");
    const el = document.createElement(tag);
    el.id = id;
    if (classes.length) el.className = classes.join(" ");
    el.getBoundingClientRect = () =>
      ({ top, bottom: top + height, left: 0, right: 100,
         width: 100, height, x: 0, y: top }) as DOMRect;
    if (hidden) {
      const section = document.createElement("section");
      section.hidden = true;
      section.appendChild(el);
      document.body.appendChild(section);
    } else {
      document.body.appendChild(el);
    }
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

  it("reports the quote card the reader is on, and the group heading above the first card", () => {
    // Decision #182: Quotes comes back to the quote, not to its group.
    renderHeadings([
      { id: "theme-billing", top: -300 },
      { id: "q-p1-10", top: -200, height: 180, as: "blockquote.quote-card" },
      { id: "q-p2-4", top: 60, height: 180, as: "blockquote.quote-card" },
      { id: "q-p3-7", top: 400, height: 180, as: "blockquote.quote-card" },
    ]);
    renderHook(() => useAnchorReporter("/report/quotes/", true));
    scrollAndSettle();
    expect(posted).toHaveBeenLastCalledWith("quotes", "q-p2-4");

    // Just past the heading, above its first card: the group.
    posted.mockClear();
    renderHeadings([
      { id: "theme-billing", top: 20 },
      { id: "q-p1-10", top: 300, height: 180, as: "blockquote.quote-card" },
    ]);
    scrollAndSettle();
    expect(posted).toHaveBeenLastCalledWith("quotes", "theme-billing");
  });

  it("skips an element inside a hidden ancestor", () => {
    // A Signals card on a place the page is not showing measures with a top of
    // 0 and would otherwise always win.
    renderHeadings([
      { id: "signal-theme-theme-1--delight", top: -100, as: "div.signal-card" },
      { id: "signal-theme-theme-2--frustration", top: 0, as: "div.signal-card", hidden: true },
    ]);
    renderHook(() => useAnchorReporter("/report/signals/", true));
    scrollAndSettle();
    expect(posted).toHaveBeenLastCalledWith("signals", "signal-theme-theme-1--delight");
  });

  it("skips an element with no height", () => {
    // A quote card collapsing as it is hidden ends at zero height.
    renderHeadings([
      { id: "q-p1-10", top: -100, height: 180, as: "blockquote.quote-card" },
      { id: "q-p1-11", top: 0, height: 0, as: "blockquote.quote-card" },
    ]);
    renderHook(() => useAnchorReporter("/report/quotes/", true));
    scrollAndSettle();
    expect(posted).toHaveBeenLastCalledWith("quotes", "q-p1-10");
  });

  it("reads codebook code rows, and not the framework headers the v1 lens had", () => {
    // `codebook-fw-` was the v1 lens's id. The v2 lens never rendered it, so
    // from 31 Aug 2026 Codebook reported nothing and always came back at the
    // top. Library preview rows (negative ids) are not the study's codes.
    renderHeadings([
      { id: "codebook-fw-nielsen", top: -20, as: "div.tag-row" },
      { id: "code-12", top: -10, as: "div.tag-row" },
      { id: "code--3", top: 0, as: "div.tag-row" },
    ]);
    renderHook(() => useAnchorReporter("/report/codebook/", true));

    scrollAndSettle();

    expect(posted).toHaveBeenLastCalledWith("codebook", "code-12");
    expect(posted).not.toHaveBeenCalledWith("codebook", "codebook-fw-nielsen");
  });

  it("reports a transcript paragraph as a place, with its session", () => {
    renderHeadings([
      { id: "t-0", top: -600, as: "div.transcript-segment" },
      { id: "t-66", top: 40, as: "div.transcript-segment" },
      { id: "t-90", top: 500, as: "div.transcript-segment" },
    ]);
    renderHook(() => useAnchorReporter("/report/sessions/s1", true));
    scrollAndSettle();
    expect(posted).toHaveBeenLastCalledWith("sessions", "s1#t-66");
  });

  it("reports the top of a transcript as null, so native keeps the session alone", () => {
    renderHeadings([{ id: "t-0", top: 300, as: "div.transcript-segment" }]);
    renderHook(() => useAnchorReporter("/report/sessions/s1", true));
    scrollAndSettle();
    expect(posted).toHaveBeenLastCalledWith("sessions", null);
  });

  it("keeps no position on the Sessions grid, and holds no listener there", () => {
    renderHeadings([{ id: "t-66", top: 40, as: "div.transcript-segment" }]);
    const add = vi.spyOn(window, "addEventListener");
    renderHook(() => useAnchorReporter("/report/sessions/", true));
    expect(posted).toHaveBeenCalledWith("sessions", null);
    expect(add.mock.calls.some(([type]) => type === "scroll")).toBe(false);
    add.mockRestore();
  });

  it("clears the position on a lens that keeps none", () => {
    // Project and Screens restore to the top (decision #182, 9 Nov 2026; until
    // then Signals did too, decided 16 Aug). They must say so rather than stay
    // quiet — otherwise the Quotes anchor the reader left behind would still be
    // on disk, and would be restored against the wrong lens.
    renderHeadings([{ id: "theme-billing", top: -50 }]);
    const { rerender } = renderHook(
      ({ path }) => useAnchorReporter(path, true),
      { initialProps: { path: "/report/" } },
    );
    expect(posted).toHaveBeenLastCalledWith("", null);

    rerender({ path: "/report/screens/" });
    expect(posted).toHaveBeenLastCalledWith("screens", null);
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

    rerender({ path: "/report/screens/" });
    expect(posted).toHaveBeenLastCalledWith("screens", null);
  });

  it("exports one selector per lens that keeps a position", () => {
    // The selector-meets-DOM pins in the components' own tests read this table.
    expect(Object.keys(ANCHOR_SELECTORS).sort()).toEqual(["codebook", "quotes", "sessions", "signals"]);
  });
});
