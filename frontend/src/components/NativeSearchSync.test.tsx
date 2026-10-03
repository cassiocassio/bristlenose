/**
 * The badge styles the Mac app's native search menu and chips are painted
 * from (docs/design-search.md §7a): which badges are measured, that each is
 * measured once per appearance, and that the component re-posts when the
 * appearance changes. The measuring itself (probeBadgeStyles) needs a real
 * engine and is stubbed here; badgeStyle.test.ts covers what it reads.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, act, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { BadgeStyle, BadgeStyles } from "../utils/badgeStyle";
import type { QuoteResponse, TagResponse } from "../utils/types";

vi.mock("../shims/bridge", () => ({
  postSearchSuggestions: vi.fn(),
  postSearchBadgeStyles: vi.fn(),
}));
vi.mock("../utils/api", () => ({
  getPeople: vi.fn().mockResolvedValue({}),
  putHidden: vi.fn(),
  putStarred: vi.fn(),
  putEdits: vi.fn(),
  putTags: vi.fn(),
  putDeletedBadges: vi.fn(),
}));
vi.mock("../utils/badgeStyle", () => ({ probeBadgeStyles: vi.fn() }));

import {
  NativeSearchSync,
  badgeStylesFor,
  badgeSubjects,
  emptyBadgeStyleCache,
  type BadgeSubjects,
} from "./NativeSearchSync";
import { addSearchToken, getQuotesSnapshot, initFromQuotes, resetStore, setSearchQuery } from "../contexts/QuotesContext";
import { personToken, tagToken } from "../utils/searchTokens";
import { postSearchBadgeStyles } from "../shims/bridge";
import { probeBadgeStyles } from "../utils/badgeStyle";
import { _resetEmbeddedCache } from "../utils/embedded";
import type { WireSuggestionRow } from "../utils/searchBridge";

const tag = (name: string, colour_set = "ux", colour_index = 0): TagResponse => ({
  name, codebook_group: "g", colour_set, colour_index,
});
const q = (dom_id: string, participant_id: string, tags: TagResponse[] = []) =>
  ({
    dom_id, participant_id, text: "delivery was late", verbatim_excerpt: "", session_id: "s1",
    speaker_name: participant_id === "p3" ? "Priya" : participant_id, start_timecode: 0, end_timecode: 1,
    sentiment: null, intensity: 1, researcher_context: null, quote_type: "section", topic_label: "",
    is_starred: false, is_hidden: false, edited_text: null, tags, deleted_badges: [], proposed_tags: [],
    segment_index: 0,
  }) as QuoteResponse;

const style = (sizePx: number): BadgeStyle => ({
  bg: { r: 1, g: 1, b: 1, a: 1 }, fg: { r: 0, g: 0, b: 0, a: 1 }, border: null,
  fontFamily: "mono", sizePx, weight: 400, padX: 7, padY: 2, radius: 3,
});

/** A probe that "measures" every badge it is asked for, sized by call. */
function fakeProbe() {
  let call = 0;
  return vi.fn((s: BadgeSubjects): BadgeStyles => {
    call++;
    return {
      tags: Object.fromEntries(s.tags.map((t) => [t.name.toLowerCase(), style(10 + call)])),
      people: Object.fromEntries(s.people.map((p) => [p.code, { code: style(10 + call), name: p.name ? style(10 + call) : null }])),
    };
  });
}

beforeEach(() => {
  resetStore();
  vi.clearAllMocks();
});

describe("badgeSubjects", () => {
  it("collects the people and tags in the rows and the tokens, with each tag's colour", () => {
    initFromQuotes([q("a", "p3", [tag("Hidden costs", "emo", 2)]), q("b", "p2", [tag("Trust", "trust", 1)])]);
    act(() => addSearchToken(tagToken({ name: "trust" })));
    act(() => addSearchToken(personToken("p2", { full_name: "Tom Fletcher", short_name: "Tom" })));
    const rows: WireSuggestionRow[] = [
      { id: "person:p3", kind: "person", label: "Priya", typed: [], count: 1, code: "p3" },
      { id: "person:p7", kind: "person", label: "p7", typed: [], count: 1, code: "p7" },
      { id: "tag:hidden costs", kind: "tag", label: "Hidden costs", typed: [], count: 1 },
    ];
    const subjects = badgeSubjects(getQuotesSnapshot(), rows);
    expect(subjects.people).toEqual([
      { code: "p3", name: "Priya" },
      { code: "p7", name: null }, // code only: no name half
      { code: "p2", name: "Tom Fletcher" },
    ]);
    expect(subjects.tags.map((t) => [t.name, t.colour_set, t.colour_index])).toEqual([
      ["Hidden costs", "emo", 2],
      ["Trust", "trust", 1], // the token's tag, coloured as on its quotes
    ]);
  });

  it("reads a tag's colour from the store's tag edits, so a recolour shows", () => {
    initFromQuotes([q("a", "p1", [tag("Trust", "trust", 1)])]);
    const store = { ...getQuotesSnapshot(), tags: { a: [tag("Trust", "opp", 4)] } };
    const rows: WireSuggestionRow[] = [{ id: "tag:trust", kind: "tag", label: "Trust", typed: [], count: 1 }];
    expect(badgeSubjects(store, rows).tags[0]).toMatchObject({ colour_set: "opp", colour_index: 4 });
  });
});

