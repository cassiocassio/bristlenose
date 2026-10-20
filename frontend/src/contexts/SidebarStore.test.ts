/**
 * Tests for SidebarStore — hiddenTagGroups, toggle/open/close, width, persistence.
 */

import { describe, it, expect, beforeEach, vi } from "vitest";
import {
  useSidebarStore,
  resetSidebarStore,
  toggleTagGroupHidden,
  setTagGroupsHidden,
  hydrateHiddenTagGroups,
  hydrateFrameworkStates,
  adoptFrameworkDisabled,
  dropFrameworkDisabled,
  toggleToc,
  toggleTags,
  toggleBoth,
  hideAllSidebars,
  showAllSidebars,
  anySidebarOpen,
  openTocOverlay,
  openTocPush,
  closeToc,
  closeTags,
  openTags,
  setTocWidth,
  setTagsWidth,
  enterSoloMode,
  exitSoloMode,
  fitPanels,
  requiredWidth,
  setLayoutContext,
  setNavTabs,
  setNavTools,
  panelFit,
  wantedWidth,
  setHostColumnFolded,
  CONTENT_FLOOR_PX,
  MINIMAP_WIDTH_PX,
} from "./SidebarStore";

import { renderHook, act, waitFor } from "@testing-library/react";

// Mock the API module so the store's writes don't hit the network.
vi.mock("../utils/api", () => ({
  getHiddenTagGroups: vi.fn(() => Promise.resolve([])),
  patchHiddenTagGroups: vi.fn(() => Promise.resolve()),
  putFrameworkStates: vi.fn(),
  getFrameworkStates: vi.fn(() => Promise.resolve({})),
}));

import {
  getFrameworkStates,
  getHiddenTagGroups,
  patchHiddenTagGroups,
  putFrameworkStates,
} from "../utils/api";

// Standalone mock for the setTagFilter callback passed to solo functions.
const mockSetTagFilter = vi.fn();

beforeEach(() => {
  resetSidebarStore();
  localStorage.clear();
  vi.clearAllMocks();
});

describe("hiddenTagGroups", () => {
  it("starts empty", () => {
    const { result } = renderHook(() => useSidebarStore());
    expect(result.current.hiddenTagGroups.size).toBe(0);
  });

  it("toggleTagGroupHidden adds a group", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => toggleTagGroupHidden("Behaviour"));
    expect(result.current.hiddenTagGroups.has("Behaviour")).toBe(true);
  });

  it("toggleTagGroupHidden removes a group on second call", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => toggleTagGroupHidden("Behaviour"));
    act(() => toggleTagGroupHidden("Behaviour"));
    expect(result.current.hiddenTagGroups.has("Behaviour")).toBe(false);
  });

  it("setTagGroupsHidden hides multiple groups", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => setTagGroupsHidden(["Trust", "Feedback", "Visibility"], true));
    expect(result.current.hiddenTagGroups.size).toBe(3);
    expect(result.current.hiddenTagGroups.has("Trust")).toBe(true);
    expect(result.current.hiddenTagGroups.has("Feedback")).toBe(true);
    expect(result.current.hiddenTagGroups.has("Visibility")).toBe(true);
  });

  it("setTagGroupsHidden unhides multiple groups", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => setTagGroupsHidden(["Trust", "Feedback"], true));
    act(() => setTagGroupsHidden(["Trust", "Feedback"], false));
    expect(result.current.hiddenTagGroups.size).toBe(0);
  });

  it("resetSidebarStore clears hiddenTagGroups", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => toggleTagGroupHidden("Behaviour"));
    act(() => resetSidebarStore());
    expect(result.current.hiddenTagGroups.size).toBe(0);
  });

  it("toggle and bulk set are independent", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => toggleTagGroupHidden("Trust"));
    act(() => setTagGroupsHidden(["Feedback"], true));
    expect(result.current.hiddenTagGroups.size).toBe(2);
    expect(result.current.hiddenTagGroups.has("Trust")).toBe(true);
    expect(result.current.hiddenTagGroups.has("Feedback")).toBe(true);
  });
});

