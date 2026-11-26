/**
 * A file cannot un-hide, so an exported report draws no hidden-quotes counter.
 * The export also leaves hidden quotes out of its embed (export.py
 * _drop_hidden_quotes); this pins the second line of defence, the gate in
 * `Counter` (shared by Quotes, Discussion and Screens), on its own, through the
 * Quotes lens that draws it.
 */

import { render } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { FocusProvider } from "../contexts/FocusContext";
import { PlayerProvider } from "../contexts/PlayerContext";
import { resetStore, initFromQuotes } from "../contexts/QuotesContext";
import { resetSidebarStore } from "../contexts/SidebarStore";
import { resetInspectorStore } from "../contexts/InspectorStore";
import { QuoteGroup } from "./QuoteGroup";
import type { QuoteResponse } from "../utils/types";
import * as exportData from "../utils/exportData";

vi.mock("../utils/api", () => ({
  toastSaveFailed: vi.fn(),
  apiGet: vi.fn().mockResolvedValue({ video_map: {} }),
  getModeratorQuestion: vi.fn().mockResolvedValue(null),
  patchHidden: vi.fn(() => Promise.resolve()),
  patchStarred: vi.fn(() => Promise.resolve()),
  patchEdits: vi.fn(() => Promise.resolve()),
  patchTags: vi.fn(() => Promise.resolve()),
  patchDeletedBadges: vi.fn(() => Promise.resolve()),
  acceptProposal: vi.fn().mockResolvedValue(undefined),
  denyProposal: vi.fn().mockResolvedValue(undefined),
}));

vi.mock("../utils/embedded", () => ({ isEmbedded: () => false }));

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



function renderGroup(quotes: QuoteResponse[]) {
  function Wrapper() {
    return createElement(
      PlayerProvider,
      null,
      createElement(
        FocusProvider,
        null,
        createElement(QuoteGroup, {
          anchor: "s0",
          editKeyBase: "k0",
          label: "S",
          description: "",
          itemType: "section",
          quotes,
          tagVocabulary: [],
          tagGroupMap: {},
          hasMedia: false,
          hasModerator: false,
        }),
      ),
    );
  }
  const router = createMemoryRouter([{ path: "/report/quotes", element: createElement(Wrapper) }], {
    initialEntries: ["/report/quotes/"],
  });
  return render(createElement(RouterProvider, { router }) as ReactNode);
}

describe("the hidden-quotes counter in an exported report", () => {
  beforeEach(() => {
    resetStore();
    resetSidebarStore();
    resetInspectorStore();
    document.body.innerHTML = "";
  });
  afterEach(() => vi.restoreAllMocks());

  const quotes = [makeQuote(), makeQuote({ dom_id: "q-p1-40", start_timecode: 40, is_hidden: true })];

  it("shows in the app", () => {
    initFromQuotes(quotes, true);
    renderGroup(quotes);
    expect(document.querySelector(".bn-hidden-badge")).not.toBeNull();
  });

  it("is not drawn in an export, even if a hidden quote reaches it", () => {
    vi.spyOn(exportData, "isExportMode").mockReturnValue(true);
    initFromQuotes(quotes, true);
    renderGroup(quotes);
    expect(document.querySelector(".bn-hidden-badge")).toBeNull();
  });
});
