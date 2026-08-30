/**
 * Tests for SidebarStore — hiddenTagGroups, toggle/open/close, width, persistence.
 */

import { describe, it, expect, beforeEach, vi } from "vitest";
import {
  useSidebarStore,
  resetSidebarStore,
  toggleTagGroupHidden,
  setTagGroupsHidden,
  initHiddenTagGroups,
  hydrateFrameworkStates,
  setFrameworkDisabled,
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
} from "./SidebarStore";
import { renderHook, act, waitFor } from "@testing-library/react";

// Mock the API module so fire-and-forget PUTs don't hit the network.
vi.mock("../utils/api", () => ({
  putHiddenTagGroups: vi.fn(),
  putFrameworkStates: vi.fn(),
  getFrameworkStates: vi.fn(() => Promise.resolve({})),
}));

import {
  getFrameworkStates,
  putFrameworkStates,
  putHiddenTagGroups,
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

describe("initHiddenTagGroups", () => {
  it("hydrates from API data", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => initHiddenTagGroups(["Behaviour", "Trust"]));
    expect(result.current.hiddenTagGroups.size).toBe(2);
    expect(result.current.hiddenTagGroups.has("Behaviour")).toBe(true);
    expect(result.current.hiddenTagGroups.has("Trust")).toBe(true);
  });

  it("replaces existing hidden groups", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => toggleTagGroupHidden("Old"));
    act(() => initHiddenTagGroups(["New"]));
    expect(result.current.hiddenTagGroups.has("Old")).toBe(false);
    expect(result.current.hiddenTagGroups.has("New")).toBe(true);
  });

  it("empty array clears all", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => initHiddenTagGroups(["A", "B"]));
    act(() => initHiddenTagGroups([]));
    expect(result.current.hiddenTagGroups.size).toBe(0);
  });

  it("does not call putHiddenTagGroups (hydration is read-only)", () => {
    act(() => initHiddenTagGroups(["A"]));
    expect(putHiddenTagGroups).not.toHaveBeenCalled();
  });
});

describe("disabledFrameworks (codebook switch)", () => {
  it("starts empty", () => {
    const { result } = renderHook(() => useSidebarStore());
    expect(result.current.disabledFrameworks.size).toBe(0);
  });

  it("setFrameworkDisabled(true) adds a framework and PUTs {fid: false}", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => setFrameworkDisabled("garrett", true));
    expect(result.current.disabledFrameworks.has("garrett")).toBe(true);
    expect(putFrameworkStates).toHaveBeenCalledWith({ garrett: false });
  });

  it("setFrameworkDisabled(false) removes it and PUTs the shrunk map", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => setFrameworkDisabled("garrett", true));
    act(() => setFrameworkDisabled("garrett", false));
    expect(result.current.disabledFrameworks.has("garrett")).toBe(false);
    expect(putFrameworkStates).toHaveBeenLastCalledWith({});
  });

  it("dropFrameworkDisabled forgets a framework locally without a PUT", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => setFrameworkDisabled("garrett", true));
    (putFrameworkStates as ReturnType<typeof vi.fn>).mockClear();
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
    act(() => setFrameworkDisabled("garrett", true));
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
    act(() => setFrameworkDisabled("garrett", true)); // user toggles before it resolves
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
  it("toggleTagGroupHidden calls putHiddenTagGroups", () => {
    act(() => toggleTagGroupHidden("Behaviour"));
    expect(putHiddenTagGroups).toHaveBeenCalledWith(["Behaviour"]);
  });

  it("toggleTagGroupHidden off sends empty array", () => {
    act(() => toggleTagGroupHidden("Behaviour"));
    vi.clearAllMocks();
    act(() => toggleTagGroupHidden("Behaviour"));
    expect(putHiddenTagGroups).toHaveBeenCalledWith([]);
  });

  it("setTagGroupsHidden calls putHiddenTagGroups", () => {
    act(() => setTagGroupsHidden(["A", "B"], true));
    expect(putHiddenTagGroups).toHaveBeenCalledWith(
      expect.arrayContaining(["A", "B"]),
    );
  });

  it("setTagGroupsHidden unhide calls putHiddenTagGroups", () => {
    act(() => setTagGroupsHidden(["A", "B"], true));
    vi.clearAllMocks();
    act(() => setTagGroupsHidden(["A"], false));
    expect(putHiddenTagGroups).toHaveBeenCalledWith(["B"]);
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
