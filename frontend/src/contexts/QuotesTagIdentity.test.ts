/**
 * A tag on a quote is its row, not its name (N146): two tags can share a name, so add, remove,
 * undo and de-duplication go by the row when the tag has one.
 */
import type { QuoteResponse, TagResponse } from "../utils/types";
import {
  acceptProposedTag,
  addTagToQuotes,
  getQuotesSnapshot,
  initFromQuotes,
  removeTag,
  resetStore,
} from "./QuotesContext";
import { redo, resetUndoStore, undo } from "./UndoStore";
import { _resetExportCache } from "../utils/exportData";

vi.mock("../utils/api", () => ({
  toastSaveFailed: vi.fn(),
  patchHidden: vi.fn(() => Promise.resolve()),
  patchStarred: vi.fn(() => Promise.resolve()),
  patchEdits: vi.fn(() => Promise.resolve()),
  patchTags: vi.fn(() => Promise.resolve()),
  patchDeletedBadges: vi.fn(() => Promise.resolve()),
  acceptProposal: vi.fn().mockResolvedValue(undefined),
  denyProposal: vi.fn().mockResolvedValue(undefined),
}));

import { patchTags } from "../utils/api";

const patchTagsMock = vi.mocked(patchTags);

function quote(dom_id: string, tags: TagResponse[] = []): QuoteResponse {
  return {
    dom_id, text: "x", verbatim_excerpt: "x", participant_id: "P1", session_id: "s1",
    speaker_name: "P1", start_timecode: 0, end_timecode: 1, sentiment: null, intensity: 0,
    researcher_context: null, quote_type: "section", topic_label: "T", is_starred: false,
    is_hidden: false, edited_text: null, tags, deleted_badges: [], proposed_tags: [],
    segment_index: 0,
  } as QuoteResponse;
}

const mine: TagResponse = {
  id: 7, name: "trust", codebook_group: "Uncategorised", colour_set: "", colour_index: 0,
  source: "human",
};
const theirs: TagResponse = {
  id: 9, name: "trust", codebook_group: "UXR", colour_set: "trust", colour_index: 2,
  source: "human",
};

const idsOn = (id: string) => (getQuotesSnapshot().tags[id] || []).map((t) => t.id);

beforeEach(() => {
  resetStore();
  resetUndoStore();
  vi.clearAllMocks();
  _resetExportCache();
});

describe("a tag with a row is added, removed and undone by the row", () => {
  it("adds by id, and the other same-named tag does not stop it", () => {
    initFromQuotes([quote("q1", [theirs])]);
    addTagToQuotes(["q1"], mine);
    expect(patchTagsMock).toHaveBeenCalledWith({ q1: { add_ids: [7] } });
    expect(idsOn("q1")).toEqual([9, 7]);
  });

  it("adding the same row twice is a duplicate", () => {
    initFromQuotes([quote("q1", [mine])]);
    addTagToQuotes(["q1"], mine);
    expect(patchTagsMock).not.toHaveBeenCalled();
  });

  it("a × removes only the tag pointed at, by id", () => {
    initFromQuotes([quote("q1", [mine, theirs])]);
    removeTag("q1", "trust", true, 9);
    expect(patchTagsMock).toHaveBeenCalledWith({ q1: { remove_ids: [9] } });
    expect(idsOn("q1")).toEqual([7]);
  });

  it("undo puts back that tag by id, and redo removes only it again", async () => {
    initFromQuotes([quote("q1", [mine, theirs])]);
    removeTag("q1", "trust", true, 9);
    patchTagsMock.mockClear();
    await undo();
    expect(patchTagsMock).toHaveBeenCalledWith({ q1: { add_ids: [9] } });
    expect(idsOn("q1")).toEqual([7, 9]);
    patchTagsMock.mockClear();
    await redo();
    expect(patchTagsMock).toHaveBeenCalledWith({ q1: { remove_ids: [9] } });
    expect(idsOn("q1")).toEqual([7]);
  });

  it("undoing an add removes only the tag that was added", async () => {
    initFromQuotes([quote("q1", [theirs])]);
    addTagToQuotes(["q1"], mine);
    patchTagsMock.mockClear();
    await undo();
    expect(patchTagsMock).toHaveBeenCalledWith({ q1: { remove_ids: [7] } });
    expect(idsOn("q1")).toEqual([9]);
  });

  it("a tag made up on the page has no row and goes by name, as before", () => {
    initFromQuotes([quote("q1")]);
    addTagToQuotes(["q1"], { name: "new", codebook_group: "Uncategorised", colour_set: "", colour_index: 0 });
    expect(patchTagsMock).toHaveBeenCalledWith({ q1: { add: ["new"] } });
    patchTagsMock.mockClear();
    removeTag("q1", "new");
    expect(patchTagsMock).toHaveBeenCalledWith({ q1: { remove: ["new"] } });
  });

  it("a made-up negative id is never sent", () => {
    initFromQuotes([quote("q1")]);
    addTagToQuotes(["q1"], { id: -3, name: "new", codebook_group: "Uncategorised", colour_set: "", colour_index: 0 });
    expect(patchTagsMock).toHaveBeenCalledWith({ q1: { add: ["new"] } });
  });
});

describe("sentiment tags and accepted suggestions", () => {
  it("a typed sentiment name is the researcher's own tag, not 'already there'", () => {
    const machine: TagResponse = {
      id: 1, name: "frustration", codebook_group: "Sentiment", colour_set: "emo", colour_index: 0,
      source: "pipeline",
    };
    initFromQuotes([quote("q1", [machine])]);
    addTagToQuotes(["q1"], {
      name: "frustration", codebook_group: "Uncategorised", colour_set: "", colour_index: 0,
      source: "human",
    });
    expect(patchTagsMock).toHaveBeenCalledWith({ q1: { add: ["frustration"] } });
    expect(getQuotesSnapshot().tags.q1).toHaveLength(2);
  });

  it("an accepted suggestion is its own row beside the researcher's same-named tag", () => {
    initFromQuotes([quote("q1", [mine])]);
    acceptProposedTag("q1", 55, { ...theirs, source: "autocode" });
    expect(idsOn("q1")).toEqual([7, 9]);
    patchTagsMock.mockClear();
    removeTag("q1", "trust", true, 7);
    expect(patchTagsMock).toHaveBeenCalledWith({ q1: { remove_ids: [7] } });
    expect(idsOn("q1")).toEqual([9]);
  });
});

