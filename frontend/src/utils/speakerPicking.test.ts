import { describe, expect, it } from "vitest";

import { knownPeopleOf, nameStateOf, stateAfter, swapPartnerOf } from "./speakerPicking";
import type { SessionsListResponse, SpeakerResponse } from "./types";

const study = (speakers: Array<Record<string, unknown>>[]): SessionsListResponse =>
  ({ sessions: speakers.map((sp, i) => ({ session_id: `s${i + 1}`, speakers: sp })) }) as unknown as SessionsListResponse;

describe("knownPeopleOf", () => {
  it("a person is confirmed if anyone said yes to them in any session (§J8.10)", () => {
    const known = knownPeopleOf(study([
      [{ speaker_code: "m1", name: "Kerri", person: "id-k", name_confirmed: false }],
      [{ speaker_code: "m1", name: "Kerri", person: "id-k", name_confirmed: true }],
      [{ speaker_code: "m2", name: "Dana", person: "id-d", name_confirmed: false }],
    ]));
    expect(known.moderator.map((r) => [r.name, r.confirmed])).toEqual([["Kerri", true], ["Dana", false]]);
  });

  it("a missing flag reads as confirmed, as the grid draws it", () => {
    const known = knownPeopleOf(study([[{ speaker_code: "m1", name: "Sarah", person: "id-s" }]]));
    expect(known.moderator[0].confirmed).toBe(true);
  });
});

describe("stateAfter", () => {
  const before = { full_name: "Martin Storey", short_name: "Martin", confirmed: false, person: "id-m" };

  it("names each act's next state (§J8)", () => {
    expect(stateAfter({ kind: "confirm" }, before)).toEqual({ ...before, confirmed: true });
    expect(stateAfter({ kind: "clear" }, before)).toEqual({ full_name: "", short_name: "", confirmed: false });
    expect(stateAfter({ kind: "name", name: "Martyn" }, before)).toEqual({ ...before, short_name: "Martyn", confirmed: true });
    expect(stateAfter({ kind: "new", name: "Mike" }, before, () => "id-new")).toEqual({
      person: "id-new", create: true, full_name: "Mike", short_name: "Mike", confirmed: true,
    });
  });
});


describe("a speaker's state, as a recode reads it (§J7 R2)", () => {
  const sp = (o: Partial<SpeakerResponse>): SpeakerResponse =>
    ({ name: "Mary", full_name: "Mary A", short_name: "Mary", name_confirmed: true, role: "participant", ...o }) as SpeakerResponse;

  it("a plain participant carries its role and no person", () => {
    expect(nameStateOf(sp({ speaker_code: "p1", slot_code: "p1" }))).toEqual({
      full_name: "Mary A", short_name: "Mary", confirmed: true, kind: "participant",
    });
  });

  it("a participant's tag recoded as the moderator reads as the moderator it now is", () => {
    const state = nameStateOf(sp({ speaker_code: "m1", slot_code: "p1", person: "id-martin" }));
    expect(state).toMatchObject({ kind: "moderator", person: "id-martin" });
  });

  it("a moderator's tag recoded as a participant carries the role and no uuid", () => {
    const state = nameStateOf(sp({ speaker_code: "p3", slot_code: "m1", person: "" }));
    expect(state.kind).toBe("participant");
    expect(state.person).toBeUndefined();
  });

  it("a pick under Participant leaves the slot a participant", () => {
    const before = { full_name: "Martin Storey", short_name: "Martin", confirmed: true, person: "id-martin", kind: "moderator" as const };
    const after = stateAfter(
      { kind: "person", role: "participant", row: { name: "Martin", code: "p3", person: "id-martin" } }, before,
    );
    expect(after.kind).toBe("participant");
    expect(after.person).toBe("id-martin");
  });
});


describe("who a speaker would swap with (§J7 call 4)", () => {
  const sp = (speaker_code: string, slot_code = speaker_code) =>
    ({ speaker_code, slot_code, name: "", role: "" }) as SpeakerResponse;

  it("in a session of one participant and one moderator, each is the other's", () => {
    const [m, p, o] = [sp("m1"), sp("p3"), sp("o1")];
    expect(swapPartnerOf([m, p, o], p)).toEqual({ code: "m1", slot: "m1" });
    expect(swapPartnerOf([m, p, o], m)).toEqual({ code: "p3", slot: "p3" });
    expect(swapPartnerOf([m, p, o], o)).toBeUndefined();
  });

  it("no swap with two participants or two moderators", () => {
    const [m, p, q] = [sp("m1"), sp("p3"), sp("p4")];
    expect(swapPartnerOf([m, p, q], p)).toBeUndefined();
    expect(swapPartnerOf([m, sp("m2", "m2"), p], p)).toBeUndefined();
  });

  it("addresses the other speaker by their slot, not the code they show", () => {
    const [m, p] = [sp("m2", "m1"), sp("p3")];
    expect(swapPartnerOf([m, p], p)).toEqual({ code: "m2", slot: "m1" });
  });
});
