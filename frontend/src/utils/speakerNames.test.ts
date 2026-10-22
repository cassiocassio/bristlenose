import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getUndoState, redo, resetUndoStore, undo } from "../contexts/UndoStore";
import { getPeople, sendPut, toastSaveFailed } from "./api";
import { nameStateOf } from "./speakerPicking";
import type { SpeakerResponse } from "./types";
import {
  PEOPLE_CHANGED_EVENT,
  actionFor,
  nameSpeaker,
  resetSpeakerNameQueue,
  swapSpeakers,
  type PeopleChangedDetail,
  type SpeakerNameState,
} from "./speakerNames";

vi.mock("./api", async (importOriginal) => {
  const real = await importOriginal<typeof import("./api")>();
  return { ...real, getPeople: vi.fn(), sendPut: vi.fn(), toastSaveFailed: vi.fn() };
});

const putMock = vi.mocked(sendPut);
const peopleMock = vi.mocked(getPeople);
const toastMock = vi.mocked(toastSaveFailed);

// A moderator slot names the person it points at (design-people.md §J8).
const proposed: SpeakerNameState = {
  full_name: "Martin Storey", short_name: "Martin", confirmed: false, person: "id-martin",
};
const picked: SpeakerNameState = { full_name: "Jo Lee", short_name: "Jo Lee", confirmed: true, person: "id-jo" };

/** Every PUT the module made, in order, as [path, body]. */
const puts = () => putMock.mock.calls.map(([path, body]) => [path, body]);

beforeEach(() => {
  putMock.mockReset().mockResolvedValue(undefined);
  peopleMock.mockReset();
  toastMock.mockReset();
});

afterEach(() => {
  resetUndoStore();
  resetSpeakerNameQueue();
});

describe("nameSpeaker — a moderator", () => {
  it("writes the whole state in one per-session request", async () => {
    await nameSpeaker({ sessionId: "s1", code: "m1", before: proposed, after: picked });
    expect(puts()).toEqual([["/sessions/s1/speakers/m1", picked]]);
  });

  it("undo restores both names and returns the slot to proposed", async () => {
    await nameSpeaker({ sessionId: "s1", code: "m1", before: proposed, after: picked });
    await undo();
    expect(puts()[1]).toEqual(["/sessions/s1/speakers/m1", proposed]);
  });

  it("redo writes the pick again", async () => {
    await nameSpeaker({ sessionId: "s1", code: "m1", before: proposed, after: picked });
    await undo();
    await redo();
    expect(puts()[2]).toEqual(["/sessions/s1/speakers/m1", picked]);
  });

  it("an undo pressed before the pick has landed waits for it", async () => {
    let land!: () => void;
    putMock.mockImplementationOnce(() => new Promise<void>((r) => { land = r; }));
    void nameSpeaker({ sessionId: "s1", code: "m1", before: proposed, after: picked });
    const undone = undo();
    await Promise.resolve();
    expect(putMock).toHaveBeenCalledTimes(1);
    land();
    await undone;
    expect(puts().map(([, body]) => body)).toEqual([picked, proposed]);
  });

  it("tells views what the slot now holds on undo and redo", async () => {
    const seen: PeopleChangedDetail[] = [];
    const on = (e: Event) => seen.push((e as CustomEvent<PeopleChangedDetail>).detail);
    window.addEventListener(PEOPLE_CHANGED_EVENT, on);
    await nameSpeaker({ sessionId: "s2", code: "o1", before: proposed, after: picked });
    expect(seen).toEqual([]);
    await undo();
    await redo();
    window.removeEventListener(PEOPLE_CHANGED_EVENT, on);
    expect(seen).toEqual([
      { sessionId: "s2", code: "o1", state: proposed },
      { sessionId: "s2", code: "o1", state: picked },
    ]);
  });
});