describe("hydrateHiddenTagGroups", () => {
  it("applies the persisted set, without writing it back", async () => {
    vi.mocked(getHiddenTagGroups).mockResolvedValueOnce(["Behaviour", "Trust"]);
    const { result } = renderHook(() => useSidebarStore());
    act(() => hydrateHiddenTagGroups());
    await waitFor(() => expect(result.current.hiddenTagGroups.size).toBe(2));
    expect(result.current.hiddenTagGroups.has("Behaviour")).toBe(true);
    expect(patchHiddenTagGroups).not.toHaveBeenCalled();
  });

  it("discards a read that was in flight when an eye was toggled", async () => {
    let answer!: (v: string[]) => void;
    vi.mocked(getHiddenTagGroups).mockReturnValueOnce(new Promise((res) => { answer = res; }));
    const { result } = renderHook(() => useSidebarStore());
    act(() => hydrateHiddenTagGroups());
    act(() => setTagGroupsHidden(["A"], true));
    await act(async () => {
      answer([]);
      await Promise.resolve();
    });
    expect(result.current.hiddenTagGroups.has("A")).toBe(true);
  });

  it("reads once per session, and again after a failed read", async () => {
    vi.mocked(getHiddenTagGroups).mockRejectedValueOnce(new Error("offline"));
    act(() => hydrateHiddenTagGroups());
    await waitFor(() => expect(getHiddenTagGroups).toHaveBeenCalledTimes(1));
    await act(async () => { await Promise.resolve(); });
    act(() => hydrateHiddenTagGroups());
    act(() => hydrateHiddenTagGroups());
    expect(getHiddenTagGroups).toHaveBeenCalledTimes(2);
  });

  // An eye clicked before the read landed used to drop the read and PUT the
  // one group it knew, erasing every other group hidden on the server.
  it("an eye clicked before the read lands keeps the server's other groups", async () => {
    let answer!: (v: string[]) => void;
    vi.mocked(getHiddenTagGroups).mockReturnValueOnce(new Promise((res) => { answer = res; }));
    const { result } = renderHook(() => useSidebarStore());
    act(() => hydrateHiddenTagGroups());
    act(() => toggleTagGroupHidden("Behaviour"));
    expect(patchHiddenTagGroups).toHaveBeenCalledWith({ Behaviour: true });
    await act(async () => {
      answer(["Trust", "Feedback"]);
      await Promise.resolve();
    });
    expect([...result.current.hiddenTagGroups].sort()).toEqual(["Behaviour", "Feedback", "Trust"]);
  });

  it("a group shown while the read was in flight stays shown", async () => {
    let answer!: (v: string[]) => void;
    vi.mocked(getHiddenTagGroups).mockReturnValueOnce(new Promise((res) => { answer = res; }));
    const { result } = renderHook(() => useSidebarStore());
    act(() => hydrateHiddenTagGroups());
    act(() => setTagGroupsHidden(["A"], false));
    await act(async () => {
      answer(["A", "B"]);
      await Promise.resolve();
    });
    expect([...result.current.hiddenTagGroups]).toEqual(["B"]);
  });

  it("after a failed read an eye sends only its group, and the next read fills in the rest", async () => {
    vi.mocked(getHiddenTagGroups).mockRejectedValueOnce(new Error("offline"));
    const { result } = renderHook(() => useSidebarStore());
    act(() => hydrateHiddenTagGroups());
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
    act(() => toggleTagGroupHidden("Behaviour"));
    expect(patchHiddenTagGroups).toHaveBeenLastCalledWith({ Behaviour: true });
    vi.mocked(getHiddenTagGroups).mockResolvedValueOnce(["Behaviour", "Trust"]);
    await act(async () => { hydrateHiddenTagGroups(); await Promise.resolve(); });
    await waitFor(() =>
      expect([...result.current.hiddenTagGroups].sort()).toEqual(["Behaviour", "Trust"]),
    );
  });
});

// A failed save takes the eye back to what the server holds (as R7 does for
// quotes); a later click is the researcher's latest word.
describe("hidden tag groups — a failed save", () => {
  function deferred() {
    let resolve!: () => void;
    let reject!: (e: unknown) => void;
    const promise = new Promise<void>((res, rej) => { resolve = res; reject = rej; });
    return { promise, resolve, reject };
  }

  it("puts the eye back", async () => {
    vi.mocked(patchHiddenTagGroups).mockRejectedValueOnce(new Error("500"));
    const { result } = renderHook(() => useSidebarStore());
    act(() => toggleTagGroupHidden("Behaviour"));
    expect(result.current.hiddenTagGroups.has("Behaviour")).toBe(true);
    await waitFor(() => expect(result.current.hiddenTagGroups.has("Behaviour")).toBe(false));
  });

  it("a failed show after a hide that landed shows the group hidden again", async () => {
    const first = deferred();
    const second = deferred();
    vi.mocked(patchHiddenTagGroups)
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise);
    const { result } = renderHook(() => useSidebarStore());
    act(() => toggleTagGroupHidden("Behaviour"));
    act(() => toggleTagGroupHidden("Behaviour"));
    expect(result.current.hiddenTagGroups.has("Behaviour")).toBe(false);
    await act(async () => { first.resolve(); await first.promise; });
    await act(async () => { second.reject(new Error("500")); await second.promise.catch(() => {}); });
    expect(result.current.hiddenTagGroups.has("Behaviour")).toBe(true);
  });

  it("a failed eye clicked before the read landed goes back to what the read says", async () => {
    let answer!: (v: string[]) => void;
    vi.mocked(getHiddenTagGroups).mockReturnValueOnce(new Promise((res) => { answer = res; }));
    const write = deferred();
    vi.mocked(patchHiddenTagGroups).mockReturnValueOnce(write.promise);
    const { result } = renderHook(() => useSidebarStore());
    act(() => hydrateHiddenTagGroups());
    act(() => setTagGroupsHidden(["Trust"], false)); // the server has it hidden
    await act(async () => { answer(["Trust"]); await Promise.resolve(); });
    expect(result.current.hiddenTagGroups.has("Trust")).toBe(false);
    await act(async () => { write.reject(new Error("500")); await write.promise.catch(() => {}); });
    expect(result.current.hiddenTagGroups.has("Trust")).toBe(true);
  });

  it("an eye whose save fails before the read lands shows what the read says", async () => {
    let answer!: (v: string[]) => void;
    vi.mocked(getHiddenTagGroups).mockReturnValueOnce(new Promise((res) => { answer = res; }));
    vi.mocked(patchHiddenTagGroups).mockRejectedValueOnce(new Error("500"));
    const { result } = renderHook(() => useSidebarStore());
    act(() => hydrateHiddenTagGroups());
    act(() => toggleTagGroupHidden("Trust"));
    await waitFor(() => expect(result.current.hiddenTagGroups.has("Trust")).toBe(false));
    await act(async () => { answer(["Trust"]); await Promise.resolve(); });
    expect(result.current.hiddenTagGroups.has("Trust")).toBe(true);
  });

  it("a read overtaken by a write that landed does not become the eye's fallback", async () => {
    let answer!: (v: string[]) => void;
    vi.mocked(getHiddenTagGroups).mockReturnValueOnce(new Promise((res) => { answer = res; }));
    const first = deferred();
    const second = deferred();
    vi.mocked(patchHiddenTagGroups)
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise);
    const { result } = renderHook(() => useSidebarStore());
    act(() => hydrateHiddenTagGroups());
    act(() => toggleTagGroupHidden("Trust")); // hide: lands
    act(() => toggleTagGroupHidden("Trust")); // show: fails
    await act(async () => { first.resolve(); await first.promise; });
    await act(async () => { answer([]); await Promise.resolve(); }); // read from before the hide
    await act(async () => { second.reject(new Error("500")); await second.promise.catch(() => {}); });
    expect(result.current.hiddenTagGroups.has("Trust")).toBe(true);
  });

  it("a failed hide followed by a show that landed stays shown", async () => {
    const first = deferred();
    const second = deferred();
    vi.mocked(patchHiddenTagGroups)
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise);
    const { result } = renderHook(() => useSidebarStore());
    act(() => toggleTagGroupHidden("Behaviour"));
    act(() => toggleTagGroupHidden("Behaviour"));
    await act(async () => { first.reject(new Error("500")); await first.promise.catch(() => {}); });
    await act(async () => { second.resolve(); await second.promise; });
    expect(result.current.hiddenTagGroups.has("Behaviour")).toBe(false);
  });
});

