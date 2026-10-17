import { describe, expect, it } from "vitest";
import { matchForm, quoteExtents, type ExtentParagraph, type ExtentQuote } from "./quoteExtents";

const words = (s: string) => s.split(" ").map((text) => ({ text }));
const quoted = (ids: string[], text: string, timed = true): ExtentParagraph => ({
  text, words: timed ? words(text) : null, quote_ids: ids,
});
const excerpts = (m: Record<string, string>): Record<string, ExtentQuote> =>
  Object.fromEntries(Object.entries(m).map(([id, excerpt]) => [id, { excerpt }]));

describe("quoteExtents", () => {
  it("finds a quote inside its paragraph, ignoring case and punctuation", () => {
    const { owners, approximate } = quoteExtents(
      [quoted(["q1"], "Yeah. It's an Alessi kettle, and um it whistles.")],
      excerpts({ q1: "it's an alessi kettle" }),
    );
    expect(owners[0]).toEqual([null, "q1", "q1", "q1", "q1", null, null, null, null]);
    expect(approximate.size).toBe(0);
  });

  it("gives two quotes in one paragraph their own words", () => {
    const { owners } = quoteExtents(
      [quoted(["q2", "q3"], "And yeah it's nice to have that. But it doesn't whistle at all.")],
      excerpts({ q2: "it's nice to have that", q3: "it doesn't whistle" }),
    );
    expect(owners[0].map((o) => o ?? "-").join(" ")).toBe("- - q2 q2 q2 q2 q2 - q3 q3 q3 - -");
  });

  it("follows a quote across a paragraph break", () => {
    const { owners } = quoteExtents(
      [quoted(["q4"], "So I went to the page and"), quoted(["q4"], "it said in stock. Then nothing.")],
      excerpts({ q4: "the page and it said in stock" }),
    );
    expect(owners[0]).toEqual([null, null, null, null, "q4", "q4", "q4"]);
    expect(owners[1]).toEqual(["q4", "q4", "q4", "q4", null, null]);
  });

  it("finds a quote that starts mid-paragraph, which the server's time join leaves out", () => {
    // The server lists a paragraph only when it starts inside the quote's time, so the
    // paragraph this quote begins in carries no id for it; the speaker and the time overlap do.
    const paragraphs: ExtentParagraph[] = [
      { ...quoted([], "Well I looked at the page and"), speaker_code: "p2", start_time: 10, end_time: 20 },
      { ...quoted([], "Mm-hm."), speaker_code: "m1", start_time: 20, end_time: 21 },
      { ...quoted(["q5"], "it said in stock."), speaker_code: "p2", start_time: 21, end_time: 25 },
    ];
    const { owners, approximate } = quoteExtents(paragraphs, {
      q5: { excerpt: "the page and it said in stock", start: 15, end: 25, participant: "p2" },
    });
    expect(owners[0]).toEqual([null, null, null, null, "q5", "q5", "q5"]);
    expect(owners[1]).toEqual([null]);
    expect(owners[2]).toEqual(["q5", "q5", "q5", "q5"]);
    expect(approximate.size).toBe(0);
  });

  it("finds a quote's words in a paragraph attributed to someone else", () => {
    // Diarisation filed the participant's words under the moderator's code.
    const paragraphs: ExtentParagraph[] = [
      { ...quoted([], "So a lot of household stuff comes from there."), speaker_code: "m1", start_time: 75, end_time: 172 },
      { ...quoted(["q1"], "I think buying something dedicated."), speaker_code: "p1", start_time: 172, end_time: 224 },
    ];
    const { owners, approximate } = quoteExtents(paragraphs, {
      q1: { excerpt: "a lot of household stuff", start: 75, end: 172, participant: "p1" },
    });
    expect(owners[0]).toEqual([null, "q1", "q1", "q1", "q1", "q1", null, null, null]);
    expect(owners[1]).toEqual([null, null, null, null, null]);
    expect(approximate.size).toBe(0);
  });

  it("anchors a tidied excerpt on its first and last words", () => {
    // The model dropped the "uh" and the repeated "the"; the quote still runs from its first
    // four words to its last four.
    const { owners, approximate } = quoteExtents(
      [quoted(["q1"], "Okay. So I went to uh the the product page and it said in stock. Right.")],
      excerpts({ q1: "so i went to the product page and it said in stock" }),
    );
    expect(owners[0].map((o) => o ?? "-").join(" ")).toBe("- q1 q1 q1 q1 q1 q1 q1 q1 q1 q1 q1 q1 q1 q1 -");
    expect(approximate.size).toBe(0);
  });

  it("does not anchor across a span far longer than the excerpt", () => {
    const { approximate } = quoteExtents(
      [quoted(["q1"], "so i went to " + "and then more ".repeat(20) + "said in stock now")],
      excerpts({ q1: "so i went to the page and it said in stock now" }),
    );
    expect(approximate.has("q1")).toBe(true);
  });

  it("reads the text when a paragraph has no word timings", () => {
    const { owners } = quoteExtents([quoted(["q5"], "Hmm. Not really, no.", false)], excerpts({ q5: "not really" }));
    expect(owners[0]).toEqual([null, "q5", "q5", null]);
  });

  it("claims punctuation drawn as its own word inside the quote", () => {
    const { owners } = quoteExtents([quoted(["q6"], "It was — honestly — fine.")], excerpts({ q6: "it was honestly fine" }));
    expect(owners[0]).toEqual(["q6", "q6", "q6", "q6", "q6", "q6"]);
  });

  it("falls back to the paragraph's remaining words when the excerpt is not there", () => {
    const { owners, approximate } = quoteExtents(
      [quoted(["q7", "q8"], "The first bit. The second bit.")],
      excerpts({ q7: "the first bit", q8: "something tidied up by the model" }),
    );
    expect(owners[0]).toEqual(["q7", "q7", "q7", "q8", "q8", "q8"]);
    expect([...approximate]).toEqual(["q8"]);
  });

  it("falls back to the server's paragraphs, not every overlapping one", () => {
    const paragraphs: ExtentParagraph[] = [
      { ...quoted([], "A neighbour that only touches."), speaker_code: "p1", start_time: 0, end_time: 10 },
      { ...quoted(["q9"], "The quote's own paragraph."), speaker_code: "p1", start_time: 10, end_time: 20 },
    ];
    const { owners } = quoteExtents(paragraphs, { q9: { excerpt: "not in either", start: 10, end: 20, participant: "p1" } });
    expect(owners[0]).toEqual([null, null, null, null, null]);
    expect(owners[1]).toEqual(["q9", "q9", "q9", "q9"]);
  });

  it("treats an empty excerpt as not located", () => {
    const { approximate, owners } = quoteExtents([quoted(["q9"], "All of it.")], excerpts({ q9: "" }));
    expect(approximate.has("q9")).toBe(true);
    expect(owners[0]).toEqual(["q9", "q9", "q9"]);
  });

  it("leaves an inaudible gap and unquoted paragraphs alone", () => {
    const { owners } = quoteExtents(
      [{ text: "", words: null, quote_ids: [], inaudible: true }, quoted([], "Nothing quoted here.")],
      {},
    );
    expect(owners).toEqual([[], [null, null, null]]);
  });
});

describe("matchForm", () => {
  it("drops case, accents' marks and punctuation, keeping letters in any script", () => {
    expect(matchForm("Café,")).toBe("cafe");
    expect(matchForm("—")).toBe("");
    expect(matchForm("「東京」")).toBe("東京");
  });
});
