/**
 * Tests for useTocOverlay — hover intent, direction-aware leave, safe zone,
 * click outside, rail area click.
 */

import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useTocOverlay } from "./useTocOverlay";
import type { TocMode } from "../contexts/SidebarStore";

// ── Mocks ────────────────────────────────────────────────────────────────

const mockOpenTocOverlay = vi.fn();
const mockOnClose = vi.fn();

vi.mock("../contexts/SidebarStore", () => ({
  openTocOverlay: (...args: unknown[]) => mockOpenTocOverlay(...args),
}));

// ── Helpers ──────────────────────────────────────────────────────────────

function makeRef<T>(value: T | null = null) {
  return { current: value };
}

function makeMouseEvent(overrides: Partial<React.MouseEvent> = {}): React.MouseEvent {
  return {
    target: document.createElement("div"),
    clientX: 0,
    clientY: 0,
    ...overrides,
  } as unknown as React.MouseEvent;
}

function renderOverlay(tocMode: TocMode) {
  const railEl = document.createElement("div");
  const panelEl = document.createElement("div");
  // Mock getBoundingClientRect for direction-aware leave tests.
  railEl.getBoundingClientRect = () => ({
    left: 0, right: 36, top: 0, bottom: 800, width: 36, height: 800,
    x: 0, y: 0, toJSON: () => "",
  });
  panelEl.getBoundingClientRect = () => ({
    left: 36, right: 316, top: 0, bottom: 800, width: 280, height: 800,
    x: 36, y: 0, toJSON: () => "",
  });
  const railRef = makeRef(railEl);
  const panelRef = makeRef(panelEl);
  return renderHook(() =>
    useTocOverlay({ tocMode, railRef, panelRef, onClose: mockOnClose }),
  );
}

// ── Setup ────────────────────────────────────────────────────────────────

beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

// ── Tests ────────────────────────────────────────────────────────────────

describe("hover intent", () => {
  it("opens overlay after 400ms hover on rail", () => {
    const { result } = renderOverlay("closed");

    act(() => {
      result.current.onRailMouseEnter(makeMouseEvent());
    });

    expect(mockOpenTocOverlay).not.toHaveBeenCalled();

    act(() => {
      vi.advanceTimersByTime(400);
    });

    expect(mockOpenTocOverlay).toHaveBeenCalledOnce();
  });

  it("cancels overlay if mouse leaves rail before 400ms", () => {
    const { result } = renderOverlay("closed");

    act(() => {
      result.current.onRailMouseEnter(makeMouseEvent());
    });

    act(() => {
      vi.advanceTimersByTime(200);
    });

    // Leave rightward (clientX > rail right) to trigger leave logic
    act(() => {
      result.current.onRailMouseLeave(makeMouseEvent({ clientX: 50 }));
    });

    act(() => {
      vi.advanceTimersByTime(300);
    });

    expect(mockOpenTocOverlay).not.toHaveBeenCalled();
  });

  it("does not start hover timer when already in overlay mode", () => {
    const { result } = renderOverlay("overlay");

    act(() => {
      result.current.onRailMouseEnter(makeMouseEvent());
    });

    act(() => {
      vi.advanceTimersByTime(500);
    });

    expect(mockOpenTocOverlay).not.toHaveBeenCalled();
  });

  it("does not start hover timer when in push mode", () => {
    const { result } = renderOverlay("push");

    act(() => {
      result.current.onRailMouseEnter(makeMouseEvent());
    });

    act(() => {
      vi.advanceTimersByTime(500);
    });

    expect(mockOpenTocOverlay).not.toHaveBeenCalled();
  });

  it("does not start hover timer when entering via .rail-btn", () => {
    const { result } = renderOverlay("closed");

    const btn = document.createElement("button");
    btn.className = "rail-btn";

    act(() => {
      result.current.onRailMouseEnter(makeMouseEvent({ target: btn }));
    });

    act(() => {
      vi.advanceTimersByTime(500);
    });

    expect(mockOpenTocOverlay).not.toHaveBeenCalled();
  });
});

describe("safe zone (button)", () => {
  it("onButtonMouseEnter cancels active hover timer", () => {
    const { result } = renderOverlay("closed");

    act(() => {
      result.current.onRailMouseEnter(makeMouseEvent());
    });

    // Button enter cancels timer
    act(() => {
      result.current.onButtonMouseEnter();
    });

    act(() => {
      vi.advanceTimersByTime(500);
    });

    expect(mockOpenTocOverlay).not.toHaveBeenCalled();
  });

  it("onButtonMouseLeave restarts hover timer", () => {
    const { result } = renderOverlay("closed");

    // Simulate: enter rail → enter button → leave button
    act(() => {
      result.current.onRailMouseEnter(makeMouseEvent());
    });
    act(() => {
      result.current.onButtonMouseEnter();
    });
    act(() => {
      result.current.onButtonMouseLeave();
    });

    // Timer restarted — should fire after full delay
    act(() => {
      vi.advanceTimersByTime(399);
    });
    expect(mockOpenTocOverlay).not.toHaveBeenCalled();

    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(mockOpenTocOverlay).toHaveBeenCalledOnce();
  });
});

