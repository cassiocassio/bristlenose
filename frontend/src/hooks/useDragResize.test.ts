/**
 * Tests for useDragResize — pointer-event state machine for sidebar resize.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useDragResize } from "./useDragResize";

// Mock SidebarStore actions.
vi.mock("../contexts/SidebarStore", () => ({
  closeToc: vi.fn(),
  closeTags: vi.fn(),
  openTocPush: vi.fn(),
  openTags: vi.fn(),
  setTocWidth: vi.fn(),
  setTagsWidth: vi.fn(),
}));

import {
  closeToc,
  closeTags,
  openTocPush,
  openTags,
  setTocWidth,
  setTagsWidth,
} from "../contexts/SidebarStore";

// ── Helpers ──────────────────────────────────────────────────────────────

function makeLayoutEl(): HTMLDivElement {
  const el = document.createElement("div");
  document.body.appendChild(el);
  return el;
}

function fire(type: string, opts: PointerEventInit = {}) {
  document.dispatchEvent(new PointerEvent(type, { bubbles: true, ...opts }));
}

function makeRef(el: HTMLDivElement) {
  return { current: el };
}

// ── Setup ────────────────────────────────────────────────────────────────

let layoutEl: HTMLDivElement;

beforeEach(() => {
  vi.clearAllMocks();
  layoutEl = makeLayoutEl();
  document.body.classList.remove("dragging");
});

afterEach(() => {
  layoutEl.remove();
});

// ── Basic lifecycle ──────────────────────────────────────────────────────

describe("basic lifecycle", () => {
  it("isDragging is false initially", () => {
    const { result } = renderHook(() =>
      useDragResize({
        side: "toc",
        source: "sidebar",
        layoutRef: makeRef(layoutEl),
        currentWidth: 280,
      }),
    );
    expect(result.current.isDragging).toBe(false);
  });

  it("pointerdown sets isDragging true and adds body.dragging", () => {
    const ref = makeRef(layoutEl);
    const { result } = renderHook(() =>
      useDragResize({ side: "toc", source: "sidebar", layoutRef: ref, currentWidth: 280 }),
    );

    act(() => {
      const event = new PointerEvent("pointerdown", { clientX: 300 });
      // Simulate React's onPointerDown by calling the handler directly.
      result.current.handlePointerDown(event as unknown as React.PointerEvent);
    });

    expect(result.current.isDragging).toBe(true);
    expect(document.body.classList.contains("dragging")).toBe(true);
  });

  it("pointerup cleans up isDragging and body.dragging", () => {
    const ref = makeRef(layoutEl);
    const { result } = renderHook(() =>
      useDragResize({ side: "toc", source: "sidebar", layoutRef: ref, currentWidth: 280 }),
    );

    act(() => {
      result.current.handlePointerDown(
        new PointerEvent("pointerdown", { clientX: 300 }) as unknown as React.PointerEvent,
      );
    });
    expect(result.current.isDragging).toBe(true);

    act(() => fire("pointerup", { clientX: 350 }));
    expect(result.current.isDragging).toBe(false);
    expect(document.body.classList.contains("dragging")).toBe(false);
  });
});

// ── TOC sidebar: rightward drag increases width ──────────────────────────

describe("TOC sidebar edge", () => {
  it("rightward drag increases --toc-width", () => {
    const ref = makeRef(layoutEl);
    const { result } = renderHook(() =>
      useDragResize({ side: "toc", source: "sidebar", layoutRef: ref, currentWidth: 260 }),
    );

    act(() => {
      result.current.handlePointerDown(
        new PointerEvent("pointerdown", { clientX: 300 }) as unknown as React.PointerEvent,
      );
    });
    act(() => fire("pointermove", { clientX: 340 }));
    // 260 + (340 - 300) = 300
    expect(layoutEl.style.getPropertyValue("--toc-width")).toBe("300px");
  });

  it("leftward drag decreases --toc-width", () => {
    const ref = makeRef(layoutEl);
    const { result } = renderHook(() =>
      useDragResize({ side: "toc", source: "sidebar", layoutRef: ref, currentWidth: 320 }),
    );

    act(() => {
      result.current.handlePointerDown(
        new PointerEvent("pointerdown", { clientX: 400 }) as unknown as React.PointerEvent,
      );
    });
    act(() => fire("pointermove", { clientX: 360 }));
    // 320 + (360 - 400) = 280
    expect(layoutEl.style.getPropertyValue("--toc-width")).toBe("280px");
  });

  it("pointerup calls setTocWidth with clamped value", () => {
    const ref = makeRef(layoutEl);
    const { result } = renderHook(() =>
      useDragResize({ side: "toc", source: "sidebar", layoutRef: ref, currentWidth: 260 }),
    );

    act(() => {
      result.current.handlePointerDown(
        new PointerEvent("pointerdown", { clientX: 300 }) as unknown as React.PointerEvent,
      );
    });
    act(() => fire("pointermove", { clientX: 340 }));
    act(() => fire("pointerup", { clientX: 340 }));
    // 260 + (340 - 300) = 300
    expect(setTocWidth).toHaveBeenCalledWith(300);
  });
});

// ── Tags sidebar: leftward drag increases width ──────────────────────────

describe("Tags sidebar edge", () => {
  it("leftward drag increases --tags-width", () => {
    const ref = makeRef(layoutEl);
    const { result } = renderHook(() =>
      useDragResize({ side: "tags", source: "sidebar", layoutRef: ref, currentWidth: 260 }),
    );

    act(() => {
      result.current.handlePointerDown(
        new PointerEvent("pointerdown", { clientX: 800 }) as unknown as React.PointerEvent,
      );
    });
    act(() => fire("pointermove", { clientX: 760 }));
    // 260 + (800 - 760) = 300
    expect(layoutEl.style.getPropertyValue("--tags-width")).toBe("300px");
  });

  it("pointerup calls setTagsWidth", () => {
    const ref = makeRef(layoutEl);
    const { result } = renderHook(() =>
      useDragResize({ side: "tags", source: "sidebar", layoutRef: ref, currentWidth: 260 }),
    );

    act(() => {
      result.current.handlePointerDown(
        new PointerEvent("pointerdown", { clientX: 800 }) as unknown as React.PointerEvent,
      );
    });
    act(() => fire("pointermove", { clientX: 760 }));
    act(() => fire("pointerup", { clientX: 760 }));
    // 260 + (800 - 760) = 300
    expect(setTagsWidth).toHaveBeenCalledWith(300);
  });
});

// ── Width clamping ───────────────────────────────────────────────────────

describe("width clamping during drag", () => {
  it("clamps to 200 minimum", () => {
    const ref = makeRef(layoutEl);
    const { result } = renderHook(() =>
      useDragResize({ side: "toc", source: "sidebar", layoutRef: ref, currentWidth: 280 }),
    );

    act(() => {
      result.current.handlePointerDown(
        new PointerEvent("pointerdown", { clientX: 300 }) as unknown as React.PointerEvent,
      );
    });
    // 280 + (200 - 300) = 180 → clamps to 200 (above snap threshold of 80)
    act(() => fire("pointermove", { clientX: 200 }));
    expect(layoutEl.style.getPropertyValue("--toc-width")).toBe("200px");
  });

  it("clamps to 320 maximum", () => {
    const ref = makeRef(layoutEl);
    const { result } = renderHook(() =>
      useDragResize({ side: "toc", source: "sidebar", layoutRef: ref, currentWidth: 300 }),
    );

    act(() => {
      result.current.handlePointerDown(
        new PointerEvent("pointerdown", { clientX: 300 }) as unknown as React.PointerEvent,
      );
    });
    // 300 + (500 - 300) = 500 → clamps to 320
    act(() => fire("pointermove", { clientX: 500 }));
    expect(layoutEl.style.getPropertyValue("--toc-width")).toBe("320px");
  });
});

// ── Snap-close ───────────────────────────────────────────────────────────

describe("snap-close", () => {
  it("width below 80px sets CSS var to 0px", () => {
    const ref = makeRef(layoutEl);
    const { result } = renderHook(() =>
      useDragResize({ side: "toc", source: "sidebar", layoutRef: ref, currentWidth: 280 }),
    );

    act(() => {
      result.current.handlePointerDown(
        new PointerEvent("pointerdown", { clientX: 300 }) as unknown as React.PointerEvent,
      );
    });
    // 280 + (20 - 300) = 0 → below 80 threshold
    act(() => fire("pointermove", { clientX: 20 }));
    expect(layoutEl.style.getPropertyValue("--toc-width")).toBe("0px");
  });

  it("pointerup after snap-close calls closeToc", () => {
    const ref = makeRef(layoutEl);
    const { result } = renderHook(() =>
      useDragResize({ side: "toc", source: "sidebar", layoutRef: ref, currentWidth: 280 }),
    );

    act(() => {
      result.current.handlePointerDown(
        new PointerEvent("pointerdown", { clientX: 300 }) as unknown as React.PointerEvent,
      );
    });
    act(() => fire("pointermove", { clientX: 20 }));
    act(() => fire("pointerup", { clientX: 20 }));
    expect(closeToc).toHaveBeenCalled();
    expect(setTocWidth).not.toHaveBeenCalled();
  });

  it("pointerup after snap-close calls closeTags for tags side", () => {
    const ref = makeRef(layoutEl);
    const { result } = renderHook(() =>
      useDragResize({ side: "tags", source: "sidebar", layoutRef: ref, currentWidth: 280 }),
    );

    act(() => {
      result.current.handlePointerDown(
        new PointerEvent("pointerdown", { clientX: 300 }) as unknown as React.PointerEvent,
      );
    });
    // Tags: startX - clientX = 300 - 600 = -300 → negative → 280 + (-300) < 80
    act(() => fire("pointermove", { clientX: 600 }));
    act(() => fire("pointerup", { clientX: 600 }));
    expect(closeTags).toHaveBeenCalled();
  });
});

// ── Rail drag-to-open ────────────────────────────────────────────────────

describe("rail drag-to-open (TOC)", () => {
  it("delta below 20px does not trigger open", () => {
    const ref = makeRef(layoutEl);
    const { result } = renderHook(() =>
      useDragResize({ side: "toc", source: "rail", layoutRef: ref, currentWidth: 280 }),
    );

    act(() => {
      result.current.handlePointerDown(
        new PointerEvent("pointerdown", { clientX: 50 }) as unknown as React.PointerEvent,
      );
    });
    act(() => fire("pointermove", { clientX: 60 }));
    expect(openTocPush).not.toHaveBeenCalled();
    expect(document.body.classList.contains("dragging")).toBe(false);
  });

  it("delta >= 20px triggers openToc", () => {
    const ref = makeRef(layoutEl);
    const { result } = renderHook(() =>
      useDragResize({ side: "toc", source: "rail", layoutRef: ref, currentWidth: 280 }),
    );

    act(() => {
      result.current.handlePointerDown(
        new PointerEvent("pointerdown", { clientX: 50 }) as unknown as React.PointerEvent,
      );
    });
    // Delta = 75 - 50 = 25 (>= 20)
    act(() => fire("pointermove", { clientX: 75 }));
    expect(openTocPush).toHaveBeenCalled();
    expect(document.body.classList.contains("dragging")).toBe(true);
  });

  it("after threshold, continues as resize and sets CSS var", () => {
    const ref = makeRef(layoutEl);
    const { result } = renderHook(() =>
      useDragResize({ side: "toc", source: "rail", layoutRef: ref, currentWidth: 280 }),
    );

    act(() => {
      result.current.handlePointerDown(
        new PointerEvent("pointerdown", { clientX: 50 }) as unknown as React.PointerEvent,
      );
    });
    // Cross threshold
    act(() => fire("pointermove", { clientX: 75 }));
    // Continue dragging further — startWidth is 0 for rail, so width = delta
    // delta = 300 - 50 = 250, clamped to [200, 320]
    act(() => fire("pointermove", { clientX: 300 }));
    expect(layoutEl.style.getPropertyValue("--toc-width")).toBe("250px");
  });

  it("pointerup without crossing threshold is a no-op", () => {
    const ref = makeRef(layoutEl);
    const { result } = renderHook(() =>
      useDragResize({ side: "toc", source: "rail", layoutRef: ref, currentWidth: 280 }),
    );

    act(() => {
      result.current.handlePointerDown(
        new PointerEvent("pointerdown", { clientX: 50 }) as unknown as React.PointerEvent,
      );
    });
    act(() => fire("pointerup", { clientX: 55 }));
    expect(openTocPush).not.toHaveBeenCalled();
    expect(setTocWidth).not.toHaveBeenCalled();
    expect(result.current.isDragging).toBe(false);
  });

  it("pointerup after rail open calls setTocWidth", () => {
    const ref = makeRef(layoutEl);
    const { result } = renderHook(() =>
      useDragResize({ side: "toc", source: "rail", layoutRef: ref, currentWidth: 280 }),
    );

    act(() => {
      result.current.handlePointerDown(
        new PointerEvent("pointerdown", { clientX: 50 }) as unknown as React.PointerEvent,
      );
    });
    act(() => fire("pointermove", { clientX: 300 }));
    act(() => fire("pointerup", { clientX: 300 }));
    expect(setTocWidth).toHaveBeenCalledWith(250);
  });
});

describe("rail drag-to-open (Tags)", () => {
  it("leftward drag >= 20px triggers openTags", () => {
    const ref = makeRef(layoutEl);
    const { result } = renderHook(() =>
      useDragResize({ side: "tags", source: "rail", layoutRef: ref, currentWidth: 280 }),
    );

    act(() => {
      result.current.handlePointerDown(
        new PointerEvent("pointerdown", { clientX: 900 }) as unknown as React.PointerEvent,
      );
    });
    // Tags: delta = startX - clientX = 900 - 870 = 30 (>= 20)
    act(() => fire("pointermove", { clientX: 870 }));
    expect(openTags).toHaveBeenCalled();
  });
});

// ── Animation class ──────────────────────────────────────────────────────

describe("animation class", () => {
  it("removes .animating on drag start", () => {
    layoutEl.classList.add("animating");
    const ref = makeRef(layoutEl);
    const { result } = renderHook(() =>
      useDragResize({ side: "toc", source: "sidebar", layoutRef: ref, currentWidth: 280 }),
    );

    act(() => {
      result.current.handlePointerDown(
        new PointerEvent("pointerdown", { clientX: 300 }) as unknown as React.PointerEvent,
      );
    });
    expect(layoutEl.classList.contains("animating")).toBe(false);
  });
});

// ── Unmount cleanup ──────────────────────────────────────────────────────

describe("cleanup on unmount", () => {
  it("removes document listeners and body.dragging", () => {
    const ref = makeRef(layoutEl);
    const { result, unmount } = renderHook(() =>
      useDragResize({ side: "toc", source: "sidebar", layoutRef: ref, currentWidth: 280 }),
    );

    act(() => {
      result.current.handlePointerDown(
        new PointerEvent("pointerdown", { clientX: 300 }) as unknown as React.PointerEvent,
      );
    });
    expect(document.body.classList.contains("dragging")).toBe(true);

    unmount();
    expect(document.body.classList.contains("dragging")).toBe(false);
  });
});