describe("disabledFrameworks (codebook switch)", () => {
  it("starts empty", () => {
    const { result } = renderHook(() => useSidebarStore());
    expect(result.current.disabledFrameworks.size).toBe(0);
  });

  // The store mirrors the navigator's set and never writes it (the navigator
  // owns the PUT); see adoptFrameworkDisabled.
  it("adoptFrameworkDisabled mirrors the navigator's set without a PUT", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => adoptFrameworkDisabled(new Set(["garrett"])));
    expect(result.current.disabledFrameworks.has("garrett")).toBe(true);
    act(() => adoptFrameworkDisabled(new Set()));
    expect(result.current.disabledFrameworks.size).toBe(0);
    expect(putFrameworkStates).not.toHaveBeenCalled();
  });

  it("dropFrameworkDisabled forgets a framework locally without a PUT", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => adoptFrameworkDisabled(new Set(["garrett"])));
    // Uninstall path: forget the disabled opinion locally (server drops its row).
    act(() => dropFrameworkDisabled("garrett"));
    expect(result.current.disabledFrameworks.has("garrett")).toBe(false);
    expect(putFrameworkStates).not.toHaveBeenCalled();
  });

  it("dropFrameworkDisabled is a no-op for a framework that wasn't disabled", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => dropFrameworkDisabled("norman"));
    expect(result.current.disabledFrameworks.size).toBe(0);
    expect(putFrameworkStates).not.toHaveBeenCalled();
  });

  it("resetSidebarStore clears disabledFrameworks", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => adoptFrameworkDisabled(new Set(["garrett"])));
    act(() => resetSidebarStore());
    expect(result.current.disabledFrameworks.size).toBe(0);
  });

  it("hydrateFrameworkStates applies only disabled (enabled=false) frameworks", async () => {
    (getFrameworkStates as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      garrett: false,
      norman: true,
    });
    const { result } = renderHook(() => useSidebarStore());
    act(() => hydrateFrameworkStates());
    await waitFor(() => expect(result.current.disabledFrameworks.has("garrett")).toBe(true));
    expect(result.current.disabledFrameworks.has("norman")).toBe(false);
  });

  it("hydrate discards a stale fetch if a local toggle landed while in flight", async () => {
    let resolveFetch!: (v: Record<string, boolean>) => void;
    (getFrameworkStates as ReturnType<typeof vi.fn>).mockReturnValueOnce(
      new Promise((res) => {
        resolveFetch = res;
      }),
    );
    const { result } = renderHook(() => useSidebarStore());
    act(() => hydrateFrameworkStates()); // GET in flight
    act(() => adoptFrameworkDisabled(new Set(["garrett"]))); // user toggles before it resolves
    // The in-flight GET now resolves with the pre-toggle (empty) server state:
    await act(async () => {
      resolveFetch({});
      await Promise.resolve();
    });
    // The stale fetch must NOT clobber the user's just-made choice.
    expect(result.current.disabledFrameworks.has("garrett")).toBe(true);
  });

  it("hydrateFrameworkStates is guarded — a second call does not refetch", async () => {
    act(() => hydrateFrameworkStates());
    await waitFor(() => expect(getFrameworkStates).toHaveBeenCalledTimes(1));
    act(() => hydrateFrameworkStates());
    expect(getFrameworkStates).toHaveBeenCalledTimes(1);
    // The guard resets so a fresh session (or test) can hydrate again.
    act(() => resetSidebarStore());
    act(() => hydrateFrameworkStates());
    expect(getFrameworkStates).toHaveBeenCalledTimes(2);
  });
});