describe("nameSpeaker — someone new, and back to nobody", () => {
  const unknown: SpeakerNameState = { short_name: "", confirmed: false };
  const mike: SpeakerNameState = {
    full_name: "Mike", short_name: "Mike", confirmed: true, person: "id-new", create: true,
  };

  it("someone new is made once, by the uuid the client chose", async () => {
    await nameSpeaker({ sessionId: "s1", code: "m1", before: unknown, after: mike });
    expect(puts()).toEqual([["/sessions/s1/speakers/m1", {
      person: "id-new", create: true, full_name: "Mike", short_name: "Mike", confirmed: true,
    }]]);
  });

  it("undo returns the slot to nobody, and redo points at the same person", async () => {
    await nameSpeaker({ sessionId: "s1", code: "m1", before: unknown, after: mike });
    await undo();
    await redo();
    expect(puts().slice(1).map(([, body]) => body)).toEqual([
      { clear: true },
      { person: "id-new", create: true, full_name: "Mike", short_name: "Mike", confirmed: true },
    ]);
  });

  it("clearing a speaker is labelled as such in Edit ▸ Undo", () => {
    expect(actionFor("m1", proposed, unknown)).toBe("clearName");
    expect(actionFor("m1", unknown, mike)).toBe("renameModerator");
  });

  it("a pick never sends a bare name the server could read as a rename", async () => {
    await nameSpeaker({ sessionId: "s1", code: "m1", before: proposed, after: picked });
    expect(puts()[0][1]).toHaveProperty("person", "id-jo");
  });
});

describe("nameSpeaker — a full name the caller does not know", () => {
  it("is left as stored, not blanked", async () => {
    const before = { short_name: "Jo", confirmed: false, person: "id-jo" };
    const after = { short_name: "Joanna", confirmed: true, person: "id-jo" };
    await nameSpeaker({ sessionId: "s1", code: "m1", before, after });
    await undo();
    // JSON drops the undefined field, so the server leaves full_name alone.
    expect(puts().map(([, body]) => JSON.parse(JSON.stringify(body)))).toEqual([after, before]);
  });

  it("a participant keeps the full name /people holds", async () => {
    peopleMock.mockResolvedValue({ p1: { full_name: "Ann Archer", short_name: "Ann", role: "" } });
    await nameSpeaker({
      sessionId: "s1", code: "p1",
      before: { short_name: "Ann", confirmed: false },
      after: { short_name: "Annie", confirmed: true },
    });
    expect(puts()[0]).toEqual([
      "/people", { p1: { full_name: "Ann Archer", short_name: "Annie", role: "" } },
    ]);
  });
});

describe("nameSpeaker — a participant", () => {
  const people = {
    p1: { full_name: "Ann Archer", short_name: "Ann", role: "" },
    p2: { full_name: "Bea Baker", short_name: "Bea", role: "" },
  };
  const ann: SpeakerNameState = { full_name: "Ann Archer", short_name: "Ann", confirmed: false };
  const annie: SpeakerNameState = { full_name: "Ann Archer", short_name: "Annie", confirmed: true };

  it("renames through /people, then sets the flag on the slot", async () => {
    peopleMock.mockResolvedValue(structuredClone(people));
    await nameSpeaker({ sessionId: "s1", code: "p1", before: ann, after: annie });
    expect(puts()).toEqual([
      ["/people", { ...people, p1: { ...people.p1, short_name: "Annie" } }],
      ["/sessions/s1/speakers/p1", { confirmed: true }],
    ]);
  });

  it("undo writes only this participant back, onto the map as it is now", async () => {
    peopleMock.mockResolvedValueOnce(structuredClone(people));
    await nameSpeaker({ sessionId: "s1", code: "p1", before: ann, after: annie });
    // Meanwhile p2 was renamed by someone else's write.
    const now = { p1: { ...people.p1, short_name: "Annie" }, p2: { ...people.p2, short_name: "Beatrice" } };
    peopleMock.mockResolvedValueOnce(structuredClone(now));
    await undo();
    expect(puts().slice(2)).toEqual([
      ["/people", { ...now, p1: { ...people.p1, short_name: "Ann" } }],
      ["/sessions/s1/speakers/p1", { confirmed: false }],
    ]);
  });

  it("a confirm alone touches only the flag", async () => {
    peopleMock.mockResolvedValue(structuredClone(people));
    await nameSpeaker({ sessionId: "s1", code: "p1", before: ann, after: { ...ann, confirmed: true } });
    expect(puts()).toEqual([["/sessions/s1/speakers/p1", { confirmed: true }]]);
  });
});

