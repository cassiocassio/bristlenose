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
  closeToc,
  closeTags,
  openToc,
  openTags,
  setTocWidth,
  setTagsWidth,
} from "./SidebarStore";
import { renderHook, act } from "@testing-library/react";

// Mock the API module so fire-and-forget PUTs don't hit the network.
vi.mock("../utils/api", () => ({
  putHiddenTagGroups: vi.fn(),
}));

import { putHiddenTagGroups } from "../utils/api";

beforeEach(() => {
  resetSidebarStore();
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

// ── Toggle / open / close ────────────────────────────────────────────────

describe("toggleToc / toggleTags", () => {
  it("toggleToc flips tocOpen", () => {
    const { result } = renderHook(() => useSidebarStore());
    expect(result.current.tocOpen).toBe(false);
    act(() => toggleToc());
    expect(result.current.tocOpen).toBe(true);
    act(() => toggleToc());
    expect(result.current.tocOpen).toBe(false);
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
    expect(result.current.tocOpen).toBe(true);
    expect(result.current.tagsOpen).toBe(true);
  });

  it("toggleBoth closes all when any open", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => toggleToc());
    act(() => toggleBoth());
    expect(result.current.tocOpen).toBe(false);
    expect(result.current.tagsOpen).toBe(false);
  });
});

describe("closeToc / closeTags", () => {
  it("closeToc sets tocOpen to false", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => toggleToc());
    expect(result.current.tocOpen).toBe(true);
    act(() => closeToc());
    expect(result.current.tocOpen).toBe(false);
  });

  it("closeTags sets tagsOpen to false", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => toggleTags());
    act(() => closeTags());
    expect(result.current.tagsOpen).toBe(false);
  });
});

describe("openToc / openTags", () => {
  it("openToc sets tocOpen to true", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => openToc());
    expect(result.current.tocOpen).toBe(true);
  });

  it("openTags sets tagsOpen to true", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => openTags());
    expect(result.current.tagsOpen).toBe(true);
  });

  it("openToc is idempotent when already open", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => openToc());
    act(() => openToc());
    expect(result.current.tocOpen).toBe(true);
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

  it("setTocWidth clamps above MAX_WIDTH (320)", () => {
    const { result } = renderHook(() => useSidebarStore());
    act(() => setTocWidth(600));
    expect(result.current.tocWidth).toBe(320);
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
    expect(result.current.tagsWidth).toBe(320);
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

  it("openToc persists to bn-toc-open", () => {
    act(() => openToc());
    expect(localStorage.getItem("bn-toc-open")).toBe("true");
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
    expect(result.current.tocOpen).toBe(false);
    expect(result.current.tagsOpen).toBe(false);
    expect(result.current.tocWidth).toBe(280);
    expect(result.current.tagsWidth).toBe(280);
  });
});