describe("persistence", () => {
  it("toggleTagGroupHidden sends that one group", () => {
    act(() => toggleTagGroupHidden("Behaviour"));
    expect(patchHiddenTagGroups).toHaveBeenCalledWith({ Behaviour: true });
  });

  it("toggleTagGroupHidden off shows that one group", () => {
    act(() => toggleTagGroupHidden("Behaviour"));
    vi.clearAllMocks();
    act(() => toggleTagGroupHidden("Behaviour"));
    expect(patchHiddenTagGroups).toHaveBeenCalledWith({ Behaviour: false });
  });

  it("setTagGroupsHidden sends the groups it names", () => {
    act(() => setTagGroupsHidden(["A", "B"], true));
    expect(patchHiddenTagGroups).toHaveBeenCalledWith({ A: true, B: true });
  });

  it("setTagGroupsHidden unhide names only the groups it shows", () => {
    act(() => setTagGroupsHidden(["A", "B"], true));
    vi.clearAllMocks();
    act(() => setTagGroupsHidden(["A"], false));
    expect(patchHiddenTagGroups).toHaveBeenCalledWith({ A: false });
  });
});

// ── Toggle / open / close (tocMode tri-state) ────────────────────────────

describe("toggleToc (closed ↔ push)", () => {
  it("toggleToc cycles closed → push → closed", () => {
    const { result } = renderHook(() => useSidebarStore());
    expect(result.current.tocMode).toBe("closed");
    act(() => toggleToc());
    expect(result.current.tocMode).toBe("push");
    act(() => toggleToc());
    expect(result.current.tocMode).toBe("closed");
  });

  it("toggleTags flips tagsOpen", () => {
    const { result } = renderHook(() => useSidebarStore());
    expect(result.current.tagsOpen).toBe(false);
    act(() => toggleTags());
    expect(result.current.tagsOpen).toBe(true);
    act(() => toggleTags());
    expect(result.current.tagsOpen).toBe(false);
  });

  it("toggleBoth opens both when all closed", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => toggleBoth());
    expect(result.current.tocMode).toBe("push");
    expect(result.current.tagsOpen).toBe(true);
  });

  it("toggleBoth closes all when toc is push", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => toggleToc());
    act(() => toggleBoth());
    expect(result.current.tocMode).toBe("closed");
    expect(result.current.tagsOpen).toBe(false);
  });

  it("toggleBoth closes all when toc is overlay", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => openTocOverlay());
    act(() => toggleBoth());
    expect(result.current.tocMode).toBe("closed");
    expect(result.current.tagsOpen).toBe(false);
  });
});

describe("hideAllSidebars / showAllSidebars", () => {
  beforeEach(() => {
    localStorage.clear();
    resetSidebarStore();
  });

  // The invariant the whole stash exists for. A bare toggle would hand back
  // BOTH here — you'd gain a sidebar you never had.
  it("restores the arrangement it hid, not everything", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => toggleToc()); // TOC only — tags stay closed
    act(() => hideAllSidebars());
    expect(result.current.tocMode).toBe("closed");
    expect(result.current.tagsOpen).toBe(false);

    act(() => showAllSidebars());
    expect(result.current.tocMode).toBe("push");
    expect(result.current.tagsOpen).toBe(false);
  });

  it("restores a tags-only arrangement", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => toggleTags());
    act(() => hideAllSidebars());
    act(() => showAllSidebars());
    expect(result.current.tocMode).toBe("closed");
    expect(result.current.tagsOpen).toBe(true);
  });

  it("opens all when there is nothing stashed", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => showAllSidebars());
    expect(result.current.tocMode).toBe("push");
    expect(result.current.tagsOpen).toBe(true);
  });

  // A stashed overlay was a transient peek, never a resting arrangement.
  it("restores a stashed overlay peek as a push panel", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => openTocOverlay());
    act(() => hideAllSidebars());
    act(() => showAllSidebars());
    expect(result.current.tocMode).toBe("push");
  });

  // Guards the stash against a second Hide (menu clicked twice, or a native
  // verb that lagged the mirror) overwriting it with an empty arrangement.
  it("a repeated hide does not clobber the stash", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => toggleToc());
    act(() => hideAllSidebars());
    act(() => hideAllSidebars());
    act(() => showAllSidebars());
    expect(result.current.tocMode).toBe("push");
    expect(result.current.tagsOpen).toBe(false);
  });

  it("anySidebarOpen reports the verb the native menu renders", () => {
    renderHook(() => useSidebarStore());
    expect(anySidebarOpen()).toBe(false);
    act(() => openTocOverlay());
    expect(anySidebarOpen()).toBe(true); // an overlay peek is showing
    act(() => hideAllSidebars());
    expect(anySidebarOpen()).toBe(false);
  });

  it("does not survive a store reset", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => toggleToc());
    act(() => hideAllSidebars());
    act(() => resetSidebarStore());
    act(() => showAllSidebars());
    expect(result.current.tocMode).toBe("push");
    expect(result.current.tagsOpen).toBe(true);
  });
});

describe("openTocOverlay / openTocPush / closeToc", () => {
  it("openTocOverlay sets tocMode to overlay", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => openTocOverlay());
    expect(result.current.tocMode).toBe("overlay");
  });

  it("openTocOverlay is no-op when already in push mode", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => openTocPush());
    act(() => openTocOverlay());
    expect(result.current.tocMode).toBe("push");
  });

  it("openTocPush sets tocMode to push", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => openTocPush());
    expect(result.current.tocMode).toBe("push");
  });

  it("openTocPush works from overlay mode", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => openTocOverlay());
    act(() => openTocPush());
    expect(result.current.tocMode).toBe("push");
  });

  it("closeToc sets tocMode to closed from push", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => openTocPush());
    act(() => closeToc());
    expect(result.current.tocMode).toBe("closed");
  });

  it("closeToc sets tocMode to closed from overlay", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => openTocOverlay());
    act(() => closeToc());
    expect(result.current.tocMode).toBe("closed");
  });
});

