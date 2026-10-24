/**
 * A write that fails takes the screen back to what the server holds (R7).
 *
 * "Couldn't save" used to appear while the star, hide, tag or edit stayed
 * drawn as if it had saved. The rollback reverts only what still shows the
 * gesture's value, because a later gesture is the researcher's latest word.
 */
import type { QuoteResponse, TagResponse } from "../utils/types";
import {
  HIDE_DURATION,
  acceptProposedTag,
  addTag,
  commitEdit,
  deleteBadge,
  denyProposedTag,
  getQuotesSnapshot,
  hideQuotes,
  initFromQuotes,
  removeTag,
  resetStore,
  restoreBadges,
  setStarred,
  unhideQuotes,
} from "./QuotesContext";
import { getUndoState, redo, resetUndoStore, undo } from "./UndoStore";
import { _resetExportCache } from "../utils/exportData";

vi.mock("../utils/api", () => ({
  patchHidden: vi.fn(() => Promise.resolve()),
  patchStarred: vi.fn(() => Promise.resolve()),
  patchEdits: vi.fn(() => Promise.resolve()),
  patchTags: vi.fn(() => Promise.resolve()),
  patchDeletedBadges: vi.fn(() => Promise.resolve()),
  acceptProposal: vi.fn().mockResolvedValue(undefined),
  denyProposal: vi.fn().mockResolvedValue(undefined),
  toastSaveFailed: vi.fn(),
}));

import {
  acceptProposal,
  denyProposal,
  patchDeletedBadges,
  patchEdits,
  patchHidden,
  patchStarred,
  patchTags,
  toastSaveFailed,
} from "../utils/api";

function quote(overrides: Partial<QuoteResponse> = {}): QuoteResponse {
  return {
    dom_id: "q1",
    text: "x",
    verbatim_excerpt: "x",
    participant_id: "P1",
    session_id: "s1",
    speaker_name: "P1",
    start_timecode: 0,
    end_timecode: 1,
    sentiment: null,
    intensity: 0,
    researcher_context: null,
    quote_type: "section",
    topic_label: "T",
    is_starred: false,
    is_hidden: false,
    edited_text: null,
    tags: [],
    deleted_badges: [],
    proposed_tags: [],
    segment_index: 0,
    ...overrides,
  } as QuoteResponse;
}

const tag = (name: string): TagResponse => ({
  name, codebook_group: "G", colour_set: "ux", colour_index: 0,
});

/** The next write to this helper fails, as `sendWrite` rejects after its toast. */
function failNext(fn: unknown): void {
  vi.mocked(fn as () => Promise<void>).mockImplementationOnce(() =>
    Promise.reject(new Error("refused")),
  );
}

/** Let a rejected write's rollback run. */
const settle = () => new Promise((r) => setTimeout(r, 0));

beforeEach(() => {
  resetStore();
  resetUndoStore();
  vi.clearAllMocks();
  _resetExportCache();
});

describe("a failed write takes the screen back", () => {
  it("a star", async () => {
    initFromQuotes([quote()]);
    failNext(patchStarred);
    setStarred(["q1"], true);
    expect(getQuotesSnapshot().starred.q1).toBe(true);
    await settle();
    expect(getQuotesSnapshot().starred.q1).toBeUndefined();
  });

  it("a restore from hidden", async () => {
    initFromQuotes([quote({ is_hidden: true })]);
    failNext(patchHidden);
    unhideQuotes(["q1"]);
    await settle();
    expect(getQuotesSnapshot().hidden.q1).toBe(true);
  });

  it("a hide, once it has landed", async () => {
    vi.useFakeTimers();
    try {
      initFromQuotes([quote()]);
      failNext(patchHidden);
      hideQuotes(["q1"]);
      vi.advanceTimersByTime(HIDE_DURATION);
      expect(getQuotesSnapshot().hidden.q1).toBe(true);
      await vi.runAllTimersAsync();
      expect(getQuotesSnapshot().hidden.q1).toBeUndefined();
    } finally {
      vi.useRealTimers();
    }
  });

  it("an edit, to the words before it", async () => {
    initFromQuotes([quote({ edited_text: "first" })]);
    failNext(patchEdits);
    commitEdit("q1", "second");
    await settle();
    expect(getQuotesSnapshot().edits.q1).toBe("first");
  });

  it("a tag added", async () => {
    initFromQuotes([quote()]);
    failNext(patchTags);
    addTag("q1", tag("Trust"));
    await settle();
    expect(getQuotesSnapshot().tags.q1).toBeUndefined();
  });

  it("a tag removed, back in its place", async () => {
    initFromQuotes([quote({ tags: [tag("A"), tag("B"), tag("C")] })]);
    failNext(patchTags);
    removeTag("q1", "B");
    await settle();
    expect(getQuotesSnapshot().tags.q1.map((t) => t.name)).toEqual(["A", "B", "C"]);
  });

  it("a badge deleted, and a restore of the badges", async () => {
    initFromQuotes([quote()]);
    failNext(patchDeletedBadges);
    deleteBadge("q1", "negative");
    await settle();
    expect(getQuotesSnapshot().deletedBadges.q1).toBeUndefined();
    expect(getUndoState().canUndo).toBe(false);

    initFromQuotes([quote({ deleted_badges: ["negative"] })], true);
    failNext(patchDeletedBadges);
    restoreBadges("q1");
    await settle();
    expect(getQuotesSnapshot().deletedBadges.q1).toEqual(["negative"]);
  });
});

