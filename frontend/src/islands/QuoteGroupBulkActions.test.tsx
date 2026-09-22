/**
 * Bulk quote actions: hide and star over a selection.
 *
 * `h` on a selection is handled in two places that do not know about each
 * other. `handleHide` (hooks/useKeyboardShortcuts.ts) loops the selection and
 * calls `hideQuote` once per quote; each of those reaches the per-card handler
 * QuoteGroup registers, and `handleToggleHide` re-expands the whole selection
 * again. The two loops multiply, so N selected quotes cost N-squared deferred
 * `toggleHide` calls, each firing a full-map PUT.
 *
 * The end state is right either way, because the store writes are idempotent —
 * which is why this has never surfaced, and why the assertion here is about
 * the *cost* of the gesture rather than its result. Both are checked: a fix
 * that makes the arithmetic right by hiding the wrong quotes is not a fix.
 *
 * The bound is deliberately "at most one write per selected quote" rather than
 * an exact count. A single bulk store call (one write for the whole gesture)
 * is the likely fix and should keep this test green; pinning an exact 3 would
 * make the right fix look like a regression.
 *
 * NOTE: this file mounts the real QuoteGroup inside the real provider tree on
 * purpose. A hand-rolled stand-in for the group's handler would only assert
 * what I believe that handler does — the multiplication lives in the
 * composition, so the composition is what has to be under test.
 */

import { render, act } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { FocusProvider, useFocus } from "../contexts/FocusContext";
import { PlayerProvider } from "../contexts/PlayerContext";
import {
  resetStore,
  initFromQuotes,
  getQuotesSnapshot,
  starActionIsUnstar,
} from "../contexts/QuotesContext";
import { resetSidebarStore } from "../contexts/SidebarStore";
import { resetInspectorStore } from "../contexts/InspectorStore";
import { useKeyboardShortcuts } from "../hooks/useKeyboardShortcuts";
import { QuoteGroup } from "./QuoteGroup";
import { putHidden, putStarred } from "../utils/api";
import type { QuoteResponse } from "../utils/types";

vi.mock("../utils/api", () => ({
  apiGet: vi.fn().mockResolvedValue({ video_map: {} }),
  getModeratorQuestion: vi.fn().mockResolvedValue(null),
  putHidden: vi.fn(),
  putStarred: vi.fn(),
  putEdits: vi.fn(),
  putTags: vi.fn(),
  putDeletedBadges: vi.fn(),
  acceptProposal: vi.fn().mockResolvedValue(undefined),
  denyProposal: vi.fn().mockResolvedValue(undefined),
}));

vi.mock("../utils/embedded", () => ({ isEmbedded: () => false }));

/** Matches HIDE_DURATION in QuoteGroup.tsx; the store write is deferred by it. */
const HIDE_DURATION = 300;

function makeQuote(overrides: Partial<QuoteResponse> = {}): QuoteResponse {
  return {
    dom_id: "q-p1-1",
    text: "The navigation was hidden behind a hamburger menu",
    verbatim_excerpt: "The navigation was hidden",
    participant_id: "p1",
    session_id: "s1",
    speaker_name: "Alice",
    start_timecode: 26,
    end_timecode: 35,
    sentiment: null,
    intensity: 1,
    researcher_context: null,
    quote_type: "screen_specific",
    topic_label: "Dashboard",
    is_starred: false,
    is_hidden: false,
    edited_text: null,
    tags: [],
    deleted_badges: [],
    proposed_tags: [],
    segment_index: 3,
    ...overrides,
  };
}