describe("closeTags / openTags", () => {
  it("closeTags sets tagsOpen to false", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => toggleTags());
    act(() => closeTags());
    expect(result.current.tagsOpen).toBe(false);
  });

  it("openTags sets tagsOpen to true", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => openTags());
    expect(result.current.tagsOpen).toBe(true);
  });

  it("openTags is idempotent when already open", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => openTags());
    act(() => openTags());
    expect(result.current.tagsOpen).toBe(true);
  });
});

// ── Width clamping ───────────────────────────────────────────────────────

describe("setTocWidth / setTagsWidth", () => {
  it("setTocWidth stores value within range", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => setTocWidth(300));
    expect(result.current.tocWidth).toBe(300);
  });

  it("setTocWidth clamps below MIN_WIDTH (200)", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => setTocWidth(100));
    expect(result.current.tocWidth).toBe(200);
  });

  it("setTocWidth clamps above MAX_WIDTH (480)", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => setTocWidth(600));
    expect(result.current.tocWidth).toBe(480);
  });

  it("setTagsWidth stores value within range", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => setTagsWidth(300));
    expect(result.current.tagsWidth).toBe(300);
  });

  it("setTagsWidth clamps below MIN_WIDTH", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => setTagsWidth(50));
    expect(result.current.tagsWidth).toBe(200);
  });

  it("setTagsWidth clamps above MAX_WIDTH", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => setTagsWidth(999));
    expect(result.current.tagsWidth).toBe(480);
  });
});

// ── localStorage persistence ─────────────────────────────────────────────

describe("localStorage persistence", () => {
  it("toggleToc persists to bn-toc-open", () => {
    act(() => toggleToc());
    expect(localStorage.getItem("bn-toc-open")).toBe("true");
    act(() => toggleToc());
    expect(localStorage.getItem("bn-toc-open")).toBe("false");
  });

  it("toggleTags persists to bn-tags-open", () => {
    act(() => toggleTags());
    expect(localStorage.getItem("bn-tags-open")).toBe("true");
  });

  it("openTocPush persists to bn-toc-open", () => {
    act(() => openTocPush());
    expect(localStorage.getItem("bn-toc-open")).toBe("true");
  });

  it("openTocOverlay does not persist", () => {
    act(() => openTocOverlay());
    // localStorage should still be "false" (default from reset)
    expect(localStorage.getItem("bn-toc-open")).toBeNull();
  });

  it("openTags persists to bn-tags-open", () => {
    act(() => openTags());
    expect(localStorage.getItem("bn-tags-open")).toBe("true");
  });

  it("setTocWidth persists to bn-toc-width", () => {
    act(() => setTocWidth(320));
    expect(localStorage.getItem("bn-toc-width")).toBe("320");
  });

  it("setTagsWidth persists to bn-tags-width", () => {
    act(() => setTagsWidth(310));
    expect(localStorage.getItem("bn-tags-width")).toBe("310");
  });
});

// ── Reset ────────────────────────────────────────────────────────────────

describe("resetSidebarStore", () => {
  it("resets width and open state", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => toggleToc());
    act(() => setTocWidth(400));
    act(() => resetSidebarStore());
    expect(result.current.tocMode).toBe("closed");
    expect(result.current.tagsOpen).toBe(false);
    // The left nav opens at 240 — above the 200px drag minimum, so a reset
    // leaves room to narrow as well as widen. The tag sidebar keeps 280.
    expect(result.current.tocWidth).toBe(240);
    expect(result.current.tagsWidth).toBe(280);
  });

  it("resets solo mode state", () => {
    const { result } = renderHook(() => useSidebarStore());
    const filter = { unchecked: ["a"], noTagsUnchecked: false, clearAll: false };
    act(() => enterSoloMode("Delight", ["Delight", "Trust", "Habit"], filter, mockSetTagFilter));
    act(() => resetSidebarStore());
    expect(result.current.soloTag).toBeNull();
    expect(result.current.savedTagFilter).toBeNull();
  });
});

// ── Solo / focus mode ─────────────────────────────────────────────────────