// Decision #15 (22 Oct 2026): a gesture whose save failed never happened, so
// Edit ▸ Undo names the act before it; an undo or redo whose save failed stays
// where it was (R9), so the menu still offers it.
describe("the undo stack after a failed save", () => {
  it("a star that did not save leaves nothing to undo", async () => {
    initFromQuotes([quote()]);
    failNext(patchStarred);
    setStarred(["q1"], true);
    expect(getUndoState().undoAction).toBe("star");
    await settle();
    expect(getUndoState()).toMatchObject({ canUndo: false, canRedo: false });
  });

  it("the act before a failed one is the one Undo names", async () => {
    initFromQuotes([quote()]);
    addTag("q1", tag("Trust"));
    failNext(patchStarred);
    setStarred(["q1"], true);
    await settle();
    expect(getUndoState().undoAction).toBe("addTag");
  });

  it("a hide, an edit, a tag added and a tag removed that did not save", async () => {
    vi.useFakeTimers();
    try {
      initFromQuotes([quote({ tags: [tag("A")] })]);
      failNext(patchHidden);
      hideQuotes(["q1"]);
      await vi.runAllTimersAsync();
      failNext(patchEdits);
      commitEdit("q1", "second");
      failNext(patchTags);
      addTag("q1", tag("Trust"));
      failNext(patchTags);
      removeTag("q1", "A");
      await vi.runAllTimersAsync();
      expect(getUndoState().canUndo).toBe(false);
    } finally {
      vi.useRealTimers();
    }
  });

  it("an undo that did not save is still the act to undo", async () => {
    initFromQuotes([quote()]);
    setStarred(["q1"], true);
    await settle();
    failNext(patchStarred);
    expect(await undo()).toBe(false);
    expect(getQuotesSnapshot().starred.q1).toBe(true);
    expect(getUndoState()).toMatchObject({ undoAction: "star", canRedo: false });
  });

  it("a redo that did not save is still the act to redo", async () => {
    initFromQuotes([quote()]);
    setStarred(["q1"], true);
    await settle();
    await undo();
    failNext(patchStarred);
    expect(await redo()).toBe(false);
    expect(getQuotesSnapshot().starred.q1).toBeUndefined();
    expect(getUndoState()).toMatchObject({ redoAction: "star", canUndo: false });
  });

  it("a failed star gives back the redo it ended", async () => {
    initFromQuotes([quote()]);
    addTag("q1", tag("Trust"));
    await undo();
    failNext(patchStarred);
    setStarred(["q1"], true);
    await settle();
    expect(getUndoState()).toMatchObject({ canUndo: false, redoAction: "addTag" });
  });

  // Its undo's write went out and landed, so the act stays where that left it.
  it("an undo pressed before a failed star answers keeps the act", async () => {
    initFromQuotes([quote()]);
    failNext(patchStarred);
    setStarred(["q1"], true);
    await undo();
    await settle();
    expect(getUndoState()).toMatchObject({ canUndo: false, redoAction: "star" });
  });

  it("a star and its undo that both fail leave nothing to undo or redo", async () => {
    initFromQuotes([quote()]);
    failNext(patchStarred);
    setStarred(["q1"], true);
    failNext(patchStarred);
    expect(await undo()).toBe(false);
    await settle();
    expect(getQuotesSnapshot().starred.q1).toBeUndefined();
    expect(getUndoState()).toMatchObject({ canUndo: false, canRedo: false });
  });

  it("two failed stars in flight give back the redo the first ended", async () => {
    initFromQuotes([quote({ dom_id: "q1" }), quote({ dom_id: "q2" })]);
    addTag("q1", tag("Trust"));
    await undo();
    failNext(patchStarred);
    failNext(patchStarred);
    setStarred(["q1"], true);
    setStarred(["q2"], true);
    await settle();
    expect(getUndoState()).toMatchObject({ canUndo: false, redoAction: "addTag" });
  });

  it("an undo the server could only partly place has moved, and is not offered again", async () => {
    initFromQuotes([quote({ dom_id: "q1" }), quote({ dom_id: "q2" })]);
    addTag("q1", tag("Trust"));
    setStarred(["q1", "q2"], true);
    await settle();
    vi.mocked(patchStarred).mockImplementationOnce(() =>
      Promise.reject(Object.assign(new Error("no such quote"), { status: 200, unresolved: ["q2"] })),
    );
    expect(await undo()).toBe(true);
    await settle();
    expect(getUndoState()).toMatchObject({ undoAction: "addTag", redoAction: "star" });
  });

  it("a badge deleted that did not save leaves nothing to undo (R10)", async () => {
    initFromQuotes([quote()]);
    addTag("q1", tag("Trust"));
    failNext(patchDeletedBadges);
    deleteBadge("q1", "negative");
    expect(getUndoState().undoAction).toBe("removeTag");
    await settle();
    expect(getUndoState()).toMatchObject({ undoAction: "addTag", canRedo: false });
  });

  it("an undo of a badge delete that did not save is still the act to undo (R10)", async () => {
    initFromQuotes([quote()]);
    deleteBadge("q1", "negative");
    await settle();
    failNext(patchDeletedBadges);
    expect(await undo()).toBe(false);
    await settle();
    expect(getQuotesSnapshot().deletedBadges.q1).toEqual(["negative"]);
    expect(getUndoState()).toMatchObject({ undoAction: "removeTag", canRedo: false });
  });

  it("a badge deleted on a quote a re-run removed is withdrawn (R10)", async () => {
    initFromQuotes([quote()]);
    vi.mocked(patchDeletedBadges).mockImplementationOnce(() =>
      Promise.reject(Object.assign(new Error("no such quote"), { status: 200, unresolved: ["q1"] })),
    );
    deleteBadge("q1", "negative");
    await settle();
    expect(getUndoState().canUndo).toBe(false);
  });

  it("a write the server could only partly place keeps its entry", async () => {
    initFromQuotes([quote({ dom_id: "q1" }), quote({ dom_id: "q2" })]);
    vi.mocked(patchStarred).mockImplementationOnce(() =>
      Promise.reject(Object.assign(new Error("no such quote"), { status: 200, unresolved: ["q2"] })),
    );
    setStarred(["q1", "q2"], true);
    await settle();
    expect(getUndoState().undoAction).toBe("star");
  });
});

