/**
 * Tests for useKeyboardShortcuts — key dispatch, guards, bulk actions.
 *
 * These tests exercise the hook through the full provider tree
 * (PlayerProvider + FocusProvider + Router) and verify keydown
 * events dispatch correct actions.
 */

import { renderHook, act } from "@testing-library/react";
import { createElement, useState, useCallback, type ReactNode } from "react";
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
import { useKeyboardShortcuts } from "./useKeyboardShortcuts";
import { putTags } from "../utils/api";

// Mock API calls (addTag calls putTags internally).
vi.mock("../utils/api", () => ({
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

  const routes = [{ path: "/report/quotes", element: createElement(Wrapper) }];
  const router = createMemoryRouter(routes, {
    initialEntries: ["/report/quotes/"],
  });
  const result = renderHook(() => useQuotesStore(), {
    wrapper: ({ children }: { children: ReactNode }) =>
      createElement(RouterProvider, { router }, children),
  });

  // We need a separate render for the actual component tree
  const { unmount } = renderHook(
    () => null,
    {
      wrapper: () => createElement(RouterProvider, { router }),
    },
  );

  return {
    getCtx: () => ctx!,
    storeResult: result,
    unmount,
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

  describe("double-t quick-repeat", () => {
    it("single t opens tag input on focused quote", () => {
      const { getCtx, unmount } = renderWithProviders();
      const openerSpy = vi.fn();
      act(() => {
        getCtx().registerVisibleQuoteIds("test", ["q-1", "q-2"]);
        getCtx().setFocus("q-1");
        getCtx().registerTagOpener("q-1", openerSpy);
      });

      act(() => pressKey("t"));
      expect(openerSpy).toHaveBeenCalledTimes(1);

      unmount();
    });

    it("double-t within 400ms applies last-used tag", () => {
      const { getCtx, unmount } = renderWithProviders();
      act(() => {
        getCtx().registerVisibleQuoteIds("test", ["q-1", "q-2"]);
        getCtx().setFocus("q-1");
        getCtx().registerTagOpener("q-1", vi.fn());
      });

      // Seed a last-used tag via addTag
      addTag("q-1", {
        name: "usability",
        codebook_group: "Garrett",
        colour_set: "garrett",
        colour_index: 0,
        source: "human",
      });
      expect(getLastUsedTag()?.name).toBe("usability");
      vi.mocked(putTags).mockClear();

      // Move focus to q-2
      act(() => getCtx().setFocus("q-2"));

      // First t — opens tag input
      let now = 1000;
      vi.spyOn(Date, "now").mockReturnValue(now);
      act(() => pressKey("t"));

      // Second t — within 400ms — should quick-apply
      now += 200;
      vi.spyOn(Date, "now").mockReturnValue(now);
      act(() => pressKey("t"));

      // putTags was called by the quick-apply addTag
      expect(putTags).toHaveBeenCalled();
      // The tags map sent to API should include q-2 with "usability"
      const calls = vi.mocked(putTags).mock.calls;
      const lastCall = calls[calls.length - 1];
      expect(lastCall?.[0]).toHaveProperty("q-2");
      expect(lastCall?.[0]["q-2"]).toContain("usability");

      unmount();
    });

    it("double-t without last tag falls back to opening tag input", () => {
      const { getCtx, unmount } = renderWithProviders();
      const openerSpy = vi.fn();
      act(() => {
        getCtx().registerVisibleQuoteIds("test", ["q-1"]);
        getCtx().setFocus("q-1");
        getCtx().registerTagOpener("q-1", openerSpy);
      });

      // No last tag set — both presses should open tag input
      let now = 1000;
      vi.spyOn(Date, "now").mockReturnValue(now);
      act(() => pressKey("t"));
      expect(openerSpy).toHaveBeenCalledTimes(1);

      now += 200;
      vi.spyOn(Date, "now").mockReturnValue(now);
      act(() => pressKey("t"));
      // Falls back to open tag input again
      expect(openerSpy).toHaveBeenCalledTimes(2);

      unmount();
    });

    it("t pressed after 400ms gap is treated as single tap", () => {
      const { getCtx, unmount } = renderWithProviders();
      const openerSpy = vi.fn();
      act(() => {
        getCtx().registerVisibleQuoteIds("test", ["q-1", "q-2"]);
        getCtx().setFocus("q-1");
        getCtx().registerTagOpener("q-1", openerSpy);
        getCtx().registerTagOpener("q-2", openerSpy);
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

      act(() => getCtx().setFocus("q-2"));

      // First t
      let now = 1000;
      vi.spyOn(Date, "now").mockReturnValue(now);
      act(() => pressKey("t"));
      expect(openerSpy).toHaveBeenCalledTimes(1);

      // Second t — after 500ms (> 400ms threshold)
      now += 500;
      vi.spyOn(Date, "now").mockReturnValue(now);
      act(() => pressKey("t"));
      // Should open tag input, not quick-apply
      expect(openerSpy).toHaveBeenCalledTimes(2);
      // putTags should NOT have been called (no quick-apply happened)
      expect(putTags).not.toHaveBeenCalled();

      unmount();
    });

    it("double-t applies to all selected quotes", () => {
      const { getCtx, unmount } = renderWithProviders();
      act(() => {
        getCtx().registerVisibleQuoteIds("test", ["q-1", "q-2", "q-3"]);
        getCtx().setFocus("q-1");
        getCtx().registerTagOpener("q-1", vi.fn());
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

      // Double-t
      let now = 1000;
      vi.spyOn(Date, "now").mockReturnValue(now);
      act(() => pressKey("t"));

      now += 200;
      vi.spyOn(Date, "now").mockReturnValue(now);
      act(() => pressKey("t"));

      // putTags called with both q-2 and q-3 having the tag
      expect(putTags).toHaveBeenCalled();
      const calls = vi.mocked(putTags).mock.calls;
      const lastCall = calls[calls.length - 1];
      expect(lastCall?.[0]).toHaveProperty("q-2");
      expect(lastCall?.[0]["q-2"]).toContain("learnability");
      expect(lastCall?.[0]).toHaveProperty("q-3");
      expect(lastCall?.[0]["q-3"]).toContain("learnability");

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
});