describe("direction-aware leave", () => {
  it("closes when mouse leaves panel rightward (into content)", () => {
    const { result } = renderOverlay("overlay");

    // clientX 320 > panel right (316) → rightward exit
    act(() => {
      result.current.onPanelMouseLeave(makeMouseEvent({ clientX: 320 }));
    });

    act(() => {
      vi.advanceTimersByTime(100);
    });

    expect(mockOnClose).toHaveBeenCalledOnce();
  });

  it("does NOT close when mouse leaves panel leftward", () => {
    const { result } = renderOverlay("overlay");

    // clientX 100 < panel right (316) → leftward/vertical exit
    act(() => {
      result.current.onPanelMouseLeave(makeMouseEvent({ clientX: 100 }));
    });

    act(() => {
      vi.advanceTimersByTime(200);
    });

    expect(mockOnClose).not.toHaveBeenCalled();
  });

  it("does NOT close when mouse leaves rail leftward (off-screen)", () => {
    const { result } = renderOverlay("overlay");

    // clientX -5 < rail left (0) → leftward exit
    act(() => {
      result.current.onRailMouseLeave(makeMouseEvent({ clientX: -5 }));
    });

    act(() => {
      vi.advanceTimersByTime(200);
    });

    expect(mockOnClose).not.toHaveBeenCalled();
  });

  it("starts grace timer when mouse leaves rail rightward", () => {
    const { result } = renderOverlay("overlay");

    // clientX 50 > rail left (0) → rightward exit
    act(() => {
      result.current.onRailMouseLeave(makeMouseEvent({ clientX: 50 }));
    });

    act(() => {
      vi.advanceTimersByTime(100);
    });

    expect(mockOnClose).toHaveBeenCalledOnce();
  });
});

describe("panel continuation", () => {
  it("keeps overlay open when mouse moves from rail to panel", () => {
    const { result } = renderOverlay("overlay");

    // Mouse leaves rail rightward
    act(() => {
      result.current.onRailMouseLeave(makeMouseEvent({ clientX: 50 }));
    });

    // Mouse enters panel within grace period
    act(() => {
      vi.advanceTimersByTime(50);
    });

    act(() => {
      result.current.onPanelMouseEnter();
    });

    // Advance well past grace period
    act(() => {
      vi.advanceTimersByTime(200);
    });

    expect(mockOnClose).not.toHaveBeenCalled();
  });
});

describe("rail area click", () => {
  it("opens overlay on rail area click when closed", () => {
    const { result } = renderOverlay("closed");

    act(() => {
      result.current.onRailAreaClick(makeMouseEvent());
    });

    expect(mockOpenTocOverlay).toHaveBeenCalledOnce();
  });

  it("does not open overlay when clicking the rail-btn", () => {
    const { result } = renderOverlay("closed");

    const btn = document.createElement("button");
    btn.className = "rail-btn";

    act(() => {
      result.current.onRailAreaClick(makeMouseEvent({ target: btn }));
    });

    expect(mockOpenTocOverlay).not.toHaveBeenCalled();
  });
});

describe("click outside", () => {
  it("closes overlay on mousedown outside rail and panel", () => {
    const railEl = document.createElement("div");
    const panelEl = document.createElement("div");
    document.body.appendChild(railEl);
    document.body.appendChild(panelEl);

    const railRef = makeRef(railEl);
    const panelRef = makeRef(panelEl);

    renderHook(() =>
      useTocOverlay({ tocMode: "overlay", railRef, panelRef, onClose: mockOnClose }),
    );

    act(() => {
      const event = new MouseEvent("mousedown", { bubbles: true });
      document.body.dispatchEvent(event);
    });

    expect(mockOnClose).toHaveBeenCalledOnce();

    document.body.removeChild(railEl);
    document.body.removeChild(panelEl);
  });

  it("does not close on click inside panel", () => {
    const railEl = document.createElement("div");
    const panelEl = document.createElement("div");
    document.body.appendChild(railEl);
    document.body.appendChild(panelEl);

    const railRef = makeRef(railEl);
    const panelRef = makeRef(panelEl);

    renderHook(() =>
      useTocOverlay({ tocMode: "overlay", railRef, panelRef, onClose: mockOnClose }),
    );

    act(() => {
      const event = new MouseEvent("mousedown", { bubbles: true });
      panelEl.dispatchEvent(event);
    });

    expect(mockOnClose).not.toHaveBeenCalled();

    document.body.removeChild(railEl);
    document.body.removeChild(panelEl);
  });

  it("does not register listener when not in overlay mode", () => {
    renderOverlay("closed");

    act(() => {
      const event = new MouseEvent("mousedown", { bubbles: true });
      document.body.dispatchEvent(event);
    });

    expect(mockOnClose).not.toHaveBeenCalled();
  });
});
