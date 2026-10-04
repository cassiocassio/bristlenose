/**
 * The sidebar reads defaults until the dev playground loads its store, then the
 * store's live values — without the sidebar ever importing the store.
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";

afterEach(() => {
  sessionStorage.clear();
  vi.resetModules();
});

describe("useSidebarTuning", () => {
  it("returns the defaults while the playground is not loaded", async () => {
    vi.resetModules();
    const { useSidebarTuning, SIDEBAR_TUNING_DEFAULTS } = await import("./sidebarTuning");
    const { result } = renderHook(() => useSidebarTuning());
    expect(result.current).toBe(SIDEBAR_TUNING_DEFAULTS);
  });

  it("follows the playground store once it loads, and its later changes", async () => {
    vi.resetModules();
    const { useSidebarTuning } = await import("./sidebarTuning");
    const { result } = renderHook(() => useSidebarTuning());
    expect(result.current.overlayStyle).toBeNull();

    const store = await act(() => import("./PlaygroundStore"));
    act(() => store.setOverlayStyle("ios"));
    expect(result.current.overlayStyle).toBe("ios");
    act(() => store.setOverlayAutoClose(true));
    expect(result.current.overlayAutoClose).toBe(true);
  });
});
