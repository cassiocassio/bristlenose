import { mergeTapestry } from "./tapestryMerge";
import type { TapestrySession } from "./types";

const session = (sid: string, quote = "I can't find the basket"): TapestrySession => ({
  session_id: sid,
  duration_seconds: 600,
  turns: [{ t0: 0, t1: 60, speaker: "m1", colour: null }],
  sections: [],
  quotes: [{ t0: 10, t1: 20, text: quote, sentiment: null, intensity: 1, section: null, theme: null }],
  strip: null,
});
const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v));

describe("mergeTapestry", () => {
  it("keeps the record when nothing changed (an idle poll)", () => {
    const prev = { s1: session("s1") };
    expect(mergeTapestry(prev, clone(prev))).toBe(prev);
  });

  it("keeps an unchanged session's object when another session arrives", () => {
    const prev = { s1: session("s1") };
    const got = mergeTapestry(prev, { ...clone(prev), s2: session("s2") });
    expect(got).not.toBe(prev);
    expect(got.s1).toBe(prev.s1);
    expect(Object.keys(got)).toEqual(["s1", "s2"]);
  });

  it("keeps the layers that did not change and takes the one that did", () => {
    const prev = { s1: session("s1") };
    const next = clone(prev);
    next.s1.strip = { png: "data:image/png;base64,AAAA", fps: 4, notches: [] } as never;
    const got = mergeTapestry(prev, next);
    expect(got.s1).not.toBe(prev.s1);
    expect(got.s1.quotes).toBe(prev.s1.quotes);
    expect(got.s1.turns).toBe(prev.s1.turns);
    expect(got.s1.strip).toEqual(next.s1.strip);
  });

  it("takes new hover frames, keeping every other layer (the grid caches frames by key)", () => {
    const prev = { s1: { ...session("s1"), frames_key: "k1" } };
    const next = clone(prev);
    next.s1.frames_key = "k2";
    const got = mergeTapestry(prev, next);
    expect(got.s1).not.toBe(prev.s1);
    expect(got.s1.frames_key).toBe("k2");
    expect(got.s1.quotes).toBe(prev.s1.quotes);
  });

  it("takes a changed quote layer, and follows the answer for which sessions exist", () => {
    const prev = { s1: session("s1"), s2: session("s2") };
    const got = mergeTapestry(prev, { s1: session("s1", "edited"), s3: session("s3") });
    expect(got.s1.quotes).not.toBe(prev.s1.quotes);
    expect(Object.keys(got)).toEqual(["s1", "s3"]);
  });
});