function renderGroup(...groups: QuoteResponse[][]) {
  let ctx: ReturnType<typeof useFocus> | null = null;

  function Harness() {
    ctx = useFocus();
    useKeyboardShortcuts({ helpModalOpen: false, onToggleHelp: () => {} });
    return createElement(
      "div",
      null,
      ...groups.map((quotes, i) =>
        createElement(QuoteGroup, {
          key: i,
          anchor: `section-${i}`,
          editKeyBase: `section-cluster-${i}`,
          label: `Section ${i}`,
          description: "",
          itemType: "section",
          quotes,
          tagVocabulary: [],
          hasMedia: false,
          hasModerator: false,
        }),
      ),
    );
  }

  function Wrapper() {
    return createElement(
      PlayerProvider,
      null,
      createElement(FocusProvider, null, createElement(Harness)),
    );
  }

  const router = createMemoryRouter(
    [{ path: "/report/quotes", element: createElement(Wrapper) }],
    { initialEntries: ["/report/quotes/"] },
  );

  const result = render(
    createElement(RouterProvider, { router }) as ReactNode,
  );
  return { getCtx: () => ctx!, ...result };
}

function pressKey(key: string) {
  const event = new KeyboardEvent("keydown", {
    key,
    bubbles: true,
    cancelable: true,
  });
  document.dispatchEvent(event);
  return event;
}