describe("solo mode", () => {
  const ALL_TAGS = ["Delight", "Trust", "Habit", "Doubt"];
  const ORIGINAL_FILTER = { unchecked: ["Trust"], noTagsUnchecked: false, clearAll: false };

  it("enterSoloMode sets soloTag", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => enterSoloMode("Delight", ALL_TAGS, ORIGINAL_FILTER, mockSetTagFilter));
    expect(result.current.soloTag).toBe("delight");
  });

  it("enterSoloMode saves the current tag filter", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => enterSoloMode("Delight", ALL_TAGS, ORIGINAL_FILTER, mockSetTagFilter));
    expect(result.current.savedTagFilter).toEqual(ORIGINAL_FILTER);
  });

  it("enterSoloMode calls setTagFilter with only the solo tag checked", () => {
    act(() => enterSoloMode("Delight", ALL_TAGS, ORIGINAL_FILTER, mockSetTagFilter));
    expect(mockSetTagFilter).toHaveBeenCalledWith({
      unchecked: ["Trust", "Habit", "Doubt"],
      noTagsUnchecked: true,
      clearAll: false,
    });
  });

  it("switching solo tag preserves original savedTagFilter", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => enterSoloMode("Delight", ALL_TAGS, ORIGINAL_FILTER, mockSetTagFilter));
    mockSetTagFilter.mockClear();
    // Now switch to Trust — the savedTagFilter should still be ORIGINAL_FILTER
    act(() => enterSoloMode("Trust", ALL_TAGS, { unchecked: ["Delight", "Habit", "Doubt"], noTagsUnchecked: true, clearAll: false }, mockSetTagFilter));
    expect(result.current.soloTag).toBe("trust");
    expect(result.current.savedTagFilter).toEqual(ORIGINAL_FILTER);
    expect(mockSetTagFilter).toHaveBeenCalledWith({
      unchecked: ["Delight", "Habit", "Doubt"],
      noTagsUnchecked: true,
      clearAll: false,
    });
  });

  it("exitSoloMode clears soloTag and savedTagFilter", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => enterSoloMode("Delight", ALL_TAGS, ORIGINAL_FILTER, mockSetTagFilter));
    act(() => exitSoloMode(mockSetTagFilter));
    expect(result.current.soloTag).toBeNull();
    expect(result.current.savedTagFilter).toBeNull();
  });

  it("exitSoloMode restores the saved tag filter", () => {
    act(() => enterSoloMode("Delight", ALL_TAGS, ORIGINAL_FILTER, mockSetTagFilter));
    mockSetTagFilter.mockClear();
    act(() => exitSoloMode(mockSetTagFilter));
    expect(mockSetTagFilter).toHaveBeenCalledWith(ORIGINAL_FILTER);
  });

  it("exitSoloMode with no saved filter restores empty filter", () => {
    // Edge case: exitSoloMode called without enterSoloMode
    mockSetTagFilter.mockClear();
    act(() => exitSoloMode(mockSetTagFilter));
    expect(mockSetTagFilter).toHaveBeenCalledWith({
      unchecked: [],
      noTagsUnchecked: false,
      clearAll: false,
    });
  });

  it("starts with soloTag null", () => {
    const { result } = renderHook(() => useSidebarStore());
    expect(result.current.soloTag).toBeNull();
    expect(result.current.savedTagFilter).toBeNull();
  });
});

// ── Fit to width ──────────────────────────────────────────────────────────

// CONTENT_FLOOR_PX / MINIMAP_WIDTH_PX are pinned to the CSS tokens they name by
// tests/test_sidebar_floor_tokens.py — from pytest, because this side has no
// node types for a file read and Vite refuses a `?raw` import from outside
// frontend/ (the same reason safeUrl.test.ts imports its fixture).

describe("fitPanels — the minimap, then the left panel, then the tag sidebar", () => {
  const wish = {
    tocWanted: true,
    tagsWanted: true,
    tocWidth: 240,
    tagsWidth: 280,
    rightColumn: true,
  };
  // floor 368 + 240 + 280 + 80
  const all = CONTENT_FLOOR_PX + 240 + 280 + MINIMAP_WIDTH_PX;
  const shown = (tocOpen: boolean, tagsOpen: boolean, minimapVisible: boolean) =>
    ({ tocOpen, tagsOpen, minimapVisible, barMode: "full" });

  it("shows everything when it fits", () => {
    expect(fitPanels({ ...wish, available: all })).toEqual(shown(true, true, true));
  });

  it("drops the minimap first: it is drawn for you, the panels you opened", () => {
    expect(fitPanels({ ...wish, available: all - 1 })).toEqual(shown(true, true, false));
  });

  it("then the left panel", () => {
    expect(fitPanels({ ...wish, available: all - MINIMAP_WIDTH_PX - 1 })).toEqual(shown(false, true, false));
  });

  it("then the tag sidebar, and never the centre", () => {
    expect(fitPanels({ ...wish, available: CONTENT_FLOOR_PX + 280 - 1 })).toEqual(shown(false, false, false));
    // Below the floor there is nothing left to close: the fit is the same.
    expect(fitPanels({ ...wish, available: 100 })).toEqual(shown(false, false, false));
  });

  it("closes only what is needed — a left panel alone survives where both would not", () => {
    const one = fitPanels({ ...wish, tagsWanted: false, available: CONTENT_FLOOR_PX + 240 });
    expect(one.tocOpen).toBe(true);
    expect(one.minimapVisible).toBe(false);
  });

  it("a lens without the right column counts neither tags nor minimap", () => {
    // tagsOpen is a persisted wish that outlives the Quotes lens.
    const fit = fitPanels({ ...wish, rightColumn: false, available: CONTENT_FLOOR_PX + 240 });
    expect(fit).toEqual(shown(true, false, false));
  });

  it("an unmeasured width (Infinity) closes nothing", () => {
    expect(fitPanels({ ...wish, available: Infinity })).toEqual(shown(true, true, true));
  });
});

