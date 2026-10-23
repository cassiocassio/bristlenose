/**
 * Each store that writes a mirrored preference hands it to the Mac app (R89).
 * One case per writer, so removing the `storePref` from any one of them fails
 * exactly that case. The Screens navigator's width is pinned in
 * `ScreensLens.test.tsx`, beside its drag.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { applyZoom } from "./zoom";
import {
  closeTags,
  openTags,
  resetSidebarStore,
  setTagsWidth,
  setTocWidth,
  toggleToc,
} from "../contexts/SidebarStore";
import {
  resetInspectorStore,
  setInspectorDimension,
  setInspectorHeight,
  setInspectorSource,
  toggleInspector,
} from "../contexts/InspectorStore";
import { resetScreensNav, setScreensNavOpen } from "../islands/screens/navPanel";
import { resetDiscussionGuide, setDiscussionGuideOpen } from "../islands/discussion/guidePanel";
import { resetLensState, writeLensState } from "../islands/discussion/lensState";
import { useQuoteGrouping } from "../islands/QuoteGroupingToggle";

const w = window as unknown as Record<string, unknown>;
let postMessage: ReturnType<typeof vi.fn>;

function posted(key: string): unknown[] {
  return postMessage.mock.calls
    .map((c) => c[0] as { type: string; key: string; value: unknown })
    .filter((m) => m.type === "report-pref" && m.key === key)
    .map((m) => m.value);
}

beforeEach(() => {
  localStorage.clear();
  resetSidebarStore();
  resetInspectorStore();
  resetScreensNav();
  resetDiscussionGuide();
  resetLensState();
  postMessage = vi.fn();
  w.webkit = { messageHandlers: { navigation: { postMessage } } };
});

afterEach(() => {
  delete w.webkit;
  document.documentElement.style.fontSize = "";
});

describe("the Mac app is handed each persisted preference (R89)", () => {
  it("zoom", () => {
    applyZoom(1.2);
    expect(posted("bristlenose-zoom")).toEqual(["1.2"]);
  });

  it("the contents panel's open state and width", () => {
    toggleToc();
    setTocWidth(300);
    expect(posted("bn-toc-open")).toEqual(["true"]);
    expect(posted("bn-toc-width")).toEqual(["300"]);
  });

  it("the tags panel's open state and width", () => {
    openTags();
    closeTags();
    setTagsWidth(320);
    expect(posted("bn-tags-open")).toEqual(["true", "false"]);
    expect(posted("bn-tags-width")).toEqual(["320"]);
  });

  it("the inspector's open state, height and dimension, but not its source", () => {
    toggleInspector();
    setInspectorHeight(400);
    setInspectorDimension("theme");
    setInspectorSource("cb-1");
    expect(posted("bn-inspector-open")).toEqual(["true"]);
    expect(posted("bn-inspector-height")).toEqual(["400"]);
    expect(posted("bn-inspector-dimension")).toEqual(["theme"]);
    expect(posted("bn-inspector-source")).toEqual([]);
    expect(localStorage.getItem("bn-inspector-source")).toBe("cb-1");
  });

  it("not the inspector height the panel measured for itself", () => {
    setInspectorHeight(352, true);
    expect(localStorage.getItem("bn-inspector-height")).toBe("352");
    expect(posted("bn-inspector-height")).toEqual([]);
  });

  it("the quote grouping", () => {
    const { result } = renderHook(() => useQuoteGrouping("1"));
    act(() => result.current[1]("session"));
    expect(posted("bristlenose-quote-grouping-1")).toEqual(["session"]);
  });

  it("the Screens navigator's open state", () => {
    setScreensNavOpen(false);
    expect(posted("bn-screens-nav-open")).toEqual(["false"]);
  });

  it("Discussion's guide: open state and width", () => {
    setDiscussionGuideOpen(false);
    writeLensState({ mode: "merged", guideView: "summary", session: null, focus: null, navWidth: 333.4 });
    expect(posted("bn-discussion-guide-open")).toEqual(["false"]);
    expect(posted("bn-discussion-nav-width")).toEqual(["333"]);
  });
});