describe("bulk hide cost", () => {
  // jsdom implements no scrollIntoView, and `setFocus` calls it on the element
  // it focuses. The sibling harness in hooks/useKeyboardShortcuts.test.ts stubs
  // it per-element because it builds its own; here the cards are rendered by the
  // real QuoteGroup, so the stub goes on the prototype and is restored after.
  let realScrollIntoView: typeof Element.prototype.scrollIntoView;

  beforeEach(() => {
    resetStore();
    resetSidebarStore();
    resetInspectorStore();
    document.body.innerHTML = "";
    realScrollIntoView = Element.prototype.scrollIntoView;
    Element.prototype.scrollIntoView = function () {};
    vi.mocked(putHidden).mockClear();
    vi.mocked(putStarred).mockClear();
    vi.useFakeTimers();
  });

  afterEach(() => {
    Element.prototype.scrollIntoView = realScrollIntoView;
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("writes at most once per quote when hiding a selection", () => {
    const quotes = [
      makeQuote({ dom_id: "q-p1-1" }),
      makeQuote({ dom_id: "q-p1-2" }),
      makeQuote({ dom_id: "q-p1-3" }),
    ];
    const ids = quotes.map((q) => q.dom_id);
    initFromQuotes(quotes, true);

    const { getCtx, unmount } = renderGroup(quotes);

    act(() => {
      getCtx().registerVisibleQuoteIds("sections", ids);
      for (const id of ids) getCtx().toggleSelection(id);
    });
    expect(getCtx().selectedIds.size).toBe(3);

    act(() => {
      pressKey("h");
      vi.advanceTimersByTime(HIDE_DURATION + 50);
    });

    // ONE write for the gesture, whatever its size.
    //
    // This was `<= ids.length` while the fix was still undecided, so that a
    // bulk-write fix would not read as a regression. That bound is now too
    // loose to fail: `hideQuotes` skips quotes already animating, so even
    // restoring the old per-quote loop in the caller produces 3 writes, not
    // 9, and passes. Mutation-proved — the loose form survived a mutation
    // that put the defect's shape back. Pinning the contract instead.
    expect(vi.mocked(putHidden).mock.calls.length).toBe(1);

    // …and it must still hide exactly the quotes that were selected.
    expect(Object.keys(getQuotesSnapshot().hidden).sort()).toEqual([...ids].sort());

    unmount();
  });

  it("collapses quotes in every group a selection spans, not just one", () => {
    // The load-bearing case for keeping the hiding set in the store.
    //
    // A selection spans groups, but the animation record used to be per-group
    // `useState`, so only the group that was told collapsed its cards. The
    // thing telling every group was the N-squared defect itself: the keyboard
    // path called each card's handler in turn and each re-expanded the whole
    // selection. Fixing the arithmetic alone would have left quotes in other
    // groups vanishing with no animation, and nothing would have caught it.
    const groupA = [makeQuote({ dom_id: "q-a-1" })];
    const groupB = [makeQuote({ dom_id: "q-b-1" })];
    initFromQuotes([...groupA, ...groupB], true);

    const { getCtx, unmount } = renderGroup(groupA, groupB);

    act(() => {
      getCtx().registerVisibleQuoteIds("sections", ["q-a-1", "q-b-1"]);
      getCtx().toggleSelection("q-a-1");
      getCtx().toggleSelection("q-b-1");
    });

    // Press, but do NOT run out the collapse window — mid-animation is the
    // only moment the class is on the DOM.
    act(() => {
      pressKey("h");
    });

    for (const id of ["q-a-1", "q-b-1"]) {
      const el = document.getElementById(id);
      expect(el, `${id} should still be rendered mid-collapse`).not.toBeNull();
      expect(el?.className, `${id} should carry the collapse class`).toContain("bn-hiding");
    }

    // And the gesture still lands, once, for both.
    act(() => {
      vi.advanceTimersByTime(HIDE_DURATION + 50);
    });
    expect(vi.mocked(putHidden).mock.calls.length).toBe(1);
    expect(Object.keys(getQuotesSnapshot().hidden).sort()).toEqual(["q-a-1", "q-b-1"]);

    unmount();
  });

  it("writes once when hiding a single focused quote", () => {
    const quotes = [makeQuote({ dom_id: "q-p1-1" }), makeQuote({ dom_id: "q-p1-2" })];
    const ids = quotes.map((q) => q.dom_id);
    initFromQuotes(quotes, true);

    const { getCtx, unmount } = renderGroup(quotes);

    act(() => {
      getCtx().registerVisibleQuoteIds("sections", ids);
      getCtx().setFocus("q-p1-1");
    });

    act(() => {
      pressKey("h");
      vi.advanceTimersByTime(HIDE_DURATION + 50);
    });

    expect(vi.mocked(putHidden).mock.calls.length).toBe(1);
    expect(Object.keys(getQuotesSnapshot().hidden)).toEqual(["q-p1-1"]);

    unmount();
  });
});

describe("bulk star direction", () => {
  // Three surfaces used to decide this differently, and one of them is a
  // LABEL: AppLayout pushes `starActionIsUnstar` over the bridge and the
  // native Quotes menu renders "Star" or "Unstar" from it. The `s` key
  // followed the focused quote's state, a click followed the clicked card's,
  // so a mixed selection could show "Star" and unstar. These pin the action
  // against the label rather than against either implementation.

  let realScrollIntoView: typeof Element.prototype.scrollIntoView;

  beforeEach(() => {
    resetStore();
    resetSidebarStore();
    resetInspectorStore();
    document.body.innerHTML = "";
    realScrollIntoView = Element.prototype.scrollIntoView;
    Element.prototype.scrollIntoView = function () {};
    vi.mocked(putStarred).mockClear();
    vi.useFakeTimers();
  });

  afterEach(() => {
    Element.prototype.scrollIntoView = realScrollIntoView;
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  /** Select every quote, focus the first, and return what the menu would say.
   *
   *  Takes the GETTER, not a context object. `useFocus()`'s value is a render
   *  snapshot, so a context captured before the selection still carries an
   *  empty `selectedIds` afterwards — which made the label read as "Unstar"
   *  off the focused quote alone and failed this test for the wrong reason. */
  function selectAllAndRead(getCtx: () => ReturnType<typeof useFocus>, ids: string[]) {
    act(() => {
      getCtx().registerVisibleQuoteIds("sections", ids);
      for (const id of ids) getCtx().toggleSelection(id);
      getCtx().setFocus(ids[0]);
    });
    return starActionIsUnstar(
      getCtx().selectedIds,
      ids[0],
      getQuotesSnapshot().starred,
    );
  }

  it("stars a mixed selection, which is what the menu label promises", () => {
    // The divergence case. Focus sits on the STARRED quote, so the old key
    // path read its state and unstarred both — while the label said "Star".
    const quotes = [
      makeQuote({ dom_id: "q-1", is_starred: true }),
      makeQuote({ dom_id: "q-2", is_starred: false }),
    ];
    const ids = quotes.map((q) => q.dom_id);
    initFromQuotes(quotes, true);

    const { getCtx, unmount } = renderGroup(quotes);
    const labelSaysUnstar = selectAllAndRead(getCtx, ids);
    expect(labelSaysUnstar, "menu should offer Star for a mixed selection").toBe(false);

    act(() => {
      pressKey("s");
    });

    // The label said Star, so both must end starred.
    expect(getQuotesSnapshot().starred).toEqual({ "q-1": true, "q-2": true });
    expect(vi.mocked(putStarred).mock.calls.length).toBe(1);

    unmount();
  });

  it("unstars only when the whole selection is already starred", () => {
    const quotes = [
      makeQuote({ dom_id: "q-1", is_starred: true }),
      makeQuote({ dom_id: "q-2", is_starred: true }),
    ];
    const ids = quotes.map((q) => q.dom_id);
    initFromQuotes(quotes, true);

    const { getCtx, unmount } = renderGroup(quotes);
    const labelSaysUnstar = selectAllAndRead(getCtx, ids);
    expect(labelSaysUnstar, "menu should offer Unstar when all are starred").toBe(true);

    act(() => {
      pressKey("s");
    });

    expect(getQuotesSnapshot().starred).toEqual({});
    expect(vi.mocked(putStarred).mock.calls.length).toBe(1);

    unmount();
  });

  it("writes once for a large selection", () => {
    const quotes = Array.from({ length: 6 }, (_, i) =>
      makeQuote({ dom_id: `q-${i}` }),
    );
    const ids = quotes.map((q) => q.dom_id);
    initFromQuotes(quotes, true);

    const { getCtx, unmount } = renderGroup(quotes);
    selectAllAndRead(getCtx, ids);

    act(() => {
      pressKey("s");
    });

    expect(Object.keys(getQuotesSnapshot().starred).sort()).toEqual([...ids].sort());
    expect(vi.mocked(putStarred).mock.calls.length).toBe(1);

    unmount();
  });

  it("ignores which card you clicked when the selection is mixed", () => {
    // Clicking the star on an ALREADY-STARRED card in a mixed selection used
    // to unstar everything, because the clicked card's own toggle intent was
    // the direction. The menu label said "Star" at the same moment. Nothing
    // covered this path: reverting it reddened none of the other 1807 tests.
    const quotes = [
      makeQuote({ dom_id: "q-1", is_starred: true }),
      makeQuote({ dom_id: "q-2", is_starred: false }),
    ];
    const ids = quotes.map((q) => q.dom_id);
    initFromQuotes(quotes, true);

    const { getCtx, unmount } = renderGroup(quotes);
    act(() => {
      getCtx().registerVisibleQuoteIds("sections", ids);
      for (const id of ids) getCtx().toggleSelection(id);
    });

    const starBtn = document
      .getElementById("q-1")
      ?.querySelector<HTMLElement>(".star-btn");
    expect(starBtn, "the starred card should expose a star control").not.toBeNull();

    act(() => {
      starBtn!.click();
    });

    // Direction comes from the set, not the card: both end starred.
    expect(getQuotesSnapshot().starred).toEqual({ "q-1": true, "q-2": true });
    expect(vi.mocked(putStarred).mock.calls.length).toBe(1);

    unmount();
  });

  it("still toggles a single focused quote with nothing selected", () => {
    const quotes = [makeQuote({ dom_id: "q-1" }), makeQuote({ dom_id: "q-2" })];
    initFromQuotes(quotes, true);

    const { getCtx, unmount } = renderGroup(quotes);
    act(() => {
      getCtx().registerVisibleQuoteIds("sections", ["q-1", "q-2"]);
      getCtx().setFocus("q-1");
    });

    act(() => {
      pressKey("s");
    });
    expect(getQuotesSnapshot().starred).toEqual({ "q-1": true });

    act(() => {
      pressKey("s");
    });
    expect(getQuotesSnapshot().starred).toEqual({});

    unmount();
  });
});