// An undo draws the slot at once and writes after. A participant's write first
// reads /people, and a failed read used to fail with no message, leaving the
// screen showing a name the server never took back.
describe("nameSpeaker — an undo or redo that fails", () => {
  const people = { p1: { full_name: "Ann Archer", short_name: "Ann", role: "" } };
  const ann: SpeakerNameState = { full_name: "Ann Archer", short_name: "Ann", confirmed: false };
  const annie: SpeakerNameState = { full_name: "Ann Archer", short_name: "Annie", confirmed: true };

  function listen() {
    const seen: SpeakerNameState[] = [];
    const on = (e: Event) => seen.push((e as CustomEvent<PeopleChangedDetail>).detail.state);
    window.addEventListener(PEOPLE_CHANGED_EVENT, on);
    return { seen, stop: () => window.removeEventListener(PEOPLE_CHANGED_EVENT, on) };
  }

  it("says so when the read fails, and puts the name back on screen", async () => {
    peopleMock.mockResolvedValueOnce(structuredClone(people));
    await nameSpeaker({ sessionId: "s1", code: "p1", before: ann, after: annie });
    const err = new Error("GET /people 500");
    peopleMock.mockRejectedValueOnce(err);
    const { seen, stop } = listen();
    const reread = vi.fn();
    window.addEventListener("bn:speakers-written", reread);
    expect(await undo()).toBe(false);
    stop();
    window.removeEventListener("bn:speakers-written", reread);
    expect(toastMock).toHaveBeenCalledTimes(1);
    expect(toastMock).toHaveBeenCalledWith(err);
    expect(seen).toEqual([ann, annie]);
    // Half of a participant's write may have landed: views read the slot again.
    expect(reread).toHaveBeenCalledTimes(1);
    expect(getUndoState().undoAction).toBe("renameParticipant");
  });

  it("a redo that fails puts the undone name back", async () => {
    peopleMock.mockResolvedValueOnce(structuredClone(people));
    await nameSpeaker({ sessionId: "s1", code: "p1", before: ann, after: annie });
    peopleMock.mockResolvedValueOnce(structuredClone(people));
    await undo();
    peopleMock.mockRejectedValueOnce(new Error("offline"));
    const { seen, stop } = listen();
    expect(await redo()).toBe(false);
    stop();
    expect(toastMock).toHaveBeenCalledTimes(1);
    expect(seen).toEqual([annie, ann]);
  });

  it("a refused write is said once, by the write, and the screen goes back", async () => {
    await nameSpeaker({ sessionId: "s1", code: "m1", before: proposed, after: picked });
    putMock.mockRejectedValueOnce(new Error("PUT 409"));
    const { seen, stop } = listen();
    expect(await undo()).toBe(false);
    stop();
    expect(toastMock).not.toHaveBeenCalled(); // sendPut has already toasted
    expect(seen).toEqual([proposed, picked]);
  });

  it("leaves the screen alone when a later act moved the slot meanwhile", async () => {
    peopleMock.mockResolvedValueOnce(structuredClone(people));
    await nameSpeaker({ sessionId: "s1", code: "p1", before: ann, after: annie });
    let fail!: (e: unknown) => void;
    peopleMock.mockReturnValueOnce(new Promise((_, rej) => { fail = rej; }));
    const { seen, stop } = listen();
    const reread = vi.fn();
    window.addEventListener("bn:speakers-written", reread);
    const undone = undo();
    peopleMock.mockResolvedValue(structuredClone(people));
    void nameSpeaker({ sessionId: "s1", code: "p1", before: ann, after: { ...ann, short_name: "A" } });
    fail(new Error("offline"));
    expect(await undone).toBe(false);
    stop();
    window.removeEventListener("bn:speakers-written", reread);
    expect(seen).toEqual([ann]);
    expect(reread).not.toHaveBeenCalled();
  });
});

