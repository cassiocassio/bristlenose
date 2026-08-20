/**
 * Tests for useKeyboardShortcuts — key dispatch, guards, bulk actions.
 *
 * These tests exercise the hook through the full provider tree
 * (PlayerProvider + FocusProvider + Router) and verify keydown
 * events dispatch correct actions.
 */

import { renderHook, act } from "@testing-library/react";
import { createElement, useState, useCallback, Fragment, type ReactNode } from "react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { FocusProvider, useFocus } from "../contexts/FocusContext";
import { PlayerProvider } from "../contexts/PlayerContext";
import {
  resetStore,
  useQuotesStore,
  addTag,
  getLastUsedTag,
} from "../contexts/QuotesContext";
import { resetSidebarStore } from "../contexts/SidebarStore";
import { resetInspectorStore } from "../contexts/InspectorStore";
import { isFocusMode, _resetFocusMode } from "../contexts/FocusModeStore";
import { useKeyboardShortcuts } from "./useKeyboardShortcuts";
import { putTags } from "../utils/api";

// Mock API calls (addTag calls putTags internally).
vi.mock("../utils/api", () => ({
  apiGet: vi.fn().mockResolvedValue({ video_map: {} }),
  putHidden: vi.fn(),
  putStarred: vi.fn(),
  putEdits: vi.fn(),
  putTags: vi.fn(),
  putDeletedBadges: vi.fn(),
  acceptProposal: vi.fn().mockResolvedValue(undefined),
  denyProposal: vi.fn().mockResolvedValue(undefined),
}));

// Mock embedded detection — default false (browser); flip per-test. The house
// pattern (SidebarLayout.test.tsx): mock the module, never toggle the global —
// isEmbedded() memoises on first call.
let mockEmbedded = false;
vi.mock("../utils/embedded", () => ({
  isEmbedded: () => mockEmbedded,
}));

/**
 * Consumer component that exposes focus context + installs keyboard shortcuts.
 */
function TestConsumer({
  onHelpToggle,
  captureCtx,
}: {
  onHelpToggle?: () => void;
  captureCtx: (ctx: ReturnType<typeof useFocus>) => void;
}) {
  const ctx = useFocus();
  captureCtx(ctx);

  const [helpOpen, setHelpOpen] = useState(false);
  const toggleHelp = useCallback(() => {
    setHelpOpen((prev) => !prev);
    onHelpToggle?.();
  }, [onHelpToggle]);

  useKeyboardShortcuts({
    helpModalOpen: helpOpen,
    onToggleHelp: toggleHelp,
  });

  return null;
}

function renderWithProviders(
  onHelpToggle?: () => void,
  initialRoute = "/report/quotes/",
) {
  let ctx: ReturnType<typeof useFocus> | null = null;

  function Wrapper() {
    return createElement(
      PlayerProvider,
      null,
      createElement(
        FocusProvider,
        null,
        createElement(TestConsumer, {
          onHelpToggle,
          captureCtx: (c: ReturnType<typeof useFocus>) => {
            ctx = c;
          },
        }),
      ),
    );
  }

  const routePath = initialRoute.replace(/\/$/, "") || "/report/quotes";
  const routes = [{ path: routePath, element: createElement(Wrapper) }];
  const router = createMemoryRouter(routes, {
    initialEntries: [initialRoute],
  });

  // ONE render for the whole harness. `RouterProvider` does not render its
  // children, so the router tree and the store hook have to be siblings under
  // a fragment rather than nested. Mounting the router twice (the shape this
  // replaced) installed `useKeyboardShortcuts`' document keydown listener
  // twice, so every bare-key handler ran twice per dispatch and post-keypress
  // state was unobservable — a toggle always flipped back. It also left the
  // first tree mounted after `unmount()`, since only the second render's
  // teardown was returned.
  const result = renderHook(() => useQuotesStore(), {
    wrapper: ({ children }: { children: ReactNode }) =>
      createElement(
        Fragment,
        null,
        createElement(RouterProvider, { router }),
        children,
      ),
  });

  return {
    getCtx: () => ctx!,
    storeResult: result,
    unmount: result.unmount,
  };
}

/**
 * Give the named quotes real boxes, and return a teardown.
 *
 * jsdom reports every `getBoundingClientRect()` as zero, which `readCardRects`
 * correctly reads as "not laid out" and drops — so a test of the geometric
 * path has to supply geometry or it silently exercises the fallback instead.
 * `scrollIntoView` is stubbed because jsdom doesn't implement it and `setFocus`
 * calls it on the next frame.
 */
