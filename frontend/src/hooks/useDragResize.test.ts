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
  it("width below 80px collapses to 0px (previews closed state)", () => {
    const ref = makeRef(layoutEl);
    const { result } = renderHook(() =>
      useDragResize({ side: "toc", source: "sidebar", layoutRef: ref, currentWidth: 280 }),
    );

    act(() => {
      result.current.handlePointerDown(
        new PointerEvent("pointerdown", { clientX: 300 }) as unknown as React.PointerEvent,
      );
    });
    // 280 + (20 - 300) = 0 → below 80 threshold → collapses to 0
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
  it("pointerdown adds body.dragging but defers toc-rail-dragging to first move", () => {
    const ref = makeRef(layoutEl);
    const { result } = renderHook(() =>
      useDragResize({ side: "toc", source: "rail", layoutRef: ref, currentWidth: 280 }),
    );

    act(() => {
      result.current.handlePointerDown(
        new PointerEvent("pointerdown", { clientX: 50 }) as unknown as React.PointerEvent,
      );
    });
    // Class deferred — no ghost border/shadow on pointerdown
    expect(layoutEl.classList.contains("toc-rail-dragging")).toBe(false);
    expect(document.body.classList.contains("dragging")).toBe(true);
    expect(openTocPush).not.toHaveBeenCalled();

    // First move reveals the overlay
    act(() => fire("pointermove", { clientX: 51 }));
    expect(layoutEl.classList.contains("toc-rail-dragging")).toBe(true);
  });

  it("tracks CSS var 1:1 with pointer movement from 0", () => {
    const ref = makeRef(layoutEl);
    const { result } = renderHook(() =>
      useDragResize({ side: "toc", source: "rail", layoutRef: ref, currentWidth: 280 }),
    );

    act(() => {
      result.current.handlePointerDown(
        new PointerEvent("pointerdown", { clientX: 50 }) as unknown as React.PointerEvent,
      );
    });

    // Small drag: delta = 10 → width 10px (tracks 1:1)
    act(() => fire("pointermove", { clientX: 60 }));
    expect(layoutEl.style.getPropertyValue("--toc-width")).toBe("10px");

    // Larger drag: delta = 250
    act(() => fire("pointermove", { clientX: 300 }));
    expect(layoutEl.style.getPropertyValue("--toc-width")).toBe("250px");

    // Clamps to MAX_WIDTH (320)
    act(() => fire("pointermove", { clientX: 500 }));
    expect(layoutEl.style.getPropertyValue("--toc-width")).toBe("320px");
  });

  it("pointerup below snap threshold aborts (stays closed)", () => {
    const ref = makeRef(layoutEl);
    const { result } = renderHook(() =>
      useDragResize({ side: "toc", source: "rail", layoutRef: ref, currentWidth: 280 }),
    );

    act(() => {
      result.current.handlePointerDown(
        new PointerEvent("pointerdown", { clientX: 50 }) as unknown as React.PointerEvent,
      );
    });
    // Small drag: delta = 5 → lastWidth = 5 (< 60 threshold)
    act(() => fire("pointermove", { clientX: 55 }));
    act(() => fire("pointerup", { clientX: 55 }));
    expect(openTocPush).not.toHaveBeenCalled();
    expect(setTocWidth).not.toHaveBeenCalled();
    expect(layoutEl.classList.contains("toc-rail-dragging")).toBe(false);
    expect(result.current.isDragging).toBe(false);
  });

  it("pointerup above snap threshold opens in push mode", () => {
    const ref = makeRef(layoutEl);
    const { result } = renderHook(() =>
      useDragResize({ side: "toc", source: "rail", layoutRef: ref, currentWidth: 280 }),
    );

    act(() => {
      result.current.handlePointerDown(
        new PointerEvent("pointerdown", { clientX: 50 }) as unknown as React.PointerEvent,
      );
    });
    // delta = 250 → lastWidth = 250 (>= 60 threshold)
    act(() => fire("pointermove", { clientX: 300 }));
    act(() => fire("pointerup", { clientX: 300 }));
    expect(openTocPush).toHaveBeenCalled();
    expect(setTocWidth).toHaveBeenCalledWith(250);
    expect(layoutEl.classList.contains("toc-rail-dragging")).toBe(false);
  });

  it("pointerup with small drag >= threshold clamps to MIN_WIDTH", () => {
    const ref = makeRef(layoutEl);
    const { result } = renderHook(() =>
      useDragResize({ side: "toc", source: "rail", layoutRef: ref, currentWidth: 280 }),
    );

    act(() => {
      result.current.handlePointerDown(
        new PointerEvent("pointerdown", { clientX: 50 }) as unknown as React.PointerEvent,
      );
    });
    // delta = 70 → lastWidth = 70 (>= 60 threshold, but < MIN_WIDTH 200)
    act(() => fire("pointermove", { clientX: 120 }));
    act(() => fire("pointerup", { clientX: 120 }));
    // Should clamp to MIN_WIDTH on commit
    expect(openTocPush).toHaveBeenCalled();
    expect(setTocWidth).toHaveBeenCalledWith(200);
  });
});