describe("badgeStylesFor", () => {
  const subjects: BadgeSubjects = {
    tags: [{ name: "Trust", colour_set: "trust", colour_index: 1 }],
    people: [{ code: "p3", name: "Priya" }],
  };

  it("measures each badge once per appearance", () => {
    const probe = fakeProbe();
    const cache = emptyBadgeStyleCache();
    const first = badgeStylesFor(subjects, "light", cache, probe);
    const again = badgeStylesFor(subjects, "light", cache, probe);
    expect(probe).toHaveBeenCalledTimes(1);
    expect(again).toEqual(first);
    expect(Object.keys(first.tags)).toEqual(["trust"]); // keyed as the wire's styleKey
    expect(Object.keys(first.people)).toEqual(["p3"]);
  });

  it("measures everything again when the appearance changes", () => {
    const probe = fakeProbe();
    const cache = emptyBadgeStyleCache();
    const light = badgeStylesFor(subjects, "light", cache, probe);
    const dark = badgeStylesFor(subjects, "dark", cache, probe);
    expect(probe).toHaveBeenCalledTimes(2);
    expect(dark.tags.trust.sizePx).not.toBe(light.tags.trust.sizePx);
  });

  it("measures a recoloured tag again, and only what is new", () => {
    const probe = fakeProbe();
    const cache = emptyBadgeStyleCache();
    badgeStylesFor(subjects, "light", cache, probe);
    badgeStylesFor({ ...subjects, tags: [{ name: "Trust", colour_set: "opp", colour_index: 4 }] }, "light", cache, probe);
    expect(probe).toHaveBeenCalledTimes(2);
    expect(probe.mock.calls[1][0]).toEqual({ tags: [{ name: "Trust", colour_set: "opp", colour_index: 4 }], people: [] });
  });

  it("leaves out a badge that could not be measured, rather than guess", () => {
    const cache = emptyBadgeStyleCache();
    const styles = badgeStylesFor(subjects, "light", cache, () => ({ tags: {}, people: {} }));
    expect(styles).toEqual({ tags: {}, people: {} });
  });
});

describe("NativeSearchSync posts badge styles in the Mac app", () => {
  beforeEach(() => {
    (window as unknown as Record<string, unknown>).__BRISTLENOSE_EMBEDDED__ = true;
    _resetEmbeddedCache();
    document.documentElement.removeAttribute("data-theme");
    document.documentElement.removeAttribute("data-person-display");
  });
  afterEach(() => {
    delete (window as unknown as Record<string, unknown>).__BRISTLENOSE_EMBEDDED__;
    _resetEmbeddedCache();
    document.documentElement.removeAttribute("data-theme");
    document.documentElement.removeAttribute("data-person-display");
  });

  it("posts the menu's badges, and posts again when the appearance changes", async () => {
    vi.mocked(probeBadgeStyles).mockImplementation((_host, s) => fakeProbe()(s));
    initFromQuotes([q("a", "p3", [tag("Trust")])]);
    render(
      <MemoryRouter initialEntries={["/report/quotes"]}>
        <NativeSearchSync />
      </MemoryRouter>,
    );
    act(() => setSearchQuery("pri"));
    await waitFor(() => {
      const calls = vi.mocked(postSearchBadgeStyles).mock.calls;
      expect(calls[calls.length - 1]?.[0].people).toHaveProperty("p3");
    });
    const before = vi.mocked(probeBadgeStyles).mock.calls.length;

    act(() => document.documentElement.setAttribute("data-theme", "dark"));
    await waitFor(() => expect(vi.mocked(probeBadgeStyles).mock.calls.length).toBeGreaterThan(before));

    // Showing codes only hides the name half, so the badges are measured again.
    const beforeDisplay = vi.mocked(probeBadgeStyles).mock.calls.length;
    act(() => document.documentElement.setAttribute("data-person-display", "code"));
    await waitFor(() =>
      expect(vi.mocked(probeBadgeStyles).mock.calls.length).toBeGreaterThan(beforeDisplay),
    );
  });

  it("does nothing outside the Mac app", async () => {
    delete (window as unknown as Record<string, unknown>).__BRISTLENOSE_EMBEDDED__;
    _resetEmbeddedCache();
    initFromQuotes([q("a", "p3")]);
    render(
      <MemoryRouter initialEntries={["/report/quotes"]}>
        <NativeSearchSync />
      </MemoryRouter>,
    );
    act(() => setSearchQuery("pri"));
    await new Promise((r) => setTimeout(r, 10));
    expect(postSearchBadgeStyles).not.toHaveBeenCalled();
    expect(probeBadgeStyles).not.toHaveBeenCalled();
  });
});