describe("fitPanels — the browser tab bar gives way before anything else", () => {
  // A bar that needs 700 on one row, 600 condensed, 500 with its icons up.
  const bar = { full: 700, condensed: 600, iconsUp: 500 };
  const wish = { tocWanted: true, tagsWanted: true, tocWidth: 240, tagsWidth: 280, rightColumn: true, bar };
  const panels = 240 + 280 + MINIMAP_WIDTH_PX;

  it("keeps the full bar while it fits beside every panel", () => {
    expect(fitPanels({ ...wish, available: panels + 700 }).barMode).toBe("full");
  });

  it("condenses, then moves its icons up, before the minimap goes", () => {
    const a = fitPanels({ ...wish, available: panels + 699 });
    expect([a.barMode, a.minimapVisible]).toEqual(["condensed", true]);
    const b = fitPanels({ ...wish, available: panels + 599 });
    expect([b.barMode, b.minimapVisible]).toEqual(["iconsUp", true]);
    const c = fitPanels({ ...wish, available: panels + 499 });
    expect([c.barMode, c.minimapVisible, c.tocOpen]).toEqual(["iconsUp", false, true]);
  });

  it("closes the reader's panels before the tabs would wrap, Contents first", () => {
    const toc = fitPanels({ ...wish, available: 240 + 280 + 499 });
    expect([toc.tocOpen, toc.tagsOpen]).toEqual([false, true]);
    const tags = fitPanels({ ...wish, available: 280 + 499 });
    expect([tags.tocOpen, tags.tagsOpen]).toEqual([false, false]);
  });

  it("needs at least the quote floor even when the bar is narrower", () => {
    const narrow = { full: 200, condensed: 150, iconsUp: 100 };
    const fit = fitPanels({ ...wish, bar: narrow, available: 240 + 280 + CONTENT_FLOOR_PX });
    expect([fit.barMode, fit.minimapVisible, fit.tocOpen, fit.tagsOpen]).toEqual(["iconsUp", false, true, true]);
  });

  it("is one-way: as the width falls, no step it took is undone", () => {
    const order = (f: ReturnType<typeof fitPanels>) => [
      f.barMode !== "full", f.barMode === "iconsUp", !f.minimapVisible, !f.tocOpen, !f.tagsOpen,
    ];
    let prev: boolean[] | null = null;
    for (let available = 2000; available >= 0; available -= 1) {
      const now = order(fitPanels({ ...wish, available }));
      if (prev) now.forEach((taken, i) => expect(prev![i] && !taken).toBe(false));
      // and the steps are taken in order: a later one never without the earlier
      now.forEach((taken, i) => { if (taken && i > 0) expect(now[i - 1]).toBe(true); });
      prev = now;
    }
  });

  it("an exempt panel is skipped, and the other gives way in its place", () => {
    const fit = fitPanels({ ...wish, exempt: "toc", available: 240 + 280 + 499 });
    expect([fit.tocOpen, fit.tagsOpen]).toEqual([true, false]);
  });
});

describe("requiredWidth — the wish, not the fit", () => {
  it("is floor + wanted panels regardless of available — the minimap goes before the Mac's column", () => {
    const input = { tocWanted: true, tagsWanted: true, tocWidth: 240, tagsWidth: 280, rightColumn: true, available: 100 };
    expect(requiredWidth(input)).toBe(CONTENT_FLOOR_PX + 240 + 280);
    expect(requiredWidth({ ...input, tocWanted: false })).toBe(CONTENT_FLOOR_PX + 280);
    expect(requiredWidth({ ...input, rightColumn: false })).toBe(CONTENT_FLOOR_PX + 240);
  });
});

describe("fitPanels — the Mac's projects column folds after the minimap", () => {
  const wish = { tocWanted: true, tagsWanted: true, tocWidth: 240, tagsWidth: 280, rightColumn: true };
  const all = CONTENT_FLOOR_PX + 240 + 280 + MINIMAP_WIDTH_PX;

  it("while the column is folded the minimap stays hidden, however wide the detail grows", () => {
    expect(fitPanels({ ...wish, available: all + 500, hostColumnFolded: true }))
      .toEqual({ tocOpen: true, tagsOpen: true, minimapVisible: false, barMode: "full" });
  });

  it("the panels still give way in their order behind the fold", () => {
    const fit = fitPanels({ ...wish, available: CONTENT_FLOOR_PX + 280, hostColumnFolded: true });
    expect([fit.tocOpen, fit.tagsOpen, fit.minimapVisible]).toEqual([false, true, false]);
  });

  it("the column folds against a wish that leaves the minimap out, so the order is one-way", () => {
    // Narrowing the detail: the minimap goes at `all`, the column at requiredWidth.
    const required = requiredWidth({ ...wish, available: 0 });
    expect(fitPanels({ ...wish, available: required }).minimapVisible).toBe(false);
    expect(fitPanels({ ...wish, available: required }).tocOpen).toBe(true);
    expect(required).toBeLessThan(all);
  });

  it("the store carries native's fold into what the layout shows, and a reset forgets it", () => {
    act(() => {
      openTocPush();
      openTags();
      setLayoutContext(all + 500, true);
    });
    expect(panelFit().minimapVisible).toBe(true);
    act(() => setHostColumnFolded(true));
    expect(panelFit().minimapVisible).toBe(false);
    act(() => setHostColumnFolded(false));
    expect(panelFit().minimapVisible).toBe(true);
    act(() => setHostColumnFolded(true));
    resetSidebarStore();
    expect(snapshot().hostColumnFolded).toBe(false);
  });

  it("a lens without the right column has nothing to hold back", () => {
    const fit = fitPanels({ ...wish, rightColumn: false, available: CONTENT_FLOOR_PX + 240, hostColumnFolded: true });
    expect([fit.tocOpen, fit.tagsOpen, fit.minimapVisible]).toEqual([true, false, false]);
  });
});

