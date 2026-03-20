import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useVerticalDragResize } from "./useVerticalDragResize";
import {
  resetInspectorStore,
  useInspectorStore,
  openInspector,
  MIN_HEIGHT,
  MAX_HEIGHT,
} from "../contexts/InspectorStore";

// ── Helpers ───────────────────────────────────────────────────────────────

function makeContainer(): HTMLDivElement {
  const el = document.createElement("div");
  document.body.appendChild(el);
  return el;
}

function makePointerEvent(
  _type: string,
  clientY: number,
): React.PointerEvent {
  return {
    clientY,
    preventDefault: vi.fn(),
  } as unknown as React.PointerEvent;
}

function firePointerMove(clientY: number) {
  document.dispatchEvent(
    new PointerEvent("pointermove", { clientY, bubbles: true }),
  );
}

function firePointerUp() {
  document.dispatchEvent(
    new PointerEvent("pointerup", { bubbles: true }),
  );
}

// ── Setup ─────────────────────────────────────────────────────────────────

beforeEach(() => {
  localStorage.clear();
  resetInspectorStore();
  document.body.className = "";
});

// ── Tests ─────────────────────────────────────────────────────────────────

describe("useVerticalDragResize", () => {
  it("returns initial state", () => {
    const container = makeContainer();
    const ref = { current: container };
    const { result } = renderHook(() =>
      useVerticalDragResize({
        containerRef: ref,
        currentHeight: 320,
        isOpen: false,
      }),
    );
    expect(result.current.isDragging).toBe(false);
    expect(typeof result.current.handlePointerDown).toBe("function");
    expect(typeof result.current.handleKeyDown).toBe("function");
  });

  it("click (no movement) on collapsed panel opens it", () => {
    const container = makeContainer();
    const ref = { current: container };

    // Use two hooks: resize + store to observe state changes
    const { result: resizeResult } = renderHook(() =>
      useVerticalDragResize({
        containerRef: ref,
        currentHeight: 320,
        isOpen: false,
      }),
    );
    const { result: storeResult } = renderHook(() => useInspectorStore());

    expect(storeResult.current.open).toBe(false);

    // pointerdown then immediate pointerup (no movement = click)
    act(() => {
      resizeResult.current.handlePointerDown(makePointerEvent("pointerdown", 500));
    });
    act(() => {
      firePointerUp();
    });

    expect(storeResult.current.open).toBe(true);
  });

  it("click on open panel closes it", () => {
    const container = makeContainer();
    const ref = { current: container };

    act(() => openInspector());

    const { result: resizeResult } = renderHook(() =>
      useVerticalDragResize({
        containerRef: ref,
        currentHeight: 320,
        isOpen: true,
      }),
    );
    const { result: storeResult } = renderHook(() => useInspectorStore());

    expect(storeResult.current.open).toBe(true);

    act(() => {
      resizeResult.current.handlePointerDown(makePointerEvent("pointerdown", 500));
    });
    act(() => {
      firePointerUp();
    });

    expect(storeResult.current.open).toBe(false);
  });

  it("movement > 3px enters drag mode (adds dragging-v class)", () => {
    const container = makeContainer();
    const ref = { current: container };

    act(() => openInspector());

    const { result } = renderHook(() =>
      useVerticalDragResize({
        containerRef: ref,
        currentHeight: 320,
        isOpen: true,
      }),
    );

    act(() => {
      result.current.handlePointerDown(makePointerEvent("pointerdown", 500));
    });

    // Move < 3px — should NOT enter drag mode
    act(() => firePointerMove(498));
    // dragging-v class was added on pointerdown
    expect(document.body.classList.contains("dragging-v")).toBe(true);

    // Move > 3px — enters drag and sets CSS var on container
    act(() => firePointerMove(493));
    expect(container.style.getPropertyValue("--inspector-height")).toBeTruthy();

    // Complete the drag
    act(() => firePointerUp());
    expect(document.body.classList.contains("dragging-v")).toBe(false);
  });

  it("drag from collapsed grows from handle height (28px), not stored height", () => {
    const container = makeContainer();
    container.classList.add("collapsed");
    const ref = { current: container };

    // Panel is collapsed but has a stored height of 320
    const { result: resizeResult } = renderHook(() =>
      useVerticalDragResize({
        containerRef: ref,
        currentHeight: 320,
        isOpen: false,
      }),
    );
    const { result: storeResult } = renderHook(() => useInspectorStore());

    // Start drag at y=500, drag up 50px to y=450
    // deltaY = 500 - 450 = 50; raw = 28 + 50 = 78px (below snap threshold)
    // Drag up more to y=300: deltaY = 500 - 300 = 200; raw = 28 + 200 = 228px
    act(() => {
      resizeResult.current.handlePointerDown(makePointerEvent("pointerdown", 500));
    });

    // Move past threshold — should remove .collapsed class
    act(() => firePointerMove(450));
    expect(container.classList.contains("collapsed")).toBe(false);

    // Continue dragging up — height grows from 28px base
    act(() => firePointerMove(300));
    const height = container.style.getPropertyValue("--inspector-height");
    // raw = 28 + (500 - 300) = 228px → clamped to [150, 600] = 228px
    expect(height).toBe("228px");

    // Release — should persist to store
    act(() => firePointerUp());
    expect(storeResult.current.open).toBe(true);
    expect(storeResult.current.height).toBe(228);
  });

  it("drag below snap threshold closes the panel", () => {
    const container = makeContainer();
    const ref = { current: container };

    act(() => openInspector());

    const { result: resizeResult } = renderHook(() =>
      useVerticalDragResize({
        containerRef: ref,
        currentHeight: 320,
        isOpen: true,
      }),
    );
    const { result: storeResult } = renderHook(() => useInspectorStore());

    // Start drag at y=200, drag down to y=600 (panel gets very short)
    act(() => {
      resizeResult.current.handlePointerDown(makePointerEvent("pointerdown", 200));
    });
    act(() => firePointerMove(600)); // delta = 200 - 600 = -400 → raw = 320 + (-400) = -80
    act(() => firePointerUp());

    expect(storeResult.current.open).toBe(false);
  });

  it("adds and removes body.dragging class", () => {
    const container = makeContainer();
    const ref = { current: container };

    const { result } = renderHook(() =>
      useVerticalDragResize({
        containerRef: ref,
        currentHeight: 320,
        isOpen: true,
      }),
    );

    act(() => {
      result.current.handlePointerDown(makePointerEvent("pointerdown", 500));
    });
    expect(document.body.classList.contains("dragging-v")).toBe(true);

    act(() => firePointerUp());
    expect(document.body.classList.contains("dragging-v")).toBe(false);
  });

  it("keyboard ArrowUp increases height", () => {
    const container = makeContainer();
    const ref = { current: container };

    const { result: resizeResult } = renderHook(() =>
      useVerticalDragResize({
        containerRef: ref,
        currentHeight: 320,
        isOpen: true,
      }),
    );
    const { result: storeResult } = renderHook(() => useInspectorStore());

    act(() => {
      resizeResult.current.handleKeyDown({
        key: "ArrowUp",
        preventDefault: vi.fn(),
      } as unknown as React.KeyboardEvent);
    });

    expect(storeResult.current.height).toBe(330);
    expect(storeResult.current.hasManualHeight).toBe(true);
  });

  it("keyboard ArrowDown decreases height", () => {
    const container = makeContainer();
    const ref = { current: container };

    const { result: resizeResult } = renderHook(() =>
      useVerticalDragResize({
        containerRef: ref,
        currentHeight: 320,
        isOpen: true,
      }),
    );
    const { result: storeResult } = renderHook(() => useInspectorStore());

    act(() => {
      resizeResult.current.handleKeyDown({
        key: "ArrowDown",
        preventDefault: vi.fn(),
      } as unknown as React.KeyboardEvent);
    });

    expect(storeResult.current.height).toBe(310);
  });

  it("keyboard Home sets max height, End sets min height", () => {
    const container = makeContainer();
    const ref = { current: container };

    const { result: resizeResult } = renderHook(() =>
      useVerticalDragResize({
        containerRef: ref,
        currentHeight: 320,
        isOpen: true,
      }),
    );
    const { result: storeResult } = renderHook(() => useInspectorStore());

    act(() => {
      resizeResult.current.handleKeyDown({
        key: "Home",
        preventDefault: vi.fn(),
      } as unknown as React.KeyboardEvent);
    });
    expect(storeResult.current.height).toBe(MAX_HEIGHT);

    act(() => {
      resizeResult.current.handleKeyDown({
        key: "End",
        preventDefault: vi.fn(),
      } as unknown as React.KeyboardEvent);
    });
    expect(storeResult.current.height).toBe(MIN_HEIGHT);
  });
});
