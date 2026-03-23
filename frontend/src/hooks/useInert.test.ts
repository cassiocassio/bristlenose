import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { renderHook } from "@testing-library/react";
import { useInert, resetInertCount } from "./useInert";

describe("useInert", () => {
  let root: HTMLDivElement;

  beforeEach(() => {
    resetInertCount();
    root = document.createElement("div");
    root.id = "bn-app-root";
    document.body.appendChild(root);
  });

  afterEach(() => {
    root.remove();
  });

  it("sets inert when active", () => {
    const { unmount } = renderHook(() => useInert(true));
    expect(root.hasAttribute("inert")).toBe(true);
    unmount();
  });

  it("removes inert on unmount", () => {
    const { unmount } = renderHook(() => useInert(true));
    expect(root.hasAttribute("inert")).toBe(true);
    unmount();
    expect(root.hasAttribute("inert")).toBe(false);
  });

  it("does nothing when inactive", () => {
    const { unmount } = renderHook(() => useInert(false));
    expect(root.hasAttribute("inert")).toBe(false);
    unmount();
  });

  it("removes inert when active changes to false", () => {
    const { rerender } = renderHook(({ active }) => useInert(active), {
      initialProps: { active: true },
    });
    expect(root.hasAttribute("inert")).toBe(true);

    rerender({ active: false });
    expect(root.hasAttribute("inert")).toBe(false);
  });

  it("handles overlapping modals via reference counting", () => {
    const hook1 = renderHook(() => useInert(true));
    const hook2 = renderHook(() => useInert(true));
    expect(root.hasAttribute("inert")).toBe(true);

    // First modal closes — inert stays because second is still open.
    hook1.unmount();
    expect(root.hasAttribute("inert")).toBe(true);

    // Second modal closes — inert removed.
    hook2.unmount();
    expect(root.hasAttribute("inert")).toBe(false);
  });

  it("is a no-op when #bn-app-root is missing", () => {
    root.remove();
    // Should not throw.
    const { unmount } = renderHook(() => useInert(true));
    unmount();
  });
});