// The Sessions grid draws a rename at once and writes after; a forward write
// that failed toasted but left the new name on screen (20 Oct 2026).
describe("nameSpeaker — a rename that fails", () => {
  const ann: SpeakerNameState = { full_name: "Ann Archer", short_name: "Ann", confirmed: false };
  const annie: SpeakerNameState = { full_name: "Ann Archer", short_name: "Annie", confirmed: true };

  function listen() {
    const seen: SpeakerNameState[] = [];
    const reread = vi.fn();
    const on = (e: Event) => seen.push((e as CustomEvent<PeopleChangedDetail>).detail.state);
    window.addEventListener(PEOPLE_CHANGED_EVENT, on);
    window.addEventListener("bn:speakers-written", reread);
    return {
      seen,
      reread,
      stop: () => {
        window.removeEventListener(PEOPLE_CHANGED_EVENT, on);
        window.removeEventListener("bn:speakers-written", reread);
      },
    };
  }

  it("puts the name back on screen when the write is refused", async () => {
    putMock.mockRejectedValueOnce(new Error("PUT 409"));
    const { seen, reread, stop } = listen();
    await expect(nameSpeaker({ sessionId: "s1", code: "m1", before: proposed, after: picked })).rejects.toThrow();
    stop();
    expect(toastMock).not.toHaveBeenCalled(); // sendPut has already toasted
    expect(seen).toEqual([proposed]);
    expect(reread).toHaveBeenCalledTimes(1);
  });

  it("says so when a participant's read fails, and puts the name back", async () => {
    const err = new Error("GET /people 500");
    peopleMock.mockRejectedValueOnce(err);
    const { seen, reread, stop } = listen();
    await expect(nameSpeaker({ sessionId: "s1", code: "p1", before: ann, after: annie })).rejects.toThrow();
    stop();
    expect(toastMock).toHaveBeenCalledWith(err);
    expect(seen).toEqual([ann]);
    // Half of a participant's write may have landed: views read the slot again.
    expect(reread).toHaveBeenCalledTimes(1);
  });

  it("leaves the screen alone when a later act moved the slot meanwhile", async () => {
    let fail!: (e: unknown) => void;
    putMock.mockReturnValueOnce(new Promise<void>((_, rej) => { fail = rej; }));
    const first = nameSpeaker({ sessionId: "s1", code: "m1", before: proposed, after: picked });
    const { seen, reread, stop } = listen();
    void nameSpeaker({ sessionId: "s1", code: "m1", before: picked, after: { ...picked, short_name: "Jo" } });
    fail(new Error("offline"));
    await expect(first).rejects.toThrow();
    stop();
    expect(seen).toEqual([]);
    expect(reread).not.toHaveBeenCalled();
  });
});

// Decision #32 under #15's rule (22 Oct 2026): the entry is recorded at once,
// so an undo pressed in flight still waits for the write, and withdrawn if the
// write fails, since the rename never happened.
describe("nameSpeaker — the undo entry of a rename that fails", () => {
  const ann: SpeakerNameState = { full_name: "Ann Archer", short_name: "Ann", confirmed: false };
  const annie: SpeakerNameState = { full_name: "Ann Archer", short_name: "Annie", confirmed: true };
  const people = { p1: { full_name: "Ann Archer", short_name: "Ann", role: "" } };

  it("leaves nothing to undo, and writes nothing on ⌘Z", async () => {
    putMock.mockRejectedValueOnce(new Error("PUT 409"));
    await expect(nameSpeaker({ sessionId: "s1", code: "m1", before: proposed, after: picked })).rejects.toThrow();
    expect(getUndoState()).toMatchObject({ canUndo: false, canRedo: false });
    putMock.mockClear();
    expect(await undo()).toBe(false);
    expect(putMock).not.toHaveBeenCalled();
  });

  // The undo's write went out after it and landed, so the act stays where
  // that left it, and Redo writes the pick for real.
  it("an undo pressed while it was in flight keeps the act", async () => {
    let fail!: (e: unknown) => void;
    putMock.mockReturnValueOnce(new Promise<void>((_, rej) => { fail = rej; }));
    const named = nameSpeaker({ sessionId: "s1", code: "m1", before: proposed, after: picked });
    const undone = undo();
    fail(new Error("offline"));
    await expect(named).rejects.toThrow();
    expect(await undone).toBe(true);
    expect(getUndoState()).toMatchObject({ canUndo: false, canRedo: true });
  });

  it("keeps the entry when a participant's name landed and only the flag failed", async () => {
    peopleMock.mockResolvedValue(structuredClone(people));
    putMock.mockResolvedValueOnce(undefined).mockRejectedValueOnce(new Error("PUT 500"));
    await expect(nameSpeaker({ sessionId: "s1", code: "p1", before: ann, after: annie })).rejects.toThrow();
    expect(getUndoState().undoAction).toBe("renameParticipant");
  });
});

describe("nameSpeaker — the undo entry", () => {
  it("names the act for the Edit menu", async () => {
    await nameSpeaker({ sessionId: "s1", code: "m1", before: proposed, after: picked });
    expect(getUndoState().undoAction).toBe("renameModerator");
  });

  it("records nothing when nothing changes", async () => {
    await nameSpeaker({ sessionId: "s1", code: "m1", before: picked, after: picked });
    expect(putMock).not.toHaveBeenCalled();
    expect(getUndoState().canUndo).toBe(false);
  });

  it.each([
    ["m1", "renameModerator"],
    ["o2", "renameObserver"],
    ["p3", "renameParticipant"],
  ])("a rename of %s is %s", (code, key) => {
    expect(actionFor(code, proposed, picked)).toBe(key);
  });

  it("a confirm is a confirm whatever the role", () => {
    expect(actionFor("m1", proposed, { ...proposed, confirmed: true })).toBe(
      "confirmName",
    );
  });
});

