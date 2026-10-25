import { describe, expect, it, vi } from "vitest";
import { render, waitFor, act } from "@testing-library/react";
import { MemoryRouter, useNavigate } from "react-router-dom";
import { LensSubtitleSync, tabFromPath } from "./LensSubtitleSync";
import { addSearchToken, initFromQuotes, resetStore } from "../contexts/QuotesContext";
import { personToken } from "../utils/searchTokens";
import { codebookSubtitle, quotesSubtitle } from "../utils/lensSubtitle";
import { getCodebook } from "../utils/api";
import type { QuoteResponse } from "../utils/types";

vi.mock("../utils/api", () => ({
  getCodebook: vi.fn().mockResolvedValue({ groups: [], ungrouped: [], all_tag_names: [] }),
}));

/**
 * The tag this returns is matched against the Swift `Tab` rawValue before the
 * window subtitle is honoured:
 *
 *     guard bridgeHandler.lensSubtitleTab == bridgeHandler.activeTab?.rawValue
 *
 * So a wrong tag does not render a wrong subtitle — it renders NO subtitle, and
 * the window silently falls back to the session count. That is what shipped on
 * the v2 lens: "/report/codebook-v2" starts with "/report/codebook", the
 * shorter test matched first, and a codebook lens reported "3 Sessions · 9m".
 */
describe("tabFromPath — longest prefix first", () => {
  it("resolves the codebook lens, library view included", () => {
    // Was "resolves the v2 route to its own tab". That route retired on
    // 31 Aug 2026 when the lens took `/report/codebook`; the library is now a
    // query param on it, which must not change the tag.
    expect(tabFromPath("/report/codebook")).toBe("codebook");
    expect(tabFromPath("/report/codebook?view=library")).toBe("codebook");
  });

  it("still resolves the shipped codebook lens", () => {
    expect(tabFromPath("/report/codebook")).toBe("codebook");
    expect(tabFromPath("/report/codebook/")).toBe("codebook");
  });

  it("returns the Swift rawValue spelling, not a route slug", () => {
    // The tag is matched against `Tab.rawValue`; a slug would fail the guard
    // silently and the window would fall back to the session count.
    expect(tabFromPath("/report/codebook")).toBe("codebook");
  });

  it("resolves the other lenses unchanged", () => {
    expect(tabFromPath("/report/quotes")).toBe("quotes");
    expect(tabFromPath("/report/signals")).toBe("signals");
    expect(tabFromPath("/report/sessions")).toBe("sessions");
  });

  it("resolves the Screens lens to its own tab, not Project", () => {
    // A wrong tag renders NO subtitle: Swift discards it (see the block above).
    expect(tabFromPath("/report/screens/")).toBe("screens");
  });
});

describe("the Quotes subtitle counts what the filters leave", () => {
  const q = (dom_id: string, participant_id: string) =>
    ({
      dom_id, participant_id, text: "x", verbatim_excerpt: "x", session_id: "s1", speaker_name: participant_id,
      start_timecode: 0, end_timecode: 1, sentiment: null, intensity: 1, researcher_context: null,
      quote_type: "section", topic_label: "", is_starred: false, is_hidden: false, edited_text: null,
      tags: [], deleted_badges: [], proposed_tags: [], segment_index: 0,
    }) as QuoteResponse;

  it("narrows with a search token", async () => {
    resetStore();
    initFromQuotes([q("a", "p1"), q("b", "p2"), q("c", "p2")]);
    render(
      <MemoryRouter initialEntries={["/report/quotes"]}>
        <LensSubtitleSync />
      </MemoryRouter>,
    );
    await waitFor(() => expect(document.title).toBe(quotesSubtitle(3)));
    act(() => addSearchToken(personToken("p2")));
    await waitFor(() => expect(document.title).toBe(quotesSubtitle(2)));
  });
});

// N180: the codebook was read at page load and again only on `codebook-changed`, which a
// tag made on a quote card never fires, so the title kept the old count while the lens
// itself (which re-reads when it opens) listed the new tag.
describe("the Codebook subtitle after a tag made elsewhere", () => {
  const book = (tags: string[]) =>
    ({
      groups: [
        {
          name: "Mine",
          framework_id: null,
          tags: tags.map((name) => ({ name })),
        },
      ],
      ungrouped: [],
      all_tag_names: tags,
    }) as never;

  it("is read again when the Codebook lens is opened", async () => {
    resetStore();
    initFromQuotes([]);
    vi.mocked(getCodebook).mockClear();
    vi.mocked(getCodebook).mockResolvedValueOnce(book(["a"]));
    const nav: { go: (to: string) => void } = { go: () => {} };
    function Nav() {
      const navigate = useNavigate();
      nav.go = navigate;
      return null;
    }
    render(
      <MemoryRouter initialEntries={["/report/quotes"]}>
        <LensSubtitleSync />
        <Nav />
      </MemoryRouter>,
    );
    await waitFor(() => expect(getCodebook).toHaveBeenCalledTimes(1));
    await act(async () => {}); // the first answer lands: the title says 1 tag

    // a second tag is made on a quote card: nothing is dispatched
    vi.mocked(getCodebook).mockResolvedValue(book(["a", "b"]));
    act(() => nav.go("/report/codebook"));

    await waitFor(() => expect(document.title).toBe(codebookSubtitle(1, 2)));
  });
});