function layout(boxes: Record<string, { x: number; y: number }>) {
  const els: HTMLElement[] = [];
  for (const [id, { x, y }] of Object.entries(boxes)) {
    const el = document.createElement("blockquote");
    el.id = id;
    el.getBoundingClientRect = () =>
      ({
        left: x, top: y, width: 200, height: 100,
        right: x + 200, bottom: y + 100, x, y,
        toJSON: () => ({}),
      }) as DOMRect;
    el.scrollIntoView = () => {};
    document.body.appendChild(el);
    els.push(el);
  }
  return () => els.forEach((el) => el.remove());
}

function pressKey(key: string, options: Partial<KeyboardEventInit> = {}) {
  const event = new KeyboardEvent("keydown", {
    key,
    bubbles: true,
    cancelable: true,
    ...options,
  });
  document.dispatchEvent(event);
  // Returned so callers can assert on `defaultPrevented` — the only way to
  // tell "the handler declined this key" from "the handler ran and no state
  // happened to change", which is exactly the off-lens case.
  return event;
}

// ── Tests ────────────────────────────────────────────────────────────────

describe("useKeyboardShortcuts", () => {
  beforeEach(() => {
    resetStore();
    resetSidebarStore();
    resetInspectorStore();
    document.body.innerHTML = "";
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("editing guard", () => {
    it("ignores keys when an input is focused", () => {
      const input = document.createElement("input");
      document.body.appendChild(input);
      input.focus();

      const { getCtx, unmount } = renderWithProviders();
      act(() => {
        getCtx().registerVisibleQuoteIds("test", ["q-1"]);
      });

      pressKey("j");
      expect(getCtx().focusedId).toBeNull();

      unmount();
    });

    it("ignores keys when a textarea is focused", () => {
      const textarea = document.createElement("textarea");
      document.body.appendChild(textarea);
      textarea.focus();

      const { getCtx, unmount } = renderWithProviders();
      act(() => {
        getCtx().registerVisibleQuoteIds("test", ["q-1"]);
      });

      pressKey("j");
      expect(getCtx().focusedId).toBeNull();

      unmount();
    });

    it("ignores keys when contenteditable is focused", () => {
      const div = document.createElement("div");
      div.contentEditable = "true";
      document.body.appendChild(div);
      div.focus();

      const { getCtx, unmount } = renderWithProviders();
      act(() => {
        getCtx().registerVisibleQuoteIds("test", ["q-1"]);
      });

      pressKey("j");
      expect(getCtx().focusedId).toBeNull();

      unmount();
    });
  });

  describe("navigation", () => {
    it("j focuses first quote when no focus", () => {
      const { getCtx, unmount } = renderWithProviders();
      act(() => {
        getCtx().registerVisibleQuoteIds("test", ["q-1", "q-2"]);
      });

      act(() => pressKey("j"));
      expect(getCtx().focusedId).toBe("q-1");

      unmount();
    });

    it("k focuses last quote when no focus", () => {
      const { getCtx, unmount } = renderWithProviders();
      act(() => {
        getCtx().registerVisibleQuoteIds("test", ["q-1", "q-2"]);
      });

      act(() => pressKey("k"));
      expect(getCtx().focusedId).toBe("q-2");

      unmount();
    });

    it("arrows decline the key when nothing is measurable", () => {
      // jsdom's zero rects are the same shape as a grid that hasn't laid out
      // yet. Entering from the *registry* here is what let the arrow hand
      // focus back to an unmeasurable card forever — so the right answer is
      // to move nothing AND leave the page scroll alone.
      const { getCtx, unmount } = renderWithProviders();
      act(() => {
        getCtx().registerVisibleQuoteIds("test", ["q-1", "q-2"]);
      });

      let event!: KeyboardEvent;
      act(() => {
        event = pressKey("ArrowDown");
      });
      expect(getCtx().focusedId).toBeNull();
      expect(event.defaultPrevented).toBe(false);

      unmount();
    });

    it("arrows enter at reading-order start/end once the grid is laid out", () => {
      const { getCtx, unmount } = renderWithProviders();
      const cleanup = layout({ "q-1": { x: 0, y: 0 }, "q-2": { x: 0, y: 200 } });
      act(() => {
        getCtx().registerVisibleQuoteIds("test", ["q-1", "q-2"]);
      });

      act(() => pressKey("ArrowDown"));
      expect(getCtx().focusedId).toBe("q-1");

      act(() => pressKey("Escape"));
      act(() => pressKey("ArrowUp"));
      expect(getCtx().focusedId).toBe("q-2");

      cleanup();
      unmount();
    });
  });

  // The arrows are geometric and j/k are DOM order. In one column they agree,
  // which is why the split went unnoticed for so long — so every test here
  // lays out TWO lanes, where DOM order and geometry genuinely disagree.
  //
  //   lane 0      lane 1
  //   q-1         q-2
  //   q-3
  //
  // DOM order is q-1, q-2, q-3. From q-1: `j` → q-2 (to the right), `↓` → q-3.
  describe("arrows are geometric, j/k are DOM order", () => {
    const TWO_LANES = { "q-1": { x: 0, y: 0 }, "q-2": { x: 300, y: 0 }, "q-3": { x: 0, y: 200 } };

    function start() {
      const h = renderWithProviders();
      const cleanup = layout(TWO_LANES);
      act(() => {
        h.getCtx().registerVisibleQuoteIds("test", ["q-1", "q-2", "q-3"]);
        h.getCtx().setFocus("q-1", { scroll: false });
      });
      return { ...h, done: () => { cleanup(); h.unmount(); } };
    }

    it("ArrowDown moves down the lane, not to the next quote in DOM order", () => {
      const { getCtx, done } = start();
      act(() => pressKey("ArrowDown"));
      expect(getCtx().focusedId).toBe("q-3");
      done();
    });

    it("ArrowRight crosses into the next lane", () => {
      const { getCtx, done } = start();
      act(() => pressKey("ArrowRight"));
      expect(getCtx().focusedId).toBe("q-2");
      done();
    });

    it("ArrowLeft comes back", () => {
      const { getCtx, done } = start();
      act(() => pressKey("ArrowRight"));
      act(() => pressKey("ArrowLeft"));
      expect(getCtx().focusedId).toBe("q-1");
      done();
    });

    it("ArrowRight does nothing at the last lane — no wrap", () => {
      const { getCtx, done } = start();
      act(() => pressKey("ArrowRight"));
      act(() => pressKey("ArrowRight"));
      expect(getCtx().focusedId).toBe("q-2");
      done();
    });

    it("j still follows DOM order across lanes", () => {
      const { getCtx, done } = start();
      act(() => pressKey("j"));
      expect(getCtx().focusedId).toBe("q-2");
      done();
    });

    it("Shift+ArrowDown extends along the geometry, matching the bare arrow", () => {
      const { getCtx, done } = start();
      act(() => pressKey("ArrowDown", { shiftKey: true }));
      expect(getCtx().focusedId).toBe("q-3");
      expect([...getCtx().selectedIds].sort()).toEqual(["q-1", "q-3"]);
      done();
    });

    it("does not claim the key at the edge of the grid — page scroll survives", () => {
      const { getCtx, done } = start();
      // q-1 is top-left; there is nothing above it.
      let event!: KeyboardEvent;
      act(() => {
        event = pressKey("ArrowUp");
      });
      expect(getCtx().focusedId).toBe("q-1");
      expect(event.defaultPrevented).toBe(false);
      done();
    });

    it("declines an arrow another control already claimed", () => {
      // The sidebar resize separator handles ←/→ with preventDefault but no
      // stopPropagation, so before the guard one keypress resized the sidebar
      // *and* moved the quote cursor *and* scrolled the page.
      const { getCtx, done } = start();
      act(() => {
        const event = new KeyboardEvent("keydown", {
          key: "ArrowRight",
          bubbles: true,
          cancelable: true,
        });
        event.preventDefault(); // what useDragResize already did
        document.dispatchEvent(event);
      });
      expect(getCtx().focusedId).toBe("q-1");
      done();
    });

    it("Shift+arrow recovers from an unmeasurable cursor instead of stalling on it", () => {
      // Both callers share the recovery, not just the scorer. When only
      // moveFocusSpatial had it, Shift+arrow on an unmeasurable cursor
      // selected the invisible quote and *stayed put* — every subsequent
      // press repeating it. Now the cursor recovers to a real quote.
      //
      // Known residual, deliberately not asserted away: the stale cursor is
      // still seeded into the selection, because `extendTo` always selects
      // the quote it starts from. `Shift+j`/`Shift+k` do exactly the same on
      // their own stale-index path, so this is shared, pre-existing
      // behaviour rather than something the geometric path introduced.
      const h = renderWithProviders();
      const cleanup = layout({ "q-1": { x: 0, y: 0 }, "q-3": { x: 0, y: 200 } });
      act(() => {
        // q-2 is registered but never laid out.
        h.getCtx().registerVisibleQuoteIds("test", ["q-1", "q-2", "q-3"]);
        h.getCtx().setFocus("q-2", { scroll: false });
      });

      act(() => pressKey("ArrowDown", { shiftKey: true }));
      expect(h.getCtx().focusedId).not.toBe("q-2");
      expect(h.getCtx().focusedId).toBe("q-1");

      cleanup();
      h.unmount();
    });
  });

  // The quote keys are gated on the Quotes lens. Focus is a logical cursor
  // that survives route changes by design, so an ungated handler stays live
  // everywhere else — swallowing the page scroll on Transcripts/Analysis and
  // mutating a quote the user has navigated away from. The registry is
  // deliberately still populated in these tests: a stale id list is precisely
  // the state the guard has to be safe in.
  describe("route guard — quote keys are inert off the quotes lens", () => {
    const OFF_LENS = "/report/sessions/s1";

    it("j does not move focus", () => {
      const { getCtx, unmount } = renderWithProviders(undefined, OFF_LENS);
      act(() => {
        getCtx().registerVisibleQuoteIds("test", ["q-1", "q-2"]);
      });

      act(() => pressKey("j"));
      expect(getCtx().focusedId).toBeNull();

      unmount();
    });

    it("ArrowDown leaves the page scroll intact", () => {
      const { getCtx, unmount } = renderWithProviders(undefined, OFF_LENS);
      act(() => {
        getCtx().registerVisibleQuoteIds("test", ["q-1", "q-2"]);
      });

      let event!: KeyboardEvent;
      act(() => {
        event = pressKey("ArrowDown");
      });
      expect(event.defaultPrevented).toBe(false);

      unmount();
    });

    it("s does not star the quote that was focused before navigating away", () => {
      const { getCtx, storeResult, unmount } = renderWithProviders(
        undefined,
        OFF_LENS,
      );
      act(() => {
        getCtx().registerVisibleQuoteIds("test", ["q-1"]);
        getCtx().setFocus("q-1", { scroll: false });
      });

      act(() => pressKey("s"));
      expect(storeResult.result.current.starred["q-1"]).toBeFalsy();

      unmount();
    });

    it("still claims ArrowDown on the quotes lens when the cursor can move", () => {
      const { getCtx, unmount } = renderWithProviders();
      const cleanup = layout({ "q-1": { x: 0, y: 0 }, "q-2": { x: 0, y: 200 } });
      act(() => {
        getCtx().registerVisibleQuoteIds("test", ["q-1", "q-2"]);
      });

      let event!: KeyboardEvent;
      act(() => {
        event = pressKey("ArrowDown");
      });
      expect(event.defaultPrevented).toBe(true);
      expect(getCtx().focusedId).toBe("q-1");

      cleanup();
      unmount();
    });
  });

  describe("escape cascade", () => {
    it("Escape clears focus when focused", () => {
      const { getCtx, unmount } = renderWithProviders();
      act(() => getCtx().setFocus("q-1"));

      act(() => pressKey("Escape"));
      expect(getCtx().focusedId).toBeNull();

      unmount();
    });

    it("Escape clears selection before focus", () => {
      const { getCtx, unmount } = renderWithProviders();
      act(() => {
        getCtx().setFocus("q-1");
        getCtx().toggleSelection("q-1");
        getCtx().toggleSelection("q-2");
      });

      act(() => pressKey("Escape"));
      // First Escape clears selection
      expect(getCtx().selectedIds.size).toBe(0);
      // Focus should still be there
      expect(getCtx().focusedId).toBe("q-1");

      // Second Escape clears focus
      act(() => pressKey("Escape"));
      expect(getCtx().focusedId).toBeNull();

      unmount();
    });
  });

  describe("selection", () => {
    it("x toggles selection on focused quote", () => {
      const { getCtx, unmount } = renderWithProviders();
      act(() => {
        getCtx().registerVisibleQuoteIds("test", ["q-1", "q-2"]);
        getCtx().setFocus("q-1");
      });

      act(() => pressKey("x"));
      expect(getCtx().selectedIds.has("q-1")).toBe(true);

      act(() => pressKey("x"));
      expect(getCtx().selectedIds.has("q-1")).toBe(false);

      unmount();
    });

    it("x does nothing without focus", () => {
      const { getCtx, unmount } = renderWithProviders();
      act(() => pressKey("x"));
      expect(getCtx().selectedIds.size).toBe(0);

      unmount();
    });
  });

  describe("search focus", () => {
    it("/ focuses search input", () => {
      const input = document.createElement("input");
      input.className = "search-input";
      const container = document.createElement("div");
      container.className = "search-container";
      container.appendChild(input);
      document.body.appendChild(container);

      const focusSpy = vi.spyOn(input, "focus");

      const { unmount } = renderWithProviders();
      act(() => pressKey("/"));

      expect(focusSpy).toHaveBeenCalled();
      expect(container.classList.contains("expanded")).toBe(true);

      unmount();
    });
  });

  describe("sidebar shortcuts", () => {
    /** Dispatch a keydown and return whether it was handled (defaultPrevented). */
    function dispatchKey(key: string, options: Partial<KeyboardEventInit> = {}): boolean {
      const event = new KeyboardEvent("keydown", {
        key,
        bubbles: true,
        cancelable: true,
        ...options,
      });
      return !document.dispatchEvent(event); // dispatchEvent returns false when preventDefault() was called
    }

    it("[ is handled on quotes page (toggles TOC)", () => {
      const { unmount } = renderWithProviders();
      const handled = dispatchKey("[");
      expect(handled).toBe(true);
      unmount();
    });

    // ── Embedded Sessions gate — asserted BOTH ways ────────────────────
    // Only the Sessions lens lost its left panel to the native switcher
    // popover; every other lens keeps `[` on both platforms, and the browser
    // keeps it everywhere. An inverted gate passes a negative-only test.

    it("[ on the sessions route still toggles in the BROWSER", () => {
      mockEmbedded = false;
      const { unmount } = renderWithProviders(undefined, "/report/sessions/s1");
      expect(dispatchKey("[")).toBe(true);
      unmount();
    });

    it("[ on the EMBEDDED sessions route is inert — the native popover owns switching", () => {
      mockEmbedded = true;
      const { unmount } = renderWithProviders(undefined, "/report/sessions/s1");
      expect(dispatchKey("[")).toBe(false);
      mockEmbedded = false;
      unmount();
    });

    it("[ on the EMBEDDED quotes route still toggles — only Sessions lost its panel", () => {
      mockEmbedded = true;
      const { unmount } = renderWithProviders();
      expect(dispatchKey("[")).toBe(true);
      mockEmbedded = false;
      unmount();
    });

    it("] is handled on quotes page (toggles tags)", () => {
      const { unmount } = renderWithProviders();
      const handled = dispatchKey("]");
      expect(handled).toBe(true);
      unmount();
    });

    it("\\ is handled on quotes page (toggles both)", () => {
      const { unmount } = renderWithProviders();
      const handled = dispatchKey("\\");
      expect(handled).toBe(true);
      unmount();
    });

    it("⌘. is handled on quotes page (toggles both)", () => {
      const { unmount } = renderWithProviders();
      const handled = dispatchKey(".", { metaKey: true });
      expect(handled).toBe(true);
      unmount();
    });
  });

  describe("r — repeat last tag", () => {
    it("r applies last-used tag to focused quote", () => {
      const { getCtx, unmount } = renderWithProviders();
      act(() => {
        getCtx().registerVisibleQuoteIds("test", ["q-1", "q-2"]);
        getCtx().setFocus("q-1");
      });

      // Seed a last-used tag
      addTag("q-1", {
        name: "usability",
        codebook_group: "Garrett",
        colour_set: "garrett",
        colour_index: 0,
        source: "human",
      });
      vi.mocked(putTags).mockClear();

      // Move focus to q-2
      act(() => getCtx().setFocus("q-2"));

      // Press r — should quick-apply
      act(() => pressKey("r"));

      expect(putTags).toHaveBeenCalled();
      const calls = vi.mocked(putTags).mock.calls;
      const lastCall = calls[calls.length - 1];
      expect(lastCall?.[0]).toHaveProperty("q-2");
      expect(lastCall?.[0]["q-2"]).toContain("usability");

      unmount();
    });

    it("r does nothing when no last-used tag", () => {
      const { getCtx, unmount } = renderWithProviders();
      act(() => {
        getCtx().registerVisibleQuoteIds("test", ["q-1"]);
        getCtx().setFocus("q-1");
      });

      vi.mocked(putTags).mockClear();
      act(() => pressKey("r"));
      expect(putTags).not.toHaveBeenCalled();

      unmount();
    });

    it("r applies to all selected quotes", () => {
      const { getCtx, unmount } = renderWithProviders();
      act(() => {
        getCtx().registerVisibleQuoteIds("test", ["q-1", "q-2", "q-3"]);
        getCtx().setFocus("q-1");
      });

      // Seed a last-used tag
      addTag("q-1", {
        name: "learnability",
        codebook_group: "Nielsen",
        colour_set: "nielsen",
        colour_index: 1,
        source: "human",
      });
      vi.mocked(putTags).mockClear();

      // Select q-2 and q-3
      act(() => {
        getCtx().setFocus("q-2");
        getCtx().toggleSelection("q-2");
        getCtx().toggleSelection("q-3");
      });

      act(() => pressKey("r"));

      expect(putTags).toHaveBeenCalled();
      const calls = vi.mocked(putTags).mock.calls;
      const lastCall = calls[calls.length - 1];
      expect(lastCall?.[0]).toHaveProperty("q-2");
      expect(lastCall?.[0]["q-2"]).toContain("learnability");
      expect(lastCall?.[0]).toHaveProperty("q-3");
      expect(lastCall?.[0]["q-3"]).toContain("learnability");

      unmount();
    });

    it("r does nothing without focus or selection", () => {
      const { unmount } = renderWithProviders();

      addTag("q-1", {
        name: "usability",
        codebook_group: "Garrett",
        colour_set: "garrett",
        colour_index: 0,
        source: "human",
      });
      vi.mocked(putTags).mockClear();

      act(() => pressKey("r"));
      expect(putTags).not.toHaveBeenCalled();

      unmount();
    });

    it("addTag records lastUsedTag as full TagResponse", () => {
      resetStore();
      expect(getLastUsedTag()).toBeNull();

      addTag("q-1", {
        name: "efficiency",
        codebook_group: "Nielsen",
        colour_set: "nielsen",
        colour_index: 2,
        source: "human",
      });

      const last = getLastUsedTag();
      expect(last).not.toBeNull();
      expect(last!.name).toBe("efficiency");
      expect(last!.colour_set).toBe("nielsen");
      expect(last!.colour_index).toBe(2);
    });

    it("resetStore clears lastUsedTag", () => {
      addTag("q-1", {
        name: "efficiency",
        codebook_group: "Nielsen",
        colour_set: "nielsen",
        colour_index: 2,
        source: "human",
      });
      expect(getLastUsedTag()).not.toBeNull();

      resetStore();
      expect(getLastUsedTag()).toBeNull();
    });
  });

  describe("m — toggle heatmap inspector", () => {
    /** Dispatch a keydown and return whether it was handled (defaultPrevented). */
    function dispatchKey(key: string): boolean {
      const event = new KeyboardEvent("keydown", {
        key,
        bubbles: true,
        cancelable: true,
      });
      return !document.dispatchEvent(event);
    }

    it("m is handled on analysis page", () => {
      const { unmount } = renderWithProviders(undefined, "/report/analysis/");

      const handled = dispatchKey("m");
      expect(handled).toBe(true);

      unmount();
    });

    it("m is not handled on non-analysis pages", () => {
      const { unmount } = renderWithProviders(undefined, "/report/quotes/");

      const handled = dispatchKey("m");
      expect(handled).toBe(false);

      unmount();
    });
  });

  describe("z — focus mode", () => {
    function dispatchKey(key: string, options: Partial<KeyboardEventInit> = {}): boolean {
      const event = new KeyboardEvent("keydown", {
        key,
        bubbles: true,
        cancelable: true,
        ...options,
      });
      return !document.dispatchEvent(event);
    }

    beforeEach(() => {
      _resetFocusMode();
    });

    // Asserting state on *both* edges is what pins the harness to a single
    // mount. `z` reads module-level FocusModeStore and needs no focused or
    // selected quote, so unlike the quote-scoped keys it has no guard to bail
    // on — a harness that mounted the tree twice ran this handler twice per
    // dispatch and the first assertion below would read `false`.
    it("z toggles focus mode on the quotes page", () => {
      const { unmount } = renderWithProviders(undefined, "/report/quotes/");

      expect(isFocusMode()).toBe(false);

      expect(dispatchKey("z")).toBe(true);
      expect(isFocusMode()).toBe(true);

      expect(dispatchKey("z")).toBe(true);
      expect(isFocusMode()).toBe(false);

      unmount();
    });

    it("z is not handled off the quotes lens", () => {
      // The native View-menu twin dims off this lens. If the key still fired,
      // the menu would claim the feature is unavailable while it was running.
      const { unmount } = renderWithProviders(undefined, "/report/analysis/");

      expect(dispatchKey("z")).toBe(false);
      expect(isFocusMode()).toBe(false);

      unmount();
    });

    it("⌘Z is left alone for Undo", () => {
      // The regression this guards: the report has inline quote/heading/name
      // editing, and Undo is most wanted just *after* an edit commits — when
      // isEditing() is already false and so guards nothing.
      const { unmount } = renderWithProviders(undefined, "/report/quotes/");

      expect(dispatchKey("z", { metaKey: true })).toBe(false);
      expect(isFocusMode()).toBe(false);

      expect(dispatchKey("z", { ctrlKey: true })).toBe(false);
      expect(isFocusMode()).toBe(false);

      unmount();
    });
  });

  describe("⌘A — select all quotes", () => {
    /** Dispatch a keydown and return whether it was handled (defaultPrevented). */
    function dispatchKey(key: string, options: Partial<KeyboardEventInit> = {}): boolean {
      const event = new KeyboardEvent("keydown", {
        key,
        bubbles: true,
        cancelable: true,
        ...options,
      });
      return !document.dispatchEvent(event);
    }

    it("⌘A selects all visible quotes on the quotes page", () => {
      const { getCtx, unmount } = renderWithProviders();
      act(() => {
        getCtx().registerVisibleQuoteIds("test", ["q-1", "q-2", "q-3"]);
      });

      act(() => pressKey("a", { metaKey: true }));
      expect(getCtx().selectedIds.size).toBe(3);
      expect(getCtx().selectedIds.has("q-1")).toBe(true);
      expect(getCtx().selectedIds.has("q-3")).toBe(true);

      unmount();
    });

    it("Ctrl+A also selects all (Windows/Linux browsers)", () => {
      const { getCtx, unmount } = renderWithProviders();
      act(() => {
        getCtx().registerVisibleQuoteIds("test", ["q-1", "q-2"]);
      });

      act(() => pressKey("a", { ctrlKey: true }));
      expect(getCtx().selectedIds.size).toBe(2);

      unmount();
    });

    it("⌘A is preventDefault'd on the quotes page (blocks native text select)", () => {
      const { getCtx, unmount } = renderWithProviders();
      act(() => {
        getCtx().registerVisibleQuoteIds("test", ["q-1"]);
      });

      let handled = false;
      act(() => {
        handled = dispatchKey("a", { metaKey: true });
      });
      expect(handled).toBe(true);

      unmount();
    });

    it("⌘A is left to the browser when there are no visible quotes", () => {
      const { getCtx, unmount } = renderWithProviders();

      let handled = false;
      act(() => {
        handled = dispatchKey("a", { metaKey: true });
      });
      expect(handled).toBe(false);
      expect(getCtx().selectedIds.size).toBe(0);

      unmount();
    });

    it("⌘A is left to the browser on non-quotes pages", () => {
      const { getCtx, unmount } = renderWithProviders(undefined, "/report/analysis/");
      act(() => {
        getCtx().registerVisibleQuoteIds("test", ["q-1", "q-2"]);
      });

      let handled = false;
      act(() => {
        handled = dispatchKey("a", { metaKey: true });
      });
      expect(handled).toBe(false);
      expect(getCtx().selectedIds.size).toBe(0);

      unmount();
    });

    it("⌘A is ignored while editing an input", () => {
      const input = document.createElement("input");
      document.body.appendChild(input);
      input.focus();

      const { getCtx, unmount } = renderWithProviders();
      act(() => {
        getCtx().registerVisibleQuoteIds("test", ["q-1", "q-2"]);
      });

      act(() => pressKey("a", { metaKey: true }));
      expect(getCtx().selectedIds.size).toBe(0);

      unmount();
    });
  });

  describe("⌘C — copy selected quotes", () => {
    function dispatchKey(key: string, options: Partial<KeyboardEventInit> = {}): boolean {
      const event = new KeyboardEvent("keydown", {
        key,
        bubbles: true,
        cancelable: true,
        ...options,
      });
      return !document.dispatchEvent(event);
    }

    it("⌘C dispatches copyQuotes(selected) when quotes are selected", () => {
      const menuEvents: CustomEvent[] = [];
      const listener = (e: Event) => menuEvents.push(e as CustomEvent);
      window.addEventListener("bn:menu-action", listener);

      const { getCtx, unmount } = renderWithProviders();
      act(() => {
        getCtx().registerVisibleQuoteIds("test", ["q-1", "q-2"]);
        getCtx().toggleSelection("q-1");
      });

      let handled = false;
      act(() => {
        handled = dispatchKey("c", { metaKey: true });
      });
      expect(handled).toBe(true);
      expect(menuEvents).toHaveLength(1);
      expect(menuEvents[0].detail).toEqual({
        action: "copyQuotes",
        payload: { scope: "selected" },
      });

      window.removeEventListener("bn:menu-action", listener);
      unmount();
    });

    it("⌘C is left to the browser with no selection", () => {
      const menuEvents: CustomEvent[] = [];
      const listener = (e: Event) => menuEvents.push(e as CustomEvent);
      window.addEventListener("bn:menu-action", listener);

      const { getCtx, unmount } = renderWithProviders();
      act(() => {
        getCtx().registerVisibleQuoteIds("test", ["q-1", "q-2"]);
      });

      let handled = false;
      act(() => {
        handled = dispatchKey("c", { metaKey: true });
      });
      expect(handled).toBe(false);
      expect(menuEvents).toHaveLength(0);

      window.removeEventListener("bn:menu-action", listener);
      unmount();
    });

    it("⌘C is left to the browser on non-quotes pages", () => {
      const menuEvents: CustomEvent[] = [];
      const listener = (e: Event) => menuEvents.push(e as CustomEvent);
      window.addEventListener("bn:menu-action", listener);

      const { getCtx, unmount } = renderWithProviders(undefined, "/report/analysis/");
      act(() => {
        getCtx().registerVisibleQuoteIds("test", ["q-1"]);
        getCtx().toggleSelection("q-1");
      });

      let handled = false;
      act(() => {
        handled = dispatchKey("c", { metaKey: true });
      });
      expect(handled).toBe(false);
      expect(menuEvents).toHaveLength(0);

      window.removeEventListener("bn:menu-action", listener);
      unmount();
    });
  });

  // ── Bare keys are inert under a ⌘/Ctrl/⌥ chord ──────────────────────
  //
  // Every one of these matched on `key` alone, so the browser's own chord
  // fired *and* the report acted: ⌘S starred the focused quote while Save
  // Page opened, ⌘X toggled selection alongside Cut. Only `z` had the guard.
  //
  // These assert the negative — `handled === false`, i.e. preventDefault was
  // never called — because that is the whole defect: the report must decline
  // the chord so the browser or the OS gets it whole. The positive (the bare
  // key still works) is already covered by the describe blocks above, and
  // asserting it again here is what would catch a guard inverted by mistake.
  describe("bare keys decline modifier chords", () => {
    function dispatchKey(key: string, options: Partial<KeyboardEventInit> = {}): boolean {
      const event = new KeyboardEvent("keydown", {
        key,
        bubbles: true,
        cancelable: true,
        ...options,
      });
      return !document.dispatchEvent(event);
    }

    // Route-scoped keys need the lens that enables them, or they would read as
    // declined for the wrong reason and pass against an unguarded handler.
    const cases: Array<[string, string]> = [
      ["[", "/report/quotes/"],
      ["]", "/report/quotes/"],
      ["\\", "/report/quotes/"],
      ["§", "/report/quotes/"],
      ["m", "/report/analysis"],
      ["/", "/report/quotes/"],
      ["j", "/report/quotes/"],
      ["k", "/report/quotes/"],
      ["z", "/report/quotes/"],
    ];

    for (const [key, route] of cases) {
      for (const modifier of ["metaKey", "ctrlKey", "altKey"] as const) {
        it(`${key} is inert with ${modifier}`, () => {
          const { unmount } = renderWithProviders(undefined, route);
          let handled = true;
          act(() => {
            handled = dispatchKey(key, { [modifier]: true });
          });
          expect(handled).toBe(false);
          unmount();
        });
      }
    }

    // x, h and s are NOT in the loop above, and the reason is the whole point
    // of writing this suite against the unfixed source first: all three bail
    // early when no quote is focused, so on a bare harness they read as
    // "declined" whether the guard exists or not. Nine vacuous passes, and
    // ⌘S — the case that started this — among them. They need a focused quote
    // before the assertion means anything.
    for (const key of ["x", "h", "s"]) {
      for (const modifier of ["metaKey", "ctrlKey", "altKey"] as const) {
        it(`${key} is inert with ${modifier} even with a focused quote`, () => {
          const { getCtx, unmount } = renderWithProviders(undefined, "/report/quotes/");
          act(() => {
            getCtx().registerVisibleQuoteIds("test", ["q-1", "q-2"]);
            getCtx().setFocus("q-1");
          });

          let handled = true;
          act(() => {
            handled = dispatchKey(key, { [modifier]: true });
          });
          expect(handled).toBe(false);
          // Nothing moved, either — declining the chord and then acting anyway
          // would still star the quote behind Save Page.
          expect(getCtx().selectedIds.size).toBe(0);

          unmount();
        });
      }
    }

    // The one chord that must still be handled: ⌘. shares its handler with
    // the bare \\ and § aliases, and guarding the whole condition rather than
    // the bare branches would have killed it.
    it("⌘. still toggles both sidebars", () => {
      const { unmount } = renderWithProviders(undefined, "/report/quotes/");
      expect(dispatchKey(".", { metaKey: true })).toBe(true);
      unmount();
    });

    // Shift is not a chord for this purpose — Shift+j/k is a real binding.
    it("Shift+j is still handled", () => {
      const { unmount } = renderWithProviders(undefined, "/report/quotes/");
      let handled = false;
      act(() => {
        handled = dispatchKey("j", { shiftKey: true });
      });
      expect(handled).toBe(true);
      unmount();
    });
  });
});
