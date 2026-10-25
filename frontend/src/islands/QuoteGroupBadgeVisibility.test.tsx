/**
 * N186: a badge is hidden by its group NAME when the eye hid it, but switching a
 * codebook off hid the badges of every group sharing a disabled group's name
 * (Norman's and CLI UX's "Discoverability"). Mounts the real QuoteGroup, because
 * the filter lives in the composition, not in a helper.
 */

import { render, act } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { FocusProvider } from "../contexts/FocusContext";
import { PlayerProvider } from "../contexts/PlayerContext";
import { resetStore, initFromQuotes } from "../contexts/QuotesContext";
import { resetSidebarStore, adoptFrameworkDisabled } from "../contexts/SidebarStore";
import { resetInspectorStore } from "../contexts/InspectorStore";
import { QuoteGroup } from "./QuoteGroup";
import type { QuoteResponse } from "../utils/types";

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


const TAG_GROUP_MAP = {
  "affordance cues": { group: "Discoverability", colour_set: "ux", colour_index: 0, frameworkId: "norman" },
  "flag discovery": { group: "Discoverability", colour_set: "ux", colour_index: 1, frameworkId: "cli-ux" },
};

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
          tagGroupMap: TAG_GROUP_MAP,
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

describe("badges of two codebooks with a same-named group", () => {
  beforeEach(() => {
    resetStore();
    resetSidebarStore();
    resetInspectorStore();
    document.body.innerHTML = "";
  });

  it("switching one codebook off hides only its own badges", () => {
    const quote = makeQuote({
      tags: [
        { name: "Affordance cues", codebook_group: "Discoverability", colour_set: "ux", colour_index: 0 },
        { name: "Flag discovery", codebook_group: "Discoverability", colour_set: "ux", colour_index: 1 },
      ],
    });
    initFromQuotes([quote], true);
    renderGroup([quote]);
    expect(document.body.textContent).toContain("Affordance cues");
    expect(document.body.textContent).toContain("Flag discovery");

    act(() => adoptFrameworkDisabled(new Set(["cli-ux"])));

    expect(document.body.textContent).toContain("Affordance cues");
    expect(document.body.textContent).not.toContain("Flag discovery");
  });
});
