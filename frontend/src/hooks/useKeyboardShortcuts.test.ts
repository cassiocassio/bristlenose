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

function pressKey(key: string, options: Partial<KeyboardEventInit> = {}) {
  const event = new KeyboardEvent("keydown", {
    key,
    bubbles: true,
    cancelable: true,
    ...options,
  });
  document.dispatchEvent(event);
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

    it("ArrowDown works like j", () => {
      const { getCtx, unmount } = renderWithProviders();
      act(() => {
        getCtx().registerVisibleQuoteIds("test", ["q-1", "q-2"]);
      });

      act(() => pressKey("ArrowDown"));
      expect(getCtx().focusedId).toBe("q-1");

      unmount();
    });

    it("ArrowUp works like k", () => {
      const { getCtx, unmount } = renderWithProviders();
      act(() => {
        getCtx().registerVisibleQuoteIds("test", ["q-1", "q-2"]);
      });

      act(() => pressKey("ArrowUp"));
      expect(getCtx().focusedId).toBe("q-2");

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
});