describe("nameSpeaker — a recode into or out of participant (§J7 R2)", () => {
  const mary: SpeakerNameState = { full_name: "Mary Adeyemi", short_name: "Mary", confirmed: true };
  const asMartin: SpeakerNameState = {
    full_name: "Martin Storey", short_name: "Martin", confirmed: true, person: "id-martin", kind: "moderator",
  };

  it("a plain participant's rename still goes through /people", async () => {
    peopleMock.mockResolvedValue({ p1: { full_name: "Mary Adeyemi", short_name: "Mary", role: "" } });
    const before = { ...mary, kind: "participant" as const };
    await nameSpeaker({ sessionId: "s1", code: "p1", before, after: { ...before, short_name: "M" } });
    expect(puts().map(([path]) => path)).toEqual(["/people", "/sessions/s1/speakers/p1"]);
  });

  it("a participant recoded as the moderator is one write to the slot, with the role", async () => {
    await nameSpeaker({ sessionId: "s1", code: "p1", before: mary, after: asMartin });
    expect(puts()).toEqual([[
      "/sessions/s1/speakers/p1",
      { person: "id-martin", kind: "moderator", full_name: "Martin Storey", short_name: "Martin", confirmed: true },
    ]]);
    expect(peopleMock).not.toHaveBeenCalled();
  });

  it("its undo names the role alone — a participant's uuid never leaves the server", async () => {
    // `before` as the grid reads a plain participant, not built by hand: the
    // first build tested a shape the app never produced (code review, R2).
    const before = nameStateOf({
      speaker_code: "p1", slot_code: "p1", name: "Mary", full_name: "Mary Adeyemi",
      short_name: "Mary", name_confirmed: true, role: "participant",
    } as SpeakerResponse);
    await nameSpeaker({ sessionId: "s1", code: "p1", before, after: asMartin });
    await undo();
    expect(puts()[1]).toEqual([
      "/sessions/s1/speakers/p1",
      { kind: "participant", full_name: "Mary Adeyemi", short_name: "Mary", confirmed: true },
    ]);
    expect(peopleMock).not.toHaveBeenCalled();
  });

  it("a moderator recoded as a participant sends the role with their person", async () => {
    const before: SpeakerNameState = { ...asMartin };
    const after: SpeakerNameState = { ...asMartin, kind: "participant" };
    await nameSpeaker({ sessionId: "s2", code: "m1", before, after });
    expect(puts()).toEqual([[
      "/sessions/s2/speakers/m1",
      { person: "id-martin", kind: "participant", full_name: "Martin Storey", short_name: "Martin", confirmed: true },
    ]]);
    expect(actionFor("m1", before, after)).toBe("changeRole");
  });

  it("a cleared speaker's undo carries its role back too", async () => {
    const unknown: SpeakerNameState = { full_name: "", short_name: "", confirmed: false, kind: "moderator" };
    const named: SpeakerNameState = { ...asMartin, kind: "participant", create: true };
    await nameSpeaker({ sessionId: "s2", code: "m1", before: unknown, after: named });
    await undo();
    expect(puts()[1]).toEqual(["/sessions/s2/speakers/m1", { clear: true, kind: "moderator" }]);
  });
});


describe("swapSpeakers (§J7 call 4)", () => {
  it("is one write, and its undo is the same write again", async () => {
    const written = vi.fn();
    window.addEventListener("bn:speakers-written", written);
    try {
      await swapSpeakers("s1", "p1", "m1");
      expect(puts()).toEqual([["/sessions/s1/speakers/p1", { swap_with: "m1" }]]);
      expect(getUndoState().undoAction).toBe("swapRoles");
      await undo();
      expect(puts()[1]).toEqual(["/sessions/s1/speakers/p1", { swap_with: "m1" }]);
      expect(written).toHaveBeenCalledTimes(2);
    } finally {
      window.removeEventListener("bn:speakers-written", written);
    }
  });
});

describe("swapSpeakers — a refused swap", () => {
  it("records nothing, so ⌘Z cannot perform the swap that failed", async () => {
    putMock.mockRejectedValueOnce(new Error("PUT 409"));
    await expect(swapSpeakers("s1", "p1", "m1")).rejects.toThrow();
    expect(getUndoState().canUndo).toBe(false);
  });
});