describe("a rollback leaves a later gesture alone", () => {
  it("an undo inside the hide's collapse writes nothing, so nothing can fail", async () => {
    vi.useFakeTimers();
    try {
      initFromQuotes([quote()]);
      failNext(patchHidden);
      hideQuotes(["q1"]);
      await undo();
      await vi.runAllTimersAsync();
      expect(patchHidden).not.toHaveBeenCalled();
      expect(getQuotesSnapshot().hidden.q1).toBeUndefined();
    } finally {
      vi.useRealTimers();
    }
  });

  it("a load that answers before a tag write lands keeps the tag drawn", async () => {
    initFromQuotes([quote()]);
    let land: () => void = () => {};
    vi.mocked(patchTags).mockImplementationOnce(() => new Promise<void>((r) => { land = r; }));
    addTag("q1", tag("Trust"));
    initFromQuotes([quote({ tags: [] })]); // a merge load whose answer predates the write
    expect(getQuotesSnapshot().tags.q1.map((t) => t.name)).toEqual(["Trust"]);
    land();
    await settle();
    initFromQuotes([quote({ tags: [] })]); // once it has landed, the server's answer counts
    expect(getQuotesSnapshot().tags.q1).toBeUndefined();
  });

  it("two failures in a row go back to before both", async () => {
    initFromQuotes([quote()]);
    failNext(patchStarred);
    failNext(patchStarred);
    setStarred(["q1"], true);
    setStarred(["q1"], false);
    await settle();
    expect(getQuotesSnapshot().starred.q1).toBeUndefined();
  });

  it("a failure after a write that landed goes back to what landed", async () => {
    initFromQuotes([quote()]);
    vi.mocked(patchStarred).mockImplementationOnce(() => Promise.resolve());
    failNext(patchStarred);
    setStarred(["q1"], true);
    setStarred(["q1"], false);
    await settle();
    expect(getQuotesSnapshot().starred.q1).toBe(true);
  });

  it("a star that failed, then an unstar and a star again, stays starred", async () => {
    initFromQuotes([quote()]);
    failNext(patchStarred);
    setStarred(["q1"], true);
    setStarred(["q1"], false);
    setStarred(["q1"], true);
    await settle();
    expect(getQuotesSnapshot().starred.q1).toBe(true);
  });

  it("a tag add that failed, then a remove and an add again, stays", async () => {
    initFromQuotes([quote()]);
    failNext(patchTags);
    addTag("q1", tag("Trust"));
    removeTag("q1", "Trust");
    addTag("q1", tag("Trust"));
    await settle();
    expect(getQuotesSnapshot().tags.q1.map((t) => t.name)).toEqual(["Trust"]);
  });

  it("a failed tag add leaves the quote's other tags", async () => {
    initFromQuotes([quote({ tags: [tag("A")] })]);
    failNext(patchTags);
    addTag("q1", tag("Trust"));
    addTag("q1", tag("Other"));
    await settle();
    expect(getQuotesSnapshot().tags.q1.map((t) => t.name)).toEqual(["A", "Other"]);
  });

  it("an edit that failed after a newer edit keeps the newer words", async () => {
    initFromQuotes([quote()]);
    failNext(patchEdits);
    commitEdit("q1", "one");
    commitEdit("q1", "two");
    await settle();
    expect(getQuotesSnapshot().edits.q1).toBe("two");
  });

  it("undo of a gesture that never landed sends nothing", async () => {
    initFromQuotes([quote()]);
    failNext(patchStarred);
    setStarred(["q1"], true);
    await settle();
    vi.mocked(patchStarred).mockClear();
    await undo();
    expect(patchStarred).not.toHaveBeenCalled();
    expect(getQuotesSnapshot().starred.q1).toBeUndefined();
  });
});

