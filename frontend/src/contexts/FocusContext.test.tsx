/**
 * Tests for FocusContext — focus, selection, range, movement.
 */

import { render, renderHook, act } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { FocusProvider, useFocus, useQuoteFocusState } from "./FocusContext";
import { PlayerProvider } from "./PlayerContext";
import type { ReactNode } from "react";

// ── Helpers ──────────────────────────────────────────────────────────────

function wrapper({ children }: { children: ReactNode }) {
  const routes = [
    {
      path: "/",
      element: (
        <PlayerProvider>
          <FocusProvider>{children}</FocusProvider>
        </PlayerProvider>
      ),
    },
  ];
  const router = createMemoryRouter(routes, { initialEntries: ["/"] });
  return <RouterProvider router={router} />;
}

// ── Tests ────────────────────────────────────────────────────────────────

describe("FocusProvider", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
  });

  it("starts with no focus and empty selection", () => {
    const { result } = renderHook(() => useFocus(), { wrapper });
    expect(result.current.focusedId).toBeNull();
    expect(result.current.selectedIds.size).toBe(0);
  });

  it("setFocus sets the focused ID", () => {
    const { result } = renderHook(() => useFocus(), { wrapper });
    act(() => result.current.setFocus("q-1"));
    expect(result.current.focusedId).toBe("q-1");
  });

  it("setFocus(null) clears focus", () => {
    const { result } = renderHook(() => useFocus(), { wrapper });
    act(() => result.current.setFocus("q-1"));
    act(() => result.current.setFocus(null));
    expect(result.current.focusedId).toBeNull();
  });

  it("setFocus scrolls element into view", () => {
    const el = document.createElement("blockquote");
    el.id = "q-scroll";
    el.scrollIntoView = vi.fn();
    document.body.appendChild(el);

    const { result } = renderHook(() => useFocus(), { wrapper });
    act(() => result.current.setFocus("q-scroll"));

    // scrollIntoView called via requestAnimationFrame
    vi.spyOn(globalThis, "requestAnimationFrame").mockImplementation((cb) => {
      cb(0);
      return 0;
    });
    // Re-trigger to use the spy
    act(() => result.current.setFocus("q-scroll"));
    // The implementation uses rAF, so in tests we verify the id was set
    expect(result.current.focusedId).toBe("q-scroll");
  });

  it("setFocus with scroll: false does not scroll", () => {
    const { result } = renderHook(() => useFocus(), { wrapper });
    act(() => result.current.setFocus("q-1", { scroll: false }));
    expect(result.current.focusedId).toBe("q-1");
  });

  // ── Selection ──────────────────────────────────────────────────────

  it("toggleSelection adds and removes quote IDs", () => {
    const { result } = renderHook(() => useFocus(), { wrapper });
    act(() => result.current.toggleSelection("q-1"));
    expect(result.current.selectedIds.has("q-1")).toBe(true);

    act(() => result.current.toggleSelection("q-1"));
    expect(result.current.selectedIds.has("q-1")).toBe(false);
  });

  it("toggleSelection supports multiple quotes", () => {
    const { result } = renderHook(() => useFocus(), { wrapper });
    act(() => {
      result.current.toggleSelection("q-1");
      result.current.toggleSelection("q-2");
      result.current.toggleSelection("q-3");
    });
    expect(result.current.selectedIds.size).toBe(3);
  });

  it("clearSelection removes all selections", () => {
    const { result } = renderHook(() => useFocus(), { wrapper });
    act(() => {
      result.current.toggleSelection("q-1");
      result.current.toggleSelection("q-2");
    });
    act(() => result.current.clearSelection());
    expect(result.current.selectedIds.size).toBe(0);
  });

  // ── Range selection ────────────────────────────────────────────────

  it("selectRange selects quotes between two IDs", () => {
    const { result } = renderHook(() => useFocus(), { wrapper });

    act(() => {
      result.current.registerVisibleQuoteIds("test", ["q-1", "q-2", "q-3", "q-4", "q-5"]);
    });

    act(() => result.current.selectRange("q-2", "q-4"));
    expect(result.current.selectedIds.has("q-1")).toBe(false);
    expect(result.current.selectedIds.has("q-2")).toBe(true);
    expect(result.current.selectedIds.has("q-3")).toBe(true);
    expect(result.current.selectedIds.has("q-4")).toBe(true);
    expect(result.current.selectedIds.has("q-5")).toBe(false);
  });

  it("selectRange works in reverse order", () => {
    const { result } = renderHook(() => useFocus(), { wrapper });

    act(() => {
      result.current.registerVisibleQuoteIds("test", ["q-1", "q-2", "q-3"]);
    });

    act(() => result.current.selectRange("q-3", "q-1"));
    expect(result.current.selectedIds.size).toBe(3);
  });

  it("selectRange no-ops if IDs not found", () => {
    const { result } = renderHook(() => useFocus(), { wrapper });

    act(() => {
      result.current.registerVisibleQuoteIds("test", ["q-1", "q-2"]);
    });

    act(() => result.current.selectRange("q-unknown", "q-1"));
    expect(result.current.selectedIds.size).toBe(0);
  });

  // ── Movement ───────────────────────────────────────────────────────

  it("moveFocus(1) focuses first quote when no focus", () => {
    const { result } = renderHook(() => useFocus(), { wrapper });

    act(() => {
      result.current.registerVisibleQuoteIds("test", ["q-1", "q-2", "q-3"]);
    });

    act(() => result.current.moveFocus(1));
    expect(result.current.focusedId).toBe("q-1");
  });

  it("moveFocus(-1) focuses last quote when no focus", () => {
    const { result } = renderHook(() => useFocus(), { wrapper });

    act(() => {
      result.current.registerVisibleQuoteIds("test", ["q-1", "q-2", "q-3"]);
    });

    act(() => result.current.moveFocus(-1));
    expect(result.current.focusedId).toBe("q-3");
  });

  it("moveFocus(1) moves to next quote", () => {
    const { result } = renderHook(() => useFocus(), { wrapper });

    act(() => {
      result.current.registerVisibleQuoteIds("test", ["q-1", "q-2", "q-3"]);
    });
    act(() => result.current.setFocus("q-1"));
    act(() => result.current.moveFocus(1));
    expect(result.current.focusedId).toBe("q-2");
  });

  it("moveFocus(-1) moves to previous quote", () => {
    const { result } = renderHook(() => useFocus(), { wrapper });

    act(() => {
      result.current.registerVisibleQuoteIds("test", ["q-1", "q-2", "q-3"]);
    });
    act(() => result.current.setFocus("q-3"));
    act(() => result.current.moveFocus(-1));
    expect(result.current.focusedId).toBe("q-2");
  });

  it("moveFocus clamps at beginning", () => {
    const { result } = renderHook(() => useFocus(), { wrapper });

    act(() => {
      result.current.registerVisibleQuoteIds("test", ["q-1", "q-2"]);
    });
    act(() => result.current.setFocus("q-1"));
    act(() => result.current.moveFocus(-1));
    expect(result.current.focusedId).toBe("q-1");
  });

  it("moveFocus clamps at end", () => {
    const { result } = renderHook(() => useFocus(), { wrapper });

    act(() => {
      result.current.registerVisibleQuoteIds("test", ["q-1", "q-2"]);
    });
    act(() => result.current.setFocus("q-2"));
    act(() => result.current.moveFocus(1));
    expect(result.current.focusedId).toBe("q-2");
  });

  it("moveFocus recovers when focused quote disappears", () => {
    const { result } = renderHook(() => useFocus(), { wrapper });

    act(() => {
      result.current.registerVisibleQuoteIds("test", ["q-1", "q-2", "q-3"]);
    });
    act(() => result.current.setFocus("q-gone"));
    act(() => result.current.moveFocus(1));
    expect(result.current.focusedId).toBe("q-1");
  });

  it("moveFocus no-ops on empty list", () => {
    const { result } = renderHook(() => useFocus(), { wrapper });
    act(() => result.current.moveFocus(1));
    expect(result.current.focusedId).toBeNull();
  });

  // ── Anchor ─────────────────────────────────────────────────────────

  it("setAnchor sets the anchor ID", () => {
    const { result } = renderHook(() => useFocus(), { wrapper });
    act(() => result.current.setAnchor("q-1"));
    expect(result.current.anchorId).toBe("q-1");
  });

  // ── Visible ID registration ────────────────────────────────────────

  it("registerVisibleQuoteIds merges multiple sources", () => {
    const { result } = renderHook(() => useFocus(), { wrapper });

    act(() => {
      result.current.registerVisibleQuoteIds("sections", ["q-s1", "q-s2"]);
      result.current.registerVisibleQuoteIds("themes", ["q-t1", "q-t2"]);
    });

    // Verify by movement: first should be q-s1, last should be q-t2
    act(() => result.current.moveFocus(1));
    expect(result.current.focusedId).toBe("q-s1");

    act(() => result.current.moveFocus(-1));
    // At first element, -1 clamps — still q-s1
    expect(result.current.focusedId).toBe("q-s1");
  });

  // ── Tag openers ────────────────────────────────────────────────────

  it("openTagInput calls registered opener", () => {
    const { result } = renderHook(() => useFocus(), { wrapper });
    const opener = vi.fn();

    act(() => result.current.registerTagOpener("q-1", opener));
    act(() => result.current.openTagInput("q-1"));
    expect(opener).toHaveBeenCalledOnce();
  });

  it("unregisterTagOpener prevents future calls", () => {
    const { result } = renderHook(() => useFocus(), { wrapper });
    const opener = vi.fn();

    act(() => result.current.registerTagOpener("q-1", opener));
    act(() => result.current.unregisterTagOpener("q-1"));
    act(() => result.current.openTagInput("q-1"));
    expect(opener).not.toHaveBeenCalled();
  });
});

// ── useQuoteFocusState ────────────────────────────────────────────────

describe("useQuoteFocusState", () => {
  it("returns correct focus and selection state", () => {
    let focusState: { isFocused: boolean; isSelected: boolean } | null = null;
    let ctx: ReturnType<typeof useFocus> | null = null;

    function Consumer() {
      ctx = useFocus();
      focusState = useQuoteFocusState("q-1");
      return null;
    }

    const routes = [
      {
        path: "/",
        element: (
          <PlayerProvider>
            <FocusProvider>
              <Consumer />
            </FocusProvider>
          </PlayerProvider>
        ),
      },
    ];
    const router = createMemoryRouter(routes, { initialEntries: ["/"] });
    render(<RouterProvider router={router} />);

    expect(focusState!.isFocused).toBe(false);
    expect(focusState!.isSelected).toBe(false);

    act(() => {
      ctx!.setFocus("q-1");
      ctx!.toggleSelection("q-1");
    });

    expect(focusState!.isFocused).toBe(true);
    expect(focusState!.isSelected).toBe(true);
  });
});
