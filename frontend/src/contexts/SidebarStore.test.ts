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
  toggleToc,
  toggleTags,
  toggleBoth,
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
import { renderHook, act } from "@testing-library/react";

// Mock the API module so fire-and-forget PUTs don't hit the network.
vi.mock("../utils/api", () => ({
  putHiddenTagGroups: vi.fn(),
}));

// Mock QuotesContext so enterSoloMode/exitSoloMode can call setTagFilter.
vi.mock("./QuotesContext", () => ({
  setTagFilter: vi.fn(),
}));

import { putHiddenTagGroups } from "../utils/api";
import { setTagFilter } from "./QuotesContext";

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
    expect(result.current.tocWidth).toBe(280);
    expect(result.current.tagsWidth).toBe(280);
  });

  it("resets solo mode state", () => {
    const { result } = renderHook(() => useSidebarStore());
    const filter = { unchecked: ["a"], noTagsUnchecked: false, clearAll: false };
    act(() => enterSoloMode("Delight", ["Delight", "Trust", "Habit"], filter));
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
    act(() => enterSoloMode("Delight", ALL_TAGS, ORIGINAL_FILTER));
    expect(result.current.soloTag).toBe("delight");
  });

  it("enterSoloMode saves the current tag filter", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => enterSoloMode("Delight", ALL_TAGS, ORIGINAL_FILTER));
    expect(result.current.savedTagFilter).toEqual(ORIGINAL_FILTER);
  });

  it("enterSoloMode calls setTagFilter with only the solo tag checked", () => {
    act(() => enterSoloMode("Delight", ALL_TAGS, ORIGINAL_FILTER));
    expect(setTagFilter).toHaveBeenCalledWith({
      unchecked: ["Trust", "Habit", "Doubt"],
      noTagsUnchecked: true,
      clearAll: false,
    });
  });

  it("switching solo tag preserves original savedTagFilter", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => enterSoloMode("Delight", ALL_TAGS, ORIGINAL_FILTER));
    vi.mocked(setTagFilter).mockClear();
    // Now switch to Trust — the savedTagFilter should still be ORIGINAL_FILTER
    act(() => enterSoloMode("Trust", ALL_TAGS, { unchecked: ["Delight", "Habit", "Doubt"], noTagsUnchecked: true, clearAll: false }));
    expect(result.current.soloTag).toBe("trust");
    expect(result.current.savedTagFilter).toEqual(ORIGINAL_FILTER);
    expect(setTagFilter).toHaveBeenCalledWith({
      unchecked: ["Delight", "Habit", "Doubt"],
      noTagsUnchecked: true,
      clearAll: false,
    });
  });

  it("exitSoloMode clears soloTag and savedTagFilter", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => enterSoloMode("Delight", ALL_TAGS, ORIGINAL_FILTER));
    act(() => exitSoloMode());
    expect(result.current.soloTag).toBeNull();
    expect(result.current.savedTagFilter).toBeNull();
  });

  it("exitSoloMode restores the saved tag filter", () => {
    act(() => enterSoloMode("Delight", ALL_TAGS, ORIGINAL_FILTER));
    vi.mocked(setTagFilter).mockClear();
    act(() => exitSoloMode());
    expect(setTagFilter).toHaveBeenCalledWith(ORIGINAL_FILTER);
  });

  it("exitSoloMode with no saved filter restores empty filter", () => {
    // Edge case: exitSoloMode called without enterSoloMode
    vi.mocked(setTagFilter).mockClear();
    act(() => exitSoloMode());
    expect(setTagFilter).toHaveBeenCalledWith({
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