describe("a write the server could only partly place", () => {
  it("takes back only the quotes it could not place", async () => {
    initFromQuotes([quote({ dom_id: "q1" }), quote({ dom_id: "q2" })]);
    vi.mocked(patchStarred).mockImplementationOnce(() =>
      Promise.reject(Object.assign(new Error("no such quote"), { status: 200, unresolved: ["q2"] })),
    );
    setStarred(["q1", "q2"], true);
    await settle();
    expect(getQuotesSnapshot().starred).toEqual({ q1: true });
  });

  it("re-reads the quotes so the one a re-run removed leaves the screen (#21)", async () => {
    // The quote stayed on screen after "Couldn't save", inviting the same
    // gesture again. The existing re-read (every quotes island listens) takes
    // it off; a write that fails for another reason re-reads nothing.
    const reread = vi.fn();
    document.addEventListener("bn:tags-changed", reread);
    try {
      initFromQuotes([quote({ dom_id: "q1" }), quote({ dom_id: "q2" })]);
      failNext(patchStarred);
      setStarred(["q1"], true);
      await settle();
      expect(reread).not.toHaveBeenCalled();

      vi.mocked(patchStarred).mockImplementationOnce(() =>
        Promise.reject(Object.assign(new Error("no such quote"), { status: 200, unresolved: ["q2"] })),
      );
      setStarred(["q2"], true);
      await settle();
      expect(reread).toHaveBeenCalledTimes(1);
    } finally {
      document.removeEventListener("bn:tags-changed", reread);
    }
  });
});

