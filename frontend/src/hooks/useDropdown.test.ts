import { renderHook, act } from "@testing-library/react";
import { useDropdown } from "./useDropdown";

describe("useDropdown", () => {
  // ── Uncontrolled mode ─────────────────────────────────────────────────

  it("starts closed in uncontrolled mode", () => {
    const { result } = renderHook(() => useDropdown());
    expect(result.current.open).toBe(false);
  });

  it("toggle() opens and closes", () => {
    const { result } = renderHook(() => useDropdown());
    act(() => result.current.toggle());
    expect(result.current.open).toBe(true);
    act(() => result.current.toggle());
    expect(result.current.open).toBe(false);
  });

  it("setOpen(true) opens, setOpen(false) closes", () => {
    const { result } = renderHook(() => useDropdown());
    act(() => result.current.setOpen(true));
    expect(result.current.open).toBe(true);
    act(() => result.current.setOpen(false));
    expect(result.current.open).toBe(false);
  });

  // ── Controlled mode ───────────────────────────────────────────────────

  it("reflects controlled isOpen prop", () => {
    const onToggle = vi.fn();
    const { result, rerender } = renderHook(
      ({ isOpen }) => useDropdown({ isOpen, onToggle }),
      { initialProps: { isOpen: false } },
    );
    expect(result.current.open).toBe(false);

    rerender({ isOpen: true });
    expect(result.current.open).toBe(true);
  });

  it("toggle() calls onToggle in controlled mode", () => {
    const onToggle = vi.fn();
    const { result } = renderHook(() => useDropdown({ isOpen: false, onToggle }));
    act(() => result.current.toggle());
    expect(onToggle).toHaveBeenCalledWith(true);
  });

  it("setOpen() calls onToggle in controlled mode", () => {
    const onToggle = vi.fn();
    const { result } = renderHook(() => useDropdown({ isOpen: true, onToggle }));
    act(() => result.current.setOpen(false));
    expect(onToggle).toHaveBeenCalledWith(false);
  });

  // ── Click-outside dismiss ─────────────────────────────────────────────

  it("closes on outside mousedown", () => {
    // Need a real container so the ref has something to check against
    const container = document.createElement("div");
    const outside = document.createElement("div");
    document.body.appendChild(container);
    document.body.appendChild(outside);

    const { result } = renderHook(() => useDropdown());
    (result.current.containerRef as { current: HTMLDivElement }).current = container;

    act(() => result.current.setOpen(true));
    expect(result.current.open).toBe(true);

    // Click outside the container
    act(() => {
      outside.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
    });
    expect(result.current.open).toBe(false);

    document.body.removeChild(container);
    document.body.removeChild(outside);
  });

  it("does not close on mousedown inside container", () => {
    const container = document.createElement("div");
    document.body.appendChild(container);

    const { result } = renderHook(() => useDropdown());
    // Manually attach the ref
    (result.current.containerRef as { current: HTMLDivElement }).current = container;

    act(() => result.current.setOpen(true));

    act(() => {
      container.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
    });
    expect(result.current.open).toBe(true);

    document.body.removeChild(container);
  });

  // ── Escape dismiss ────────────────────────────────────────────────────

  it("closes on Escape keydown", () => {
    const { result } = renderHook(() => useDropdown());
    act(() => result.current.setOpen(true));

    act(() => {
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    });
    expect(result.current.open).toBe(false);
  });

  it("does not close on non-Escape keydown", () => {
    const { result } = renderHook(() => useDropdown());
    act(() => result.current.setOpen(true));

    act(() => {
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter" }));
    });
    expect(result.current.open).toBe(true);
  });

  it("does not add listeners when closed", () => {
    const addSpy = vi.spyOn(document, "addEventListener");
    renderHook(() => useDropdown());
    // Should not add mousedown or keydown listeners when closed
    const calls = addSpy.mock.calls.map(([event]) => event);
    expect(calls).not.toContain("mousedown");
    expect(calls).not.toContain("keydown");
    addSpy.mockRestore();
  });

  // ── Controlled + Escape ───────────────────────────────────────────────

  it("Escape calls onToggle(false) in controlled mode", () => {
    const onToggle = vi.fn();
    renderHook(() => useDropdown({ isOpen: true, onToggle }));

    act(() => {
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    });
    expect(onToggle).toHaveBeenCalledWith(false);
  });
});
