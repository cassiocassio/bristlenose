import { describe, expect, it } from "vitest";

import { drawsCapital, startsSentence } from "./sentenceStart";

// From a real session (IKEA with uxfriends, s1), with two splits added.
const SEGS = [
  { speaker_code: "p1", text: "i guess okay what is it that you like about it, which is very good." },
  { speaker_code: "p1", text: "and the design of it's good and so when it's fermenting the air" },
  { speaker_code: "p1", text: "it's kind of a simple ingenious solution." },
  { speaker_code: "m1", text: "what do you think your choice of that object says about you" },
  { speaker_code: "p1", text: "and um well i think kind of buying something dedicated to ferment" },
  { speaker_code: "p1", text: "I mean, that's what I'm saying.”" },
  { speaker_code: "p1", text: "normally i would but you know" },
];

describe("startsSentence", () => {
  it("the first paragraph, and every new speaker's turn, begin a sentence", () => {
    expect(startsSentence(SEGS, 0)).toBe(true);
    expect(startsSentence(SEGS, 3)).toBe(true);
    expect(startsSentence(SEGS, 4)).toBe(true);
  });

  it("the same speaker after a full stop begins one; carrying on mid-sentence does not", () => {
    expect(startsSentence(SEGS, 1)).toBe(true);
    expect(startsSentence(SEGS, 2)).toBe(false);
  });

  it("a closing quote after the full stop still ends the sentence", () => {
    expect(startsSentence(SEGS, 6)).toBe(true);
  });

  it("a question mark or an ideographic full stop ends one too", () => {
    expect(startsSentence([{ speaker_code: "p1", text: "Why?" }, { speaker_code: "p1", text: "so" }], 1)).toBe(true);
    expect(startsSentence([{ speaker_code: "p1", text: "そうです。" }, { speaker_code: "p1", text: "x" }], 1)).toBe(true);
  });
});

describe("drawsCapital — the iPhone guard", () => {
  const one = [{ speaker_code: "p1", text: "x" }];
  it("a word spelled lower-case on purpose keeps its spelling", () => {
    for (const w of ["iPhone", "eBay", "macOS", "(iPad", "ikea.com", "bbc.co.uk"]) {
      expect(drawsCapital(one, 0, w)).toBe(false);
    }
  });
  it("an ordinary word, or I, is drawn with a capital", () => {
    for (const w of ["okay", "i", "um,", "¿qué", "(Speaker"]) expect(drawsCapital(one, 0, w)).toBe(true);
  });
});