// Accepting or denying a suggestion looked done when it failed: the console
// heard, the researcher did not (R5). A refusal now says so, and the screen
// follows what the server decided: "already accepted" keeps the tag, "already
// denied" drops it, anything else puts the suggestion back.
describe("accepting or denying a suggestion that does not save", () => {
  const proposal = { id: 7, tag_name: "Trust", group_name: "UX", colour_set: "ux",
    colour_index: 2, confidence: 0.8, rationale: "r" };
  const trust: TagResponse = { name: "Trust", codebook_group: "UX", colour_set: "ux",
    colour_index: 2, source: "autocode" };
  const refusedAs = (reason?: string) =>
    Object.assign(new Error("refused"), reason ? { status: 409, reason } : {});
  const names = () => (getQuotesSnapshot().tags.q1 || []).map((t) => t.name);
  const offered = () => (getQuotesSnapshot().proposedTags.q1 || []).map((p) => p.id);

  it("an accept that fails puts the suggestion back and says so", async () => {
    initFromQuotes([quote({ proposed_tags: [proposal] })]);
    vi.mocked(acceptProposal).mockRejectedValueOnce(refusedAs());
    acceptProposedTag("q1", 7, trust);
    expect(names()).toEqual(["Trust"]);
    await settle();
    expect(names()).toEqual([]);
    expect(offered()).toEqual([7]);
    expect(toastSaveFailed).toHaveBeenCalledTimes(1);
  });

  it("an accept of one denied elsewhere drops the tag, and the suggestion stays gone", async () => {
    initFromQuotes([quote({ proposed_tags: [proposal] })]);
    vi.mocked(acceptProposal).mockRejectedValueOnce(refusedAs("proposal_denied"));
    acceptProposedTag("q1", 7, trust);
    await settle();
    expect(names()).toEqual([]);
    expect(offered()).toEqual([]);
  });

  it("an accept of one accepted elsewhere keeps the tag", async () => {
    initFromQuotes([quote({ proposed_tags: [proposal] })]);
    vi.mocked(acceptProposal).mockRejectedValueOnce(refusedAs("proposal_accepted"));
    acceptProposedTag("q1", 7, trust);
    await settle();
    expect(names()).toEqual(["Trust"]);
    expect(offered()).toEqual([]);
  });

  it("a failed accept of a tag the quote already had leaves that tag", async () => {
    initFromQuotes([quote({ tags: [trust], proposed_tags: [proposal] })]);
    vi.mocked(acceptProposal).mockRejectedValueOnce(refusedAs());
    acceptProposedTag("q1", 7, trust);
    expect(names()).toEqual(["Trust"]); // one badge, not two
    await settle();
    expect(names()).toEqual(["Trust"]);
  });

  it("a suggestion the server no longer has (404) stays gone", async () => {
    initFromQuotes([quote({ proposed_tags: [proposal] })]);
    vi.mocked(acceptProposal).mockRejectedValueOnce(
      Object.assign(new Error("404"), { status: 404 }),
    );
    acceptProposedTag("q1", 7, trust);
    await settle();
    expect(names()).toEqual([]);
    expect(offered()).toEqual([]);
    expect(toastSaveFailed).toHaveBeenCalledTimes(1);
  });

  it("a deny that fails puts the suggestion back and says so", async () => {
    initFromQuotes([quote({ proposed_tags: [proposal] })]);
    vi.mocked(denyProposal).mockRejectedValueOnce(refusedAs());
    denyProposedTag("q1", 7);
    expect(offered()).toEqual([]);
    await settle();
    expect(offered()).toEqual([7]);
    expect(toastSaveFailed).toHaveBeenCalledTimes(1);
  });

  it("a deny of one accepted elsewhere shows the tag", async () => {
    initFromQuotes([quote({ proposed_tags: [proposal] })]);
    vi.mocked(denyProposal).mockRejectedValueOnce(refusedAs("proposal_accepted"));
    denyProposedTag("q1", 7);
    await settle();
    expect(names()).toEqual(["Trust"]);
    expect(offered()).toEqual([]);
  });

  it("a deny of one denied elsewhere changes nothing more", async () => {
    initFromQuotes([quote({ proposed_tags: [proposal] })]);
    vi.mocked(denyProposal).mockRejectedValueOnce(refusedAs("proposal_denied"));
    denyProposedTag("q1", 7);
    await settle();
    expect(offered()).toEqual([]);
    expect(names()).toEqual([]);
  });
});