describe("fitPanels — the panel just opened is exempt", () => {
  const wish = { tocWanted: true, tagsWanted: true, tocWidth: 240, tagsWidth: 280, rightColumn: true };
  // Both panels beside the floor, no minimap: a pixel less and a panel must go.
  const both = CONTENT_FLOOR_PX + 240 + 280;
  const shown = (tocOpen: boolean, tagsOpen: boolean, minimapVisible: boolean) =>
    ({ tocOpen, tagsOpen, minimapVisible, barMode: "full" });

  it("tags just opened: the minimap goes, then the left panel, tags stays", () => {
    expect(fitPanels({ ...wish, available: both - 1, exempt: "tags" })).toEqual(shown(false, true, false));
  });

  it("left panel just opened: the minimap goes, then tags, the left panel stays", () => {
    // 680 holds floor + toc (608) but not + tags: the minimap AND tags go.
    expect(fitPanels({ ...wish, available: 680, exempt: "toc" })).toEqual(shown(true, false, false));
  });

  it("the exempt panel is never closed, even when the centre must squeeze", () => {
    // 480 cannot hold floor + tags (648): the centre squeezes rather than the
    // press opening nothing.
    expect(fitPanels({ ...wish, available: 480, exempt: "tags" })).toEqual(shown(false, true, false));
  });
});

describe("store fit — toggles act on what is showing", () => {
  // Both panels beside the floor, no minimap: a pixel less and a panel must go.
  const both = CONTENT_FLOOR_PX + 240 + 280;
  const shown = (tocOpen: boolean, tagsOpen: boolean, minimapVisible: boolean) =>
    ({ tocOpen, tagsOpen, minimapVisible, barMode: "full" });

  it("a narrow window auto-closes the left panel without touching the wish", () => {
    act(() => {
      openTocPush();
      openTags();
      setLayoutContext(both - 1, true);
    });
    // tags was opened last, so it is exempt and the left panel gives way.
    expect(panelFit()).toEqual(shown(false, true, false));
    expect(snapshot().tocMode).toBe("push");
    // The Mac folds its projects column against the wished panels, not the minimap.
    expect(wantedWidth()).toBe(both);
    // Widening brings it back with nothing to remember, the minimap last.
    act(() => setLayoutContext(both, true));
    expect(panelFit()).toEqual(shown(true, true, false));
    act(() => setLayoutContext(both + MINIMAP_WIDTH_PX, true));
    expect(panelFit()).toEqual(shown(true, true, true));
  });

  it("`[` on an auto-closed left panel OPENS it — the tag sidebar gives way, its wish untouched", () => {
    act(() => {
      openTocPush();
      openTags();
      setLayoutContext(both - 1, true);
    });
    expect(panelFit().tocOpen).toBe(false);
    act(() => toggleToc());
    expect(panelFit()).toEqual(shown(true, false, false));
    expect(snapshot().tagsOpen).toBe(true);
    expect(localStorage.getItem("bn-tags-open")).toBe("true");
    // …and widening shows both again.
    act(() => setLayoutContext(both, true));
    expect(panelFit()).toEqual(shown(true, true, false));
  });

  it("`]` on an auto-closed tag sidebar OPENS it — the left panel gives way", () => {
    act(() => {
      openTags();
      openTocPush();
      setLayoutContext(both - 1, true);
    });
    expect(panelFit()).toEqual(shown(true, false, false));
    act(() => toggleTags());
    expect(panelFit()).toEqual(shown(false, true, false));
    expect(snapshot().tocMode).toBe("push");
  });

  it("closing the exempt panel ends its exemption", () => {
    act(() => {
      openTocPush();
      openTags();
      closeTags();
      openTags();
      closeTags();
      setLayoutContext(both - 1, true);
    });
    expect(snapshot().lastOpened).toBeNull();
    // Only the left panel is wished; it fits, minimap and all.
    expect(panelFit()).toEqual(shown(true, false, true));
  });

  it("`]` on a showing tag sidebar closes it, and the left panel returns", () => {
    act(() => {
      openTocPush();
      openTags();
      setLayoutContext(both - 1, true);
      toggleTags();
    });
    expect(snapshot().tagsOpen).toBe(false);
    expect(panelFit().tocOpen).toBe(true);
  });

  it("show all sidebars clears the exemption — plain order applies", () => {
    act(() => {
      openTocPush();
      openTags();
      hideAllSidebars();
      showAllSidebars();
      setLayoutContext(both - 1, true);
    });
    expect(snapshot().lastOpened).toBeNull();
    expect(panelFit()).toEqual(shown(false, true, false));
  });

  it("the toggles see the tab bar too: a panel the bar closed reads as closed", () => {
    // NavBar reports a bar that needs more than the floor; with both panels
    // wished, the left panel closes for it, and `[` must open it, not close it.
    act(() => {
      openTocPush();
      openTags();
      setNavTabs({ full: 500, condensed: 450 });
      setNavTools({ full: 100, condensed: 90 });
      setLayoutContext(240 + 280 + 449, true, 0);
    });
    expect(panelFit()).toEqual({ tocOpen: false, tagsOpen: true, minimapVisible: false, barMode: "iconsUp" });
    act(() => toggleToc());
    expect(panelFit().tocOpen).toBe(true);
    act(() => { setNavTabs(null); setNavTools(null); });
  });

  it("setLayoutContext is equality-guarded", () => {
    const { result } = renderHook(() => useSidebarStore());
    const before = result.current;
    act(() => setLayoutContext(Infinity, false));
    expect(result.current).toBe(before);
  });
});

function snapshot() {
  const { result } = renderHook(() => useSidebarStore());
  return result.current;
}