describe("rail drag-to-open (Tags)", () => {
  it("leftward drag opens tags on pointerup", () => {
    const ref = makeRef(layoutEl);
    const { result } = renderHook(() =>
      useDragResize({ side: "tags", source: "rail", layoutRef: ref, currentWidth: 280 }),
    );

    act(() => {
      result.current.handlePointerDown(
        new PointerEvent("pointerdown", { clientX: 900 }) as unknown as React.PointerEvent,
      );
    });
    // Class deferred to first move
    expect(layoutEl.classList.contains("tags-rail-dragging")).toBe(false);

    // Tags: delta = startX - clientX = 900 - 600 = 300
    act(() => fire("pointermove", { clientX: 600 }));
    expect(layoutEl.classList.contains("tags-rail-dragging")).toBe(true);
    act(() => fire("pointerup", { clientX: 600 }));
    expect(openTags).toHaveBeenCalled();
    expect(setTagsWidth).toHaveBeenCalledWith(300);
    expect(layoutEl.classList.contains("tags-rail-dragging")).toBe(false);
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

// ── Custom min/max widths ─────────────────────────────────────────────

describe("custom minWidth/maxWidth", () => {
  it("clamps to custom minimum", () => {
    const ref = makeRef(layoutEl);
    const { result } = renderHook(() =>
      useDragResize({
        side: "toc", source: "sidebar", layoutRef: ref, currentWidth: 300,
        minWidth: 250, maxWidth: 400,
      }),
    );

    act(() => {
      result.current.handlePointerDown(
        new PointerEvent("pointerdown", { clientX: 300 }) as unknown as React.PointerEvent,
      );
    });
    // 300 + (200 - 300) = 200 → below custom min 250 (but above snap threshold 80)
    act(() => fire("pointermove", { clientX: 200 }));
    expect(layoutEl.style.getPropertyValue("--toc-width")).toBe("250px");
  });

  it("clamps to custom maximum", () => {
    const ref = makeRef(layoutEl);
    const { result } = renderHook(() =>
      useDragResize({
        side: "toc", source: "sidebar", layoutRef: ref, currentWidth: 300,
        minWidth: 250, maxWidth: 400,
      }),
    );

    act(() => {
      result.current.handlePointerDown(
        new PointerEvent("pointerdown", { clientX: 300 }) as unknown as React.PointerEvent,
      );
    });
    // 300 + (500 - 300) = 500 → above custom max 400
    act(() => fire("pointermove", { clientX: 500 }));
    expect(layoutEl.style.getPropertyValue("--toc-width")).toBe("400px");
  });

  it("rail drag clamps to custom max", () => {
    const ref = makeRef(layoutEl);
    const { result } = renderHook(() =>
      useDragResize({
        side: "toc", source: "rail", layoutRef: ref, currentWidth: 0,
        minWidth: 250, maxWidth: 400,
      }),
    );

    act(() => {
      result.current.handlePointerDown(
        new PointerEvent("pointerdown", { clientX: 50 }) as unknown as React.PointerEvent,
      );
    });
    // delta = 500 → clamped to custom max 400
    act(() => fire("pointermove", { clientX: 550 }));
    expect(layoutEl.style.getPropertyValue("--toc-width")).toBe("400px");
  });

  it("rail commit clamps to custom min", () => {
    const ref = makeRef(layoutEl);
    const { result } = renderHook(() =>
      useDragResize({
        side: "toc", source: "rail", layoutRef: ref, currentWidth: 0,
        minWidth: 250, maxWidth: 400,
      }),
    );

    act(() => {
      result.current.handlePointerDown(
        new PointerEvent("pointerdown", { clientX: 50 }) as unknown as React.PointerEvent,
      );
    });
    // delta = 70 → lastWidth = 70 (>= 60 threshold, but < custom min 250)
    act(() => fire("pointermove", { clientX: 120 }));
    act(() => fire("pointerup", { clientX: 120 }));
    expect(openTocPush).toHaveBeenCalled();
    expect(setTocWidth).toHaveBeenCalledWith(250);
  });
});

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
